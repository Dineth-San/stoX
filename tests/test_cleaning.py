"""
test_cleaning.py — Phase 2 cleaning layer tests.

Run from ml/:
    pytest tests/test_cleaning.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ML_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ML_DIR / "src"))

from sl20_ml.utils.config import load_config

SL20 = load_config()["tickers"]["sl20"]
PRICES_PATH = ML_DIR / load_config()["paths"]["cleaned"]["prices"]
MARKET_PATH = ML_DIR / load_config()["paths"]["cleaned"]["market_context"]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def prices():
    if not PRICES_PATH.exists():
        pytest.skip(f"Prices file not found: {PRICES_PATH}")
    return pd.read_parquet(PRICES_PATH)


@pytest.fixture(scope="module")
def market():
    if not MARKET_PATH.exists():
        pytest.skip(f"Market context file not found: {MARKET_PATH}")
    return pd.read_parquet(MARKET_PATH)


# ── Price tests ───────────────────────────────────────────────────────────────

def test_all_sl20_tickers_present(prices):
    missing = [t for t in SL20 if t not in prices["ticker"].values]
    assert missing == [], f"Missing SL20 tickers: {missing}"


def test_no_duplicate_ticker_date(prices):
    dupes = prices.duplicated(subset=["ticker", "date"]).sum()
    assert dupes == 0, f"Found {dupes} duplicate (ticker, date) rows"


def test_close_price_positive(prices):
    bad = prices[prices["close"] <= 0]
    assert len(bad) == 0, f"Found {len(bad)} rows with close <= 0"


def test_date_range(prices):
    cfg = load_config()
    start = cfg["dates"]["historical_start"]
    assert prices["date"].min() <= pd.Timestamp(start) + pd.Timedelta(days=10), \
        f"Data starts too late: {prices['date'].min().date()}"
    assert prices["date"].max().year >= 2024, \
        f"Data ends too early: {prices['date'].max().date()}"


def test_all_years_present(prices):
    years = sorted(prices["year"].unique().tolist())
    expected = list(range(2011, 2026))
    assert years == expected, f"Missing years: {set(expected) - set(years)}"


def test_row_count_reasonable(prices):
    assert len(prices) > 800_000, f"Too few rows: {len(prices):,}"


def test_ohlc_violations_are_flagged(prices):
    """Any row violating OHLC consistency must be in ohlc_inconsistent=True."""
    assert "ohlc_inconsistent" in prices.columns, "ohlc_inconsistent column missing"
    clean = prices[~prices["ohlc_inconsistent"]]
    assert (clean["high"] >= clean["low"]).all(),   "Unflagged high < low violation"
    assert (clean["high"] >= clean["close"]).all(), "Unflagged high < close violation"
    assert (clean["low"]  <= clean["close"]).all(), "Unflagged low > close violation"


def test_volume_non_negative(prices):
    bad = prices[prices["volume"] < 0]
    assert len(bad) == 0, f"Found {len(bad)} rows with negative volume"


def test_sl20_minimum_trading_days(prices):
    cfg = load_config()
    min_days = cfg["cleaning"]["min_trading_days"]
    counts = prices[prices["ticker"].isin(SL20)].groupby("ticker")["date"].count()
    below = counts[counts < min_days]
    assert len(below) == 0, f"Tickers below {min_days} trading days:\n{below}"


def test_required_columns_present(prices):
    required = ["ticker", "date", "open", "high", "low", "close",
                "volume", "turnover", "trades", "year",
                "daily_return", "ohlc_inconsistent", "suspicious_move"]
    missing = [c for c in required if c not in prices.columns]
    assert missing == [], f"Missing columns: {missing}"


# ── Market context tests ──────────────────────────────────────────────────────

def test_market_no_duplicate_dates(market):
    dupes = market["date"].duplicated().sum()
    assert dupes == 0, f"Found {dupes} duplicate dates in market context"


def test_market_aspi_positive(market):
    assert (market["aspi"] > 0).all(), f"ASPI has non-positive values"


def test_market_sl20_coverage(market):
    pct = market["sl20_index"].notna().mean()
    assert pct >= 0.90, f"sl20_index coverage too low: {pct:.1%}"


def test_market_per_range(market):
    per = market["market_per"].dropna()
    assert per.between(1, 200).all(), \
        f"market_per out of range [1,200]: min={per.min():.1f}, max={per.max():.1f}"


def test_market_date_range(market):
    assert market["date"].min().year == 2011
    assert market["date"].max().year >= 2024


def test_price_market_date_overlap(prices, market):
    p_dates = set(prices["date"].dt.date.unique())
    m_dates = set(market["date"].dt.date.unique())
    overlap = len(p_dates & m_dates)
    assert overlap > 3400, f"Too few overlapping dates: {overlap}"
