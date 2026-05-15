"""
evaluate.py — Compute evaluation metrics for the TFT model.

Metrics
-------
  MAE   — Mean Absolute Error on P50 (point forecast)
  RMSE  — Root Mean Squared Error on P50
  MAPE  — Mean Absolute Percentage Error on P50 (where actual != 0)
  DA    — Directional Accuracy: % of predictions with correct sign of return
  QC    — Quantile Coverage: % of actuals inside [P10, P90] interval

All metrics are computed in log-return space then MAE/RMSE are also
reported in price terms (LKR) for interpretability.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader

logger = logging.getLogger(__name__)


def compute_metrics(
    model,
    dataloader: DataLoader,
    split_name: str = "val",
) -> dict[str, float]:
    """
    Run inference on a dataloader and compute all evaluation metrics.

    Parameters
    ----------
    model      : trained TemporalFusionTransformer
    dataloader : val or test dataloader
    split_name : label for logging

    Returns
    -------
    dict with keys: mae, rmse, mape, directional_accuracy, quantile_coverage
    """
    model.eval()
    all_preds   = []   # P10, P50, P90 — shape (N, 3)
    all_actuals = []   # actual log returns — shape (N,)

    with torch.no_grad():
        for batch in dataloader:
            x, y = batch
            preds = model(x)["prediction"]          # (batch, pred_len, n_quantiles)
            preds = preds[:, 0, :]                  # squeeze pred_len=1 → (batch, 3)
            target = y[0][:, 0]                     # (batch,)  — first (and only) step

            all_preds.append(preds.cpu().numpy())
            all_actuals.append(target.cpu().numpy())

    preds   = np.concatenate(all_preds,   axis=0)   # (N, 3)
    actuals = np.concatenate(all_actuals, axis=0)   # (N,)

    p10, p50, p90 = preds[:, 0], preds[:, 1], preds[:, 2]

    # ── MAE / RMSE ────────────────────────────────────────────────────────────
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

    logger.info(f"  [{split_name}] MAE={mae:.4f}  RMSE={rmse:.4f}  "
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
