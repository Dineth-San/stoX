"""
Shared pytest fixtures for the stoX backend test suite.

Uses httpx.AsyncClient with ASGITransport so every test hits the real
FastAPI application without a live server.

Note: ASGITransport does not trigger FastAPI lifespan events, so we
manually call the startup sequence (init_db → init_price_service →
init_prediction_service → seed_if_empty) before yielding the client.
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.database import init_db
from app.db.seed import seed_if_empty
from app.services.prediction_service import init_prediction_service
from app.services.price_service import init_price_service
from main import app


@pytest_asyncio.fixture(scope="session")
async def client():
    """Session-scoped async HTTP client wired directly to the ASGI app."""
    # Replicate the lifespan startup so singletons are ready before any test.
    await init_db()
    init_price_service()
    init_prediction_service()
    await seed_if_empty()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
