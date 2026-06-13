"""
Tests for GET /news.

Covers:
  - Exactly 20 items returned
  - Required fields present on every item
  - sentiment constrained to allowed values
  - isLocal is a boolean
"""
import pytest
from httpx import AsyncClient

VALID_SENTIMENTS = {"Positive", "Neutral", "Negative"}
REQUIRED_FIELDS  = {"id", "source", "isLocal", "headline", "url", "sentiment", "timeAgo"}


@pytest.mark.anyio
async def test_news_count(client: AsyncClient):
    r = await client.get("/news")
    assert r.status_code == 200
    assert len(r.json()) == 20


@pytest.mark.anyio
async def test_news_required_fields(client: AsyncClient):
    data = (await client.get("/news")).json()
    for item in data:
        for field in REQUIRED_FIELDS:
            assert field in item, f"Missing field '{field}' in news item {item.get('id')}"


@pytest.mark.anyio
async def test_news_sentiment_values(client: AsyncClient):
    data = (await client.get("/news")).json()
    for item in data:
        assert item["sentiment"] in VALID_SENTIMENTS, \
            f"Invalid sentiment '{item['sentiment']}' on item {item.get('id')}"


@pytest.mark.anyio
async def test_news_is_local_boolean(client: AsyncClient):
    data = (await client.get("/news")).json()
    for item in data:
        assert isinstance(item["isLocal"], bool), \
            f"isLocal is not bool on item {item.get('id')}"


@pytest.mark.anyio
async def test_news_ids_unique(client: AsyncClient):
    data = (await client.get("/news")).json()
    ids = [item["id"] for item in data]
    assert len(ids) == len(set(ids)), "Duplicate news IDs found"


@pytest.mark.anyio
async def test_news_headlines_non_empty(client: AsyncClient):
    data = (await client.get("/news")).json()
    for item in data:
        assert item["headline"].strip(), f"Empty headline on item {item.get('id')}"
