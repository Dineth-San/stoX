"""
Seed the database on first run.

Each seeding stage is a no-op if the relevant table already has data,
so this is safe to call on every startup.

Stages are filled in by later iterations:
  - Iteration 6: backfill predictions (90 trading days)
  - Iteration 7: simulate paper trading history (90 trading days)
"""
import logging

from app.db.database import get_db

logger = logging.getLogger(__name__)


async def seed_if_empty() -> None:
    """Entry point called from main.py lifespan. Currently a no-op placeholder."""
    logger.info("seed_if_empty: no seeding stages active yet (will be wired in later iterations)")
