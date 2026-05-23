"""
Seed the database on first run.

Stages (each is a no-op if data already exists):
  Stage 1 — Today's predictions: run real TFT inference for all 20 tickers,
             store in predictions table. Falls back to mock if model fails.
  Stage 2 — Historical backfill: insert mock predictions (using actual closes)
             for the last BACKFILL_DAYS trading dates so /history shows bands.
  Stage 3 — Portfolio simulation: walk the same historical dates applying
             BUY/SELL signals to build a 90-day paper-trading history.
"""
import logging

import aiosqlite

from app.db.database import _db_path

logger = logging.getLogger(__name__)

BACKFILL_DAYS = 90


async def _prediction_count() -> int:
    async with aiosqlite.connect(_db_path()) as db:
        cur = await db.execute("SELECT COUNT(*) FROM predictions")
        (n,) = await cur.fetchone()
        return n


async def _predictions_count_before(date_str: str) -> int:
    async with aiosqlite.connect(_db_path()) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM predictions WHERE date < ?", (date_str,)
        )
        (n,) = await cur.fetchone()
        return n


async def _max_prediction_date() -> str | None:
    async with aiosqlite.connect(_db_path()) as db:
        cur = await db.execute("SELECT MAX(date) FROM predictions")
        (d,) = await cur.fetchone()
        return d


async def seed_if_empty() -> None:
    """Entry point called from main.py lifespan."""
    from app.services.prediction_service import SL20_TICKERS, get_prediction_service
    from app.services.price_service import get_price_service

    pred_svc  = get_prediction_service()
    price_svc = get_price_service()

    # ── Stage 1: run real inference if predictions table is empty ────────────
    total = await _prediction_count()
    if total == 0:
        logger.info("seed: predictions table empty — running real inference …")
        n = await pred_svc.prefill_today()
        logger.info("seed: stage 1 complete — inserted %d real predictions", n)
    else:
        logger.info("seed: %d prediction rows already present — skipping stage 1", total)

    # ── Stage 2: historical mock backfill ────────────────────────────────────
    # Use the max date in the predictions table as the "today" boundary.
    today = await _max_prediction_date()
    if today is None:
        logger.warning("seed: no predictions in table after stage 1 — skipping backfill")
        return

    # Get the last BACKFILL_DAYS trading dates BEFORE today
    all_dates = price_svc.get_trading_dates(BACKFILL_DAYS + 1)
    historical_dates = [d for d in all_dates if d < today]

    if not historical_dates:
        logger.info("seed: no historical dates to backfill")
        return

    expected_hist_rows = len(historical_dates) * len(SL20_TICKERS)
    current_hist_rows  = await _predictions_count_before(today)

    if current_hist_rows < expected_hist_rows:
        missing = expected_hist_rows - current_hist_rows
        logger.info(
            "seed: backfilling %d dates × %d tickers (%d rows missing) …",
            len(historical_dates), len(SL20_TICKERS), missing,
        )
        n = await pred_svc.backfill_historical(historical_dates)
        logger.info("seed: stage 2 complete — inserted %d historical rows", n)
    else:
        logger.info(
            "seed: historical backfill complete (%d rows) — skipping stage 2",
            current_hist_rows,
        )

    # ── Stage 3: portfolio backtest ──────────────────────────────────────────
    from app.services.portfolio_service import _trades_empty, simulate_backtest

    async with aiosqlite.connect(_db_path()) as _db:
        empty = await _trades_empty(_db)

    if empty:
        backtest_dates = sorted(historical_dates) + [today]
        logger.info(
            "seed: stage 3 — running portfolio backtest over %d dates …",
            len(backtest_dates),
        )
        stats = await simulate_backtest(backtest_dates)
        logger.info(
            "seed: stage 3 complete — %d trades | %d history rows | %d positions | cash=%.2f",
            stats["trades"], stats["history_rows"], stats["open_positions"], stats["final_cash"],
        )
    else:
        logger.info("seed: trades table not empty — skipping stage 3")
