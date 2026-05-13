"""
corporate_actions.py — Load and normalise CSE corporate action files.

Produces a unified table of adjustment events used to compute adjusted
close prices.  Four source files are parsed:

  01Dividends.xls           — Cash dividends (one sheet per year)
  02Scrip Dividends.xls     — Stock dividends paid in shares (one sheet per year)
  03Capitalisation of...xls — Bonus share issues (one sheet per year)
  05Sub Division...xls      — Share splits (one sheet per year)

Output columns
--------------
  date        datetime64  — Ex-date for dividends; effective/listing date for splits/bonus
  ticker      str         — SL20 ticker symbol
  action_type str         — 'dividend' | 'scrip_div' | 'bonus' | 'split'
  factor      float       — Backward price adjustment factor (multiply all prices
                            BEFORE this date by this number to get adjusted price)

Adjustment factor formulas
--------------------------
  split   : OLD_PROPORTION / NEW_PROPORTION
              e.g. 1:10 split  → factor = 1/10 = 0.10
  bonus   : OLD / (OLD + NEW)
              e.g. 10:1 bonus  → factor = 10/11 ≈ 0.909
  scrip   : OLD / (OLD + NEW)
              e.g. 21.4:1      → factor = 21.4/22.4 ≈ 0.955
  dividend: (CUM_PRICE - DIVIDEND_RATE) / CUM_PRICE
              Theoretical adjustment, avoids noise from actual ex-date movement.
              Rows with missing CUM_PRICE are skipped.
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# ── SL20 ticker name mapping ───────────────────────────────────────────────────
# Used to map free-text company names in bonus/scrip files to ticker symbols.
# Matches on case-insensitive substring so minor name variations still resolve.
_NAME_TO_TICKER: list[tuple[str, str]] = [
    ("john keells",               "JKH"),
    ("commercial bank",           "COMB"),
    ("dialog axiata",             "DIAL"),
    ("sampath bank",              "SAMP"),
    ("hayleys",                   "HAYL"),
    ("ceylon tobacco",            "CTC"),
    ("hatton national bank",      "HNB"),
    ("lanka ioc",                 "LIOC"),
    ("aitken spence",             "SPEN"),
    ("dfcc bank",                 "DFCC"),
    ("nations trust bank",        "NTB"),
    ("bukit darah",               "BUKI"),
    ("cargills",                  "CARG"),
    ("ceylon cold stores",        "CCS"),
    ("hemas holdings",            "HHL"),
    ("lion brewery",              "LION"),
    ("melstacorp",                "MELS"),
    ("tokyo cement",              "TKYO"),
    ("vallibel one",              "VONE"),
    ("access engineering",        "AEL"),
]

# Year sheets with leading/trailing spaces (e.g. "2018 ", " 2020") are common
_ML_START_YEAR = 2011


def _normalise_year_sheet(name: str) -> int | None:
    """Parse a sheet name like '2022', '2018 ', ' 2020' → int year."""
    try:
        return int(str(name).strip())
    except ValueError:
        return None


def _name_to_ticker(name: str) -> str | None:
    """Map a free-text company name to a SL20 ticker, or None if not SL20."""
    low = str(name).lower()
    for fragment, ticker in _NAME_TO_TICKER:
        if fragment in low:
            return ticker
    return None


def _security_to_ticker(security: str) -> str | None:
    """
    Convert a CSE security code to a base ticker.
    e.g. 'COMB-N-0000' → 'COMB', 'HNB-X-0000' → 'HNB'
    """
    if not isinstance(security, str):
        return None
    parts = str(security).strip().split("-")
    if parts:
        return parts[0].strip().upper() or None
    return None


def _read_all_sheets(path: Path, engine: str = "xlrd") -> pd.DataFrame:
    """Read all year sheets and stack them into one DataFrame with the raw layout."""
    xl = pd.ExcelFile(path, engine=engine)
    frames = []
    for sheet in xl.sheet_names:
        year = _normalise_year_sheet(sheet)
        if year is None or year < _ML_START_YEAR:
            continue
        df = pd.read_excel(xl, sheet_name=sheet, header=None)
        df["_sheet_year"] = year
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ── File 01: Cash dividends ────────────────────────────────────────────────────

def load_dividends(cse_dir: Path) -> pd.DataFrame:
    """
    Parse cash dividends.

    Layout (after 3-row header):
      col 0: DATE OF ANNOUNCEMENT
      col 1: SECURITY           (e.g. 'COMB-N-0000')
      col 2: SHORT NAME
      col 3: RATE OF DIVIDEND   (LKR per share)
      col 4: REMARKS
      col 5: DATE OF EX
      col 6: DATE OF PAYMENT
      col 7: CUM PRICE
      col 8: EX PRICE
    """
    path = cse_dir / "01Dividends.xls"
    logger.info(f"Loading dividends from {path.name} ...")
    raw = _read_all_sheets(path)
    if raw.empty:
        return _empty_actions()

    records = []
    for _, row in raw.iterrows():
        # Skip header/title rows — real rows have a datetime in col 0 or col 5
        ex_date = pd.to_datetime(row.iloc[5], errors="coerce")
        if pd.isna(ex_date):
            continue

        ticker   = _security_to_ticker(row.iloc[1])
        div_rate = pd.to_numeric(row.iloc[3], errors="coerce")
        cum_p    = pd.to_numeric(row.iloc[7], errors="coerce")

        if ticker is None or pd.isna(div_rate) or pd.isna(cum_p) or cum_p <= 0:
            continue

        # Theoretical adjustment factor
        factor = (cum_p - div_rate) / cum_p
        if not (0.50 < factor < 1.0):
            # Implausible ratio — skip (probably data error or special situation)
            continue

        records.append({
            "date":        ex_date,
            "ticker":      ticker,
            "action_type": "dividend",
            "factor":      round(factor, 8),
        })

    df = pd.DataFrame(records)
    logger.info(f"  -> {len(df):,} dividend events for {df['ticker'].nunique() if len(df) else 0} tickers")
    return df


# ── File 02: Scrip dividends ───────────────────────────────────────────────────

def load_scrip_dividends(cse_dir: Path) -> pd.DataFrame:
    """
    Parse scrip (stock) dividends.

    Layout (after 3-row header):
      col 1: Company Name
      col 3: Allotment Date / Date listed
      col 4: Old Proportion
      col 5: New Proportion
    """
    path = cse_dir / "02Scrip Dividends.xls"
    logger.info(f"Loading scrip dividends from {path.name} ...")
    raw = _read_all_sheets(path)
    if raw.empty:
        return _empty_actions()
    return _parse_proportion_file(raw, action_type="scrip_div", date_col=3, name_col=2, old_col=4, new_col=5)


# ── File 03: Bonus issues ──────────────────────────────────────────────────────

def load_bonus_issues(cse_dir: Path) -> pd.DataFrame:
    """
    Parse capitalisation of reserves (bonus share issues).

    Layout (after 3-row header):
      col 1: Company name
      col 2: Allotment Date
      col 3: Old Proportion
      col 4: New Proportion
    """
    path = cse_dir / "03Capitalization of Reserves (Bonus Issues).xls"
    logger.info(f"Loading bonus issues from {path.name} ...")
    raw = _read_all_sheets(path)
    if raw.empty:
        return _empty_actions()
    return _parse_proportion_file(raw, action_type="bonus", date_col=2, name_col=1, old_col=3, new_col=4)


# ── File 05: Share splits ──────────────────────────────────────────────────────

def load_splits(cse_dir: Path) -> pd.DataFrame:
    """
    Parse sub-division (share split) events.

    Layout (after 3-row header):
      col 2: COMPANY ID    (direct ticker, e.g. 'CCS')
      col 4: OLD PROPORTION
      col 5: NEW PROPORTION
      col 6: EFFECTIVE DATE
    """
    path = cse_dir / "05Sub Division (Share Splits).xls"
    logger.info(f"Loading splits from {path.name} ...")
    raw = _read_all_sheets(path)
    if raw.empty:
        return _empty_actions()

    records = []
    for _, row in raw.iterrows():
        eff_date = pd.to_datetime(row.iloc[6], errors="coerce")
        if pd.isna(eff_date):
            continue

        ticker = str(row.iloc[2]).strip().upper() if pd.notna(row.iloc[2]) else None
        if not ticker or ticker in ("COMPANY ID", "NAN", ""):
            continue

        old = pd.to_numeric(row.iloc[4], errors="coerce")
        new = pd.to_numeric(row.iloc[5], errors="coerce")
        if pd.isna(old) or pd.isna(new) or new <= 0:
            continue

        factor = old / new   # e.g. 1:10 split → 0.10
        if not (0.0 < factor < 2.0):
            continue

        records.append({
            "date":        eff_date,
            "ticker":      ticker,
            "action_type": "split",
            "factor":      round(factor, 8),
        })

    df = pd.DataFrame(records)
    logger.info(f"  -> {len(df):,} split events for {df['ticker'].nunique() if len(df) else 0} tickers")
    return df


# ── Public API ─────────────────────────────────────────────────────────────────

def load_all_corporate_actions(cse_dir: Path, sl20_tickers: list[str]) -> pd.DataFrame:
    """
    Load and combine all corporate action events, filtered to SL20 tickers.

    Parameters
    ----------
    cse_dir      : Path to the stock_data directory
    sl20_tickers : list of 20 SL20 ticker symbols (from pipeline.yaml)

    Returns
    -------
    pd.DataFrame with columns: date, ticker, action_type, factor
    Sorted by ticker, date.  One row per corporate action event.
    """
    sl20_set = set(t.upper() for t in sl20_tickers)

    frames = [
        load_dividends(cse_dir),
        load_scrip_dividends(cse_dir),
        load_bonus_issues(cse_dir),
        load_splits(cse_dir),
    ]
    # Filter out empty frames before concat to avoid FutureWarning about all-NA columns
    frames = [f for f in frames if not f.empty]
    if not frames:
        logger.warning("No corporate action events loaded.")
        return _empty_actions()

    df = pd.concat(frames, ignore_index=True)

    if df.empty:
        logger.warning("No corporate action events loaded.")
        return _empty_actions()

    # Filter to SL20 tickers only
    df = df[df["ticker"].isin(sl20_set)].copy()
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    summary = df.groupby("action_type")["ticker"].count()
    logger.info(f"Corporate actions (SL20 only): {len(df):,} total events")
    for atype, count in summary.items():
        logger.info(f"  {atype:<12s}: {count:>4d}")
    return df


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_proportion_file(
    raw: pd.DataFrame,
    action_type: str,
    date_col: int,
    name_col: int,
    old_col: int,
    new_col: int,
) -> pd.DataFrame:
    """Parse bonus / scrip dividend files that use an Old:New proportion format."""
    records = []
    for _, row in raw.iterrows():
        event_date = pd.to_datetime(row.iloc[date_col], errors="coerce")
        if pd.isna(event_date):
            continue

        company_name = str(row.iloc[name_col]).strip() if pd.notna(row.iloc[name_col]) else ""
        ticker = _name_to_ticker(company_name)
        if ticker is None:
            continue

        old = pd.to_numeric(row.iloc[old_col], errors="coerce")
        new = pd.to_numeric(row.iloc[new_col], errors="coerce")
        if pd.isna(old) or pd.isna(new) or (old + new) <= 0:
            continue

        # factor = old_total / new_total
        # e.g. 10 old + 1 bonus = 11 total → prices before this must be × (10/11)
        factor = old / (old + new)
        if not (0.50 < factor < 1.0):
            continue

        records.append({
            "date":        event_date,
            "ticker":      ticker,
            "action_type": action_type,
            "factor":      round(factor, 8),
        })

    df = pd.DataFrame(records) if records else _empty_actions()
    if len(df):
        logger.info(f"  -> {len(df):,} {action_type} events for {df['ticker'].nunique()} tickers")
    else:
        logger.info(f"  -> 0 {action_type} events (none matched SL20 tickers)")
    return df


def _empty_actions() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "ticker", "action_type", "factor"])
