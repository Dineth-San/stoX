"""
build_alignment.py — Phase 3 entry point: join all sources onto trading calendar.

Produces: data/aligned/sl20_daily_panel.parquet
  Rows: 20 SL20 tickers × N CSE trading days (≈71,300 rows)
  Columns: ~85 (prices + market context + CBSL + FRED + GDP)

Run from ml/:
    python build_alignment.py
"""

import logging
import sys
from pathlib import Path

ML_DIR = Path(__file__).parent
sys.path.insert(0, str(ML_DIR / "src"))

from sl20_ml.utils.config import load_config, get_ml_dir
from sl20_ml.alignment.calendar import build_cse_trading_calendar
from sl20_ml.alignment.align import build_daily_panel

cfg = load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(
            open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
        ),
        logging.FileHandler(ML_DIR / "build_alignment.log", mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    ml_dir = get_ml_dir()
    p      = cfg["paths"]

    prices_path = ml_dir / p["cleaned"]["prices"]
    market_path = ml_dir / p["cleaned"]["market_context"]
    cbsl_path   = ml_dir / p["cleaned"]["cbsl"]
    gdp_path    = ml_dir / p["cleaned"]["gdp"]
    fred_path   = ml_dir / p["cleaned"]["fred"]
    out_path    = ml_dir / p["aligned"]["panel"]

    sl20         = cfg["tickers"]["sl20"]
    start_date   = cfg["dates"]["historical_start"]
    end_date     = cfg["dates"]["historical_end"]

    logger.info("=" * 60)
    logger.info("stoX — Phase 3: Alignment layer")
    logger.info("=" * 60)

    # ── Step 1: Trading calendar ───────────────────────────────────────────────
    logger.info("\n[1/3] Building CSE trading calendar ...")
    trading_cal = build_cse_trading_calendar(
        prices_path=prices_path,
        sl20_tickers=sl20,
        start_date=start_date,
        end_date=end_date,
    )

    # ── Step 2: Assemble panel ─────────────────────────────────────────────────
    logger.info("\n[2/3] Assembling daily panel ...")
    panel = build_daily_panel(
        trading_cal=trading_cal,
        prices_path=prices_path,
        market_path=market_path,
        cbsl_path=cbsl_path,
        gdp_path=gdp_path,
        fred_path=fred_path,
        sl20_tickers=sl20,
        cfg=cfg,
    )

    # ── Step 3: Save ───────────────────────────────────────────────────────────
    logger.info("\n[3/3] Saving ...")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(out_path, index=False, engine="pyarrow")
    size_mb = out_path.stat().st_size / 1_048_576

    logger.info("\n" + "=" * 60)
    logger.info(f"Done.  {out_path}")
    logger.info(f"  Rows    : {len(panel):,}")
    logger.info(f"  Columns : {panel.shape[1]}")
    logger.info(f"  Size    : {size_mb:.1f} MB")
    logger.info(f"  Splits  : {panel.groupby('split')['date'].nunique().to_dict()}")
    logger.info(f"  Columns : {list(panel.columns)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
