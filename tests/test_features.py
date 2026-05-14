"""
test_features.py — Phase 4 feature engineering tests.

Run from ml/:
    pytest tests/test_features.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ML_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ML_DIR / "src"))

from sl20_ml.utils.config import load_config

cfg          = load_config()
PANEL_PATH   = ML_DIR / cfg["paths"]["features"]["panel"]
ALIGNED_PATH = ML_DIR / cfg["paths"]["aligned"]["panel"]


@pytest.fixture(scope="module")
def panel():
    if not PANEL_PATH.exists():
        pytest.skip(f"Feature panel not found: {PANEL_PATH}")
    return pd.read_parquet(PANEL_PATH)


@pytest.fixture(scope="module")
def aligned():
    if not ALIGNED_PATH.exists():
        pytest.skip(f"Aligned panel not found: {ALIGNED_PATH}")
    return pd.read_parquet(ALIGNED_PATH)


# ── Shape & completeness ───────────────────────────────────────────────────────

def test_row_count_unchanged(panel, aligned):
    """Feature engineering must not add or drop rows."""
    assert len(panel) == len(aligned), (
        f"Row count changed: aligned={len(aligned):,}, features={len(panel):,}"
    )


def test_required_feature_columns(panel):
    required = [
        # Rolling returns
        "ret_5d", "ret_10d", "ret_20d", "ret_60d",
        # Rolling volatility
        "vol_5d", "vol_10d", "vol_20d", "vol_60d",
        # Technical
        "rsi_14", "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_lower", "bb_pct", "bb_width",
        "atr_14", "obv", "obv_ma_20", "volume_ratio_20d",
        "price_to_52w_high", "price_to_52w_low",
        # Cross-sectional
        "xs_zscore_daily_return", "xs_rank_daily_return",
        "xs_zscore_ret_20d", "xs_rank_ret_20d",
        "xs_zscore_rsi_14", "xs_rank_rsi_14",
        # Calendar
        "day_of_week", "month", "quarter",
        "is_month_end", "is_quarter_end", "trading_day_of_month",
        # Target
        "target_next_close", "target_next_return",
    ]
    missing = [c for c in required if c not in panel.columns]
    assert missing == [], f"Missing feature columns: {missing}"


def test_aligned_columns_preserved(panel, aligned):
    """All columns from the aligned panel must still be present."""
    missing = [c for c in aligned.columns if c not in panel.columns]
    assert missing == [], f"Columns dropped during feature engineering: {missing}"


# ── Rolling returns ────────────────────────────────────────────────────────────

def test_ret_5d_nan_at_start(panel):
    """First 4 rows of each ticker should have NaN ret_5d (not enough history)."""
    for ticker, grp in panel.groupby("ticker"):
        grp = grp.sort_values("date")
        n_nan = grp["ret_5d"].iloc[:4].isna().sum()
        assert n_nan == 4, (
            f"Ticker {ticker}: expected 4 NaN at start of ret_5d, got {n_nan}"
        )


def test_ret_20d_nan_at_start(panel):
    """First 19 rows of each ticker should have NaN ret_20d."""
    for ticker, grp in panel.groupby("ticker"):
        grp = grp.sort_values("date")
        n_nan = grp["ret_20d"].iloc[:19].isna().sum()
        assert n_nan == 19, (
            f"Ticker {ticker}: expected 19 NaN at start of ret_20d, got {n_nan}"
        )


def test_ret_values_plausible(panel):
    """
    5-day return should not exceed ±200% when the entire 5-day rolling window
    is free of price quality flags.  Rows where any of the past 5 days had
    ohlc_inconsistent=True are excluded — those contaminate the window.
    """
    def _clean_window_mask(grp: pd.DataFrame) -> pd.Series:
        """True where the 5-day rolling window contains no flagged rows."""
        flag = grp["ohlc_inconsistent"].fillna(False).astype(int)
        any_flagged = flag.rolling(5, min_periods=1).max().astype(bool)
        return ~any_flagged

    clean_mask = panel.groupby("ticker", group_keys=False).apply(
        lambda g: _clean_window_mask(g.sort_values("date"))
    )
    valid = panel.loc[clean_mask, "ret_5d"].dropna()
    extreme = (valid.abs() > 2.0).sum()
    assert extreme == 0, f"{extreme:,} clean-window rows with |ret_5d| > 200%"


def test_vol_positive(panel):
    """Rolling volatility must be non-negative."""
    for w in [5, 10, 20, 60]:
        col = f"vol_{w}d"
        neg = (panel[col].dropna() < 0).sum()
        assert neg == 0, f"{neg:,} negative values in {col}"


# ── Technical indicators ────────────────────────────────────────────────────────

def test_rsi_bounds(panel):
    """RSI must be in [0, 100]."""
    valid = panel["rsi_14"].dropna()
    assert (valid >= 0).all() and (valid <= 100).all(), (
        f"RSI out of [0, 100]: min={valid.min():.2f}, max={valid.max():.2f}"
    )


def test_rsi_nan_at_start(panel):
    """Each ticker should have NaN RSI for at least its first 13 rows."""
    for ticker, grp in panel.groupby("ticker"):
        grp = grp.sort_values("date")
        n_nan = grp["rsi_14"].iloc[:13].isna().sum()
        assert n_nan == 13, (
            f"Ticker {ticker}: expected ≥13 NaN at start of rsi_14, got {n_nan}"
        )


def test_macd_hist_equals_macd_minus_signal(panel):
    """MACD histogram must equal macd - macd_signal (within float tolerance)."""
    valid = panel[["macd", "macd_signal", "macd_hist"]].dropna()
    expected = valid["macd"] - valid["macd_signal"]
    max_diff = (valid["macd_hist"] - expected).abs().max()
    assert max_diff < 1e-8, f"MACD histogram mismatch: max diff = {max_diff:.2e}"


def test_bollinger_upper_above_lower(panel):
    """Bollinger upper band must always be >= lower band."""
    valid = panel[["bb_upper", "bb_lower"]].dropna()
    bad = (valid["bb_upper"] < valid["bb_lower"]).sum()
    assert bad == 0, f"{bad:,} rows where bb_upper < bb_lower"


def test_atr_positive(panel):
    """ATR must be non-negative."""
    valid = panel["atr_14"].dropna()
    neg = (valid < 0).sum()
    assert neg == 0, f"{neg:,} negative ATR values"


def test_volume_ratio_plausible(panel):
    """Volume ratio vs 20d MA should almost always be in [0, 50]."""
    valid = panel["volume_ratio_20d"].dropna()
    extreme = (valid > 100).sum()
    pct = extreme / len(valid)
    assert pct < 0.001, f"Too many extreme volume ratios (>100×): {extreme:,} rows ({pct:.2%})"


# ── Cross-sectional features ──────────────────────────────────────────────────

def test_xs_zscore_mean_near_zero(panel):
    """Daily cross-sectional z-scores should average near 0 on each trading day."""
    col = "xs_zscore_daily_return"
    daily_means = panel.groupby("date")[col].mean().dropna()
    max_abs_mean = daily_means.abs().max()
    assert max_abs_mean < 1e-6, (
        f"Cross-sectional z-score daily mean too large: {max_abs_mean:.2e}"
    )


def test_xs_rank_in_01(panel):
    """Percentile rank must be in (0, 1]."""
    col = "xs_rank_daily_return"
    valid = panel[col].dropna()
    assert (valid > 0).all() and (valid <= 1.0).all(), (
        f"xs_rank_daily_return out of (0, 1]: min={valid.min():.4f}, max={valid.max():.4f}"
    )


# ── Calendar features ────────────────────────────────────────────────────────

def test_day_of_week_range(panel):
    """day_of_week must be 0–4 (Mon–Fri). No weekends."""
    bad = panel[panel["day_of_week"] > 4]
    assert len(bad) == 0, f"{len(bad):,} rows with day_of_week > 4 (weekend)"


def test_month_range(panel):
    assert panel["month"].between(1, 12).all()


def test_quarter_range(panel):
    assert panel["quarter"].between(1, 4).all()


def test_trading_day_of_month_positive(panel):
    assert (panel["trading_day_of_month"] >= 1).all()


# ── Target variable ───────────────────────────────────────────────────────────

def test_target_null_only_last_day(panel):
    """
    target_next_close is NaN when:
      (a) it is the last trading day for the ticker — no 'tomorrow', OR
      (b) the ticker didn't trade the next day (close[t+1] is NaN).

    The important invariant: if close[t] is NOT NaN and close[t+1] is NOT NaN,
    then target_next_close[t] must NOT be NaN.
    """
    for ticker, grp in panel.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        # Find rows where close is valid AND next-day close is also valid
        close_valid      = grp["close"].notna()
        next_close_valid = grp["close"].shift(-1).notna()
        should_have_target = close_valid & next_close_valid
        target_null = grp["target_next_close"].isna()
        # There should be no row where both conditions hold but target is null
        bad = should_have_target & target_null
        assert bad.sum() == 0, (
            f"Ticker {ticker}: {bad.sum()} rows where next close is available "
            f"but target_next_close is NaN"
        )


def test_target_equals_next_close(panel):
    """
    For each ticker, target_next_close[t] should equal close[t+1].
    Verify on a sample of tickers.
    """
    sample_tickers = panel["ticker"].unique()[:5]
    for ticker in sample_tickers:
        grp = panel[panel["ticker"] == ticker].sort_values("date").reset_index(drop=True)
        close_shifted = grp["close"].shift(-1)
        target        = grp["target_next_close"]
        # Compare where both are non-null
        both_valid = close_shifted.notna() & target.notna()
        if both_valid.sum() == 0:
            continue
        max_diff = (target[both_valid] - close_shifted[both_valid]).abs().max()
        assert max_diff < 1e-6, (
            f"Ticker {ticker}: target_next_close != close.shift(-1), max diff = {max_diff}"
        )


def test_target_return_consistent(panel):
    """target_next_return must equal (target_next_close / close) - 1."""
    valid = panel[["close", "target_next_close", "target_next_return"]].dropna()
    expected = valid["target_next_close"] / valid["close"] - 1
    max_diff = (valid["target_next_return"] - expected).abs().max()
    assert max_diff < 1e-8, f"target_next_return inconsistency: max diff = {max_diff:.2e}"


def test_target_return_plausible(panel):
    """Overnight return should not exceed ±100% for the bulk of the data."""
    valid = panel["target_next_return"].dropna()
    extreme = (valid.abs() > 1.0).sum()
    pct = extreme / len(valid)
    assert pct < 0.001, (
        f"Too many extreme target returns (>±100%): {extreme:,} rows ({pct:.2%})"
    )


# ── No look-ahead in rolling features ────────────────────────────────────────

def test_ret_5d_no_future_leakage(panel):
    """
    ret_5d at time t should not depend on prices after t.
    Cross-check: ret_5d[t] == (close[t] / close[t-5]) - 1 for a sample.
    """
    sample_tickers = panel["ticker"].unique()[:3]
    for ticker in sample_tickers:
        grp = panel[panel["ticker"] == ticker].sort_values("date").reset_index(drop=True)
        idx = grp.index[grp["ret_5d"].notna()]
        if len(idx) < 10:
            continue
        check_idx = idx[5:15]  # a few rows in the middle
        for i in check_idx:
            if i < 5:
                continue
            expected = grp.loc[i, "close"] / grp.loc[i - 5, "close"] - 1
            actual   = grp.loc[i, "ret_5d"]
            if np.isnan(expected) or np.isnan(actual):
                continue
            assert abs(actual - expected) < 1e-8, (
                f"Ticker {ticker} row {i}: ret_5d={actual:.6f} but "
                f"(close[t]/close[t-5])-1={expected:.6f}"
            )
