"""
evaluate.py — Compute evaluation metrics for the TFT model.

Metrics
-------
  MAE   — Mean Absolute Error on P50 (point forecast)
  RMSE  — Root Mean Squared Error on P50
  MAPE  — Mean Absolute Percentage Error on P50 (where actual != 0)
  DA    — Directional Accuracy: % of predictions with correct sign of return
  QC    — Quantile Coverage: % of actuals inside [P10, P90] interval

All metrics are computed in log-return space.

Conformal calibration
---------------------
`compute_metrics()` accepts an optional `conformal_delta` scalar. When
nonzero, P10 is widened by -delta and P90 by +delta before computing QC.
This is the standard split-conformal CQR adjustment — see conformal.py
for the math.
"""

from __future__ import annotations

import logging
from typing import Tuple

import numpy as np
import torch
from torch.utils.data import DataLoader

from sl20_ml.model.conformal import apply_conformal

logger = logging.getLogger(__name__)


def extract_predictions(
    model,
    dataloader: DataLoader,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Run the model on a dataloader and return (p10, p50, p90, actuals)
    as 1-D numpy arrays in the original (log-return) target space.

    pf 1.x: model.predict(..., mode="quantiles", return_y=True) returns a
    Prediction namedtuple. The output is un-normalized by the dataset's
    target_normalizer, so it's directly in log-return space.
    """
    model.eval()

    result      = model.predict(dataloader, mode="quantiles", return_y=True)
    raw_preds   = result.output    # (N, pred_len, n_quantiles)
    raw_actuals = result.y[0]      # y is a tuple (target_tensor, weight)

    preds_t   = raw_preds.cpu()
    actuals_t = raw_actuals.cpu()

    if preds_t.ndim == 3:
        preds_t = preds_t[:, 0, :]
    if actuals_t.ndim == 2:
        actuals_t = actuals_t[:, 0]

    preds   = preds_t.numpy()     # (N, 3)
    actuals = actuals_t.numpy()   # (N,)

    p10, p50, p90 = preds[:, 0], preds[:, 1], preds[:, 2]
    return p10, p50, p90, actuals


def compute_metrics(
    model,
    dataloader: DataLoader,
    split_name: str = "val",
    conformal_delta: float = 0.0,
) -> dict[str, float]:
    """
    Run inference on a dataloader and compute all evaluation metrics.

    Parameters
    ----------
    model            : trained TemporalFusionTransformer
    dataloader       : val or test dataloader
    split_name       : label for logging
    conformal_delta  : if nonzero, widens P10/P90 by ±delta before computing QC.
                       Used to report calibrated metrics. Defaults to 0 (raw).

    Returns
    -------
    dict with keys: mae, rmse, mape, directional_accuracy, quantile_coverage
    """
    p10, p50, p90, actuals = extract_predictions(model, dataloader)

    if conformal_delta != 0.0:
        p10, p50, p90 = apply_conformal(p10, p50, p90, conformal_delta)

    # ── MAE / RMSE on P50 ─────────────────────────────────────────────────────
    errors = p50 - actuals
    mae    = float(np.abs(errors).mean())
    rmse   = float(np.sqrt((errors ** 2).mean()))

    # ── MAPE (skip actuals near zero) ─────────────────────────────────────────
    valid_mask = np.abs(actuals) > 1e-6
    if valid_mask.sum() > 0:
        mape = float(np.abs(errors[valid_mask] / actuals[valid_mask]).mean())
    else:
        mape = float("nan")

    # ── Directional accuracy ──────────────────────────────────────────────────
    correct_direction = np.sign(p50) == np.sign(actuals)
    da = float(correct_direction.mean())

    # ── Quantile coverage [P10, P90] ──────────────────────────────────────────
    inside = (actuals >= p10) & (actuals <= p90)
    qc = float(inside.mean())

    metrics = {
        "mae":                  mae,
        "rmse":                 rmse,
        "mape":                 mape,
        "directional_accuracy": da,
        "quantile_coverage":    qc,
    }

    tag = f"{split_name}"
    if conformal_delta != 0.0:
        tag += f" (calibrated, δ={conformal_delta:+.4f})"
    logger.info(f"  [{tag}] MAE={mae:.4f}  RMSE={rmse:.4f}  "
                f"MAPE={mape:.2%}  DA={da:.2%}  QC={qc:.2%}")
    return metrics


def log_metrics_to_mlflow(
    metrics: dict[str, float],
    split: str,
    run,
) -> None:
    """Log a metrics dict to an active MLflow run with split prefix."""
    for k, v in metrics.items():
        if not np.isnan(v):
            run.log_metric(f"{split}_{k}", v)
