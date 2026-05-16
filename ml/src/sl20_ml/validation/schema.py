"""
schema.py — Pandera schema for the Phase 4 feature panel.

Defines hard constraints on the most critical columns.  Extra columns (beyond
what's listed here) are allowed (strict=False) so the schema doesn't need
updating every time a new feature group is added.

Usage
-----
    from sl20_ml.validation.schema import build_feature_panel_schema
    schema = build_feature_panel_schema(sl20_tickers)
    schema.validate(panel, lazy=True)   # lazy=True collects all errors first
"""

from __future__ import annotations

import pandera.pandas as pa
from pandera.pandas import Column, Check, DataFrameSchema
import pandera.errors  # noqa: F401 — SchemaErrors lives here


def build_feature_panel_schema(sl20_tickers: list[str]) -> DataFrameSchema:
    """
    Build and return the Pandera schema for sl20_feature_panel.parquet.

    Parameters
    ----------
    sl20_tickers : list of 20 SL20 ticker symbols (from pipeline.yaml)

    Returns
    -------
    pa.DataFrameSchema — validate with schema.validate(df, lazy=True)
    """
    return DataFrameSchema(
        columns={
            # ── Identity ──────────────────────────────────────────────────────
            "date": Column(
                pa.DateTime,
                nullable=False,
                description="CSE trading date (no weekends, no holidays)",
            ),
            "ticker": Column(
                str,
                Check.isin(sl20_tickers),
                nullable=False,
                description="SL20 ticker symbol",
            ),
            "split": Column(
                str,
                Check.isin(["train", "val", "test"]),
                nullable=False,
                description="Time-based data split label",
            ),

            # ── Price columns ─────────────────────────────────────────────────
            "open": Column(
                float,
                Check.ge(0),
                nullable=True,
                description="Opening price (LKR) — NaN on non-trading days",
            ),
            "high": Column(
                float,
                Check.ge(0),
                nullable=True,
                description="Intraday high price (LKR)",
            ),
            "low": Column(
                float,
                Check.ge(0),
                nullable=True,
                description="Intraday low price (LKR)",
            ),
            "close": Column(
                float,
                Check.ge(0),
                nullable=True,
                description="Closing price (LKR)",
            ),
            "adj_close": Column(
                float,
                Check.ge(0),
                nullable=True,
                description="Backward-adjusted close (anchored to latest price)",
            ),
            "volume": Column(
                float,
                Check.ge(0),
                nullable=True,
                description="Shares traded",
            ),
            "daily_return": Column(
                float,
                Check.ge(-0.999),   # No upper cap: extreme +ve moves flagged by ohlc_inconsistent
                nullable=True,
                description="Simple daily return = (close - prev_close) / prev_close",
            ),

            # ── Market macro (date-level) ─────────────────────────────────────
            "aspi": Column(
                float,
                Check.gt(0),
                nullable=True,
                description="All Share Price Index (CSE)",
            ),
            "usd_lkr": Column(
                float,
                Check.gt(0),
                nullable=False,
                description="USD/LKR exchange rate (CBSL)",
            ),
            "policy_rate_mid": Column(
                float,
                Check.ge(0),
                nullable=False,
                description="CBSL policy rate midpoint = (SDF + SLF) / 2 (%)",
            ),
            "vix": Column(
                float,
                Check.gt(0),
                nullable=False,
                description="CBOE VIX volatility index (FRED)",
            ),
            "gdp_days_stale": Column(
                float,
                Check.ge(0),        # MUST be non-negative (look-ahead guard)
                nullable=True,
                description="Days since last annual GDP update (staleness indicator)",
            ),

            # ── Rolling returns ───────────────────────────────────────────────
            "ret_5d": Column(
                float,
                nullable=True,
                description="5-trading-day cumulative return",
            ),
            "ret_10d": Column(
                float,
                nullable=True,
                description="10-trading-day cumulative return",
            ),
            "ret_20d": Column(
                float,
                nullable=True,
                description="20-trading-day cumulative return (~1 month)",
            ),
            "ret_60d": Column(
                float,
                nullable=True,
                description="60-trading-day cumulative return (~1 quarter)",
            ),

            # ── Rolling volatility ────────────────────────────────────────────
            "vol_5d": Column(
                float,
                Check.ge(0),
                nullable=True,
                description="5-day rolling std of daily returns",
            ),
            "vol_20d": Column(
                float,
                Check.ge(0),
                nullable=True,
                description="20-day rolling std of daily returns (~1 month)",
            ),

            # ── Technical indicators ──────────────────────────────────────────
            "rsi_14": Column(
                float,
                Check.in_range(0, 100),
                nullable=True,
                description="RSI(14) — Wilder's Relative Strength Index",
            ),
            "macd": Column(
                float,
                nullable=True,
                description="MACD line = EMA(12) - EMA(26)",
            ),
            "macd_signal": Column(
                float,
                nullable=True,
                description="MACD signal line = EMA(9) of MACD",
            ),
            "macd_hist": Column(
                float,
                nullable=True,
                description="MACD histogram = MACD - signal",
            ),
            "bb_upper": Column(
                float,
                Check.ge(0),
                nullable=True,
                description="Bollinger Band upper = SMA(20) + 2σ",
            ),
            "bb_lower": Column(
                float,
                nullable=True,
                description="Bollinger Band lower = SMA(20) - 2σ (can be negative for high-vol assets)",
            ),
            "bb_pct": Column(
                float,
                nullable=True,
                description="%B = (close - lower) / (upper - lower); >1 above upper band",
            ),
            "atr_14": Column(
                float,
                Check.ge(0),
                nullable=True,
                description="ATR(14) — Average True Range using Wilder's EWM",
            ),
            "obv": Column(
                float,
                nullable=True,
                description="On-Balance Volume (cumulative signed volume)",
            ),

            # ── Cross-sectional ───────────────────────────────────────────────
            "xs_zscore_daily_return": Column(
                float,
                nullable=True,
                description="Daily cross-sectional z-score of daily_return across 20 tickers",
            ),
            "xs_rank_daily_return": Column(
                float,
                Check.in_range(0, 1, include_min=False),
                nullable=True,
                description="Daily percentile rank of daily_return (0→1]",
            ),

            # ── Calendar — dtype not enforced (int32/int64 both valid) ──────
            "day_of_week": Column(
                checks=Check.in_range(0, 4),
                nullable=False,
                description="Day of week: 0=Monday, 4=Friday",
            ),
            "month": Column(
                checks=Check.in_range(1, 12),
                nullable=False,
                description="Calendar month (1–12)",
            ),
            "quarter": Column(
                checks=Check.in_range(1, 4),
                nullable=False,
                description="Calendar quarter (1–4)",
            ),
            "is_month_end": Column(
                checks=Check.isin([0, 1]),
                nullable=False,
                description="1 if last calendar day of month, else 0",
            ),
            "trading_day_of_month": Column(
                checks=Check.ge(1),
                nullable=False,
                description="Ordinal trading day within the current calendar month",
            ),

            # ── Target ────────────────────────────────────────────────────────
            "target_next_close": Column(
                float,
                Check.ge(0),
                nullable=True,
                description="Next trading day's close price — the prediction target",
            ),
            "target_next_return": Column(
                float,
                Check.ge(-0.999),   # No upper cap; same data quality issue as daily_return
                nullable=True,
                description="(target_next_close / close) - 1",
            ),
        },
        coerce=False,
        strict=False,   # extra columns (sector indices, TRIs, etc.) are fine
    )
