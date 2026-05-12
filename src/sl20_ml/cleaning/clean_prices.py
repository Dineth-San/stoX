"""
clean_prices.py — Cleaning and quality checks on the raw merged price DataFrame.

What this does (in order):
  1. Drop exact duplicates (same ticker + date appearing twice)
  2. Keep only rows where close > 0
  3. Flag and report tickers with suspiciously large single-day price moves (>50%)
  4. Fill forward open price for years where it was missing (2011–2016) using the
     previous close as a reasonable proxy
  5. Add a simple daily_return column (percentage change in close)
  6. Report a data quality summary before saving

The output is saved as a Parquet file for fast loading later.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def clean(df: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    """
    Run all cleaning steps on the raw merged price DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Output from load_all_years() — raw, unfiltered.
    cfg : dict, optional
        Pipeline config from load_config(). If None, uses hardcoded defaults.
        Reads: cfg["cleaning"]["max_daily_return_flag"]
               cfg["cleaning"]["min_close_price"]

    Returns
    -------
    pd.DataFrame — cleaned, with added flag columns.
    """
    cleaning_cfg = (cfg or {}).get("cleaning", {})
    max_return_flag = cleaning_cfg.get("max_daily_return_flag", 0.50)
    min_close       = cleaning_cfg.get("min_close_price", 0.01)

    original_len = len(df)
    logger.info(f"Starting clean: {original_len:,} rows")

    # ── 1. Drop exact duplicates ──────────────────────────────────────────────
    df = df.drop_duplicates(subset=["ticker", "date"])
    logger.info(f"After dedup: {len(df):,} rows (removed {original_len - len(df):,})")

    # ── 2. Drop rows where close is below minimum ─────────────────────────────
    before = len(df)
    df = df[df["close"].notna() & (df["close"] >= min_close)]
    logger.info(f"After close>={min_close} filter: {len(df):,} rows (removed {before - len(df):,})")

    # ── 3. Sort for consistent ordering ──────────────────────────────────────
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    # ── 4. Fill missing open prices (2011–2016 had no open column) ───────────
    # For days with NaN open, use the previous day's close as a proxy.
    # This is standard practice for markets where open is unavailable.
    df["open"] = df.groupby("ticker")["open"].transform(
        lambda s: s.fillna(df.loc[s.index, "close"].shift(1))
    )

    # ── 5. Add daily return ───────────────────────────────────────────────────
    df["daily_return"] = df.groupby("ticker")["close"].pct_change()

    # ── 6. Flag OHLC consistency violations ───────────────────────────────────
    # These are kept in the dataset (per spec: "flag and log, do not drop").
    # Root cause: CSE source data sometimes records a reference price (e.g.
    # previous close or open) in the PRICE HIGH column rather than the true
    # intraday high. This is a known data quality issue in some CSE files.
    ohlc_bad = (
        df["high"].isna() |
        df["low"].isna() |
        (df["high"] < df["low"]) |
        (df["high"] < df["close"]) |
        (df["low"]  > df["close"])
    )
    df["ohlc_inconsistent"] = ohlc_bad
    n_ohlc = ohlc_bad.sum()
    if n_ohlc > 0:
        logger.warning(
            f"Found {n_ohlc:,} rows with OHLC inconsistencies "
            f"(high<low, high<close, or low>close). "
            f"Rows are kept and flagged with ohlc_inconsistent=True."
        )

    # ── 7. Flag extreme moves for review ─────────────────────────────────────
    extreme = df[df["daily_return"].abs() > max_return_flag]
    if len(extreme) > 0:
        logger.warning(
            f"Found {len(extreme):,} rows with |daily_return| > {max_return_flag:.0%} — "
            f"likely data errors or corporate actions (splits, bonuses). "
            f"These are kept in the dataset but flagged."
        )
        df["suspicious_move"] = df["daily_return"].abs() > max_return_flag
    else:
        df["suspicious_move"] = False

    logger.info(f"Clean complete: {len(df):,} rows | {df['ticker'].nunique()} tickers")
    return df


def quality_report(df: pd.DataFrame) -> None:
    """Print a human-readable quality summary to the log."""
    logger.info("=== DATA QUALITY REPORT ===")
    logger.info(f"Total rows       : {len(df):,}")
    logger.info(f"Unique tickers   : {df['ticker'].nunique()}")
    logger.info(f"Date range       : {df['date'].min().date()} to {df['date'].max().date()}")
    logger.info(f"Years covered    : {sorted(df['year'].unique().tolist())}")
    logger.info(f"Missing open     : {df['open'].isna().sum():,}")
    logger.info(f"Missing high     : {df['high'].isna().sum():,}")
    logger.info(f"Missing low      : {df['low'].isna().sum():,}")
    logger.info(f"Missing volume   : {df['volume'].isna().sum():,}")
    logger.info(f"OHLC inconsistent: {df['ohlc_inconsistent'].sum():,}")
    logger.info(f"Suspicious moves : {df['suspicious_move'].sum():,}")

    # Tickers with the most trading days (completeness check)
    days_per_ticker = df.groupby("ticker")["date"].count().sort_values(ascending=False)
    logger.info(f"Top 5 tickers by trading days:\n{days_per_ticker.head()}")
    logger.info(f"Bottom 5 tickers by trading days:\n{days_per_ticker.tail()}")


def save(df: pd.DataFrame, out_path: Path) -> Path:
    """
    Save the cleaned DataFrame to a Parquet file.

    Parameters
    ----------
    df : pd.DataFrame
    out_path : Path — full destination path (e.g. ml/data/cleaned/master_prices.parquet)

    Returns
    -------
    Path — the saved file path.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False, engine="pyarrow")
    size_mb = out_path.stat().st_size / 1_048_576
    logger.info(f"Saved to {out_path}  ({size_mb:.1f} MB)")
    return out_path
