"""
dataset.py — Prepare the feature panel for TFT training.

Transforms sl20_feature_panel.parquet into TimeSeriesDataSet objects
ready for pytorch-forecasting.

Key transforms applied here
---------------------------
1. Filter to rows where the ticker actually traded (close not NaN) AND
   the target (next-day close) exists.
2. Assign monotonically increasing time_idx per ticker (TFT requirement).
3. Compute log_target = log(target_next_close / close) — stationary target.
4. Add cyclic calendar encodings (sin/cos) for smooth periodicity.
5. Forward-fill any residual NaN in continuous feature columns, strictly
   within each ticker's chronological order (no look-ahead).
6. Clip extreme values to ±10 std to prevent outlier-driven instability.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
from pytorch_forecasting import TimeSeriesDataSet
from pytorch_forecasting.data import GroupNormalizer

logger = logging.getLogger(__name__)

# ── Feature column definitions ─────────────────────────────────────────────────

# Calendar features that are always known in advance (past AND future)
TIME_VARYING_KNOWN_REALS = [
    "time_idx",
    "dow_sin", "dow_cos",        # cyclic day-of-week
    "month_sin", "month_cos",    # cyclic month
    "is_month_end",
    "is_quarter_end",
    "trading_day_of_month",
]

# Features only known up to prediction time (prices, technicals, macro)
TIME_VARYING_UNKNOWN_REALS = [
    # Price & returns
    "log_close",          # log-normalised close (stationarity)
    "daily_return",
    "ret_5d", "ret_10d", "ret_20d", "ret_60d",
    # Volatility
    "vol_5d", "vol_20d", "vol_60d",
    # Technical
    "rsi_14", "macd", "macd_hist", "bb_pct", "bb_width",
    "atr_14", "obv_ma_20", "volume_ratio_20d",
    # Price position
    "price_to_52w_high",
    # Cross-sectional
    "xs_zscore_daily_return", "xs_rank_ret_20d", "xs_zscore_rsi_14",
    # Macro — CBSL
    "usd_lkr", "policy_rate_mid",
    # Macro — FRED
    "vix", "oil_wti", "sp500", "gold", "gdp_growth_pct", "inflation_pct",
    # Market
    "aspi", "sl20_index", "market_per",
]

STATIC_CATEGORICALS = ["ticker"]


# ── Main data preparation ──────────────────────────────────────────────────────

def prepare_tft_dataframe(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Transform the feature panel into a TFT-ready DataFrame.

    Parameters
    ----------
    panel : sl20_feature_panel.parquet, loaded as-is

    Returns
    -------
    pd.DataFrame with extra columns: time_idx, log_target, log_close,
    dow_sin, dow_cos, month_sin, month_cos
    """
    df = panel.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    # ── 1. Keep only rows where the ticker traded AND next-day target exists ──
    before = len(df)
    df = df[df["close"].notna() & df["target_next_close"].notna()].copy()
    logger.info(
        f"  Kept {len(df):,} / {before:,} rows "
        f"(dropped {before - len(df):,} non-trading / terminal rows)"
    )

    # ── 2. time_idx — monotonic integer per ticker ────────────────────────────
    df["time_idx"] = df.groupby("ticker").cumcount()

    # ── 3. Log-return target ──────────────────────────────────────────────────
    df["log_target"] = np.log(df["target_next_close"] / df["close"])

    # ── 4. Log-normalised close (detrended price level) ───────────────────────
    df["log_close"] = np.log(df["close"])

    # ── 5. Cyclic calendar encodings ──────────────────────────────────────────
    df["dow_sin"]   = np.sin(2 * np.pi * df["day_of_week"] / 5)
    df["dow_cos"]   = np.cos(2 * np.pi * df["day_of_week"] / 5)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    # ── 6. Forward-fill residual NaN in continuous features ───────────────────
    all_continuous = TIME_VARYING_KNOWN_REALS + TIME_VARYING_UNKNOWN_REALS
    cols_to_fill = [c for c in all_continuous if c in df.columns and df[c].isna().any()]
    if cols_to_fill:
        df[cols_to_fill] = (
            df.groupby("ticker")[cols_to_fill]
            .transform(lambda x: x.ffill())
        )
        # Any remaining NaN at the very start of a ticker's history → 0
        df[cols_to_fill] = df[cols_to_fill].fillna(0.0)
        logger.info(
            f"  Forward-filled {len(cols_to_fill)} columns "
            f"(remaining NaN set to 0)"
        )

    # ── 7. Clip extremes: cap at ±10 std per column (outlier guard) ───────────
    float_cols = [
        c for c in TIME_VARYING_UNKNOWN_REALS
        if c in df.columns and df[c].dtype == float
    ]
    for col in float_cols:
        μ, σ = df[col].mean(), df[col].std()
        if σ > 0:
            df[col] = df[col].clip(μ - 10 * σ, μ + 10 * σ)

    logger.info(
        f"  TFT dataframe ready: {len(df):,} rows | "
        f"{df['ticker'].nunique()} tickers | "
        f"time_idx range: 0–{df['time_idx'].max()}"
    )
    return df


def build_tft_datasets(
    df: pd.DataFrame,
    cfg: dict,
) -> tuple[TimeSeriesDataSet, TimeSeriesDataSet, TimeSeriesDataSet]:
    """
    Build train, val, test TimeSeriesDataSet objects.

    Normalisation is fit on training data only (via GroupNormalizer);
    val/test datasets inherit those parameters via from_dataset().

    Parameters
    ----------
    df  : output of prepare_tft_dataframe()
    cfg : full pipeline config dict

    Returns
    -------
    (training, validation, test) TimeSeriesDataSet
    """
    model_cfg = cfg["model"]
    dates     = cfg["dates"]

    val_start  = pd.Timestamp(dates["val_start"])
    test_start = pd.Timestamp(dates["test_start"])

    enc_len  = model_cfg["encoder_length"]
    pred_len = model_cfg["prediction_length"]

    train_df = df[df["date"] < val_start].copy()
    val_df   = df[df["date"] >= val_start].copy()   # includes test; from_dataset handles cutoff
    test_df  = df[df["date"] >= test_start].copy()

    logger.info(
        f"  Split sizes: train={len(train_df):,}  "
        f"val_pool={len(val_df):,}  test_pool={len(test_df):,}"
    )

    # Only include features that are actually present in df
    known_reals   = [c for c in TIME_VARYING_KNOWN_REALS   if c in df.columns]
    unknown_reals = [c for c in TIME_VARYING_UNKNOWN_REALS if c in df.columns]

    training = TimeSeriesDataSet(
        train_df,
        time_idx="time_idx",
        target="log_target",
        group_ids=STATIC_CATEGORICALS,
        min_encoder_length=enc_len // 2,
        max_encoder_length=enc_len,
        min_prediction_length=pred_len,
        max_prediction_length=pred_len,
        time_varying_known_reals=known_reals,
        time_varying_unknown_reals=unknown_reals,
        static_categoricals=STATIC_CATEGORICALS,
        # Per-ticker normalisation, fit on training data only
        target_normalizer=GroupNormalizer(
            groups=STATIC_CATEGORICALS,
            transformation=None,   # z-score (center + scale by group mean/std)
        ),
        add_relative_time_idx=True,
        add_target_scales=True,
        add_encoder_length=True,
        allow_missing_timesteps=False,
    )

    # predict=False keeps ALL windows (not just last per ticker), giving many
    # more evaluation samples. stop_randomization=True ensures deterministic order.
    validation = TimeSeriesDataSet.from_dataset(
        training, val_df[val_df["date"] < test_start],
        predict=False, stop_randomization=True,
    )
    test = TimeSeriesDataSet.from_dataset(
        training, test_df,
        predict=False, stop_randomization=True,
    )

    logger.info(
        f"  Training samples : {len(training):,}"
        f"  | Val samples : {len(validation):,}"
        f"  | Test samples : {len(test):,}"
    )

    return training, validation, test


def make_dataloaders(
    training: TimeSeriesDataSet,
    validation: TimeSeriesDataSet,
    test: TimeSeriesDataSet,
    cfg: dict,
) -> tuple:
    """Return (train_dl, val_dl, test_dl)."""
    m = cfg["model"]
    train_dl = training.to_dataloader(
        train=True, batch_size=m["batch_size"], num_workers=0, persistent_workers=False
    )
    val_dl = validation.to_dataloader(
        train=False, batch_size=m["val_batch_size"], num_workers=0, persistent_workers=False
    )
    test_dl = test.to_dataloader(
        train=False, batch_size=m["val_batch_size"], num_workers=0, persistent_workers=False
    )
    return train_dl, val_dl, test_dl
