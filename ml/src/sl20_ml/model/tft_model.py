"""
tft_model.py — Build and configure the TemporalFusionTransformer.
"""

from __future__ import annotations

import logging

from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
from pytorch_forecasting.metrics import QuantileLoss

logger = logging.getLogger(__name__)


def build_tft(
    training: TimeSeriesDataSet,
    cfg: dict,
) -> TemporalFusionTransformer:
    """
    Instantiate TFT from the training dataset + pipeline config.

    The model is constructed via from_dataset() so it inherits all
    normalisation parameters and feature metadata automatically.

    Parameters
    ----------
    training : TimeSeriesDataSet built on training data
    cfg      : full pipeline config dict

    Returns
    -------
    TemporalFusionTransformer (untrained)
    """
    m = cfg["model"]
    quantiles = m["quantiles"]

    tft = TemporalFusionTransformer.from_dataset(
        training,
        learning_rate=m["learning_rate"],
        hidden_size=m["hidden_size"],
        attention_head_size=m["attention_head_size"],
        dropout=m["dropout"],
        hidden_continuous_size=m["hidden_continuous_size"],
        output_size=len(quantiles),
        loss=QuantileLoss(quantiles=quantiles),
        log_interval=10,
        log_val_interval=1,
        reduce_on_plateau_patience=m["reduce_lr_patience"],
    )

    n_params = sum(p.numel() for p in tft.parameters() if p.requires_grad)
    logger.info(
        f"  TFT built: {n_params:,} trainable parameters | "
        f"hidden_size={m['hidden_size']} | "
        f"attention_heads={m['attention_head_size']} | "
        f"quantiles={quantiles}"
    )
    return tft
