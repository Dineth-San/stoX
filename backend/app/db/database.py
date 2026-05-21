from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

from app.config import settings

# Resolve schema path relative to this file so it works regardless of cwd
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _db_path() -> str:
    """Resolve DB_PATH relative to the current working directory (backend/)."""
    return str(Path(settings.db_path).resolve())


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """FastAPI dependency: yields an open aiosqlite connection per request."""
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db() -> None:
    """
    Create all tables defined in schema.sql.
    Safe to call on every startup — all statements use CREATE TABLE IF NOT EXISTS.
    """
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    async with aiosqlite.connect(_db_path()) as db:
        await db.executescript(schema)
        await db.commit()
