"""
Portfolio service — paper-trading backtest simulator.

Rules (SPEC Section 9):
  - Max 10 % of current portfolio value per ticker
  - >= LKR 50 000 cash buffer always retained
  - Total daily deployment <= 70 % of available cash (above buffer)
  - BUY only when ticker NOT already held; SELL clears the full position
  - Reason strings:
      BUY  → "Model BUY signal: P50 predicted +X.XX%"
      SELL → "Model SELL signal: P50 predicted -X.XX%"
"""
import logging
import math
from typing import Optional

import aiosqlite

from app.db.database import _db_path
from app.services.price_service import get_price_service

logger = logging.getLogger(__name__)

INITIAL_CASH     = 1_000_000.0
MAX_POS_PCT      = 0.10   # max 10 % of portfolio value per ticker
CASH_BUFFER      = 50_000.0   # minimum cash always retained
DAILY_DEPLOY_PCT = 0.70   # max 70 % of available cash deployed per day


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _trades_empty(db: aiosqlite.Connection) -> bool:
    cur = await db.execute("SELECT COUNT(*) FROM trades")
    (n,) = await cur.fetchone()
    return n == 0


async def _preds_for_date(db: aiosqlite.Connection, date: str) -> dict[str, dict]:
    """Return {ticker: {p50, signal}} for all tickers on `date`."""
    cur = await db.execute(
        "SELECT ticker, p50, signal FROM predictions WHERE date=?", (date,)
    )
    rows = await cur.fetchall()
    return {r[0]: {"p50": r[1], "signal": r[2]} for r in rows}


# ── Main simulator ────────────────────────────────────────────────────────────

async def simulate_backtest(
    trading_dates: list[str],
    initial_cash: float = INITIAL_CASH,
) -> dict:
    """
    Walk `trading_dates` day-by-day applying BUY/SELL signals stored in the
    predictions table.  Writes to trades, positions, portfolio_history tables.

    Idempotent: clears the three tables before writing.
    Returns a summary dict.
    """
    price_svc = get_price_service()

    cash = initial_cash
    # {ticker: {"shares": float, "avg_buy_price": float, "opened_date": str}}
    positions: dict[str, dict] = {}

    trades_n   = 0
    history_n  = 0

    async with aiosqlite.connect(_db_path()) as db:
        # Idempotent reset
        await db.execute("DELETE FROM trades")
        await db.execute("DELETE FROM positions")
        await db.execute("DELETE FROM portfolio_history")
        await db.commit()

        for date in trading_dates:
            # 1 ── Predictions for today
            preds = await _preds_for_date(db, date)

            # 2 ── Mark-to-market portfolio value at today's close
            portfolio_value = cash
            for tkr, pos in positions.items():
                px = price_svc.get_close_on_date(tkr, date)
                if px:
                    portfolio_value += pos["shares"] * px

            # 3 ── Daily cash budget
            avail       = cash - CASH_BUFFER          # cash we can actually touch
            daily_cap   = avail * DAILY_DEPLOY_PCT    # cap for today
            deployed    = 0.0

            # 4 ── Apply signals (BUY first, then SELL so sells free cash for buys on same day)
            sells = [(t, p) for t, p in preds.items() if p["signal"] == "SELL" and t in positions]
            buys  = [(t, p) for t, p in preds.items() if p["signal"] == "BUY"  and t not in positions]

            # --- SELL ---
            for ticker, pred in sells:
                pos    = positions.pop(ticker)
                shares = pos["shares"]
                px     = price_svc.get_close_on_date(ticker, date)
                if px is None:
                    positions[ticker] = pos   # restore if no price
                    continue
                cash  += shares * px
                pct    = (pred["p50"] - px) / px * 100
                reason = f"Model SELL signal: P50 predicted {pct:+.2f}%"
                await db.execute(
                    "INSERT INTO trades (date,ticker,action,quantity,price,reason) VALUES(?,?,?,?,?,?)",
                    (date, ticker, "SELL", shares, px, reason),
                )
                trades_n += 1

            # Recompute available cash after sells
            avail     = cash - CASH_BUFFER
            daily_cap = avail * DAILY_DEPLOY_PCT

            # --- BUY ---
            for ticker, pred in buys:
                if deployed >= daily_cap or avail - deployed < 0:
                    break
                px = price_svc.get_close_on_date(ticker, date)
                if px is None or px <= 0:
                    continue

                max_pos_val   = portfolio_value * MAX_POS_PCT
                room_in_cap   = daily_cap - deployed
                room_in_cash  = avail - deployed
                trade_value   = min(max_pos_val, room_in_cap, room_in_cash)

                if trade_value < px:
                    continue   # can't afford even 1 share

                shares = math.floor(trade_value / px)
                if shares <= 0:
                    continue

                cost      = shares * px
                cash     -= cost
                deployed += cost
                positions[ticker] = {
                    "shares": shares,
                    "avg_buy_price": px,
                    "opened_date": date,
                }
                pct    = (pred["p50"] - px) / px * 100
                reason = f"Model BUY signal: P50 predicted {pct:+.2f}%"
                await db.execute(
                    "INSERT INTO trades (date,ticker,action,quantity,price,reason) VALUES(?,?,?,?,?,?)",
                    (date, ticker, "BUY", shares, px, reason),
                )
                trades_n += 1

            # 5 ── End-of-day portfolio value (mark-to-market again after trades)
            eod_value = cash
            for tkr, pos in positions.items():
                px = price_svc.get_close_on_date(tkr, date)
                if px:
                    eod_value += pos["shares"] * px

            await db.execute(
                "INSERT OR IGNORE INTO portfolio_history (date, value) VALUES (?,?)",
                (date, eod_value),
            )
            history_n += 1

        # 6 ── Persist final open positions
        for ticker, pos in positions.items():
            await db.execute(
                "INSERT OR REPLACE INTO positions (ticker, shares, avg_buy_price, opened_date) VALUES(?,?,?,?)",
                (ticker, pos["shares"], pos["avg_buy_price"], pos["opened_date"]),
            )

        await db.commit()

    logger.info(
        "portfolio: backtest complete — %d trades | %d history rows | %d open positions | cash=LKR %.2f",
        trades_n, history_n, len(positions), cash,
    )
    return {
        "trades":         trades_n,
        "history_rows":   history_n,
        "open_positions": len(positions),
        "final_cash":     cash,
    }
