"""
report.py — Generate human-readable validation report and data dictionary.

Outputs
-------
  data/features/validation_report.md   — full validation summary
  data/features/data_dictionary.md     — column reference for all 130 columns
  data/features/feature_stats.parquet  — machine-readable per-column stats
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


# ── Data dictionary ────────────────────────────────────────────────────────────

# Maps column → (source_group, description)
_COLUMN_REGISTRY: dict[str, tuple[str, str]] = {
    # Identity
    "date":              ("Identity",   "CSE trading date"),
    "ticker":            ("Identity",   "SL20 ticker symbol"),
    "split":             ("Identity",   "Time-based split: train / val / test"),
    # Raw prices
    "open":              ("Prices",     "Opening price (LKR)"),
    "high":              ("Prices",     "Intraday high price (LKR)"),
    "low":               ("Prices",     "Intraday low price (LKR)"),
    "close":             ("Prices",     "Closing price (LKR)"),
    "adj_close":         ("Prices",     "Backward-adjusted close (anchored to latest price)"),
    "volume":            ("Prices",     "Shares traded"),
    "turnover":          ("Prices",     "Turnover value (LKR mn)"),
    "trades":            ("Prices",     "Number of trades"),
    "daily_return":      ("Prices",     "(close - prev_close) / prev_close"),
    "ohlc_inconsistent": ("Prices",     "Flag: OHLC data inconsistency detected"),
    "suspicious_move":   ("Prices",     "Flag: |daily_return| > 50% threshold"),
    # Market context
    "aspi":              ("Market",     "All Share Price Index"),
    "mpi":               ("Market",     "Milanka Price Index"),
    "sl20_index":        ("Market",     "S&P SL20 Index level"),
    "astri":             ("Market",     "All Share Total Return Index"),
    "mtri":              ("Market",     "Milanka Total Return Index"),
    "sl20_tri":          ("Market",     "S&P SL20 Total Return Index"),
    "market_per":        ("Market",     "Market price-to-earnings ratio"),
    "market_pbv":        ("Market",     "Market price-to-book-value ratio"),
    "market_dy":         ("Market",     "Market dividend yield (%)"),
    "equity_turnover_mn": ("Market",    "Total equity market turnover (LKR mn)"),
    "shares_traded_000": ("Market",     "Total shares traded (thousands)"),
    "trades_equity":     ("Market",     "Total equity trade count"),
    "market_cap_mn":     ("Market",     "Total market capitalisation (LKR mn)"),
    # Sector indices
    "sector_bfi":        ("Market",     "Banking Finance & Insurance sector index"),
    "sector_bft":        ("Market",     "Beverages Food & Tobacco sector index"),
    "sector_cp":         ("Market",     "Chemicals & Pharmaceuticals sector index"),
    "sector_ce":         ("Market",     "Construction & Engineering sector index"),
    "sector_div":        ("Market",     "Diversified Holdings sector index"),
    "sector_ft":         ("Market",     "Footwear & Textiles sector index"),
    "sector_hlt":        ("Market",     "Healthcare sector index"),
    "sector_ht":         ("Market",     "Hotels & Travel sector index"),
    "sector_inv":        ("Market",     "Investment Trusts sector index"),
    "sector_it":         ("Market",     "Information Technology sector index"),
    "sector_lp":         ("Market",     "Land & Property sector index"),
    "sector_mfg":        ("Market",     "Manufacturing sector index"),
    "sector_mtr":        ("Market",     "Motors sector index"),
    "sector_oil":        ("Market",     "Oil Palms sector index"),
    "sector_plt":        ("Market",     "Plantations sector index"),
    "sector_pe":         ("Market",     "Power & Energy sector index"),
    "sector_srv":        ("Market",     "Services sector index"),
    "sector_ss":         ("Market",     "Store Supplies sector index"),
    "sector_tel":        ("Market",     "Telecommunication sector index"),
    "sector_trd":        ("Market",     "Trading sector index"),
    # TRI sector indices
    "tri_bfi":           ("Market",     "BFI sector Total Return Index"),
    "tri_bft":           ("Market",     "BFT sector Total Return Index"),
    "tri_cp":            ("Market",     "CP sector Total Return Index"),
    "tri_ce":            ("Market",     "CE sector Total Return Index"),
    "tri_div":           ("Market",     "Diversified sector Total Return Index"),
    "tri_ft":            ("Market",     "FT sector Total Return Index"),
    "tri_hlt":           ("Market",     "Healthcare sector Total Return Index"),
    "tri_ht":            ("Market",     "Hotels & Travel sector Total Return Index"),
    "tri_inv":           ("Market",     "Investment Trusts sector Total Return Index"),
    "tri_it":            ("Market",     "IT sector Total Return Index"),
    "tri_lp":            ("Market",     "Land & Property sector Total Return Index"),
    "tri_mfg":           ("Market",     "Manufacturing sector Total Return Index"),
    "tri_mtr":           ("Market",     "Motors sector Total Return Index"),
    "tri_oil":           ("Market",     "Oil Palms sector Total Return Index"),
    "tri_plt":           ("Market",     "Plantations sector Total Return Index"),
    "tri_pe":            ("Market",     "Power & Energy sector Total Return Index"),
    "tri_srv":           ("Market",     "Services sector Total Return Index"),
    "tri_ss":            ("Market",     "Store Supplies sector Total Return Index"),
    "tri_tel":           ("Market",     "Telecommunication sector Total Return Index"),
    "tri_trd":           ("Market",     "Trading sector Total Return Index"),
    # Debt market
    "debt_corp_000":     ("Market",     "Corporate debt traded (thousands LKR)"),
    "debt_govt_000":     ("Market",     "Government debt traded (thousands LKR)"),
    "funds_turnover_000":("Market",     "Unit trusts turnover (thousands LKR)"),
    # CBSL
    "usd_lkr":           ("CBSL",       "USD/LKR exchange rate (daily, ffilled weekends)"),
    "sdf_rate":          ("CBSL",       "Standing Deposit Facility rate (%)"),
    "slf_rate":          ("CBSL",       "Standing Lending Facility rate (%)"),
    "policy_rate_mid":   ("CBSL",       "Policy rate midpoint = (SDF + SLF) / 2 (%)"),
    # FRED global macro
    "oil_wti":           ("FRED",       "WTI crude oil price (USD/barrel)"),
    "sp500":             ("FRED",       "S&P 500 index level"),
    "vix":               ("FRED",       "CBOE VIX volatility index"),
    "us_10y_yield":      ("FRED",       "US 10-year Treasury yield (%)"),
    "dxy":               ("FRED",       "USD Dollar Index (DXY)"),
    "gold":              ("FRED",       "Gold spot price (USD/troy oz)"),
    # GDP / WDI (annual, 12-month lag)
    "gdp_growth_pct":    ("GDP/WDI",    "Sri Lanka real GDP growth rate (% annual, World Bank)"),
    "gdp_constant_usd":  ("GDP/WDI",    "Sri Lanka real GDP constant 2015 USD (World Bank)"),
    "inflation_pct":     ("GDP/WDI",    "CPI inflation rate (% annual, World Bank)"),
    "unemployment_pct":  ("GDP/WDI",    "Unemployment rate (% of labour force, World Bank)"),
    "gdp_days_stale":    ("GDP/WDI",    "Calendar days since last annual GDP update (look-ahead guard)"),
    # Split
    # (split already in Identity)
    # Rolling returns
    "ret_5d":            ("Features",   "5-trading-day cumulative return = close[t]/close[t-5]-1"),
    "ret_10d":           ("Features",   "10-day cumulative return"),
    "ret_20d":           ("Features",   "20-day cumulative return (~1 month)"),
    "ret_60d":           ("Features",   "60-day cumulative return (~1 quarter)"),
    # Rolling volatility
    "vol_5d":            ("Features",   "5-day rolling std of daily_return"),
    "vol_10d":           ("Features",   "10-day rolling std of daily_return"),
    "vol_20d":           ("Features",   "20-day rolling std of daily_return"),
    "vol_60d":           ("Features",   "60-day rolling std of daily_return"),
    # Price position
    "price_to_52w_high": ("Features",   "close / 252-day rolling max close (0→1)"),
    "price_to_52w_low":  ("Features",   "close / 252-day rolling min close (≥1)"),
    # Technical
    "rsi_14":            ("Features",   "RSI(14) — Wilder's Relative Strength Index [0, 100]"),
    "macd":              ("Features",   "MACD line = EMA(12) - EMA(26)"),
    "macd_signal":       ("Features",   "MACD signal line = EMA(9) of MACD line"),
    "macd_hist":         ("Features",   "MACD histogram = MACD - signal"),
    "bb_upper":          ("Features",   "Bollinger Band upper = SMA(20) + 2σ"),
    "bb_lower":          ("Features",   "Bollinger Band lower = SMA(20) - 2σ"),
    "bb_pct":            ("Features",   "%B = (close - bb_lower) / (bb_upper - bb_lower)"),
    "bb_width":          ("Features",   "Bandwidth = (bb_upper - bb_lower) / SMA(20)"),
    "atr_14":            ("Features",   "ATR(14) using Wilder's EWM smoothing"),
    "obv":               ("Features",   "On-Balance Volume (cumulative signed volume)"),
    "obv_ma_20":         ("Features",   "20-day SMA of OBV"),
    "volume_ratio_20d":  ("Features",   "volume / 20-day MA of volume (surge indicator)"),
    # Cross-sectional
    "xs_zscore_daily_return":  ("Features", "Cross-sectional z-score of daily_return (across 20 tickers, per day)"),
    "xs_rank_daily_return":    ("Features", "Cross-sectional percentile rank of daily_return (0→1]"),
    "xs_zscore_ret_5d":        ("Features", "Cross-sectional z-score of ret_5d"),
    "xs_rank_ret_5d":          ("Features", "Cross-sectional percentile rank of ret_5d (0→1]"),
    "xs_zscore_ret_10d":       ("Features", "Cross-sectional z-score of ret_10d"),
    "xs_rank_ret_10d":         ("Features", "Cross-sectional percentile rank of ret_10d (0→1]"),
    "xs_zscore_ret_20d":       ("Features", "Cross-sectional z-score of ret_20d"),
    "xs_rank_ret_20d":         ("Features", "Cross-sectional percentile rank of ret_20d (0→1]"),
    "xs_zscore_vol_20d":       ("Features", "Cross-sectional z-score of vol_20d"),
    "xs_rank_vol_20d":         ("Features", "Cross-sectional percentile rank of vol_20d (0→1]"),
    "xs_zscore_rsi_14":        ("Features", "Cross-sectional z-score of rsi_14"),
    "xs_rank_rsi_14":          ("Features", "Cross-sectional percentile rank of rsi_14 (0→1]"),
    "xs_zscore_volume":        ("Features", "Cross-sectional z-score of volume"),
    "xs_rank_volume":          ("Features", "Cross-sectional percentile rank of volume (0→1]"),
    # Calendar
    "day_of_week":             ("Calendar", "Day of week: 0=Monday, 4=Friday"),
    "month":                   ("Calendar", "Calendar month (1–12)"),
    "quarter":                 ("Calendar", "Calendar quarter (1–4)"),
    "is_month_end":            ("Calendar", "1 if last calendar day of month, else 0"),
    "is_quarter_end":          ("Calendar", "1 if last calendar day of quarter, else 0"),
    "trading_day_of_month":    ("Calendar", "Ordinal position among trading days within the month"),
    # Staleness / quality
    "gdp_stale_flag":          ("Quality",  "1 if gdp_days_stale > 395 days (> 1 year + 1 month)"),
    # Target
    "target_next_close":       ("Target",   "Next trading day's close price (the prediction target)"),
    "target_next_return":      ("Target",   "(target_next_close / close) - 1"),
}


def build_data_dictionary(panel: pd.DataFrame) -> str:
    """Generate the data dictionary as a Markdown string."""
    lines = [
        "# stoX — Feature Panel Data Dictionary",
        "",
        f"**Panel:** `sl20_feature_panel.parquet`  ",
        f"**Shape:** {len(panel):,} rows × {panel.shape[1]} columns  ",
        f"**Date range:** {panel['date'].min().date()} → {panel['date'].max().date()}  ",
        f"**Tickers:** {panel['ticker'].nunique()} SL20 stocks  ",
        "",
        "Columns are grouped by source.  "
        "`Nullable` = Y means the column contains NaN for non-trading days or "
        "warm-up periods at the start of each ticker's history.",
        "",
    ]

    # Group columns by source
    groups: dict[str, list[str]] = {}
    for col, (group, _) in _COLUMN_REGISTRY.items():
        groups.setdefault(group, []).append(col)

    group_order = ["Identity", "Prices", "Market", "CBSL", "FRED", "GDP/WDI",
                   "Features", "Calendar", "Quality", "Target"]

    for group in group_order:
        if group not in groups:
            continue
        lines.append(f"## {group}")
        lines.append("")
        lines.append("| Column | Type | Nullable | Description |")
        lines.append("|--------|------|----------|-------------|")
        for col in groups[group]:
            if col not in panel.columns:
                continue
            dtype    = str(panel[col].dtype)
            nullable = "Y" if panel[col].isna().any() else "N"
            _, desc  = _COLUMN_REGISTRY[col]
            lines.append(f"| `{col}` | {dtype} | {nullable} | {desc} |")
        lines.append("")

    # Any columns in the panel but not in the registry
    unregistered = [c for c in panel.columns if c not in _COLUMN_REGISTRY]
    if unregistered:
        lines.append("## Other")
        lines.append("")
        lines.append("| Column | Type | Nullable |")
        lines.append("|--------|------|----------|")
        for col in unregistered:
            dtype    = str(panel[col].dtype)
            nullable = "Y" if panel[col].isna().any() else "N"
            lines.append(f"| `{col}` | {dtype} | {nullable} |")
        lines.append("")

    return "\n".join(lines)


# ── Validation report ──────────────────────────────────────────────────────────

def build_validation_report(
    panel: pd.DataFrame,
    null_rates: pd.DataFrame,
    feature_stats: pd.DataFrame,
    ticker_coverage: pd.DataFrame,
    split_summary: pd.DataFrame,
    lookahead_results: list[dict],
    schema_errors: list[str],
) -> str:
    """Render all validation results as a single Markdown document."""
    n_pass = sum(1 for r in lookahead_results if r["status"] == "PASS")
    n_fail = sum(1 for r in lookahead_results if r["status"] == "FAIL")
    schema_ok = len(schema_errors) == 0

    lines = [
        "# stoX — Feature Panel Validation Report",
        "",
        f"**Panel:** `sl20_feature_panel.parquet`  ",
        f"**Rows:** {len(panel):,}  ",
        f"**Columns:** {panel.shape[1]}  ",
        f"**Memory:** {panel.memory_usage(deep=True).sum() / 1_048_576:.1f} MB  ",
        f"**Date range:** {panel['date'].min().date()} → {panel['date'].max().date()}  ",
        "",
        "---",
        "",
    ]

    # ── 1. Schema validation ────────────────────────────────────────────────
    lines += [
        "## 1. Schema Validation (Pandera)",
        "",
        f"**Status:** {'✅ PASS — no schema errors' if schema_ok else f'❌ FAIL — {len(schema_errors)} errors'}",
        "",
    ]
    if schema_errors:
        lines.append("```")
        lines.extend(schema_errors[:20])
        if len(schema_errors) > 20:
            lines.append(f"... and {len(schema_errors) - 20} more")
        lines.append("```")
        lines.append("")

    # ── 2. Look-ahead audit ─────────────────────────────────────────────────
    lines += [
        "## 2. Look-Ahead Bias Audit",
        "",
        f"**{n_pass}/{n_pass + n_fail} checks passed**",
        "",
        "| Check | Status | Detail |",
        "|-------|--------|--------|",
    ]
    for r in lookahead_results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        lines.append(f"| {r['check']} | {icon} {r['status']} | {r['detail']} |")
    lines.append("")

    # ── 3. Split summary ────────────────────────────────────────────────────
    lines += [
        "## 3. Data Split Summary",
        "",
        "| Split | Trading Days | Rows | Date Range | Target Null% |",
        "|-------|-------------|------|------------|-------------|",
    ]
    for split, row in split_summary.iterrows():
        lines.append(
            f"| {split} | {row['unique_days']:,} | {row['total_rows']:,} | "
            f"{row['first_date'].date()} → {row['last_date'].date()} | "
            f"{row['target_null_pct']:.1%} |"
        )
    lines.append("")

    # ── 4. Ticker coverage ──────────────────────────────────────────────────
    lines += [
        "## 4. Coverage by Ticker",
        "",
        "| Ticker | Trading Days | Coverage | First Date | Last Date |",
        "|--------|------------|----------|------------|-----------|",
    ]
    for ticker, row in ticker_coverage.sort_values("ticker").iterrows():
        cov_icon = "⚠️" if row["coverage_pct"] < 0.90 else ""
        lines.append(
            f"| {ticker} | {int(row['trading_days']):,} | "
            f"{row['coverage_pct']:.1%} {cov_icon} | "
            f"{row['first_date'].date()} | {row['last_date'].date()} |"
        )
    lines.append("")

    # ── 5. Null rates (top 25 highest) ─────────────────────────────────────
    lines += [
        "## 5. Null Rates (Top 25 by null%)",
        "",
        "| Column | Null Count | Null % | dtype |",
        "|--------|-----------|--------|-------|",
    ]
    for col, row in null_rates.head(25).iterrows():
        if row["null_pct"] == 0:
            break
        lines.append(
            f"| `{col}` | {int(row['null_count']):,} | "
            f"{row['null_pct']:.1%} | {row['dtype']} |"
        )
    lines.append("")

    # ── 6. Feature distributions ────────────────────────────────────────────
    lines += [
        "## 6. Key Feature Distributions",
        "",
        "| Feature | Count | Null% | Mean | Std | P5 | P50 | P95 | Skew |",
        "|---------|-------|-------|------|-----|-----|-----|-----|------|",
    ]
    for col, row in feature_stats.iterrows():
        lines.append(
            f"| `{col}` | {int(row['count']):,} | {row['null_pct']:.1%} | "
            f"{row['mean']:.4f} | {row['std']:.4f} | "
            f"{row['p5']:.4f} | {row['p50']:.4f} | {row['p95']:.4f} | "
            f"{row['skew']:.2f} |"
        )
    lines.append("")

    lines += [
        "---",
        "",
        "_Generated by `build_validation.py`_",
    ]

    return "\n".join(lines)


# ── Top-level orchestrator ─────────────────────────────────────────────────────

def run_validation(
    panel: pd.DataFrame,
    cfg: dict,
    schema_errors: list[str],
) -> tuple[str, str, pd.DataFrame]:
    """
    Run all checks and build both output documents.

    Returns
    -------
    (validation_report_md, data_dictionary_md, feature_stats_df)
    """
    from sl20_ml.validation.checks import (
        compute_null_rates,
        compute_feature_stats,
        compute_ticker_coverage,
        compute_split_summary,
        run_lookahead_audit,
    )

    logger.info("  Computing null rates ...")
    null_rates = compute_null_rates(panel)

    logger.info("  Computing feature statistics ...")
    feature_stats = compute_feature_stats(panel)

    logger.info("  Computing ticker coverage ...")
    ticker_cov = compute_ticker_coverage(panel)

    logger.info("  Computing split summary ...")
    split_sum = compute_split_summary(panel)

    logger.info("  Running look-ahead audit ...")
    lookahead = run_lookahead_audit(panel, cfg)

    n_pass = sum(1 for r in lookahead if r["status"] == "PASS")
    n_fail = sum(1 for r in lookahead if r["status"] == "FAIL")
    if n_fail:
        logger.warning(f"  Look-ahead audit: {n_fail} FAIL(s) detected!")
        for r in lookahead:
            if r["status"] == "FAIL":
                logger.warning(f"    FAIL: {r['check']} — {r['detail']}")
    else:
        logger.info(f"  Look-ahead audit: {n_pass}/{n_pass} PASS")

    validation_md = build_validation_report(
        panel, null_rates, feature_stats, ticker_cov, split_sum, lookahead, schema_errors
    )
    dictionary_md = build_data_dictionary(panel)

    return validation_md, dictionary_md, feature_stats
