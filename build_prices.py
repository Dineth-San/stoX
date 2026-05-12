"""
build_prices.py — Phase 1+2 entry point for CSE daily price data.

Run from ml/:
    python build_prices.py

Reads all paths and settings from configs/pipeline.yaml.
"""

import logging
import sys
from pathlib import Path

ML_DIR = Path(__file__).parent
sys.path.insert(0, str(ML_DIR / "src"))

from sl20_ml.utils.config import load_config, get_ml_dir
from sl20_ml.ingestion.prices import load_all_years
from sl20_ml.cleaning.clean_prices import clean, quality_report, save

cfg = load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(
            open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
        ),
        logging.FileHandler(ML_DIR / "build_prices.log", mode="w"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    ml_dir     = get_ml_dir()
    stock_data = ml_dir / cfg["paths"]["raw"]["cse"]
    out_path   = ml_dir / cfg["paths"]["cleaned"]["prices"]

    logger.info("=" * 60)
    logger.info("stoX — Phase 1+2: Build master price dataset")
    logger.info("=" * 60)

    logger.info("\n[1/3] Loading raw price files ...")
    raw = load_all_years(stock_data)
    if raw.empty:
        logger.error("No data loaded. Check data/raw/cse/stock_data/")
        sys.exit(1)
    logger.info(f"Raw loaded: {len(raw):,} rows | {raw['ticker'].nunique()} tickers")

    logger.info("\n[2/3] Cleaning ...")
    cleaned = clean(raw, cfg)

    logger.info("\n--- Quality report ---")
    quality_report(cleaned)

    logger.info("\n[3/3] Saving ...")
    save(cleaned, out_path)

    logger.info("\n" + "=" * 60)
    logger.info(f"Done.  Output: {out_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
