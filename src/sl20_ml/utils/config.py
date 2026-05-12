"""
config.py — Central config loader.

Every script reads pipeline settings from configs/pipeline.yaml via this
module. Nothing domain-specific (paths, tickers, thresholds, windows) is
hardcoded anywhere else.

Usage:
    from sl20_ml.utils.config import load_config, get_ml_dir

    cfg = load_config()
    tickers = cfg["tickers"]["sl20"]
    start   = cfg["dates"]["historical_start"]
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def get_ml_dir() -> Path:
    """Return the absolute path to the ml/ directory."""
    # This file lives at ml/src/sl20_ml/utils/config.py
    return Path(__file__).parent.parent.parent.parent.resolve()


@lru_cache(maxsize=1)
def load_config(config_path: str | None = None) -> dict[str, Any]:
    """
    Load and return the pipeline configuration as a dict.

    Parameters
    ----------
    config_path : str or None
        Path to the YAML config file. If None, defaults to
        ml/configs/pipeline.yaml.

    Returns
    -------
    dict — the full parsed pipeline.yaml contents.
    """
    if config_path is None:
        config_path = str(get_ml_dir() / "configs" / "pipeline.yaml")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    return cfg


def get_path(key: str, sub_key: str) -> Path:
    """
    Resolve a path from configs → paths → {key} → {sub_key}.
    Returns an absolute Path relative to ml/.

    Example:
        get_path("cleaned", "prices")
        # Returns Path("D:/stox/ml/data/cleaned/master_prices.parquet")
    """
    cfg = load_config()
    rel = cfg["paths"][key][sub_key]
    return get_ml_dir() / rel
