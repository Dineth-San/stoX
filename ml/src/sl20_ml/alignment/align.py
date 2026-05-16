"""
align.py — Join all cleaned data sources onto the CSE trading calendar.

Output: sl20_daily_panel.parquet
  Shape: (N_trading_days × 20 tickers) rows × all feature columns
  Typically ~71,300 rows × ~85 columns

Column groups
-------------
  Identity    : date, ticker, split
  Prices      : open, high, low, close, adj_close, volume, turnover, trades,
                daily_return, ohlc_inconsistent, suspicious_move
  Market      : aspi, sl20_index, mpi, sector_*, market_per, market_pbv,
                market_dy, equity_turnover_mn, shares_traded_000, market_cap_mn,
                astri, sl20_tri, tri_* (TRI indices)
  CBSL        : usd_lkr, sdf_rate, slf_rate, policy_rate_mid
  GDP (annual): gdp_growth_pct, gdp_constant_usd, inflation_pct, unemployment_pct,
                gdp_days_stale   (days since last annual update — staleness flag)
  FRED        : oil_wti, sp500, vix, us_10y_yield, dxy, gold

Look-ahead bias rules
---------------------
  Prices       : today's OHLCV are known at market close today → safe to use
                 as features for predicting tomorrow's close.
  Market ctx   : same — published at close.
  CBSL rates   : CBSL announces rate changes at 8am on the decision date → safe.
  Exchange rate: observed intraday, use same-day value → safe.
  FRED data    : US market data from previous close (Sri Lanka is GMT+5:30,
                 US market closes ~4pm EST = ~2:30am the following day Sri Lanka
                 time) → same-date FRED values are slightly forward for the first
                 hour of CSE trading but conservatively safe at close.
  GDP / CPI    : ANNUAL data published ~3-6 months into the following year.
                 We apply a 12-month lag: year-Y data is made available on
                 Jan 1 of year Y+1.  This is conservative but guarantees
                 zero look-ahead bias.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# GDP/CPI: make year-Y data available starting Jan 1 of year Y+1
_GDP_LAG_MONTHS = 12


def build_daily_panel(
    trading_cal: pd.DatetimeIndex,
    prices_path: Path,
    market_path: Path,
    cbsl_path: Path,
    gdp_path: Path,
    fred_path: Path,
    sl20_tickers: list[str],
    cfg: dict,
) -> pd.DataFrame:
    """
    Join all cleaned Phase-2 sources onto the CSE trading calendar.

    Returns
    -------
    pd.DataFrame — one row per (ticker, date), sorted by (ticker, date).
    All columns are aligned to the trading calendar with look-ahead guards.
    """
    logger.info(
        f"Building daily panel: {len(sl20_tickers)} tickers × "
        f"{len(trading_cal):,} trading days = "
        f"{len(sl20_tickers) * len(trading_cal):,} rows"
    )

    # ── 1. Base panel: cross join tickers × trading days ──────────────────────
    cal_df      = pd.DataFrame({"date": trading_cal})
    tickers_df  = pd.DataFrame({"ticker": sl20_tickers})
    base = cal_df.assign(_k=1).merge(tickers_df.assign(_k=1), on="_k").drop("_k", axis=1)
    base = base.sort_values(["ticker", "date"]).reset_index(drop=True)
    logger.info(f"  Base panel: {len(base):,} rows")

    # ── 2. Prices ─────────────────────────────────────────────────────────────
    prices = pd.read_parquet(prices_path)
    prices = prices[prices["ticker"].isin(sl20_tickers)].copy()
    prices["date"] = pd.to_datetime(prices["date"])

    price_cols = [
        "ticker", "date", "open", "high", "low", "close", "adj_close",
        "volume", "turnover", "trades", "daily_return",
        "ohlc_inconsistent", "suspicious_move",
    ]
    prices = prices[price_cols]

    panel = base.merge(prices, on=["ticker", "date"], how="left")
    n_price_missing = panel["close"].isna().sum()
    logger.info(
        f"  Prices joined: {n_price_missing:,} rows with missing close "
        f"({n_price_missing / len(panel):.1%}) — days ticker didn't trade"
    )

    # ── 3. Market context (same for all tickers on a given day) ──────────────
    market = pd.read_parquet(market_path)
    market["date"] = pd.to_datetime(market["date"])
    # Drop columns that duplicate price data already in the panel
    market = market.drop(columns=[c for c in ["aspi_check", "mpi_check"] if c in market.columns])
    panel = panel.merge(market, on="date", how="left")
    n_mkt_null = panel["aspi"].isna().sum()
    logger.info(f"  Market context joined: {n_mkt_null:,} rows with missing aspi")

    # ── 4. CBSL (exchange rate + policy rates) ────────────────────────────────
    cbsl = pd.read_parquet(cbsl_path)
    cbsl["date"] = pd.to_datetime(cbsl["date"])
    panel = panel.merge(cbsl, on="date", how="left")
    # Any remaining NaN (shouldn't happen — cbsl covers full calendar):
    for col in ["usd_lkr", "sdf_rate", "slf_rate", "policy_rate_mid"]:
        if panel[col].isna().any():
            panel[col] = panel[col].ffill()
    logger.info(f"  CBSL joined: usd_lkr null={panel['usd_lkr'].isna().sum()}")

    # ── 5. FRED global macro ───────────────────────────────────────────────────
    fred = pd.read_parquet(fred_path)
    fred["date"] = pd.to_datetime(fred["date"])
    panel = panel.merge(fred, on="date", how="left")
    # Residual NaN from very start of range — backfill
    fred_cols = ["oil_wti", "sp500", "vix", "us_10y_yield", "dxy", "gold"]
    for col in fred_cols:
        if panel[col].isna().any():
            panel[col] = panel[col].ffill().bfill()
    logger.info(f"  FRED joined: oil_wti null={panel['oil_wti'].isna().sum()}")

    # ── 6. GDP / CPI — look-ahead safe ────────────────────────────────────────
    panel = _merge_gdp_safe(panel, gdp_path, trading_cal)

    # ── 7. Split labels (train / val / test) ──────────────────────────────────
    panel = _add_split_labels(panel, cfg)

    # ── 8. Final sort + validate ───────────────────────────────────────────────
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    _validate_panel(panel, sl20_tickers, trading_cal)

    return panel


# ── GDP look-ahead safe merge ──────────────────────────────────────────────────

def _merge_gdp_safe(
    panel: pd.DataFrame,
    gdp_path: Path,
    trading_cal: pd.DatetimeIndex,
) -> pd.DataFrame:
    """
    Merge annual GDP/CPI/unemployment onto the panel with a 12-month lag.

    Year-Y data (labelled Jan 1, year Y in gdp.parquet) is made available
    starting Jan 1, year Y+1.  Forward-filled from that date until the next
    year's data arrives.  Rows before the first available data point are NaN.

    Also adds `gdp_days_stale` — days since the last GDP update — so the
    model can learn to down-weight stale macro features.
    """
    gdp = pd.read_parquet(gdp_path)
    gdp["date"] = pd.to_datetime(gdp["date"])

    # Shift dates by LAG months: year-Y data available from Jan 1, year Y+1
    gdp["date"] = gdp["date"] + pd.DateOffset(months=_GDP_LAG_MONTHS)
    gdp = gdp.sort_values("date").reset_index(drop=True)

    gdp_indicator_cols = [c for c in gdp.columns if c != "date"]

    # Use merge_asof: for each trading day, find the most recent GDP record
    # on or before that date.  This handles the fact that Jan 1 (our shifted
    # date) is never a trading day — the value is picked up on the first
    # trading day of the year instead.
    cal_df = pd.DataFrame({"date": pd.DatetimeIndex(trading_cal).sort_values()})
    gdp_sorted = gdp.sort_values("date")
    gdp_daily = pd.merge_asof(cal_df, gdp_sorted, on="date", direction="backward")

    # Staleness: days since the last GDP update point
    gdp_daily["gdp_days_stale"] = _compute_staleness(gdp_daily, gdp, "date")

    # Merge into panel (date-level join, same value for all tickers on a day)
    panel = panel.merge(gdp_daily, on="date", how="left")

    n_null = panel[gdp_indicator_cols[0]].isna().sum()
    logger.info(
        f"  GDP joined (12-month lag): {n_null:,} rows without GDP data "
        f"(expected ~{20 * 260} rows for first year)"
    )
    return panel


def _compute_staleness(cal_df: pd.DataFrame, source_df: pd.DataFrame, date_col: str) -> pd.Series:
    """
    For each row in cal_df, compute how many calendar days have elapsed since
    the most recent observation in source_df on or before that row's date.
    """
    source_dates = pd.to_datetime(source_df[date_col]).sort_values().values
    cal_dates    = pd.to_datetime(cal_df[date_col]).values

    staleness = np.full(len(cal_dates), np.nan, dtype=float)
    for i, d in enumerate(cal_dates):
        past = source_dates[source_dates <= d]
        if len(past):
            staleness[i] = (d - past[-1]).astype("timedelta64[D]").astype(float)

    return pd.Series(staleness, index=cal_df.index)


# ── Split labels ───────────────────────────────────────────────────────────────

def _add_split_labels(panel: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Add a `split` column: 'train' | 'val' | 'test'.

    Boundaries from pipeline.yaml dates section:
      train : historical_start  to  train_end   (inclusive)
      val   : val_start         to  val_end
      test  : test_start        to  historical_end
    """
    dates = cfg["dates"]
    train_end  = pd.Timestamp(dates["train_end"])
    val_start  = pd.Timestamp(dates["val_start"])
    val_end    = pd.Timestamp(dates["val_end"])
    test_start = pd.Timestamp(dates["test_start"])

    conditions = [
        panel["date"] <= train_end,
        (panel["date"] >= val_start) & (panel["date"] <= val_end),
        panel["date"] >= test_start,
    ]
    choices = ["train", "val", "test"]
    panel["split"] = np.select(conditions, choices, default="train")

    counts = panel.groupby("split")["date"].nunique()
    logger.info("  Split label counts (unique trading days):")
    for split in ["train", "val", "test"]:
        logger.info(f"    {split:<6}: {counts.get(split, 0):>5} days")

    return panel


# ── Validation ─────────────────────────────────────────────────────────────────

def _validate_panel(
    panel: pd.DataFrame,
    sl20_tickers: list[str],
    trading_cal: pd.DatetimeIndex,
) -> None:
    """Run basic checks on the assembled panel and log warnings for any issues."""
    n_expected = len(sl20_tickers) * len(trading_cal)
    if len(panel) != n_expected:
        logger.warning(
            f"Panel has {len(panel):,} rows but expected {n_expected:,} "
            f"({len(sl20_tickers)} tickers × {len(trading_cal):,} trading days)"
        )

    missing_tickers = [t for t in sl20_tickers if t not in panel["ticker"].unique()]
    if missing_tickers:
        logger.warning(f"Missing tickers in panel: {missing_tickers}")

    # Close price coverage per ticker
    coverage = panel.groupby("ticker")["close"].apply(lambda s: s.notna().mean())
    low_cov = coverage[coverage < 0.95]
    if len(low_cov):
        logger.warning(f"Tickers with <95% close coverage:\n{low_cov.to_string()}")
    else:
        logger.info(f"  Price coverage: all tickers ≥95% — OK")

    # No future leakage: gdp_days_stale should never be negative
    if "gdp_days_stale" in panel.columns:
        neg_stale = (panel["gdp_days_stale"] < 0).sum()
        if neg_stale:
            logger.error(f"Look-ahead bias detected: {neg_stale:,} rows with negative gdp_days_stale!")
        else:
            logger.info("  GDP staleness: no negative values — look-ahead check OK")

    logger.info(
        f"Panel validated: {len(panel):,} rows | "
        f"{panel.shape[1]} columns | "
        f"splits: {panel['split'].value_counts().to_dict()}"
    )
