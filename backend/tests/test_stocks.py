"""
Tests for /stocks endpoints.

Covers:
  - GET /stocks         — 20 items, all SL20 tickers, camelCase keys, valid signals
  - GET /stocks/{t}/prediction — shape, 404 on unknown ticker
  - GET /stocks/{t}/info       — shape, 404 on unknown ticker
  - GET /stocks/{t}/stats      — shape, 404 on unknown ticker
  - GET /stocks/{t}/history    — shape, 404 on unknown ticker
"""
import pytest
from httpx import AsyncClient

from app.services.prediction_service import SL20_TICKERS

VALID_SIGNALS = {"BUY", "HOLD", "SELL"}
PREDICTION_KEYS = {
    "ticker", "name", "sector",
    "lastClose", "predictedP10", "predictedP50", "predictedP90",
    "predictedChangePercent", "signal", "sparkline",
    "directionalAccuracy", "meanError",
}


@pytest.mark.anyio
async def test_get_all_stocks_count(client: AsyncClient):
    r = await client.get("/stocks")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 20


@pytest.mark.anyio
async def test_get_all_stocks_all_tickers_present(client: AsyncClient):
    r = await client.get("/stocks")
    returned_tickers = {s["ticker"] for s in r.json()}
    assert returned_tickers == set(SL20_TICKERS)


@pytest.mark.anyio
async def test_get_all_stocks_camel_case_keys(client: AsyncClient):
    r = await client.get("/stocks")
    first = r.json()[0]
    for key in PREDICTION_KEYS:
        assert key in first, f"Missing key: {key}"


@pytest.mark.anyio
async def test_get_all_stocks_signals_valid(client: AsyncClient):
    r = await client.get("/stocks")
    for stock in r.json():
        assert stock["signal"] in VALID_SIGNALS, f"Bad signal: {stock['signal']}"


@pytest.mark.anyio
async def test_get_all_stocks_sparkline_is_list(client: AsyncClient):
    r = await client.get("/stocks")
    for stock in r.json():
        assert isinstance(stock["sparkline"], list)
        assert len(stock["sparkline"]) > 0


@pytest.mark.anyio
async def test_get_stock_prediction_known(client: AsyncClient):
    r = await client.get("/stocks/JKH/prediction")
    assert r.status_code == 200
    d = r.json()
    assert d["ticker"] == "JKH"
    assert d["signal"] in VALID_SIGNALS
    assert isinstance(d["predictedP50"], float)


@pytest.mark.anyio
async def test_get_stock_prediction_unknown(client: AsyncClient):
    r = await client.get("/stocks/FAKE/prediction")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_get_stock_info_known(client: AsyncClient):
    r = await client.get("/stocks/JKH/info")
    assert r.status_code == 200
    d = r.json()
    assert d["ticker"] == "JKH"
    assert "name" in d and "sector" in d and "blurb" in d


@pytest.mark.anyio
async def test_get_stock_info_unknown(client: AsyncClient):
    r = await client.get("/stocks/FAKE/info")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_get_stock_stats_known(client: AsyncClient):
    r = await client.get("/stocks/JKH/stats")
    assert r.status_code == 200
    d = r.json()
    assert "high52w" in d and "low52w" in d
    assert "avgVolume" in d and "marketCap" in d and "peRatio" in d
    assert d["high52w"] >= d["low52w"]
    assert d["marketCap"] > 0


@pytest.mark.anyio
async def test_get_stock_stats_unknown(client: AsyncClient):
    r = await client.get("/stocks/FAKE/stats")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_get_stock_history_known(client: AsyncClient):
    r = await client.get("/stocks/JKH/history?days=30")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 30
    for pt in data:
        assert "date" in pt and "close" in pt
        assert "predictedP10" in pt and "predictedP50" in pt and "predictedP90" in pt


@pytest.mark.anyio
async def test_get_stock_history_unknown(client: AsyncClient):
    r = await client.get("/stocks/FAKE/history")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_get_stock_history_sorted_asc(client: AsyncClient):
    r = await client.get("/stocks/JKH/history?days=10")
    dates = [pt["date"] for pt in r.json()]
    assert dates == sorted(dates)
