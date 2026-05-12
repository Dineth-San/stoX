"""
market.py — Loaders for CSE daily market context files.

Four files are parsed here:

  07Market Indices - Daily.xls
    Daily index values: ASPI, S&P SL20, Milanka, and 20 sector indices.
    Goes back to 1985. Data starts at row 5 (rows 3-4 are split headers).

  09Total Returns Indices - Daily.xls
    Daily Total Return Indices: ASTRI, MTRI, S&P SL20 TRI, and sector TRIs.
    Goes back to 2004. Data starts at row 5.

  10Market Ratios - Daily.xls
    Daily market-wide P/E ratio, Price-to-Book, and Dividend Yield.
    Goes back to 1996. Data starts at row 4. Despite having 106 columns,
    only the first 4 contain meaningful data.

  11Market Statistics-Daily.xls
    Daily equity turnover, shares traded, number of trades, and total
    market cap. Goes back to 1994. Data starts at row 5.

All four are merged by date into one output DataFrame: market_context.parquet.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _read_xls_skip_header(path: Path, sheet: int | str, data_start_row: int) -> pd.DataFrame:
    """
    Read an XLS file where rows 0..data_start_row-1 are title/header junk
    and the date is in column 0. Returns a raw DataFrame with numeric index.
    """
    df = pd.read_excel(
        path,
        sheet_name=sheet,
        header=None,
        skiprows=data_start_row,
        engine="xlrd",
    )
    return df


# ── File 07: Market Indices ────────────────────────────────────────────────────

def load_market_indices(path: Path) -> pd.DataFrame:
    """
    Parse 07Market Indices - Daily.xls.

    Column layout after row 5 (data_start_row=5):
      col 0  : date
      col 1  : ASPI  (All Share Price Index)
      col 2  : MPI   (Milanka Price Index)
      col 3  : sl20_index  (S&P Sri Lanka 20)
      col 4  : sector_bfi  (Banks, Finance & Insurance)
      col 5  : sector_bft  (Beverage, Food & Tobacco)
      col 6  : sector_cp   (Chemicals & Pharmaceuticals)
      col 7  : sector_ce   (Construction & Engineering)
      col 8  : sector_div  (Diversified)
      col 9  : sector_ft   (Footwear & Textile)
      col 10 : sector_hlt  (Healthcare)
      col 11 : sector_ht   (Hotels & Travels)
      col 12 : sector_inv  (Investment Trusts)
      col 13 : sector_it   (IT)
      col 14 : sector_lp   (Land & Property)
      col 15 : sector_mfg  (Manufacturing)
      col 16 : sector_mtr  (Motors)
      col 17 : sector_oil  (Oil Palms)
      col 18 : sector_plt  (Plantations)
      col 19 : sector_pe   (Power & Energy)
      col 20 : sector_srv  (Services)
      col 21 : (blank — gap in original file)
      col 22 : sector_ss   (Stores & Supplies)
      col 23 : sector_tel  (Telecommunications)
      col 24 : sector_trd  (Trading)
    """
    logger.info(f"Loading market indices from {path.name} ...")
    df = _read_xls_skip_header(path, sheet=0, data_start_row=5)

    df.columns = [
        "date", "aspi", "mpi", "sl20_index",
        "sector_bfi", "sector_bft", "sector_cp", "sector_ce",
        "sector_div", "sector_ft", "sector_hlt", "sector_ht",
        "sector_inv", "sector_it", "sector_lp", "sector_mfg",
        "sector_mtr", "sector_oil", "sector_plt", "sector_pe",
        "sector_srv", "_blank",
        "sector_ss", "sector_tel", "sector_trd",
    ]
    df = df.drop(columns=["_blank"])

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()

    # Convert all value columns to numeric (some cells contain '-' or spaces)
    value_cols = [c for c in df.columns if c != "date"]
    for col in value_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("date").reset_index(drop=True)
    logger.info(f"  -> {len(df):,} rows | {df['date'].min().date()} to {df['date'].max().date()}")
    return df


# ── File 09: Total Return Indices ─────────────────────────────────────────────

def load_tri(path: Path) -> pd.DataFrame:
    """
    Parse 09Total Returns Indices - Daily.xls.

    Column layout after row 5 (data_start_row=5):
      col 0  : date
      col 1  : astri      (All Share Total Return Index)
      col 2  : mtri       (Milanka TRI)
      col 3  : sl20_tri   (S&P SL 20 TRI)
      col 4  : tri_bfi    (Banks, Finance & Insurance TRI)
      col 5  : tri_bft    (Beverage, Food & Tobacco TRI)
      col 6  : tri_cp
      col 7  : tri_ce
      col 8  : tri_div
      col 9  : tri_ft
      col 10 : tri_hlt
      col 11 : tri_ht
      col 12 : tri_inv
      col 13 : tri_it
      col 14 : tri_lp
      col 15 : tri_mfg
      col 16 : tri_mtr
      col 17 : tri_oil
      col 18 : tri_plt
      col 19 : tri_pe
      col 20 : tri_srv
      col 21 : tri_ss
      col 22 : tri_tel
      col 23 : tri_trd
    """
    logger.info(f"Loading TRI from {path.name} ...")
    df = _read_xls_skip_header(path, sheet=0, data_start_row=5)

    # The file has 25 columns but some may be blank trailing columns
    col_names = [
        "date", "astri", "mtri", "sl20_tri",
        "tri_bfi", "tri_bft", "tri_cp", "tri_ce",
        "tri_div", "tri_ft", "tri_hlt", "tri_ht",
        "tri_inv", "tri_it", "tri_lp", "tri_mfg",
        "tri_mtr", "tri_oil", "tri_plt", "tri_pe",
        "tri_srv", "tri_ss", "tri_tel", "tri_trd",
    ]
    df = df.iloc[:, : len(col_names)].copy()
    df.columns = col_names

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()

    value_cols = [c for c in df.columns if c != "date"]
    for col in value_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("date").reset_index(drop=True)
    logger.info(f"  -> {len(df):,} rows | {df['date'].min().date()} to {df['date'].max().date()}")
    return df


# ── File 10: Market Ratios ─────────────────────────────────────────────────────

def load_market_ratios(path: Path) -> pd.DataFrame:
    """
    Parse 10Market Ratios - Daily.xls.

    Despite having 106 columns, only the first 4 contain data:
      col 0 : date
      col 1 : market_per  (Market Price/Earnings Ratio)
      col 2 : market_pbv  (Market Price to Book Value)
      col 3 : market_dy   (Market Dividend Yield %)
    """
    logger.info(f"Loading market ratios from {path.name} ...")
    df = _read_xls_skip_header(path, sheet=0, data_start_row=4)

    # Only keep the 4 meaningful columns
    df = df.iloc[:, :4].copy()
    df.columns = ["date", "market_per", "market_pbv", "market_dy"]

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()

    df["market_per"] = pd.to_numeric(df["market_per"], errors="coerce")
    df["market_pbv"] = pd.to_numeric(df["market_pbv"], errors="coerce")
    df["market_dy"]  = pd.to_numeric(df["market_dy"],  errors="coerce")

    df = df.sort_values("date").reset_index(drop=True)
    logger.info(f"  -> {len(df):,} rows | {df['date'].min().date()} to {df['date'].max().date()}")
    return df


# ── File 11: Daily Market Statistics ──────────────────────────────────────────

def load_market_stats(path: Path) -> pd.DataFrame:
    """
    Parse 11Market Statistics-Daily.xls.

    Column layout after row 5 (data_start_row=5):
      col 0  : date
      col 1  : aspi               (duplicated from file 07, used as cross-check)
      col 2  : mpi
      col 3  : sl20_index         (duplicated, cross-check)
      col 4  : equity_turnover_mn (daily equity market turnover, LKR millions)
      col 5  : debt_corp_000      (corporate debt turnover, LKR '000)
      col 6  : debt_govt_000      (government debt turnover, LKR '000)
      col 7  : funds_turnover_000 (unit trust / fund turnover, LKR '000)
      col 8  : shares_traded_000  (total equity shares traded, '000)
      col 9  : trades_equity      (number of equity trades)
      col 10 : market_cap_mn      (total market capitalisation, LKR millions)
    """
    logger.info(f"Loading daily market stats from {path.name} ...")
    df = _read_xls_skip_header(path, sheet=0, data_start_row=5)

    df.columns = [
        "date", "aspi_check", "mpi_check", "sl20_check",
        "equity_turnover_mn", "debt_corp_000", "debt_govt_000", "funds_turnover_000",
        "shares_traded_000", "trades_equity", "market_cap_mn",
    ]

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()

    # Drop the duplicate index columns — we already have those from file 07
    df = df.drop(columns=["aspi_check", "mpi_check", "sl20_check"])

    value_cols = [c for c in df.columns if c != "date"]
    for col in value_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("date").reset_index(drop=True)
    logger.info(f"  -> {len(df):,} rows | {df['date'].min().date()} to {df['date'].max().date()}")
    return df


# ── Public API ─────────────────────────────────────────────────────────────────

def load_all_market_context(stock_data_dir: Path) -> pd.DataFrame:
    """
    Load all 4 market context files and merge them into one DataFrame by date.

    The merge is a LEFT join anchored on the market indices file (file 07),
    which has the longest history and is the primary source of truth for
    index values. Files 09, 10, 11 add their columns where dates overlap.

    Parameters
    ----------
    stock_data_dir : Path
        Path to the stock_data directory.

    Returns
    -------
    pd.DataFrame with one row per trading day and columns from all 4 files.
    """
    indices  = load_market_indices(stock_data_dir / "07Market Indices - Daily.xls")
    tri      = load_tri(stock_data_dir / "09Total Returns Indices - Daily.xls")
    ratios   = load_market_ratios(stock_data_dir / "10Market Ratios - Daily.xls")
    stats    = load_market_stats(stock_data_dir / "11Market Statistics-Daily.xls")

    logger.info("Merging all market context files on date ...")

    df = indices.merge(tri,     on="date", how="left")
    df = df.merge(ratios,       on="date", how="left")
    df = df.merge(stats,        on="date", how="left")

    df = df.sort_values("date").reset_index(drop=True)
    logger.info(f"Merged market context: {len(df):,} rows | {df.shape[1]} columns")
    return df
