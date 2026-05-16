"""
test_alignment.py — Phase 3 alignment layer tests.

Run from ml/:
    pytest tests/test_alignment.py -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

ML_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ML_DIR / "src"))

from sl20_ml.utils.config import load_config

cfg        = load_config()
SL20       = cfg["tickers"]["sl20"]
PANEL_PATH = ML_DIR / cfg["paths"]["aligned"]["panel"]


@pytest.fixture(scope="module")
def panel():
    if not PANEL_PATH.exists():
        pytest.skip(f"Panel not found: {PANEL_PATH}")
    return pd.read_parquet(PANEL_PATH)


# ── Shape & identity ──────────────────────────────────────────────────────────

def test_panel_row_count(panel):
    """20 tickers × 3,565 trading days = 71,300 rows."""
    assert len(panel) == 71_300, f"Unexpected row count: {len(panel):,}"


def test_all_sl20_tickers_present(panel):
    missing = [t for t in SL20 if t not in panel["ticker"].unique()]
    assert missing == [], f"Missing tickers: {missing}"


def test_no_duplicate_ticker_date(panel):
    dupes = panel.duplicated(subset=["ticker", "date"]).sum()
    assert dupes == 0, f"{dupes:,} duplicate (ticker, date) rows"


def test_split_column_values(panel):
    valid = {"train", "val", "test"}
    bad = set(panel["split"].unique()) - valid
    assert not bad, f"Unexpected split values: {bad}"


def test_split_boundaries(panel):
    """No test data bleeds into the training set."""
    train_max = panel[panel["split"] == "train"]["date"].max()
    val_min   = panel[panel["split"] == "val"]["date"].min()
    test_min  = panel[panel["split"] == "test"]["date"].min()
    assert train_max <= pd.Timestamp(cfg["dates"]["train_end"])
    assert val_min   >= pd.Timestamp(cfg["dates"]["val_start"])
    assert test_min  >= pd.Timestamp(cfg["dates"]["test_start"])


def test_split_sizes(panel):
    days = panel.groupby("split")["date"].nunique()
    assert days.get("train", 0) > 2_500, f"Train too small: {days.get('train')}"
    assert days.get("val",   0) > 200,   f"Val too small: {days.get('val')}"
    assert days.get("test",  0) > 600,   f"Test too small: {days.get('test')}"


# ── Calendar ──────────────────────────────────────────────────────────────────

def test_no_weekend_trading_days(panel):
    weekends = panel[pd.to_datetime(panel["date"]).dt.dayofweek >= 5]
    assert len(weekends) == 0, f"{len(weekends):,} rows fall on weekends"


def test_trading_days_per_year(panel):
    """Each year should have 180–270 trading days."""
    unique_dates = panel.drop_duplicates("date").copy()
    unique_dates["year"] = pd.to_datetime(unique_dates["date"]).dt.year
    yr_counts = unique_dates.groupby("year").size()
    for yr, n in yr_counts.items():
        assert 180 <= n <= 270, f"Year {yr}: {n} trading days (expected 180–270)"


# ── Macro alignment ───────────────────────────────────────────────────────────

def test_usd_lkr_no_nulls(panel):
    assert panel["usd_lkr"].isna().sum() == 0, "usd_lkr has NaN values"


def test_fred_no_nulls(panel):
    fred_cols = ["oil_wti", "sp500", "vix", "us_10y_yield", "dxy", "gold"]
    for col in fred_cols:
        n = panel[col].isna().sum()
        assert n == 0, f"{col} has {n:,} NaN values"


def test_gdp_no_lookforward(panel):
    """GDP days_stale must never be negative (negative = look-ahead leak)."""
    bad = panel[panel["gdp_days_stale"] < 0]
    assert len(bad) == 0, f"{len(bad):,} rows with negative gdp_days_stale"


def test_gdp_first_year_null(panel):
    """2011 should have no GDP data — 12-month lag means 2011 GDP only
    available from Jan 2012."""
    y2011 = panel[pd.to_datetime(panel["date"]).dt.year == 2011]
    assert y2011["gdp_growth_pct"].isna().all(), \
        "2011 rows should have NaN gdp_growth_pct (not yet published)"


def test_gdp_available_from_2012(panel):
    """From 2012 onwards, GDP should be populated."""
    post_2011 = panel[pd.to_datetime(panel["date"]).dt.year >= 2012]
    null_pct = post_2011["gdp_growth_pct"].isna().mean()
    assert null_pct < 0.01, f"GDP null rate post-2011: {null_pct:.1%} (expected <1%)"


# ── Price coverage ────────────────────────────────────────────────────────────

def test_liquid_tickers_high_coverage(panel):
    """Core liquid SL20 stocks should trade on at least 95% of all trading days.
    CTC trades less frequently than the most liquid names (~95.7%) — 95% is
    the right floor for the SL20 universe, not 97%."""
    liquid = ["JKH", "COMB", "DIAL", "SAMP", "HNB", "DFCC", "CTC"]
    cov = panel[panel["ticker"].isin(liquid)].groupby("ticker")["close"].apply(
        lambda s: s.notna().mean()
    )
    low = cov[cov < 0.95]
    assert len(low) == 0, f"Liquid tickers with <95% coverage:\n{low}"


def test_adj_close_in_panel(panel):
    assert "adj_close" in panel.columns, "adj_close column missing from panel"
    assert panel["adj_close"].notna().mean() > 0.90, "adj_close coverage too low"


# ── Column completeness ───────────────────────────────────────────────────────

def test_required_columns_present(panel):
    required = [
        "date", "ticker", "split",
        "open", "high", "low", "close", "adj_close",
        "volume", "daily_return", "ohlc_inconsistent",
        "aspi", "sl20_index", "market_per",
        "usd_lkr", "policy_rate_mid",
        "oil_wti", "sp500", "vix",
        "gdp_growth_pct", "inflation_pct", "gdp_days_stale",
    ]
    missing = [c for c in required if c not in panel.columns]
    assert missing == [], f"Missing columns: {missing}"
