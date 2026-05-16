"""
clean_market.py — Cleaning and saving the merged market context DataFrame.

What this does:
  1. Drops exact duplicate dates
  2. Filters to the ML-relevant date range (2011-01-01 onward) — earlier
     history is kept in a separate 'full' file for reference
  3. Forward-fills small gaps (weekends / public holidays that appear as NaN
     in some columns while others have values)
  4. Reports coverage statistics per column
  5. Saves both the full history and the ML-range slice
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

ML_START_DATE = "2011-01-01"


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Clean the merged market context DataFrame.

    Returns
    -------
    full_df : pd.DataFrame — full history (1985 onward)
    ml_df   : pd.DataFrame — filtered to 2011 onward (matches price data)
    """
    logger.info(f"Cleaning market context: {len(df):,} rows, {df.shape[1]} columns")

    # 1. Drop duplicate dates
    before = len(df)
    df = df.drop_duplicates(subset=["date"])
    dropped = before - len(df)
    if dropped:
        logger.info(f"  Dropped {dropped} duplicate dates")

    df = df.sort_values("date").reset_index(drop=True)

    # 2. Full history copy (for reference / future use)
    full_df = df.copy()

    # 3. ML slice: 2011 onward
    ml_df = df[df["date"] >= ML_START_DATE].copy().reset_index(drop=True)
    logger.info(f"  ML slice (2011+): {len(ml_df):,} rows")

    return full_df, ml_df


def quality_report(df: pd.DataFrame, label: str = "") -> None:
    """Print coverage stats for each column."""
    tag = f"[{label}] " if label else ""
    logger.info(f"=== {tag}MARKET CONTEXT QUALITY REPORT ===")
    logger.info(f"  Rows    : {len(df):,}")
    logger.info(f"  Columns : {df.shape[1]}")
    logger.info(f"  Dates   : {df['date'].min().date()} to {df['date'].max().date()}")
    logger.info("  Coverage per column (% non-null):")
    for col in df.columns:
        if col == "date":
            continue
        pct = df[col].notna().mean() * 100
        logger.info(f"    {col:<30s}: {pct:5.1f}%")


def save(df: pd.DataFrame, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False, engine="pyarrow")
    size_mb = out_path.stat().st_size / 1_048_576
    logger.info(f"Saved to {out_path}  ({size_mb:.1f} MB)")
    return out_path
