"""
prices.py — Raw price file loader for CSE daily price data (2011–2025)

The CSE files come in 3 distinct formats across the years:

  FORMAT A — Block format (2011–2015)
    Each company occupies a block of rows. The company ticker sits in a
    header row that contains "Company Id". Data rows have an Excel serial
    number in column 0 (the trading date). No open price exists for these
    years — that column will be NaN.

  FORMAT B — Flat table (2016–2020)
    A proper table: one row per company per day. 2016 dates are Excel serial
    numbers; 2017–2020 dates are strings like "02-JAN-17". 2016 has no open
    price column either. From 2017 onward, open price is present.

  FORMAT C — Multi-sheet flat (2021–2025)
    Same flat layout as Format B but split across quarterly sheets (2021,
    2022) or kept in one sheet (2024). 2023 is a CSV. 2025 is .xlsx with
    dates already parsed as Python datetime objects.

All formats are normalised to the same output schema:
  ticker    : str   — CSE company ID (e.g. "JKH")
  date      : date  — trading date
  open      : float — opening price (NaN for 2011–2016)
  high      : float — intraday high
  low       : float — intraday low
  close     : float — closing price
  volume    : float — number of shares traded
  turnover  : float — value traded in LKR
  trades    : float — number of individual trades (NaN if unavailable)
"""

import re
import csv
import datetime
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import xlrd
import openpyxl

logger = logging.getLogger(__name__)

# ── Excel serial date origin (Windows/Lotus epoch) ────────────────────────────
_XL_EPOCH = datetime.date(1899, 12, 30)


def _xl_serial_to_date(serial: float) -> Optional[datetime.date]:
    """Convert an Excel serial number to a Python date."""
    try:
        return _XL_EPOCH + datetime.timedelta(days=int(serial))
    except (TypeError, ValueError, OverflowError):
        return None


# ── String date parsing ────────────────────────────────────────────────────────
_DATE_FORMATS = [
    "%d-%b-%y",   # 02-JAN-17  (xlrd lowercases month abbrev sometimes)
    "%d-%b-%Y",   # 02-Jan-2017
    "%d-%B-%Y",   # 02-January-2017
    "%-d-%b-%y",  # 2-Jan-23   (no leading zero — Linux only)
    "%Y-%m-%d",   # 2023-01-02
]


def _parse_date_string(s: str) -> Optional[datetime.date]:
    """Try multiple date formats; return None if none match."""
    s = s.strip()
    # Normalise ambiguous two-digit years embedded in strings like "02-JAN-18"
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    # Last resort: pandas
    try:
        return pd.to_datetime(s, dayfirst=True).date()
    except Exception:
        return None


def _to_float(val) -> float:
    """Coerce a value to float, stripping commas/spaces. Returns NaN on failure."""
    if val is None or val == "":
        return np.nan
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return np.nan


# ── Format A parser (2011–2015 block format) ──────────────────────────────────

def _extract_ticker_block(row: list) -> Optional[str]:
    """
    Given a row that contains 'Company Id', extract the ticker symbol.

    Three sub-styles seen in the data:
      2011 → row[0] = 'Company Id :  AAIC'          (ticker in col 0 after colon)
      2012 → row[0] = 'Company Id', row[1] = ':  AAF' (ticker in col 1 after colon)
      2013 → row[0] = 'Company Id :', row[1] = 'AAF'  (ticker is col 1 directly)
    """
    col0 = str(row[0]).strip()
    col1 = str(row[1]).strip() if len(row) > 1 else ""

    # Style 2011: ticker embedded in col0 after the last ':'
    if ":" in col0 and len(col0.split(":")[-1].strip()) > 0:
        candidate = col0.split(":")[-1].strip()
        if candidate and candidate not in ("N", "0000"):
            return candidate

    # Style 2012: col1 starts with ':'
    if col1.startswith(":"):
        candidate = col1.lstrip(":").strip()
        if candidate:
            return candidate

    # Style 2013/2014/2015: col1 is the raw ticker
    if col1 and not col1.startswith(":"):
        # Make sure it looks like a ticker (short, alphanumeric)
        if re.match(r"^[A-Z0-9]{1,10}$", col1):
            return col1

    return None


def _parse_block_format(ws, year: int) -> list[dict]:
    """
    Parse Format A (block-per-company).

    Walks row by row:
      - A 'Company Id' row updates the current ticker.
      - A row whose col 0 is a numeric serial date and col 2 is numeric is a data row.
      - Everything else is skipped (headers, blank lines).
    """
    records = []
    current_ticker: Optional[str] = None

    for row_idx in range(ws.nrows):
        row = ws.row_values(row_idx)
        col0 = str(row[0]).strip()

        # Detect company header row
        if "Company Id" in col0 or (col0 == "Company Id" and len(row) > 1):
            ticker = _extract_ticker_block(row)
            if ticker:
                current_ticker = ticker
            continue

        # Detect data row: col 0 is a positive number (serial date), col 2 numeric
        if current_ticker is None:
            continue

        try:
            serial = float(row[0])
            if serial < 30000 or serial > 60000:   # rough sanity range
                continue
        except (TypeError, ValueError):
            continue

        trading_date = _xl_serial_to_date(serial)
        if trading_date is None:
            continue

        # Columns: Day, DateHigh, High, DateLow, Low, Closing, Trades, Shares, Turnover, LastTraded
        try:
            high     = _to_float(row[2])
            low      = _to_float(row[4])
            close    = _to_float(row[5])
            trades   = _to_float(row[6]) if len(row) > 6 else np.nan
            volume   = _to_float(row[7]) if len(row) > 7 else np.nan
            turnover = _to_float(row[8]) if len(row) > 8 else np.nan
        except IndexError:
            continue

        # Skip rows where close is zero or NaN (non-trading days sometimes appear)
        if np.isnan(close) or close == 0:
            continue

        records.append({
            "ticker":   current_ticker,
            "date":     trading_date,
            "open":     np.nan,   # Not available in 2011–2015
            "high":     high,
            "low":      low,
            "close":    close,
            "volume":   volume,
            "turnover": turnover,
            "trades":   trades,
        })

    return records


# ── Format B/C parser (2016–2025 flat table) ──────────────────────────────────

def _find_header_row(rows: list[list]) -> int:
    """
    Return the index of the row containing the column headers.
    We detect it by looking for 'COMPANY ID' or 'TRADING DATE'.
    """
    for i, row in enumerate(rows):
        joined = " ".join(str(v).upper().strip() for v in row if v is not None)
        if "COMPANY ID" in joined or "TRADING DATE" in joined:
            return i
    return -1


def _parse_flat_rows(rows: list[list], has_open: bool, date_is_serial: bool) -> list[dict]:
    """
    Parse a flat table (one row = one stock × one date).

    Expected column order (after header row):
      0: COMPANY ID
      1: MAIN TYPE
      2: SUB TYPE
      3: SHORT NAME
      4: TRADING DATE
      5: PRICE HIGH
      6: PRICE LOW
      7: CLOSE PRICE
      8: OPEN PRICE   ← only if has_open=True
      9: TRADE VOLUME
     10: SHARE VOLUME (sometimes)
     11: TURNOVER     (sometimes)

    Note: `date_is_serial` is a hint, not a guarantee. Some files (e.g. 2022
    quarterly sheets) mix string dates in Q1/Q2 and serial dates in Q3/Q4.
    The parser auto-detects per row: if the raw date is a float in the range
    of plausible Excel serials (30000–60000), it is treated as a serial number
    regardless of the `date_is_serial` flag.
    """
    records = []
    header_idx = _find_header_row(rows)
    if header_idx == -1:
        logger.warning("Could not find header row in flat sheet")
        return records

    for row in rows[header_idx + 1:]:
        if not row or row[0] is None or str(row[0]).strip() == "":
            continue

        ticker = str(row[0]).strip().upper()
        if not ticker or ticker == "COMPANY ID":
            continue

        # Parse date — auto-detect format per row
        raw_date = row[4] if len(row) > 4 else None
        if raw_date is None:
            continue

        if isinstance(raw_date, (datetime.datetime, datetime.date)):
            # openpyxl already parsed it as a datetime object
            trading_date = raw_date.date() if isinstance(raw_date, datetime.datetime) else raw_date
        elif isinstance(raw_date, (int, float)):
            # Numeric value — treat as Excel serial if it looks like one,
            # regardless of the year-level date_is_serial hint.
            # This handles mixed-format files (e.g. 2022 Q3/Q4 vs Q1/Q2).
            try:
                serial = float(raw_date)
                if 30000 < serial < 60000:
                    trading_date = _xl_serial_to_date(serial)
                else:
                    trading_date = None
            except (TypeError, ValueError):
                trading_date = None
        else:
            trading_date = _parse_date_string(str(raw_date))

        if trading_date is None:
            continue

        high     = _to_float(row[5]) if len(row) > 5 else np.nan
        low      = _to_float(row[6]) if len(row) > 6 else np.nan
        close    = _to_float(row[7]) if len(row) > 7 else np.nan

        if has_open:
            open_p   = _to_float(row[8]) if len(row) > 8 else np.nan
            volume   = _to_float(row[9]) if len(row) > 9 else np.nan
            turnover = _to_float(row[10]) if len(row) > 10 else np.nan
            trades   = _to_float(row[11]) if len(row) > 11 else np.nan
        else:
            open_p   = np.nan
            volume   = _to_float(row[8]) if len(row) > 8 else np.nan
            turnover = _to_float(row[9]) if len(row) > 9 else np.nan
            trades   = np.nan

        if np.isnan(close) or close == 0:
            continue

        records.append({
            "ticker":   ticker,
            "date":     trading_date,
            "open":     open_p,
            "high":     high,
            "low":      low,
            "close":    close,
            "volume":   volume,
            "turnover": turnover,
            "trades":   trades,
        })

    return records


# ── Per-year loaders ───────────────────────────────────────────────────────────

def _load_block_xls(path: Path, year: int) -> list[dict]:
    """Load a Format A (block) .xls file."""
    wb = xlrd.open_workbook(str(path))
    ws = wb.sheet_by_index(0)
    return _parse_block_format(ws, year)


def _load_flat_xls(path: Path, year: int) -> list[dict]:
    """Load a Format B (flat, single sheet) .xls file."""
    wb = xlrd.open_workbook(str(path))
    records = []
    for sheet_idx in range(wb.nsheets):
        ws = wb.sheet_by_index(sheet_idx)
        rows = [ws.row_values(i) for i in range(ws.nrows)]
        # 2016 and 2017 use Excel serial dates; 2018+ use string dates
        date_is_serial = (year <= 2017)
        has_open = (year >= 2017)
        records.extend(_parse_flat_rows(rows, has_open=has_open, date_is_serial=date_is_serial))
    return records


def _load_flat_xlsx(path: Path, year: int) -> list[dict]:
    """Load a Format C (flat) .xlsx file."""
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    records = []
    for sheet in wb.worksheets:
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
        records.extend(_parse_flat_rows(rows, has_open=True, date_is_serial=False))
    wb.close()
    return records


def _load_csv(path: Path, year: int) -> list[dict]:
    """Load the 2023 CSV file (same column layout as flat format)."""
    records = []
    with open(str(path), encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        all_rows = list(reader)

    records.extend(_parse_flat_rows(all_rows, has_open=True, date_is_serial=False))
    return records


# ── Public API ─────────────────────────────────────────────────────────────────

# Maps each year to its file path (relative to the stock_data directory)
# and the loader function to use.
_YEAR_CONFIG = {
    2011: ("32Daily Shares Price List -2011-2020/2011 Data.xls",  "block"),
    2012: ("32Daily Shares Price List -2011-2020/2012 Data.xls",  "block"),
    2013: ("32Daily Shares Price List -2011-2020/2013 Data.xls",  "block"),
    2014: ("32Daily Shares Price List -2011-2020/2014 Data.xls",  "block"),
    2015: ("32Daily Shares Price List -2011-2020/2015 Data.xls",  "block"),
    2016: ("32Daily Shares Price List -2011-2020/2016 Data.xls",  "flat_xls"),
    2017: ("32Daily Shares Price List -2011-2020/2017 Data.xls",  "flat_xls"),
    2018: ("32Daily Shares Price List -2011-2020/2018 Data.xls",  "flat_xls"),
    2019: ("32Daily Shares Price List -2011-2020/2019 Data.xls",  "flat_xls"),
    2020: ("32Daily Shares Price List -2011-2020/2020 Data.xls",  "flat_xls"),
    2021: ("33Daily Shares Price List -2021-2025/2021 Data.xls",  "flat_xls"),
    2022: ("33Daily Shares Price List -2021-2025/2022 Data.xls",  "flat_xls"),
    2023: ("33Daily Shares Price List -2021-2025/2023 Data.csv",  "csv"),
    2024: ("33Daily Shares Price List -2021-2025/2024 Data.xls",  "flat_xls"),
    2025: ("33Daily Shares Price List -2021-2025/2025 Data.xlsx", "flat_xlsx"),
}


def load_year(year: int, stock_data_dir: Path) -> pd.DataFrame:
    """
    Load and parse a single year's price file.

    Parameters
    ----------
    year : int
        The year to load (2011–2025).
    stock_data_dir : Path
        Path to the stock_data directory containing the raw files.

    Returns
    -------
    pd.DataFrame with columns: ticker, date, open, high, low, close,
                                volume, turnover, trades
    """
    if year not in _YEAR_CONFIG:
        raise ValueError(f"Year {year} is not configured. Available: {sorted(_YEAR_CONFIG)}")

    rel_path, loader_type = _YEAR_CONFIG[year]
    path = stock_data_dir / rel_path

    if not path.exists():
        raise FileNotFoundError(f"Price file not found: {path}")

    logger.info(f"Loading {year} ({loader_type}) from {path.name} ...")

    if loader_type == "block":
        records = _load_block_xls(path, year)
    elif loader_type == "flat_xls":
        records = _load_flat_xls(path, year)
    elif loader_type == "flat_xlsx":
        records = _load_flat_xlsx(path, year)
    elif loader_type == "csv":
        records = _load_csv(path, year)
    else:
        raise ValueError(f"Unknown loader type: {loader_type}")

    if not records:
        logger.warning(f"No records parsed for year {year}")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["year"] = year
    df["date"] = pd.to_datetime(df["date"])

    logger.info(f"  -> {len(df):,} rows | {df['ticker'].nunique()} tickers")
    return df


def load_all_years(stock_data_dir: Path, years: list[int] = None) -> pd.DataFrame:
    """
    Load and concatenate all (or selected) years into one DataFrame.

    Parameters
    ----------
    stock_data_dir : Path
        Path to the stock_data directory.
    years : list[int], optional
        Subset of years to load. Defaults to all available (2011–2025).

    Returns
    -------
    pd.DataFrame — all years stacked, sorted by ticker then date.
    """
    if years is None:
        years = sorted(_YEAR_CONFIG.keys())

    frames = []
    for year in years:
        try:
            df = load_year(year, stock_data_dir)
            if not df.empty:
                frames.append(df)
        except FileNotFoundError as e:
            logger.error(str(e))
        except Exception as e:
            logger.error(f"Failed to load year {year}: {e}", exc_info=True)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["ticker", "date"]).reset_index(drop=True)
    return combined
