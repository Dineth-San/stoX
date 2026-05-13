"""
clean_macro.py — Cleaning and saving the macro context DataFrames.

Produces two Parquet files:

  data/cleaned/cbsl.parquet
    Daily Sri Lanka macro: USD/LKR rate + CBSL policy rates (SDF/SLF).
    Policy rates are event-driven (one row per change) → forward-filled to daily.
    Coverage: 2011-01-01 to end of available data.

  data/cleaned/gdp.parquet
    Annual Sri Lanka macro: GDP growth, CPI inflation, unemployment.
    Rows are labelled by year (Jan 1 of the given year).
    Intentionally left as annual; forward-filling to daily happens in Phase 3
    (alignment layer) with proper look-ahead bias guards.

  data/cleaned/fred.parquet
    Daily global macro: oil (WTI), S&P 500, VIX, US 10-year yield, DXY, gold.
    Weekend/holiday gaps are forward-filled (market values don't change on non-
    trading days, and the last known value is the correct feature value).

Notes on look-ahead bias
------------------------
All ffill operations here are safe because they fill *backward* gaps (weekends,
holidays) with already-known values.  The annual GDP/CPI forward-fill is NOT
done here to avoid accidentally using year-N data for year-N observations
before the official publication date.  That alignment is handled in Phase 3.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── CBSL (exchange rates + policy rates) ───────────────────────────────────────

def clean_cbsl(
    exchange_df: pd.DataFrame,
    policy_df: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Merge exchange rates and policy rates into a single daily DataFrame.

    Exchange rates are already daily (weekdays only, from FRED).
    Policy rates are event-driven (sparse) — we expand them to a daily calendar
    by forward-filling: the rate stays constant until the next change event.

    Parameters
    ----------
    exchange_df : columns date, usd_lkr
    policy_df   : columns date, sdf_rate, slf_rate  (one row per rate change)
    start_date  : "YYYY-MM-DD"
    end_date    : "YYYY-MM-DD"

    Returns
    -------
    pd.DataFrame — daily (calendar days), columns:
        date, usd_lkr, sdf_rate, slf_rate, policy_rate_mid
    """
    logger.info("Cleaning CBSL macro data ...")

    # Build a full calendar-day index for the ML range
    date_index = pd.date_range(start=start_date, end=end_date, freq="D")

    # ── Exchange rates ─────────────────────────────────────────────────────────
    exch = exchange_df.set_index("date")["usd_lkr"]
    exch = exch.reindex(date_index)
    # Forward-fill weekends/holidays, then back-fill any leading NaN
    exch = exch.ffill().bfill()

    # ── Policy rates ──────────────────────────────────────────────────────────
    pol = policy_df.set_index("date")[["sdf_rate", "slf_rate"]]
    pol = pol.reindex(date_index)
    # Forward-fill: rate is unchanged until the next announcement
    pol = pol.ffill().bfill()

    # ── Combine ───────────────────────────────────────────────────────────────
    df = pd.DataFrame({"date": date_index, "usd_lkr": exch.values})
    df["sdf_rate"]        = pol["sdf_rate"].values
    df["slf_rate"]        = pol["slf_rate"].values
    df["policy_rate_mid"] = (df["sdf_rate"] + df["slf_rate"]) / 2.0

    # Trim to actual ML range (start_date onward)
    df = df[df["date"] >= start_date].reset_index(drop=True)

    _cbsl_quality_report(df)
    return df


def _cbsl_quality_report(df: pd.DataFrame) -> None:
    logger.info("=== CBSL QUALITY REPORT ===")
    logger.info(f"  Rows   : {len(df):,}")
    logger.info(f"  Dates  : {df['date'].min().date()} to {df['date'].max().date()}")
    for col in ["usd_lkr", "sdf_rate", "slf_rate", "policy_rate_mid"]:
        n_null = df[col].isna().sum()
        logger.info(
            f"  {col:<22s}: min={df[col].min():.2f}  "
            f"max={df[col].max():.2f}  "
            f"null={n_null}"
        )


# ── GDP / WDI (annual) ─────────────────────────────────────────────────────────

def clean_gdp(
    gdp_df: pd.DataFrame,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """
    Filter and validate the annual WDI macro DataFrame.

    Parameters
    ----------
    gdp_df     : output of ingestion.gdp.load_wdi()
    start_year : first year to keep (e.g. 2011)
    end_year   : last year to keep  (e.g. 2025)

    Returns
    -------
    pd.DataFrame with columns: date (Jan 1 of the year) + indicator columns.
    Kept as annual; Phase 3 alignment layer handles ffill to daily.
    """
    logger.info("Cleaning GDP / WDI macro data ...")

    df = gdp_df[
        (gdp_df["year"] >= start_year) & (gdp_df["year"] <= end_year)
    ].copy()

    # Convert year to a proper date (Jan 1) as the reference point
    df["date"] = pd.to_datetime(df["year"].astype(str) + "-01-01")
    df = df.drop(columns=["year"])
    df = df.sort_values("date").reset_index(drop=True)

    indicator_cols = [c for c in df.columns if c != "date"]
    logger.info("=== GDP / WDI QUALITY REPORT ===")
    logger.info(f"  Rows    : {len(df)}")
    logger.info(f"  Years   : {df['date'].dt.year.min()} - {df['date'].dt.year.max()}")
    for col in indicator_cols:
        n_null = df[col].isna().sum()
        vals   = df[col].dropna()
        logger.info(
            f"  {col:<22s}: {len(vals)}/{len(df)} non-null | "
            f"range [{vals.min():.2f}, {vals.max():.2f}]"
            if len(vals) else
            f"  {col:<22s}: ALL NULL"
        )
    return df


# ── FRED (daily global macro) ──────────────────────────────────────────────────

def clean_fred(
    fred_df: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Clean the merged FRED daily DataFrame.

    Steps:
      1. Trim to ML date range
      2. Forward-fill weekend/holiday gaps (at most 4 consecutive days)
      3. Report coverage per column

    Parameters
    ----------
    fred_df    : output of ingestion.fred.load_all_fred()
    start_date : "YYYY-MM-DD"
    end_date   : "YYYY-MM-DD"

    Returns
    -------
    pd.DataFrame — daily, trimmed, forward-filled.
    """
    logger.info("Cleaning FRED global macro data ...")

    df = fred_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()

    # Reindex to full calendar so gaps are explicit
    date_index = pd.date_range(start=df["date"].min(), end=df["date"].max(), freq="D")
    df = df.set_index("date").reindex(date_index)
    df.index.name = "date"

    # Forward-fill (max 4 days = long weekend), then back-fill leading NaNs
    df = df.ffill(limit=4).bfill()
    df = df.reset_index()

    # Any remaining NaN → warn (gaps longer than 4 days)
    value_cols = [c for c in df.columns if c != "date"]
    logger.info("=== FRED QUALITY REPORT ===")
    logger.info(f"  Rows   : {len(df):,}")
    logger.info(f"  Dates  : {df['date'].min().date()} to {df['date'].max().date()}")
    for col in value_cols:
        n_null = df[col].isna().sum()
        pct    = df[col].notna().mean() * 100
        logger.info(
            f"  {col:<16s}: coverage {pct:5.1f}% | "
            f"null={n_null} | "
            f"range [{df[col].min():.1f}, {df[col].max():.1f}]"
        )
    return df


# ── Save helper ────────────────────────────────────────────────────────────────

def save(df: pd.DataFrame, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False, engine="pyarrow")
    size_mb = out_path.stat().st_size / 1_048_576
    logger.info(f"Saved to {out_path}  ({size_mb:.1f} MB)")
    return out_path
