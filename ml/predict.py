"""
predict.py — Inference script: load the trained TFT and produce next-day forecasts.

Usage
-----
    # Predict tomorrow's close for all 20 tickers as of the latest available date:
    python predict.py

    # Predict for a specific ticker and date:
    python predict.py --ticker JKH --date 2025-06-01

    # Output JSON instead of console table:
    python predict.py --format json

The script produces P10, P50, P90 quantile forecasts in price terms (LKR).
P50 is the point forecast. The [P10, P90] interval is the 80% confidence band.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

ML_DIR = Path(__file__).parent
sys.path.insert(0, str(ML_DIR / "src"))

import numpy as np
import pandas as pd
import torch

from sl20_ml.model.dataset import (
    TIME_VARYING_KNOWN_REALS,
    TIME_VARYING_UNKNOWN_REALS,
    STATIC_CATEGORICALS,
    prepare_tft_dataframe,
    build_tft_datasets,
    make_dataloaders,
)
from sl20_ml.utils.config import get_ml_dir, load_config

logger = logging.getLogger(__name__)


def load_model(ckpt_path: Path):
    """Load the best TFT checkpoint."""
    from pytorch_forecasting import TemporalFusionTransformer
    model = TemporalFusionTransformer.load_from_checkpoint(str(ckpt_path))
    model.eval()
    return model


def get_latest_checkpoint(ckpt_dir: Path) -> Path:
    """Find best.ckpt in the checkpoint directory."""
    best = ckpt_dir / "best.ckpt"
    if best.exists():
        return best
    # Fallback: any .ckpt file
    ckpts = sorted(ckpt_dir.glob("*.ckpt"))
    if not ckpts:
        raise FileNotFoundError(
            f"No checkpoint found in {ckpt_dir}. Run train_model.py first."
        )
    return ckpts[-1]


def predict_all(
    panel: pd.DataFrame,
    cfg: dict,
    tickers: list[str] | None = None,
    as_of_date: str | None = None,
) -> pd.DataFrame:
    """
    Produce next-day P10/P50/P90 forecasts for one or all tickers.

    Parameters
    ----------
    panel       : feature panel (loaded from parquet)
    cfg         : pipeline config
    tickers     : list of tickers to forecast (None = all 20)
    as_of_date  : YYYY-MM-DD forecast origin (None = latest date in panel)

    Returns
    -------
    DataFrame with columns: ticker, as_of_date, p10, p50, p90 (in LKR)
    """
    from pytorch_forecasting import TimeSeriesDataSet

    ml_dir   = get_ml_dir()
    ckpt_dir = ml_dir / cfg["model"]["checkpoint_dir"]
    ckpt     = get_latest_checkpoint(ckpt_dir)

    logger.info(f"Loading model from {ckpt} ...")
    model = load_model(ckpt)

    # Prepare dataframe (same transforms as training)
    df = prepare_tft_dataframe(panel)

    if as_of_date:
        df = df[df["date"] <= pd.Timestamp(as_of_date)]

    # ── Build training dataset so its normalizer (GroupNormalizer) is used ──────
    # IMPORTANT: The model was trained with a GroupNormalizer fit on the training
    # split. Using a fresh normalizer fit on only ~61 rows gives wrong stats.
    # We rebuild the training dataset from the full df and inherit its normalizer
    # via TimeSeriesDataSet.from_dataset().
    logger.info("Rebuilding training dataset to inherit training normalizer ...")
    training, _, _ = build_tft_datasets(df, cfg)

    # ── Filter to forecast tickers / date ────────────────────────────────────────
    if tickers:
        df = df[df["ticker"].isin(tickers)]

    # We need at least encoder_length rows per ticker
    enc_len = cfg["model"]["encoder_length"]
    valid_tickers = (
        df.groupby("ticker").size()[lambda s: s >= enc_len].index.tolist()
    )
    if not valid_tickers:
        raise ValueError(
            f"No tickers with ≥{enc_len} rows available for prediction."
        )
    df = df[df["ticker"].isin(valid_tickers)]

    # Use the last enc_len + 1 rows per ticker as the inference window.
    # predict=True → one window per ticker (last window), stop_randomization for order.
    inference_df = (
        df.sort_values(["ticker", "date"])
          .groupby("ticker")
          .tail(enc_len + 1)
          .copy()
    )
    # Re-number time_idx so it's contiguous within the inference slice
    inference_df["time_idx"] = inference_df.groupby("ticker").cumcount()

    # Inherit training normalizer via from_dataset() — this is the correct approach
    pred_dataset = TimeSeriesDataSet.from_dataset(
        training, inference_df,
        predict=True,          # one window per ticker
        stop_randomization=True,
    )

    pred_dl = pred_dataset.to_dataloader(
        train=False, batch_size=len(valid_tickers), num_workers=0
    )

    # Run inference
    # pf 1.x model.predict() returns a Prediction namedtuple.
    # Access .output for the predicted tensor — never unpack or call .ndim directly.
    with torch.no_grad():
        result = model.predict(pred_dl, mode="quantiles")

    raw_preds = result.output if hasattr(result, "output") else result
    if raw_preds.ndim == 3:
        raw_preds = raw_preds[:, 0, :]   # squeeze pred_len dim → (N, 3)

    preds_np = raw_preds.cpu().numpy()   # (n_tickers, 3)

    # Get last-known close per ticker for price reconstruction
    last_close = (
        inference_df.groupby("ticker")["close"].last().to_dict()
    )
    as_of = inference_df["date"].max()

    rows = []
    for i, ticker in enumerate(valid_tickers):
        lc = last_close.get(ticker, np.nan)
        p10 = float(lc * np.exp(preds_np[i, 0]))
        p50 = float(lc * np.exp(preds_np[i, 1]))
        p90 = float(lc * np.exp(preds_np[i, 2]))
        rows.append({
            "ticker":      ticker,
            "as_of_date":  str(as_of.date()),
            "last_close":  round(lc, 2),
            "p10":         round(p10, 2),
            "p50":         round(p50, 2),
            "p90":         round(p90, 2),
            "implied_ret": round(p50 / lc - 1, 4) if lc > 0 else None,
        })

    return pd.DataFrame(rows).sort_values("ticker").reset_index(drop=True)


def run_inference(ticker: str | None = None, date: str | None = None) -> list[dict]:
    """
    Backend-facing API. Load the model, run inference, return results as a list of dicts.

    Parameters
    ----------
    ticker : str or None
        Single ticker (e.g. 'JKH'). None = all 20 SL20 tickers.
    date : str or None
        Forecast as-of date 'YYYY-MM-DD'. None = latest date in panel.

    Returns
    -------
    List of dicts, one per ticker:
        [{'ticker': 'JKH', 'as_of_date': '2025-06-01', 'last_close': 183.5,
          'p10': 179.2, 'p50': 184.8, 'p90': 191.3, 'implied_ret': 0.0071}, ...]
    """
    cfg    = load_config()
    ml_dir = get_ml_dir()
    panel  = pd.read_parquet(ml_dir / cfg["paths"]["features"]["panel"])

    tickers = [ticker.upper()] if ticker else None
    results = predict_all(panel, cfg, tickers=tickers, as_of_date=date)
    return results.to_dict(orient="records")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="stoX TFT next-day price forecast")
    parser.add_argument("--ticker", nargs="+", default=None,
                        help="Ticker(s) to forecast (default: all 20 SL20)")
    parser.add_argument("--date", default=None,
                        help="Forecast as-of date YYYY-MM-DD (default: latest in panel)")
    parser.add_argument("--format", choices=["table", "json"], default="table",
                        help="Output format (default: table)")
    args = parser.parse_args()

    cfg    = load_config()
    ml_dir = get_ml_dir()
    panel  = pd.read_parquet(ml_dir / cfg["paths"]["features"]["panel"])

    results = predict_all(
        panel,
        cfg,
        tickers=args.ticker,
        as_of_date=args.date,
    )

    if args.format == "json":
        print(results.to_json(orient="records", indent=2))
    else:
        print("\n  stoX — Next-Day Close Price Forecast")
        print(f"  As of: {results['as_of_date'].iloc[0]}")
        print(f"  Model: TFT v1 | Quantiles: P10 / P50 (point) / P90\n")
        print(results.to_string(index=False))
        print()


if __name__ == "__main__":
    main()
