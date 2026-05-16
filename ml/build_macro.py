"""
build_macro.py — Phase 1+2 entry point for all macro context data.

Produces three cleaned Parquet files:
  data/cleaned/cbsl.parquet   — daily: USD/LKR rate + CBSL policy rates
  data/cleaned/gdp.parquet    — annual: GDP growth, CPI, unemployment
  data/cleaned/fred.parquet   — daily: oil, S&P 500, VIX, gold, DXY, US 10Y yield

Run from ml/:
    python build_macro.py

FRED data requires FRED_API_KEY in .env (or set as env variable).
If the key is missing, yfinance is used as a fallback for most series.
"""

import logging
import sys
from pathlib import Path

ML_DIR = Path(__file__).parent
sys.path.insert(0, str(ML_DIR / "src"))

from sl20_ml.utils.config import load_config, get_ml_dir
from sl20_ml.ingestion.cbsl import load_exchange_rates, load_policy_rates
from sl20_ml.ingestion.gdp  import load_wdi
from sl20_ml.ingestion.fred import load_all_fred
from sl20_ml.cleaning.clean_macro import clean_cbsl, clean_gdp, clean_fred, save

cfg = load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(
            open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
        ),
        logging.FileHandler(ML_DIR / "build_macro.log", mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    ml_dir   = get_ml_dir()
    cbsl_dir = ml_dir / cfg["paths"]["raw"]["cbsl"]
    fund_dir = ml_dir / cfg["paths"]["raw"]["fundamentals"]
    fred_dir = ml_dir / cfg["paths"]["raw"]["fred"]

    start_date = cfg["dates"]["historical_start"]   # "2011-01-01"
    end_date   = cfg["dates"]["historical_end"]     # "2025-12-31"
    start_year = int(start_date[:4])
    end_year   = int(end_date[:4])
    # Fetch FRED data one year before ML start for ffill coverage
    fred_fetch_start = f"{start_year - 1}-01-01"

    out_cbsl = ml_dir / cfg["paths"]["cleaned"]["cbsl"]
    out_gdp  = ml_dir / cfg["paths"]["cleaned"]["gdp"]
    out_fred = ml_dir / cfg["paths"]["cleaned"]["fred"]

    logger.info("=" * 60)
    logger.info("stoX — Phase 1+2: Build macro context datasets")
    logger.info("=" * 60)

    # ── CBSL ──────────────────────────────────────────────────────────────────
    logger.info("\n[1/6] Loading CBSL exchange rates ...")
    exchange_df = load_exchange_rates(cbsl_dir)

    logger.info("\n[2/6] Loading CBSL policy rates ...")
    policy_df = load_policy_rates(cbsl_dir)

    logger.info("\n[3/6] Cleaning + saving CBSL data ...")
    cbsl_clean = clean_cbsl(exchange_df, policy_df, start_date, end_date)
    save(cbsl_clean, out_cbsl)

    # ── GDP / WDI ─────────────────────────────────────────────────────────────
    logger.info("\n[4/6] Loading World Bank WDI (GDP / CPI / unemployment) ...")
    gdp_raw = load_wdi(fund_dir, cfg["wdi_indicators"])

    logger.info("\n[4b] Cleaning + saving GDP data ...")
    gdp_clean = clean_gdp(gdp_raw, start_year=start_year, end_year=end_year)
    save(gdp_clean, out_gdp)

    # ── FRED ──────────────────────────────────────────────────────────────────
    logger.info("\n[5/6] Fetching / loading FRED global macro data ...")
    fred_raw = load_all_fred(
        fred_dir=fred_dir,
        series_cfg=cfg["fred_series"],
        start=fred_fetch_start,
        end=end_date,
    )

    logger.info("\n[6/6] Cleaning + saving FRED data ...")
    fred_clean = clean_fred(fred_raw, start_date=start_date, end_date=end_date)
    save(fred_clean, out_fred)

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("Done.  Output files:")
    for label, path in [("CBSL", out_cbsl), ("GDP", out_gdp), ("FRED", out_fred)]:
        size_mb = Path(ml_dir / path).stat().st_size / 1_048_576
        logger.info(f"  {label:<6s}: {path}  ({size_mb:.1f} MB)")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
