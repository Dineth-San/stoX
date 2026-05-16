"""
cbsl.py — Loaders for CBSL (Central Bank of Sri Lanka) macro data.

Two source files are parsed here:

  exchange_rates.csv
    Daily USD/LKR exchange rate fetched from FRED (series DEXSLUS).
    Columns: observation_date, DEXSLUS
    Coverage: 2010-01-04 onward, daily (weekdays only).

  20250522_historical_policy_interest_rates.xlsx
    Event-driven table of CBSL policy rate changes.
    Sheet "Historical Policy Rates" has: Date, SDF Rate (%), SLF Rate (%).
    Dates are formatted as DD.MM.YYYY strings.
    Coverage: 2000-01-05 onward, one row per rate change (~106 events total).

The policy rate table is sparse (only records the dates when rates change).
Forward-filling to a daily calendar is done in clean_macro.py, not here.
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_POLICY_SHEET   = "Historical Policy Rates"
_POLICY_SKIPROWS = 2   # rows 0-1 are title / blank; row 2 is the real header


# ── Exchange rates ─────────────────────────────────────────────────────────────

def load_exchange_rates(cbsl_dir: Path) -> pd.DataFrame:
    """
    Load daily USD/LKR exchange rate from FRED DEXSLUS export.

    Parameters
    ----------
    cbsl_dir : Path — directory containing exchange_rates.csv

    Returns
    -------
    pd.DataFrame with columns: date (datetime64), usd_lkr (float)
    """
    path = cbsl_dir / "exchange_rates.csv"
    logger.info(f"Loading exchange rates from {path.name} ...")

    df = pd.read_csv(path)
    df.columns = ["date", "usd_lkr"]
    df["date"]    = pd.to_datetime(df["date"], errors="coerce")
    df["usd_lkr"] = pd.to_numeric(df["usd_lkr"], errors="coerce")
    df = df[df["date"].notna()].sort_values("date").reset_index(drop=True)

    logger.info(
        f"  -> {len(df):,} rows | {df['date'].min().date()} to {df['date'].max().date()} "
        f"| NaN usd_lkr: {df['usd_lkr'].isna().sum()}"
    )
    return df


# ── Policy interest rates ──────────────────────────────────────────────────────

def load_policy_rates(cbsl_dir: Path) -> pd.DataFrame:
    """
    Load CBSL policy interest rates from the historical rates Excel file.

    Finds the Excel file by glob (name contains 'policy_interest_rates') so the
    date-stamped filename doesn't need to be hardcoded.

    The sheet "Historical Policy Rates" records each rate change event:
      Date      : DD.MM.YYYY string (e.g. '05.01.2000')
      SDF Rate  : Standing Deposit Facility rate (floor of corridor)
      SLF Rate  : Standing Lending Facility rate (ceiling of corridor)

    Returns
    -------
    pd.DataFrame with columns: date (datetime64), sdf_rate (float), slf_rate (float)
    One row per rate change event, sorted ascending by date.
    """
    # Find the file — name is date-stamped so we glob for it
    matches = sorted(cbsl_dir.glob("*policy_interest_rates*.xlsx"))
    if not matches:
        raise FileNotFoundError(
            f"No policy interest rates file found in {cbsl_dir}. "
            "Expected a file matching '*policy_interest_rates*.xlsx'."
        )
    path = matches[-1]   # Take most recent if multiple
    logger.info(f"Loading policy rates from {path.name} ...")

    df = pd.read_excel(
        path,
        sheet_name=_POLICY_SHEET,
        skiprows=_POLICY_SKIPROWS,
        header=0,
        usecols=[1, 2, 3],
    )
    df.columns = ["date", "sdf_rate", "slf_rate"]

    # Drop the header row that got read as data (skiprows=2 lands on the
    # "Per cent" label row, then row 2 = the real column names → they become data)
    df = df[df["date"] != "Date"].copy()
    df = df[df["date"].notna()].copy()

    # Dates are formatted as DD.MM.YYYY or YYYY-MM-DD depending on Excel parsing
    def _parse_date(val):
        if isinstance(val, str):
            val = val.strip()
            for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%m/%d/%Y"):
                try:
                    return pd.to_datetime(val, format=fmt)
                except (ValueError, TypeError):
                    continue
        try:
            return pd.to_datetime(val)
        except Exception:
            return pd.NaT

    df["date"]     = df["date"].apply(_parse_date)
    df["sdf_rate"] = pd.to_numeric(df["sdf_rate"], errors="coerce")
    df["slf_rate"] = pd.to_numeric(df["slf_rate"], errors="coerce")

    df = df[df["date"].notna()].sort_values("date").reset_index(drop=True)

    logger.info(
        f"  -> {len(df):,} rate-change events | "
        f"{df['date'].min().date()} to {df['date'].max().date()}"
    )
    return df
