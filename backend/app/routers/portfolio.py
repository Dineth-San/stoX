"""
Portfolio router — five endpoints backed by the paper-trading tables.

GET /portfolio/summary
GET /portfolio/history?days=N
GET /portfolio/positions
GET /portfolio/trades?limit=N
GET /portfolio/metrics
"""
import math
import logging
from typing import Optional

import aiosqlite
from fastapi import APIRouter, Depends, Query

from app.db.database import get_db
from app.models.portfolio import (
    PerformanceMetrics,
    PortfolioHistoryPoint,
    PortfolioSummary,
    Position,
    Trade,
)
from app.services.price_service import PriceService, get_price_service
from app.services.stock_info_service import get_stock_info

logger = logging.getLogger(__name__)
router = APIRouter()

_INITIAL_CASH = 1_000_000.0


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_cash(db: aiosqlite.Connection) -> float:
    """Recompute remaining cash from the trades ledger."""
    buy_cost = (await (await db.execute(
        "SELECT COALESCE(SUM(quantity*price),0) FROM trades WHERE action='BUY'"
    )).fetchone())[0]
    sell_proceeds = (await (await db.execute(
        "SELECT COALESCE(SUM(quantity*price),0) FROM trades WHERE action='SELL'"
    )).fetchone())[0]
    return _INITIAL_CASH - buy_cost + sell_proceeds


async def _latest_history_dates(db: aiosqlite.Connection, n: int) -> list[tuple]:
    """Return (date, value) for the last `n` portfolio_history rows."""
    cur = await db.execute(
        "SELECT date, value FROM portfolio_history ORDER BY date DESC LIMIT ?", (n,)
    )
    rows = await cur.fetchall()
    return list(reversed(rows))  # chronological order


# ── 1. Summary ────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=PortfolioSummary, response_model_by_alias=True)
async def get_portfolio_summary(
    price_svc: PriceService = Depends(get_price_service),
    db: aiosqlite.Connection = Depends(get_db),
) -> PortfolioSummary:
    # Current position value (mark to latest panel price)
    cur = await db.execute("SELECT ticker, shares FROM positions")
    rows = await cur.fetchall()
    position_value = sum(
        (price_svc.get_latest_close(r[0]) or 0) * r[1] for r in rows
    )
    cash = await _get_cash(db)
    total_value = position_value + cash

    # Daily P&L from portfolio_history
    history = await _latest_history_dates(db, 2)
    if len(history) >= 2:
        today_val = history[-1][1]
        yest_val  = history[-2][1]
        daily_pnl = today_val - yest_val
        daily_pnl_pct = (daily_pnl / yest_val * 100) if yest_val else 0.0
    else:
        daily_pnl = 0.0
        daily_pnl_pct = 0.0

    # Trades on the most-recent history date
    today_date = history[-1][0] if history else ""
    cur = await db.execute(
        "SELECT COUNT(*) FROM trades WHERE date=?", (today_date,)
    )
    today_trades_count = (await cur.fetchone())[0]

    # Active positions
    cur = await db.execute("SELECT COUNT(*) FROM positions")
    active_positions = (await cur.fetchone())[0]

    return PortfolioSummary(
        **{
            "totalValue":           round(total_value, 2),
            "dailyPnL":             round(daily_pnl, 2),
            "dailyPnLPercent":      round(daily_pnl_pct, 4),
            "todayTradesCount":     today_trades_count,
            "activePositionsCount": active_positions,
        }
    )


# ── 2. History ────────────────────────────────────────────────────────────────

@router.get(
    "/history",
    response_model=list[PortfolioHistoryPoint],
    response_model_by_alias=True,
)
async def get_portfolio_history(
    days: int = Query(default=90, ge=1, le=3650),
    price_svc: PriceService = Depends(get_price_service),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[PortfolioHistoryPoint]:
    rows = await _latest_history_dates(db, days)
    if not rows:
        return []

    dates = [r[0] for r in rows]
    sl20_map = price_svc.get_sl20_index_series(dates)

    return [
        PortfolioHistoryPoint(
            **{
                "date":      r[0],
                "value":     round(r[1], 2),
                "sl20Index": sl20_map.get(r[0], 0.0),
            }
        )
        for r in rows
    ]


# ── 3. Positions ──────────────────────────────────────────────────────────────

@router.get(
    "/positions",
    response_model=list[Position],
    response_model_by_alias=True,
)
async def get_positions(
    price_svc: PriceService = Depends(get_price_service),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[Position]:
    cur = await db.execute(
        "SELECT ticker, shares, avg_buy_price FROM positions ORDER BY ticker"
    )
    rows = await cur.fetchall()
    if not rows:
        return []

    # Total portfolio value for weight calculation
    cash = await _get_cash(db)
    total_value = cash + sum(
        (price_svc.get_latest_close(r[0]) or r[2]) * r[1] for r in rows
    )

    result = []
    for ticker, shares, avg_buy in rows:
        current_price = price_svc.get_latest_close(ticker) or avg_buy
        cost_basis    = avg_buy * shares
        mkt_value     = current_price * shares
        unrealized    = mkt_value - cost_basis
        unrealized_pct = (unrealized / cost_basis * 100) if cost_basis else 0.0
        weight         = (mkt_value / total_value * 100) if total_value else 0.0
        info = get_stock_info(ticker)
        result.append(
            Position(
                **{
                    "ticker":               ticker,
                    "name":                 info.name if info else ticker,
                    "shares":               shares,
                    "avgBuyPrice":          round(avg_buy, 4),
                    "currentPrice":         round(current_price, 4),
                    "unrealizedPnL":        round(unrealized, 2),
                    "unrealizedPnLPercent": round(unrealized_pct, 4),
                    "positionWeight":       round(weight, 4),
                }
            )
        )
    return result


# ── 4. Trades ─────────────────────────────────────────────────────────────────

@router.get(
    "/trades",
    response_model=list[Trade],
    response_model_by_alias=True,
)
async def get_trades(
    limit: int = Query(default=50, ge=1, le=500),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[Trade]:
    cur = await db.execute(
        "SELECT date, ticker, action, quantity, price, reason FROM trades ORDER BY date DESC, id DESC LIMIT ?",
        (limit,),
    )
    rows = await cur.fetchall()
    return [
        Trade(date=r[0], ticker=r[1], action=r[2], quantity=r[3], price=r[4], reason=r[5])
        for r in rows
    ]


# ── 5. Metrics ────────────────────────────────────────────────────────────────

@router.get(
    "/metrics",
    response_model=PerformanceMetrics,
    response_model_by_alias=True,
)
async def get_metrics(
    db: aiosqlite.Connection = Depends(get_db),
) -> PerformanceMetrics:
    cur = await db.execute(
        "SELECT date, value FROM portfolio_history ORDER BY date"
    )
    history = await cur.fetchall()

    if not history:
        return PerformanceMetrics(
            **{"sharpeRatio": 0.0, "maxDrawdown": 0.0, "totalReturn": 0.0, "winRate": 0.0}
        )

    values = [r[1] for r in history]

    # ── Total return ──────────────────────────────────────────────────────────
    total_return = (values[-1] - values[0]) / values[0] * 100 if values[0] else 0.0

    # ── Max drawdown (rolling peak → min trough) ──────────────────────────────
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (v - peak) / peak
        if dd < max_dd:
            max_dd = dd

    # ── Sharpe ratio (annualised) ─────────────────────────────────────────────
    daily_returns = [
        (values[i] - values[i - 1]) / values[i - 1]
        for i in range(1, len(values))
        if values[i - 1] != 0
    ]
    if len(daily_returns) >= 2:
        n = len(daily_returns)
        mean_r = sum(daily_returns) / n
        variance = sum((r - mean_r) ** 2 for r in daily_returns) / (n - 1)
        std_r = math.sqrt(variance) if variance > 0 else 0.0
        sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0
    else:
        sharpe = 0.0

    # ── Win rate (SELL trades where sell price > avg buy price for that ticker)
    cur = await db.execute(
        "SELECT ticker, AVG(price) FROM trades WHERE action='BUY' GROUP BY ticker"
    )
    avg_buy_by_ticker: dict[str, float] = {r[0]: r[1] for r in await cur.fetchall()}

    cur = await db.execute(
        "SELECT ticker, price FROM trades WHERE action='SELL'"
    )
    sell_rows = await cur.fetchall()

    wins = sum(
        1 for tkr, sp in sell_rows
        if tkr in avg_buy_by_ticker and sp > avg_buy_by_ticker[tkr]
    )
    win_rate = (wins / len(sell_rows) * 100) if sell_rows else 0.0

    return PerformanceMetrics(
        **{
            "sharpeRatio": round(sharpe, 4),
            "maxDrawdown": round(max_dd, 4),
            "totalReturn": round(total_return, 4),
            "winRate":     round(win_rate, 4),
        }
    )
