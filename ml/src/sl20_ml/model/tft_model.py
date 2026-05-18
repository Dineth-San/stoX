"""
tft_model.py — Build and configure the TemporalFusionTransformer.
"""

from __future__ import annotations

import logging

import torch
import torch.nn as nn
from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
from pytorch_forecasting.metrics import QuantileLoss

logger = logging.getLogger(__name__)

# FP16 (float16) can only represent values up to ~±65504.
# pytorch-forecasting's attention module uses mask_bias = -1e9 by default,
# which overflows to -inf in FP16 and causes a RuntimeError during masked_fill.
# This constant is a safe large-negative value that's well within FP16 range
# and still effectively zeros out masked attention weights through softmax.
_FP16_SAFE_MASK_BIAS = -1e4   # softmax(-10000) ≈ 0; safely representable as FP16


def _fix_fp16_mask_bias(model: nn.Module) -> None:
    """
    Clamp mask_bias on all TFT attention sub-modules to a value that is
    representable in float16 (~±65504 max).

    Called after model construction when FP16 mixed precision is used.
    Without this fix, masked_fill in InterpretableMultiHeadAttention raises:
      RuntimeError: value cannot be converted to type c10::Half without overflow
    """
    patched = 0
    for module in model.modules():
        if hasattr(module, "mask_bias"):
            bias = module.mask_bias
            if isinstance(bias, nn.Parameter):
                with torch.no_grad():
                    bias.fill_(_FP16_SAFE_MASK_BIAS)
                patched += 1
            elif isinstance(bias, (int, float)) and bias < _FP16_SAFE_MASK_BIAS:
                module.mask_bias = _FP16_SAFE_MASK_BIAS
                patched += 1
    if patched:
        logger.info(f"  FP16 mask_bias fix applied to {patched} attention module(s)")


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

    # FP16 mixed precision requires mask_bias to be within float16 range.
    # Always apply — harmless on FP32, essential on FP16.
    _fix_fp16_mask_bias(tft)

    return tft
