"""
engineer.py — Phase 4 feature engineering.

Takes the aligned daily panel (sl20_daily_panel.parquet) and produces
the ML-ready feature panel (sl20_feature_panel.parquet).

Feature groups
--------------
  Price / returns    : rolling cumulative returns & volatility (5, 10, 20, 60d)
  Technical          : RSI-14, MACD(12/26/9), Bollinger Bands(20, 2σ),
                       ATR-14, OBV + OBV-MA-20
  Uncertainty        : vol_regime (current vol / long-run vol),
                       daily_range_pct (intraday spread / close)
  Cross-sectional    : daily z-score and percentile rank across 20 tickers
                       for: daily_return, ret_5d, ret_20d, vol_20d, rsi_14, volume
                       market_breadth (fraction of tickers advancing)
  Macro derived      : usd_lkr_5d_change (5-day FX momentum),
                       foreign_net_flow_30d (CSE monthly foreign net flow, Bn LKR)
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

    # ── Uncertainty / regime features ────────────────────────────────────────
    # vol_regime: ratio of short-term to long-run volatility.
    # > 1.0 means the market is currently MORE volatile than its historical norm.
    # This teaches the model when to widen its prediction bands.
    vol_252 = grp["daily_return"].rolling(252, min_periods=60).std()
    grp["vol_regime"] = grp["vol_20d"] / vol_252.replace(0, np.nan)
    # Fill early NaNs (first ~252 rows per ticker before vol_252 is valid) with
    # 1.0 = "neutral/normal regime". pytorch-forecasting would otherwise impute
    # NaN as 0, which signals "near-zero volatility" and corrupts early training.
    grp["vol_regime"] = grp["vol_regime"].fillna(1.0)

    # daily_range_pct: intraday high-low spread as fraction of close.
    # High values indicate uncertainty / price discovery difficulty.
    grp["daily_range_pct"] = (high - low) / close.replace(0, np.nan)
    # Forward-fill any NaNs (rare: missing OHLC days), then fill remaining with
    # a sensible default (0.01 = 1% intraday range, typical for CSE).
    grp["daily_range_pct"] = grp["daily_range_pct"].ffill().fillna(0.01)

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

    # market_breadth: fraction of SL20 tickers with positive return on each day.
    # When most stocks fall simultaneously the model should widen its intervals.
    if "daily_return" in panel.columns:
        panel["market_breadth"] = panel.groupby("date")["daily_return"].transform(
            lambda x: (x > 0).mean()
        )

    logger.info(f"  Cross-sectional features added: {len(cols)} base columns × 2 = {len(cols) * 2} new columns + market_breadth")
    return panel


# ── Derived macro features ────────────────────────────────────────────────────

def _load_foreign_flow(cfg: dict) -> pd.DataFrame:
    """
    Parse CSE '20Foreign Activity - Monthly.xlsx' and return a daily DataFrame
    with one column: foreign_net_flow_30d (Total Foreign net purchases, Bn LKR).

    Layout of the file:
      Row 0  : dates (monthly, starting 1992-01)
      Row 15 : "Total Foreign" net purchases/(sales) in Rs.

    The monthly value is forward-filled to daily and scaled to billions of LKR
    for numeric stability.  The dataset normalisation step in dataset.py clips
    extremes to ±10σ, so no further scaling is needed.
    """
    from pathlib import Path
    try:
        from sl20_ml.utils.config import get_ml_dir
        ml_dir = get_ml_dir()
    except Exception:
        ml_dir = Path(__file__).parent.parent.parent.parent  # fallback: ml/

    raw_dir  = ml_dir / cfg["paths"]["raw"]["cse"]
    filename = cfg.get("cse_files", {}).get("foreign_activity", "20Foreign Activity - Monthly.xlsx")
    path = raw_dir / filename

    if not path.exists():
        logger.warning(f"  Foreign activity file not found: {path} — skipping feature")
        return pd.DataFrame(columns=["date", "foreign_net_flow_30d"])

    try:
        raw = pd.read_excel(path, sheet_name=0, header=None)
        # Row 0 = header with dates in columns 1..end
        dates = pd.to_datetime(raw.iloc[0, 1:], errors="coerce")
        # Row 15 = "Total Foreign" net flow
        values = pd.to_numeric(raw.iloc[15, 1:], errors="coerce")

        flow = pd.DataFrame({
            "date": dates.values,
            "foreign_net_flow_30d": values.values / 1e9,  # scale to Bn LKR
        })
        flow = flow[flow["date"].notna()].sort_values("date").reset_index(drop=True)

        # Expand monthly → daily by forward-filling onto a daily date range
        if len(flow) == 0:
            return pd.DataFrame(columns=["date", "foreign_net_flow_30d"])

        daily_idx = pd.date_range(flow["date"].min(), flow["date"].max(), freq="D")
        daily = pd.DataFrame({"date": daily_idx})
        daily = daily.merge(flow, on="date", how="left")
        daily["foreign_net_flow_30d"] = daily["foreign_net_flow_30d"].ffill()

        logger.info(
            f"  Foreign flow loaded: {len(flow)} monthly obs "
            f"({flow['date'].min().date()} – {flow['date'].max().date()}), "
            f"expanded to {len(daily):,} daily rows"
        )
        return daily[["date", "foreign_net_flow_30d"]]

    except Exception as exc:
        logger.warning(f"  Could not load foreign flow data: {exc} — skipping feature")
        return pd.DataFrame(columns=["date", "foreign_net_flow_30d"])


def _add_derived_macro(panel: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Add macro-derived features that are the same for all tickers on a given day:
      - usd_lkr_5d_change : 5-day percentage change in USD/LKR rate
      - foreign_net_flow_30d : CSE monthly net foreign flow (Bn LKR), daily fwd-fill
    """
    # usd_lkr_5d_change — 5-day FX momentum signal
    if "usd_lkr" in panel.columns:
        # Compute on unique dates (same for all tickers) then merge back
        fx = (
            panel[["date", "usd_lkr"]]
            .drop_duplicates("date")
            .sort_values("date")
            .reset_index(drop=True)
        )
        fx["usd_lkr_5d_change"] = fx["usd_lkr"].pct_change(5)
        panel = panel.merge(fx[["date", "usd_lkr_5d_change"]], on="date", how="left")
        logger.info("  usd_lkr_5d_change added")

    # foreign_net_flow_30d — monthly CSE foreign investor net flow
    flow_df = _load_foreign_flow(cfg)
    if len(flow_df) > 0:
        flow_df["date"] = pd.to_datetime(flow_df["date"])
        panel["date"] = pd.to_datetime(panel["date"])
        panel = panel.merge(flow_df, on="date", how="left")
        # Forward-fill any gaps at the tail (most recent months not yet in file)
        panel["foreign_net_flow_30d"] = panel["foreign_net_flow_30d"].ffill()
        null_pct = panel["foreign_net_flow_30d"].isna().mean()
        logger.info(f"  foreign_net_flow_30d added (null rate: {null_pct:.1%})")

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
    logger.info("  [2/5] Computing cross-sectional features ...")
    panel = _add_cross_sectional(panel, toggles)

    # ── Step 3: Derived macro features ───────────────────────────────────────
    logger.info("  [3/5] Adding derived macro features ...")
    panel = _add_derived_macro(panel, cfg)

    # ── Step 4: Calendar features ─────────────────────────────────────────────
    logger.info("  [4/5] Adding calendar features ...")
    panel = _add_calendar(panel, toggles)

    # ── Step 5: Staleness flags ───────────────────────────────────────────────
    logger.info("  [5/5] Adding staleness flags ...")
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
