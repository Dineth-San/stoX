"""
build_news_ingest.py — Stage 1 of the news sentiment pipeline.

Fetches raw news from two sources and saves to:
  ml/data/raw/news/raw_news.parquet

Sources
-------
  cse   : CSE official announcements (POST API, no auth)
  almas : Almas Equities news feed (Playwright + saved session)

Usage
-----
  # First-time Almas setup — opens a browser for you to log in manually:
  python build_news_ingest.py --setup-almas-session

  # Normal run (both sources):
  python build_news_ingest.py

  # CSE only (skip Almas):
  python build_news_ingest.py --cse-only

  # Almas only:
  python build_news_ingest.py --almas-only

Output schema
-------------
  date, source, ticker, headline, body, url, url_hash, annct_type
"""

import argparse
import logging
import sys
from pathlib import Path

ML_DIR = Path(__file__).parent
sys.path.insert(0, str(ML_DIR / "src"))

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(ML_DIR / ".env")
except ImportError:
    pass

from sl20_ml.ingestion.news import CSEFetcher, AlmasFetcher, save_raw

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_PATH = ML_DIR / "data" / "raw" / "news" / "raw_news.parquet"


def main():
    parser = argparse.ArgumentParser(description="Fetch raw news for SL20 stocks")
    parser.add_argument("--setup-almas-session", action="store_true",
                        help="Open browser to log in to Almas and save the session (run once)")
    parser.add_argument("--cse-only",   action="store_true", help="Skip Almas")
    parser.add_argument("--almas-only", action="store_true", help="Skip CSE")
    parser.add_argument("--headful",    action="store_true", help="Show browser window (Almas debug)")
    args = parser.parse_args()

    # ── Session setup mode ────────────────────────────────────────────────────
    if args.setup_almas_session:
        AlmasFetcher().setup_session()
        return

    logger.info("=" * 60)
    logger.info("stoX — News Ingestion")
    logger.info("=" * 60)

    all_rows = []

    # ── 1. CSE announcements ──────────────────────────────────────────────────
    if not args.almas_only:
        logger.info("\n[1/2] Fetching CSE announcements ...")
        try:
            rows = CSEFetcher().fetch()
            all_rows.extend(rows)
            logger.info(f"  CSE: {len(rows)} announcements fetched")
        except Exception as exc:
            logger.error(f"  CSE fetch failed: {exc}")

    # ── 2. Almas news feed ────────────────────────────────────────────────────
    if not args.cse_only:
        logger.info("\n[2/2] Scraping Almas Equities news feed ...")
        try:
            rows = AlmasFetcher(headless=not args.headful).fetch()
            all_rows.extend(rows)
            logger.info(f"  Almas: {len(rows)} articles fetched")
        except RuntimeError as exc:
            logger.warning(f"  Almas skipped: {exc}")
        except Exception as exc:
            logger.error(f"  Almas scrape failed: {exc}")

    # ── 3. Save ───────────────────────────────────────────────────────────────
    logger.info(f"\nSaving {len(all_rows)} rows to {OUTPUT_PATH} ...")
    df = save_raw(all_rows, OUTPUT_PATH)

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info(f"  Total rows saved : {len(df)}")
    if len(df) > 0:
        logger.info(f"  Date range       : {df['date'].min().date()} → {df['date'].max().date()}")
        logger.info(f"  Sources          : {df['source'].value_counts().to_dict()}")
        tagged = df['ticker'].notna().sum()
        logger.info(f"  Ticker-tagged    : {tagged}/{len(df)} ({tagged/len(df):.0%})")
    logger.info("=" * 60)
    logger.info("Next step: run python build_news_clean.py")


if __name__ == "__main__":
    main()
