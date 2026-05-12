"""
build_market.py — Phase 1+2 entry point for CSE market context data.

Run from ml/:
    python build_market.py

Reads all paths and settings from configs/pipeline.yaml.
"""

import logging
import sys
from pathlib import Path

ML_DIR = Path(__file__).parent
sys.path.insert(0, str(ML_DIR / "src"))

from sl20_ml.utils.config import load_config, get_ml_dir
from sl20_ml.ingestion.market import load_all_market_context
from sl20_ml.cleaning.clean_market import clean, quality_report, save

cfg = load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(
            open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
        ),
        logging.FileHandler(ML_DIR / "build_market.log", mode="w"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    ml_dir     = get_ml_dir()
    stock_data = ml_dir / cfg["paths"]["raw"]["cse"]
    out_ml     = ml_dir / cfg["paths"]["cleaned"]["market_context"]
    out_full   = ml_dir / cfg["paths"]["cleaned"]["market_context_full"]

    logger.info("=" * 60)
    logger.info("stoX — Phase 1+2: Build market context dataset")
    logger.info("=" * 60)

    logger.info("\n[1/3] Loading market context files ...")
    raw = load_all_market_context(stock_data)

    logger.info("\n[2/3] Cleaning ...")
    full_df, ml_df = clean(raw)

    logger.info("\n--- Quality report (ML slice) ---")
    quality_report(ml_df, label="2011+")

    logger.info("\n[3/3] Saving ...")
    save(full_df, out_full)
    save(ml_df,   out_ml)

    logger.info("\n" + "=" * 60)
    logger.info("Done.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
