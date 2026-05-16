"""
test_validation.py — Phase 5 validation tests.

Tests that:
  1. The Pandera schema passes on the live feature panel
  2. All look-ahead audit checks pass
  3. The validation report and data dictionary files exist and are non-empty
  4. The feature stats parquet has the expected rows and columns
  5. No new feature columns are undocumented

Run from ml/:
    pytest tests/test_validation.py -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

ML_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ML_DIR / "src"))

from sl20_ml.utils.config import load_config

cfg          = load_config()
PANEL_PATH   = ML_DIR / cfg["paths"]["features"]["panel"]
REPORT_PATH  = ML_DIR / cfg["paths"]["features"]["validation"]
DICT_PATH    = ML_DIR / cfg["paths"]["features"]["dictionary"]
STATS_PATH   = ML_DIR / cfg["paths"]["features"]["stats"]


@pytest.fixture(scope="module")
def panel():
    if not PANEL_PATH.exists():
        pytest.skip(f"Feature panel not found: {PANEL_PATH}")
    return pd.read_parquet(PANEL_PATH)


@pytest.fixture(scope="module")
def feature_stats():
    if not STATS_PATH.exists():
        pytest.skip(f"Feature stats not found: {STATS_PATH}")
    return pd.read_parquet(STATS_PATH)


# ── Schema validation ─────────────────────────────────────────────────────────

def test_pandera_schema_passes(panel):
    """Pandera schema must validate without errors."""
    from pandera.errors import SchemaErrors as PanderaSchemaErrors
    from sl20_ml.validation.schema import build_feature_panel_schema

    schema = build_feature_panel_schema(cfg["tickers"]["sl20"])
    try:
        schema.validate(panel, lazy=True)
    except PanderaSchemaErrors as exc:
        errors = exc.failure_cases
        # Format a concise error message
        top5 = errors.head(5)[["column", "check", "failure_case"]].to_string()
        pytest.fail(
            f"Pandera schema failed with {len(errors)} error(s):\n{top5}"
        )


# ── Look-ahead audit ──────────────────────────────────────────────────────────

def test_lookahead_audit_all_pass(panel):
    """Every look-ahead bias check must return PASS."""
    from sl20_ml.validation.checks import run_lookahead_audit

    results = run_lookahead_audit(panel, cfg)
    failures = [r for r in results if r["status"] != "PASS"]
    if failures:
        details = "\n".join(f"  FAIL: {r['check']} — {r['detail']}" for r in failures)
        pytest.fail(f"Look-ahead audit: {len(failures)} failure(s):\n{details}")


# ── Null rate expectations ────────────────────────────────────────────────────

def test_cbsl_zero_nulls(panel):
    """CBSL columns must have zero nulls (fully forward-filled)."""
    for col in ["usd_lkr", "sdf_rate", "slf_rate", "policy_rate_mid"]:
        n = panel[col].isna().sum()
        assert n == 0, f"{col}: {n:,} unexpected NaN values"


def test_fred_zero_nulls(panel):
    """FRED global macro columns must have zero nulls."""
    for col in ["oil_wti", "sp500", "vix", "us_10y_yield", "dxy", "gold"]:
        n = panel[col].isna().sum()
        assert n == 0, f"{col}: {n:,} unexpected NaN values"


def test_calendar_zero_nulls(panel):
    """Calendar features are derived from the date — must never be NaN."""
    for col in ["day_of_week", "month", "quarter", "is_month_end",
                "is_quarter_end", "trading_day_of_month"]:
        n = panel[col].isna().sum()
        assert n == 0, f"{col}: {n:,} unexpected NaN values"


def test_ret_5d_null_rate_reasonable(panel):
    """ret_5d null rate should be under 15% (warm-up + non-trading days)."""
    null_pct = panel["ret_5d"].isna().mean()
    assert null_pct < 0.15, f"ret_5d null rate {null_pct:.1%} seems too high"


def test_rsi_null_rate_reasonable(panel):
    """RSI null rate should be under 10% (14-day warm-up + non-trading days)."""
    null_pct = panel["rsi_14"].isna().mean()
    assert null_pct < 0.10, f"rsi_14 null rate {null_pct:.1%} seems too high"


# ── Feature stats parquet ─────────────────────────────────────────────────────

def test_feature_stats_file_exists():
    assert STATS_PATH.exists(), f"Feature stats file missing: {STATS_PATH}"


def test_feature_stats_has_key_columns(feature_stats):
    required_index = ["ret_5d", "ret_20d", "vol_20d", "rsi_14", "macd", "atr_14"]
    missing = [c for c in required_index if c not in feature_stats.index]
    assert missing == [], f"Missing feature stats rows: {missing}"


def test_feature_stats_columns(feature_stats):
    expected_cols = ["count", "null_pct", "mean", "std", "min", "p5", "p50", "p95", "max", "skew"]
    missing = [c for c in expected_cols if c not in feature_stats.columns]
    assert missing == [], f"Missing stat columns: {missing}"


def test_rsi_mean_plausible(feature_stats):
    """Across the full panel, mean RSI should be somewhere near 50."""
    rsi_mean = feature_stats.loc["rsi_14", "mean"]
    assert 30 <= rsi_mean <= 70, f"Mean RSI = {rsi_mean:.2f} — implausible"


def test_vol_20d_positive_mean(feature_stats):
    assert feature_stats.loc["vol_20d", "mean"] > 0


# ── Output file existence ─────────────────────────────────────────────────────

def test_validation_report_exists():
    assert REPORT_PATH.exists(), f"Validation report missing: {REPORT_PATH}"


def test_validation_report_non_empty():
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert len(content) > 1000, "Validation report is suspiciously short"
    assert "## 2. Look-Ahead Bias Audit" in content
    assert "PASS" in content


def test_data_dictionary_exists():
    assert DICT_PATH.exists(), f"Data dictionary missing: {DICT_PATH}"


def test_data_dictionary_covers_all_columns(panel):
    """Every column in the feature panel must appear in the data dictionary."""
    content = DICT_PATH.read_text(encoding="utf-8")
    missing = [col for col in panel.columns if f"`{col}`" not in content]
    assert missing == [], (
        f"{len(missing)} columns missing from data dictionary: {missing[:10]}"
    )
