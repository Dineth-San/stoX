"""
engineer.py — Phase 4 feature engineering.

Takes the aligned daily panel (sl20_daily_panel.parquet) and produces
the ML-ready feature panel (sl20_feature_panel.parquet).

Feature groups
--------------
  Price / returns    : rolling cumulative returns & volatility (5, 10, 20, 60d)
  Technical          : RSI-14, MACD(12/26/9), Bollinger Bands(20, 2σ),
                       ATR-14, OBV + OBV-MA-20
  Cross-sectional    : daily z-score and percentile rank across 20 tickers
                       for: daily_return, ret_5d, ret_20d, vol_20d, rsi_14, volume
  Calendar           : day_of_week, month, quarter, is_month_end, is_quarter_end,
                       trading_day_of_month
  Target             : target_next_close, target_next_return

Look-ahead rules
----------------
  All rolling/technical features use only t and earlier data.  The target
  (next-day close) is intentionally forward-looking — that's the label.
  Rows where the target is NaN (last trading day per ticker) are flagged
  but kept so the panel schema stays consistent; they must be dropped at
  training time.
"""

import logging
import warnings

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Low-level indicator helpers ────────────────────────────────────────────────

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI using exponential smoothing (alpha = 1/period)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return (100.0 - (100.0 / (1.0 + rs))).rename("rsi")


def _macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, signal line, histogram."""
    ema_fast   = close.ewm(span=fast,   adjust=False).mean()
    ema_slow   = close.ewm(span=slow,   adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist        = macd_line - signal_line
    return macd_line, signal_line, hist


def _bollinger(
    close: pd.Series,
    period: int = 20,
    n_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands: upper, lower, %B, bandwidth."""
    sma   = close.rolling(period).mean()
    std   = close.rolling(period).std(ddof=1)
    upper = sma + n_std * std
    lower = sma - n_std * std
    denom = (upper - lower).replace(0.0, np.nan)
    pct_b = (close - lower) / denom
    width = denom / sma.replace(0.0, np.nan)
    return upper, lower, pct_b, width


def _atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average True Range using Wilder's smoothing."""
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume — cumulative signed volume."""
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


# ── Per-ticker feature computation ────────────────────────────────────────────

def _engineer_one_ticker(grp: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Apply all per-ticker features to a single ticker's time-sorted DataFrame.
    Called via groupby(...).apply(...).

    Parameters
    ----------
    grp : sorted slice for one ticker (date ascending)
    cfg : full pipeline config dict

    Returns
    -------
    grp with new feature columns appended.
    """
    feat  = cfg["features"]
    tech  = feat["technical"]
    toggles = cfg.get("feature_toggles", {})

    close  = grp["close"]
    high   = grp["high"]
    low    = grp["low"]
    volume = grp["volume"].fillna(0)

    # ── Rolling returns & volatility ─────────────────────────────────────────
    if toggles.get("price_returns", True):
        for w in feat["return_windows"]:
            grp[f"ret_{w}d"]  = close.pct_change(w, fill_method=None)
            grp[f"vol_{w}d"]  = grp["daily_return"].rolling(w).std(ddof=1)

        # Price relative to recent rolling highs/lows
        grp["price_to_52w_high"] = close / close.rolling(252).max()
        grp["price_to_52w_low"]  = close / close.rolling(252).min().replace(0, np.nan)

    # ── Technical indicators ─────────────────────────────────────────────────
    if toggles.get("technical", True):
        grp["rsi_14"] = _rsi(close, tech["rsi_period"])

        macd_line, signal_line, hist = _macd(
            close, tech["macd_fast"], tech["macd_slow"], tech["macd_signal"]
        )
        grp["macd"]        = macd_line
        grp["macd_signal"] = signal_line
        grp["macd_hist"]   = hist

        bb_upper, bb_lower, bb_pct, bb_width = _bollinger(
            close, tech["bollinger_period"], tech["bollinger_std"]
        )
        grp["bb_upper"] = bb_upper
        grp["bb_lower"] = bb_lower
        grp["bb_pct"]   = bb_pct
        grp["bb_width"] = bb_width

        grp["atr_14"] = _atr(high, low, close, tech["atr_period"])

        obv_raw = _obv(close, volume)
        grp["obv"]      = obv_raw
        grp["obv_ma_20"] = obv_raw.rolling(tech["obv_ma_period"]).mean()

        # Volume relative to its own 20-day average (volume surge indicator)
        vol_ma20 = volume.rolling(20).mean().replace(0, np.nan)
        grp["volume_ratio_20d"] = volume / vol_ma20

    # ── Target variable ───────────────────────────────────────────────────────
    grp["target_next_close"]  = close.shift(-1)
    grp["target_next_return"] = grp["target_next_close"] / close - 1

    return grp


# ── Cross-sectional features ──────────────────────────────────────────────────

_XS_COLS = [
    "daily_return",
    "ret_5d",
    "ret_10d",
    "ret_20d",
    "vol_20d",
    "rsi_14",
    "volume",
]


def _add_cross_sectional(panel: pd.DataFrame, toggles: dict) -> pd.DataFrame:
    """
    Add daily z-scores and percentile ranks across all 20 tickers.

    These capture relative positioning: e.g. 'ticker X had the highest 5-day
    return in the SL20 today'.
    """
    if not toggles.get("cross_sectional", True):
        return panel

    cols = [c for c in _XS_COLS if c in panel.columns]

    def _zscore(x: pd.Series) -> pd.Series:
        s = x.std(ddof=1)
        m = x.mean()
        return (x - m) / s if s > 0 else pd.Series(0.0, index=x.index)

    for col in cols:
        panel[f"xs_zscore_{col}"] = (
            panel.groupby("date")[col].transform(_zscore)
        )
        panel[f"xs_rank_{col}"] = (
            panel.groupby("date")[col].transform(lambda x: x.rank(pct=True))
        )

    logger.info(f"  Cross-sectional features added: {len(cols)} base columns × 2 = {len(cols) * 2} new columns")
    return panel


# ── Calendar features ─────────────────────────────────────────────────────────

def _add_calendar(panel: pd.DataFrame, toggles: dict) -> pd.DataFrame:
    """
    Add temporal calendar features.

    These help the model learn seasonality and recurrence patterns
    (e.g. month-end rebalancing, quarterly earnings effect).
    """
    if not toggles.get("calendar", True):
        return panel

    dt = pd.to_datetime(panel["date"])
    panel["day_of_week"]   = dt.dt.dayofweek          # 0 = Monday, 4 = Friday
    panel["month"]         = dt.dt.month
    panel["quarter"]       = dt.dt.quarter
    panel["is_month_end"]  = dt.dt.is_month_end.astype(int)
    panel["is_quarter_end"] = dt.dt.is_quarter_end.astype(int)

    # Trading day of month: rank of this date within its month's trading days
    panel["_ym"] = dt.dt.to_period("M")
    panel["trading_day_of_month"] = (
        panel.groupby(["ticker", "_ym"])["date"]
        .transform(lambda x: x.rank(method="first").astype(int))
    )
    panel = panel.drop(columns=["_ym"])

    logger.info("  Calendar features added: day_of_week, month, quarter, is_month_end, is_quarter_end, trading_day_of_month")
    return panel


# ── Staleness / data-quality flags ───────────────────────────────────────────

def _add_staleness_flags(panel: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Flag rows where forward-filled macro data might be stale.
    These let the model down-weight periods with potentially outdated features.
    """
    thresholds = cfg["features"].get("staleness", {})
    macro_max  = thresholds.get("macro_max_days", 35)

    if "gdp_days_stale" in panel.columns:
        panel["gdp_stale_flag"] = (panel["gdp_days_stale"] > 365 + 30).astype(int)

    logger.info("  Staleness flags added")
    return panel


# ── Main orchestrator ─────────────────────────────────────────────────────────

def build_feature_panel(
    aligned_panel: pd.DataFrame,
    cfg: dict,
) -> pd.DataFrame:
    """
    Build the full ML feature panel from the aligned daily panel.

    Parameters
    ----------
    aligned_panel : output of Phase 3 (sl20_daily_panel.parquet)
    cfg           : full pipeline config dict

    Returns
    -------
    pd.DataFrame  — one row per (ticker, date), all features added.
    """
    toggles = cfg.get("feature_toggles", {})

    n_tickers = aligned_panel["ticker"].nunique()
    n_days    = aligned_panel["date"].nunique()
    logger.info(
        f"Engineering features: {n_tickers} tickers × {n_days:,} trading days "
        f"= {len(aligned_panel):,} rows"
    )

    # Sort once; all per-ticker ops assume this order
    panel = aligned_panel.sort_values(["ticker", "date"]).reset_index(drop=True)

    # ── Step 1: Per-ticker features (returns, technical, target) ──────────────
    logger.info("  [1/4] Computing per-ticker features ...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        panel = panel.groupby("ticker", group_keys=False).apply(
            _engineer_one_ticker, cfg=cfg
        )
    panel = panel.reset_index(drop=True)

    # ── Step 2: Cross-sectional features ─────────────────────────────────────
    logger.info("  [2/4] Computing cross-sectional features ...")
    panel = _add_cross_sectional(panel, toggles)

    # ── Step 3: Calendar features ─────────────────────────────────────────────
    logger.info("  [3/4] Adding calendar features ...")
    panel = _add_calendar(panel, toggles)

    # ── Step 4: Staleness flags ───────────────────────────────────────────────
    logger.info("  [4/4] Adding staleness flags ...")
    panel = _add_staleness_flags(panel, cfg)

    # ── Re-sort and report ────────────────────────────────────────────────────
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)

    n_feat_cols   = panel.shape[1]
    n_target_null = panel["target_next_close"].isna().sum()
    n_total       = len(panel)
    logger.info(
        f"  Feature panel complete: {n_total:,} rows × {n_feat_cols} columns"
    )
    logger.info(
        f"  Rows with null target (last day per ticker): "
        f"{n_target_null} ({n_target_null/n_total:.2%})"
    )

    return panel
