"""
calendar.py — Build the CSE trading calendar from the master prices file.

A trading day is defined as any date in the historical range where at least
MIN_SL20_ACTIVE of the 20 SL20 stocks have price data.  This derives the
calendar directly from observed data — no hardcoded holiday list needed.

Why this approach?
------------------
The CSE doesn't publish a machine-readable holiday calendar.  Using the
price data itself is more reliable: if the exchange was open, the stocks
traded; if it was closed, there is no data for any stock.

The MIN_SL20_ACTIVE threshold (default 10) handles days where a few stocks
might be suspended, have data gaps, or were newly listed — the day is still
treated as a trading day as long as the majority of the index was active.
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

MIN_SL20_ACTIVE = 10   # Minimum SL20 tickers with data to count as a trading day


def build_cse_trading_calendar(
    prices_path: Path,
    sl20_tickers: list[str],
    start_date: str,
    end_date: str,
    min_active: int = MIN_SL20_ACTIVE,
) -> pd.DatetimeIndex:
    """
    Extract CSE trading days from master_prices.parquet.

    Parameters
    ----------
    prices_path  : Path to master_prices.parquet
    sl20_tickers : List of 20 SL20 ticker symbols
    start_date   : "YYYY-MM-DD" — first date to include
    end_date     : "YYYY-MM-DD" — last date to include
    min_active   : Minimum SL20 tickers that must have data for a day to count

    Returns
    -------
    pd.DatetimeIndex — sorted trading dates within the requested range
    """
    logger.info("Building CSE trading calendar from price data ...")

    # Load only the columns we need (fast)
    df = pd.read_parquet(prices_path, columns=["date", "ticker"])
    df = df[df["ticker"].isin(sl20_tickers)].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

    # Count distinct SL20 tickers per date
    daily_active = df.groupby("date")["ticker"].nunique()

    # A trading day needs at least min_active SL20 stocks
    trading_days = daily_active[daily_active >= min_active].index.sort_values()

    logger.info(
        f"  Trading calendar: {len(trading_days):,} days | "
        f"{trading_days[0].date()} to {trading_days[-1].date()} | "
        f"avg SL20 active: {daily_active[daily_active >= min_active].mean():.1f}/20"
    )

    # Sanity checks
    _validate_calendar(trading_days)
    return trading_days


def _validate_calendar(cal: pd.DatetimeIndex) -> None:
    """Basic sanity checks on the derived trading calendar."""
    # No weekends should appear
    n_weekends = (cal.dayofweek >= 5).sum()
    if n_weekends > 0:
        logger.warning(f"Calendar contains {n_weekends} weekend days — check source data.")

    # Check there are no implausibly long gaps (> 20 consecutive missing days)
    gaps = cal.to_series().diff().dt.days.dropna()
    max_gap = gaps.max()
    if max_gap > 20:
        gap_date = gaps.idxmax()
        logger.warning(
            f"Largest gap in trading calendar: {int(max_gap)} days before {gap_date.date()}. "
            "Possibly a market closure period (e.g. Easter 2020 or 2022 crisis)."
        )

    # Expected roughly 240–260 trading days per year
    years = cal.year.unique()
    for yr in sorted(years):
        n = (cal.year == yr).sum()
        if n < 180 or n > 275:
            logger.warning(f"  Year {yr}: {n} trading days (expected ~240–260)")
        else:
            logger.info(f"  Year {yr}: {n} trading days")
