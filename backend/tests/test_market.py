"""
Tests for GET /market/movers.

Covers:
  - Exactly 5 movers returned
  - Required fields present
  - Sorted by abs(changePercent) descending
  - changePercent is a float (can be negative)
"""
import pytest
from httpx import AsyncClient

REQUIRED_FIELDS = {"ticker", "name", "price", "changePercent"}


@pytest.mark.anyio
async def test_movers_count(client: AsyncClient):
    r = await client.get("/market/movers")
    assert r.status_code == 200
    assert len(r.json()) == 5


@pytest.mark.anyio
async def test_movers_required_fields(client: AsyncClient):
    data = (await client.get("/market/movers")).json()
    for mover in data:
        for field in REQUIRED_FIELDS:
            assert field in mover, f"Missing field '{field}'"


@pytest.mark.anyio
async def test_movers_sorted_by_abs_change_desc(client: AsyncClient):
    data = (await client.get("/market/movers")).json()
    abs_changes = [abs(m["changePercent"]) for m in data]
    assert abs_changes == sorted(abs_changes, reverse=True), \
        f"Movers not sorted by |changePercent| desc: {abs_changes}"


@pytest.mark.anyio
async def test_movers_price_positive(client: AsyncClient):
    data = (await client.get("/market/movers")).json()
    for mover in data:
        assert mover["price"] > 0, f"Non-positive price for {mover['ticker']}"


@pytest.mark.anyio
async def test_movers_tickers_non_empty(client: AsyncClient):
    data = (await client.get("/market/movers")).json()
    for mover in data:
        assert mover["ticker"].strip()
        assert mover["name"].strip()
