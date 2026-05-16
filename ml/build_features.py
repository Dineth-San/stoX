"""
build_features.py — Phase 4 entry point: engineer ML features from aligned panel.

Reads   : data/aligned/sl20_daily_panel.parquet
Produces: data/features/sl20_feature_panel.parquet

Run from ml/:
    python build_features.py
"""

import logging
import sys
from pathlib import Path

ML_DIR = Path(__file__).parent
sys.path.insert(0, str(ML_DIR / "src"))

from sl20_ml.utils.config import load_config, get_ml_dir
from sl20_ml.features.engineer import build_feature_panel

import pandas as pd

cfg = load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(
            open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
        ),
        logging.FileHandler(ML_DIR / "build_features.log", mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    ml_dir     = get_ml_dir()
    panel_path = ml_dir / cfg["paths"]["aligned"]["panel"]
    out_path   = ml_dir / cfg["paths"]["features"]["panel"]

    logger.info("=" * 60)
    logger.info("stoX — Phase 4: Feature Engineering")
    logger.info("=" * 60)

    # ── Load aligned panel ─────────────────────────────────────────────────────
    logger.info(f"\n[1/3] Loading aligned panel from {panel_path} ...")
    if not panel_path.exists():
        logger.error(f"Panel not found: {panel_path}")
        logger.error("Run build_alignment.py first.")
        sys.exit(1)
    aligned = pd.read_parquet(panel_path)
    logger.info(f"  Loaded: {len(aligned):,} rows × {aligned.shape[1]} columns")

    # ── Build feature panel ────────────────────────────────────────────────────
    logger.info("\n[2/3] Engineering features ...")
    feature_panel = build_feature_panel(aligned, cfg)

    # ── Save ───────────────────────────────────────────────────────────────────
    logger.info("\n[3/3] Saving ...")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    feature_panel.to_parquet(out_path, index=False, engine="pyarrow")
    size_mb = out_path.stat().st_size / 1_048_576

    logger.info("\n" + "=" * 60)
    logger.info(f"Done.  {out_path}")
    logger.info(f"  Rows     : {len(feature_panel):,}")
    logger.info(f"  Columns  : {feature_panel.shape[1]}")
    logger.info(f"  Size     : {size_mb:.1f} MB")
    logger.info(f"  Splits   : {feature_panel.groupby('split')['date'].nunique().to_dict()}")

    # Report null rates for key feature groups
    key_cols = [
        "ret_5d", "ret_20d", "vol_20d",
        "rsi_14", "macd", "bb_pct", "atr_14",
        "xs_zscore_daily_return", "xs_rank_ret_20d",
        "target_next_close",
    ]
    logger.info("\n  Key column null rates:")
    for col in key_cols:
        if col in feature_panel.columns:
            null_pct = feature_panel[col].isna().mean()
            logger.info(f"    {col:<30} {null_pct:.1%}")

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
