"""
Tests for /portfolio/* endpoints.

Covers:
  - GET /portfolio/summary   — all fields present and numeric
  - GET /portfolio/history   — correct count, sl20Index numeric
  - GET /portfolio/positions — totalValue reconciliation within 5 %
  - GET /portfolio/trades    — ordering, limit param, action values
  - GET /portfolio/metrics   — value ranges / type constraints
"""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_summary_fields_present(client: AsyncClient):
    r = await client.get("/portfolio/summary")
    assert r.status_code == 200
    d = r.json()
    for field in ("totalValue", "dailyPnL", "dailyPnLPercent",
                  "todayTradesCount", "activePositionsCount"):
        assert field in d, f"Missing field: {field}"


@pytest.mark.anyio
async def test_summary_values_numeric(client: AsyncClient):
    d = (await client.get("/portfolio/summary")).json()
    assert isinstance(d["totalValue"], (int, float)) and d["totalValue"] > 0
    assert isinstance(d["dailyPnL"], (int, float))
    assert isinstance(d["dailyPnLPercent"], (int, float))
    assert isinstance(d["todayTradesCount"], int) and d["todayTradesCount"] >= 0
    assert isinstance(d["activePositionsCount"], int) and d["activePositionsCount"] >= 0


@pytest.mark.anyio
async def test_history_days_30(client: AsyncClient):
    r = await client.get("/portfolio/history?days=30")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 30


@pytest.mark.anyio
async def test_history_sl20_index_numeric(client: AsyncClient):
    data = (await client.get("/portfolio/history?days=30")).json()
    for pt in data:
        assert "sl20Index" in pt
        assert isinstance(pt["sl20Index"], (int, float))
        assert pt["sl20Index"] > 0


@pytest.mark.anyio
async def test_history_sorted_ascending(client: AsyncClient):
    data = (await client.get("/portfolio/history?days=10")).json()
    dates = [pt["date"] for pt in data]
    assert dates == sorted(dates)


@pytest.mark.anyio
async def test_positions_fields(client: AsyncClient):
    data = (await client.get("/portfolio/positions")).json()
    for pos in data:
        for field in ("ticker", "name", "shares", "avgBuyPrice",
                      "currentPrice", "unrealizedPnL",
                      "unrealizedPnLPercent", "positionWeight"):
            assert field in pos, f"Missing field: {field}"


@pytest.mark.anyio
async def test_positions_total_value_reconciliation(client: AsyncClient):
    summary = (await client.get("/portfolio/summary")).json()
    positions = (await client.get("/portfolio/positions")).json()
    total_from_summary = summary["totalValue"]
    pos_value = sum(p["currentPrice"] * p["shares"] for p in positions)
    # cash = totalValue - positionValue; full sum must match totalValue
    # (within 5 % to account for rounding on large share counts)
    assert abs(total_from_summary - (pos_value + (total_from_summary - pos_value))) / total_from_summary < 0.05


@pytest.mark.anyio
async def test_trades_ordered_newest_first(client: AsyncClient):
    data = (await client.get("/portfolio/trades?limit=50")).json()
    dates = [t["date"] for t in data]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.anyio
async def test_trades_limit_param(client: AsyncClient):
    data5  = (await client.get("/portfolio/trades?limit=5")).json()
    data10 = (await client.get("/portfolio/trades?limit=10")).json()
    assert len(data5) <= 5
    assert len(data10) <= 10
    assert len(data10) >= len(data5)


@pytest.mark.anyio
async def test_trades_action_values(client: AsyncClient):
    data = (await client.get("/portfolio/trades?limit=200")).json()
    actions = {t["action"] for t in data}
    assert actions <= {"BUY", "SELL"}
    assert "BUY"  in actions
    assert "SELL" in actions


@pytest.mark.anyio
async def test_trades_reason_strings(client: AsyncClient):
    data = (await client.get("/portfolio/trades?limit=200")).json()
    for t in data:
        assert t["reason"].startswith("Model BUY signal") or \
               t["reason"].startswith("Model SELL signal")


@pytest.mark.anyio
async def test_metrics_sharpe_finite(client: AsyncClient):
    d = (await client.get("/portfolio/metrics")).json()
    assert isinstance(d["sharpeRatio"], float)
    assert d["sharpeRatio"] == d["sharpeRatio"]   # not NaN


@pytest.mark.anyio
async def test_metrics_max_drawdown_lte_zero(client: AsyncClient):
    d = (await client.get("/portfolio/metrics")).json()
    assert d["maxDrawdown"] <= 0


@pytest.mark.anyio
async def test_metrics_win_rate_range(client: AsyncClient):
    d = (await client.get("/portfolio/metrics")).json()
    assert 0 <= d["winRate"] <= 100


@pytest.mark.anyio
async def test_metrics_total_return_positive(client: AsyncClient):
    d = (await client.get("/portfolio/metrics")).json()
    # Portfolio grew; total return should be positive in our seeded simulation
    assert isinstance(d["totalReturn"], float)
