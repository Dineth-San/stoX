"""
conformal.py — Split conformal calibration for the TFT quantile outputs.

Background
----------
TemporalFusionTransformer trained with QuantileLoss([0.1, 0.5, 0.9]) is, by
definition, targeting an 80% prediction interval. A perfectly calibrated
model produces exactly 80% coverage; real models drift around this number
depending on data, training, and OOD-ness of the test set.

To hit a *specific* target coverage (e.g. 90%) deterministically, we apply
split conformal prediction — specifically Conformalized Quantile Regression
(CQR, Romano-Patterson-Candès 2019). This is a well-established post-hoc
calibration technique with finite-sample marginal coverage guarantees.

How it works
------------
1. Train the TFT normally on the training set.
2. On the validation set, for each sample compute the nonconformity score:
       s_i = max(P10_i - actual_i, actual_i - P90_i)
   s_i > 0  → actual fell outside [P10, P90]   (miss)
   s_i ≤ 0  → actual fell inside the interval  (covered)
3. Compute the (1-α) finite-sample quantile of {s_i}, where α = 1-target.
   This scalar is `delta`.
4. At inference, the *calibrated* interval is [P10 - delta, P90 + delta].
   By construction, validation coverage equals `target_coverage` exactly.
   Under exchangeability, test coverage ≈ target_coverage with finite-sample
   probability bounds (Vovk et al. 2005, Lei et al. 2018).

What it does NOT do
-------------------
It does NOT change training or the model. It does NOT change the meaning of
P10/P50/P90 in any deceptive way: the model still outputs quantile estimates
from QuantileLoss; we add a single, logged, transparent scalar offset.

References
----------
  Romano, Patterson, Candès. "Conformalized Quantile Regression." NeurIPS 2019.
  Vovk, Gammerman, Shafer. "Algorithmic Learning in a Random World." 2005.
  Lei et al. "Distribution-Free Predictive Inference for Regression." JASA 2018.
"""

from __future__ import annotations

import logging
from typing import Tuple

import numpy as np

logger = logging.getLogger(__name__)


def compute_conformal_delta(
    p10: np.ndarray,
    p90: np.ndarray,
    actual: np.ndarray,
    target_coverage: float = 0.90,
) -> float:
    """
    Compute the CQR calibration offset on a held-out (validation) set.

    Parameters
    ----------
    p10, p90, actual : 1-D arrays of equal length (in log-return space)
    target_coverage  : desired marginal coverage of the calibrated interval

    Returns
    -------
    delta : float
        Apply as: calibrated_p10 = p10 - delta, calibrated_p90 = p90 + delta.
        Positive delta → raw model under-covers, widen the band.
        Negative delta → raw model over-covers, narrow the band.

    Notes
    -----
    Uses the standard finite-sample conformal quantile level
        q_level = ⌈(n+1)·target⌉ / n
    which gives marginal coverage ≥ target on the test set under exchangeability.
    """
    actual = np.asarray(actual).flatten()
    p10    = np.asarray(p10).flatten()
    p90    = np.asarray(p90).flatten()

    assert len(actual) == len(p10) == len(p90), "p10/p90/actual must have equal length"

    n = len(actual)
    if n < 20:
        logger.warning(
            f"  conformal calibration recommended n>=20, got {n}; "
            "delta=0 (no calibration)"
        )
        return 0.0

    if not (0.0 < target_coverage < 1.0):
        raise ValueError(f"target_coverage must be in (0,1), got {target_coverage}")

    # Nonconformity score per sample
    scores = np.maximum(p10 - actual, actual - p90)

    # Finite-sample conformal quantile level
    q_level = min(np.ceil((n + 1) * target_coverage) / n, 1.0)

    # `method="higher"` matches the standard split-conformal definition
    # (use the upper sample quantile, which guarantees the coverage bound).
    delta = float(np.quantile(scores, q_level, method="higher"))

    logger.info(
        f"  Conformal calibration: n={n}, target={target_coverage:.0%}, "
        f"q_level={q_level:.4f}, delta={delta:+.6f}"
    )
    return delta


def apply_conformal(
    p10: np.ndarray,
    p50: np.ndarray,
    p90: np.ndarray,
    delta: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Apply the conformal offset to widen (or narrow) the prediction band.

    Returns calibrated (p10, p50, p90). P50 is unchanged (it's the median).
    Enforces P10 ≤ P50 ≤ P90 even if delta is negative and would cross P50.
    """
    p10 = np.asarray(p10)
    p50 = np.asarray(p50)
    p90 = np.asarray(p90)

    p10_cal = p10 - delta
    p90_cal = p90 + delta

    # Numerical safety: never let the calibrated band cross the median.
    p10_cal = np.minimum(p10_cal, p50)
    p90_cal = np.maximum(p90_cal, p50)

    return p10_cal, p50, p90_cal


def coverage(
    p10: np.ndarray,
    p90: np.ndarray,
    actual: np.ndarray,
) -> float:
    """Empirical coverage: fraction of `actual` inside [p10, p90]."""
    actual = np.asarray(actual).flatten()
    p10    = np.asarray(p10).flatten()
    p90    = np.asarray(p90).flatten()
    inside = (actual >= p10) & (actual <= p90)
    return float(inside.mean())
