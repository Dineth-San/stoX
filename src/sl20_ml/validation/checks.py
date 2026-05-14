"""
checks.py — Statistical and look-ahead bias checks for the feature panel.

Returns structured dicts / DataFrames so the results can be rendered to
markdown by report.py or consumed by automated CI gates.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Null-rate analysis ─────────────────────────────────────────────────────────

def compute_null_rates(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Return a DataFrame with null count and null pct for every column,
    sorted descending by null pct.
    """
    null_counts = panel.isna().sum()
    null_pct    = null_counts / len(panel)
    result = pd.DataFrame({
        "null_count": null_counts,
        "null_pct":   null_pct,
        "dtype":      panel.dtypes.astype(str),
    }).sort_values("null_pct", ascending=False)
    return result


# ── Distribution statistics ───────────────────────────────────────────────────

_STATS_COLS = [
    # Price
    "close", "adj_close", "daily_return",
    # Returns
    "ret_5d", "ret_10d", "ret_20d", "ret_60d",
    # Volatility
    "vol_5d", "vol_20d", "vol_60d",
    # Technical
    "rsi_14", "macd", "bb_pct", "bb_width", "atr_14", "volume_ratio_20d",
    # Price position
    "price_to_52w_high", "price_to_52w_low",
    # Macro
    "usd_lkr", "policy_rate_mid", "vix", "oil_wti", "gold",
    "gdp_growth_pct", "inflation_pct",
    # Cross-sectional
    "xs_zscore_daily_return", "xs_rank_daily_return",
    # Target
    "target_next_return",
]


def compute_feature_stats(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Compute descriptive statistics for key feature columns.

    Returns a DataFrame indexed by column name with columns:
    count, null_pct, mean, std, min, p5, p25, p50, p75, p95, max, skew
    """
    rows = []
    for col in _STATS_COLS:
        if col not in panel.columns:
            continue
        s = panel[col].dropna()
        if len(s) == 0:
            continue
        rows.append({
            "column":   col,
            "count":    len(s),
            "null_pct": panel[col].isna().mean(),
            "mean":     s.mean(),
            "std":      s.std(ddof=1),
            "min":      s.min(),
            "p5":       s.quantile(0.05),
            "p25":      s.quantile(0.25),
            "p50":      s.quantile(0.50),
            "p75":      s.quantile(0.75),
            "p95":      s.quantile(0.95),
            "max":      s.max(),
            "skew":     float(s.skew()),
        })
    return pd.DataFrame(rows).set_index("column")


# ── Coverage by ticker ────────────────────────────────────────────────────────

def compute_ticker_coverage(panel: pd.DataFrame) -> pd.DataFrame:
    """
    For each ticker: total rows, trading days (close not NaN), coverage pct,
    first date, last date.
    """
    rows = []
    for ticker, grp in panel.groupby("ticker"):
        rows.append({
            "ticker":        ticker,
            "total_rows":    len(grp),
            "trading_days":  grp["close"].notna().sum(),
            "coverage_pct":  grp["close"].notna().mean(),
            "first_date":    grp["date"].min(),
            "last_date":     grp["date"].max(),
            "ret_5d_null":   grp["ret_5d"].isna().mean(),
            "rsi_14_null":   grp["rsi_14"].isna().mean(),
        })
    return pd.DataFrame(rows).set_index("ticker").sort_values("coverage_pct")


# ── Coverage by split ─────────────────────────────────────────────────────────

def compute_split_summary(panel: pd.DataFrame) -> pd.DataFrame:
    """
    For each split: unique trading days, total rows, date range.
    """
    rows = []
    for split, grp in panel.groupby("split"):
        rows.append({
            "split":          split,
            "unique_days":    grp["date"].nunique(),
            "total_rows":     len(grp),
            "first_date":     grp["date"].min(),
            "last_date":      grp["date"].max(),
            "target_null_pct": grp["target_next_close"].isna().mean(),
        })
    df = pd.DataFrame(rows).set_index("split")
    return df.loc[["train", "val", "test"]]


# ── Look-ahead bias audit ──────────────────────────────────────────────────────

def run_lookahead_audit(
    panel: pd.DataFrame,
    cfg: dict,
) -> list[dict[str, Any]]:
    """
    Run a suite of look-ahead bias checks.

    Returns a list of result dicts:
      { "check": str, "status": "PASS" | "FAIL", "detail": str }
    """
    results: list[dict[str, Any]] = []

    def _record(check: str, passed: bool, detail: str = "") -> None:
        results.append({
            "check":  check,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
        })

    # ── 1. GDP staleness never negative ───────────────────────────────────────
    if "gdp_days_stale" in panel.columns:
        neg = (panel["gdp_days_stale"] < 0).sum()
        _record(
            "gdp_days_stale >= 0",
            neg == 0,
            f"{neg:,} rows with negative gdp_days_stale" if neg else "OK",
        )

    # ── 2. 2011 GDP is null (12-month lag means 2011 data only arrives Jan 2012) ─
    if "gdp_growth_pct" in panel.columns:
        y2011 = panel[pd.to_datetime(panel["date"]).dt.year == 2011]
        all_null = y2011["gdp_growth_pct"].isna().all()
        _record(
            "gdp_growth_pct null for 2011",
            all_null,
            "OK" if all_null else f"{y2011['gdp_growth_pct'].notna().sum()} non-null rows in 2011",
        )

    # ── 3. target_next_close[t] == close[t+1] per ticker ──────────────────────
    mismatch_total = 0
    for ticker, grp in panel.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        expected  = grp["close"].shift(-1)
        actual    = grp["target_next_close"]
        both_valid = expected.notna() & actual.notna()
        if both_valid.sum() == 0:
            continue
        diff = (actual[both_valid] - expected[both_valid]).abs()
        mismatch_total += (diff > 1e-6).sum()
    _record(
        "target_next_close == close.shift(-1)",
        mismatch_total == 0,
        "OK" if mismatch_total == 0 else f"{mismatch_total:,} mismatches",
    )

    # ── 4. No rolling feature uses future close ────────────────────────────────
    # Spot-check: for a sample ticker, verify ret_5d[t] = close[t] / close[t-5] - 1
    sample_ticker = panel["ticker"].iloc[0]
    grp = panel[panel["ticker"] == sample_ticker].sort_values("date").reset_index(drop=True)
    valid_idx = grp.index[grp["ret_5d"].notna() & grp["close"].notna()]
    if len(valid_idx) >= 10:
        check_idx = valid_idx[5:15]
        bad_count = 0
        for i in check_idx:
            if i < 5:
                continue
            expected_ret = grp.loc[i, "close"] / grp.loc[i - 5, "close"] - 1
            actual_ret   = grp.loc[i, "ret_5d"]
            if np.isnan(expected_ret) or np.isnan(actual_ret):
                continue
            if abs(actual_ret - expected_ret) > 1e-8:
                bad_count += 1
        _record(
            f"ret_5d no look-ahead ({sample_ticker})",
            bad_count == 0,
            f"{bad_count} mismatches in spot check" if bad_count else "OK",
        )

    # ── 5. Split boundaries ────────────────────────────────────────────────────
    dates = cfg["dates"]
    train_max  = panel[panel["split"] == "train"]["date"].max()
    val_min    = panel[panel["split"] == "val"]["date"].min()
    test_min   = panel[panel["split"] == "test"]["date"].min()

    _record(
        "train_end boundary",
        train_max <= pd.Timestamp(dates["train_end"]),
        f"train_max={train_max.date()} ≤ {dates['train_end']}",
    )
    _record(
        "val_start boundary",
        val_min >= pd.Timestamp(dates["val_start"]),
        f"val_min={val_min.date()} ≥ {dates['val_start']}",
    )
    _record(
        "test_start boundary",
        test_min >= pd.Timestamp(dates["test_start"]),
        f"test_min={test_min.date()} ≥ {dates['test_start']}",
    )

    # ── 6. CBSL columns fully filled (no NaN) ─────────────────────────────────
    for col in ["usd_lkr", "policy_rate_mid"]:
        n_null = panel[col].isna().sum()
        _record(
            f"{col} fully populated",
            n_null == 0,
            "OK" if n_null == 0 else f"{n_null:,} NaN values",
        )

    # ── 7. FRED columns fully filled ──────────────────────────────────────────
    for col in ["oil_wti", "sp500", "vix", "gold"]:
        n_null = panel[col].isna().sum()
        _record(
            f"{col} fully populated",
            n_null == 0,
            "OK" if n_null == 0 else f"{n_null:,} NaN values",
        )

    return results
