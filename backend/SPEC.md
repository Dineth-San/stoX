# stoX Backend — Complete Specification

---

## 1. Overview

The backend has three jobs:

1. **Serve ML predictions** — run `ml/predict.py` (or call the model directly) for each of the 20 SL20 tickers and expose the results via REST endpoints
2. **Run the paper trading simulator** — implement a simple rule-based simulator that converts BUY/HOLD/SELL signals into virtual trades and tracks a portfolio
3. **Serve supporting data** — price history, stock info, market movers, and placeholder news

---

## 2. Build Plan — Iterations (FOLLOW THIS)

Sections 3 onward are the **reference** for *what* to build. This section is the **execution order** — eleven small, testable iterations that take the backend from an empty folder to a fully wired API the frontend can consume. Each iteration ends with a concrete acceptance check; do not advance until the check passes.

### Ground rules (apply to every iteration)

- **Scope:** all work happens inside `backend/`. Do not edit `frontend/`, `ml/`, or `docs/` without explicit user approval — see *External Touch-Points* below.
- **Always-green dev server:** run `uvicorn main:app --reload --port 8000` after every iteration. If it can't boot, the iteration is not done.
- **Contract conformance:** every JSON response must match the TypeScript types in `../frontend/app/src/lib/api/types.ts` exactly — same field names, same types, same nullability. camelCase aliases on every Pydantic model + `response_model_by_alias=True` on every route.
- **One environment:** reuse the existing `ml/` Python interpreter so `import torch`, `pytorch_forecasting`, etc. work without a fresh venv.
- **No new dependencies** beyond Section 20 unless the user approves.
- **Commit per iteration:** one logical commit per iteration with a message like `feat(backend): iteration N — <name>`. Easier to revert and review.

### External touch-points (must be confirmed before they are crossed)

These are the only points where the backend interacts with code outside `backend/`. Iterations that hit them must **pause and ask the user** before modifying anything external.

| # | External artifact | Backend interaction | Iteration | Status |
|---|---|---|---|---|
| A | `ml/predict.py` → `run_inference(ticker, date)` | Import & call | 6 | ✅ Already exists at `ml/predict.py:184`. No edit required unless the signature differs from Section 19. If it does, **stop and ask**. |
| B | `ml/data/features/sl20_feature_panel.parquet` | Read-only `pd.read_parquet` | 4 | Read-only. Never write. |
| C | `ml/models/tft_v1/best-v1.ckpt` | Loaded transitively by `run_inference` | 6 | Read-only. Never write. |
| D | `ml/models/tft_v1/model_config.json` | Read once at startup for `directionalAccuracy` / `meanError` | 5 | Read-only. |
| E | `frontend/app/.env.local` | Must be flipped to `NEXT_PUBLIC_USE_MOCK=false`, `NEXT_PUBLIC_API_URL=http://localhost:8000` | 10 | **User action.** The backend never edits frontend env. |
| F | `frontend/app/src/lib/api/types.ts` | Read-only reference | All | If a shape needs to change, surface it; **do not edit** the frontend. |

If anything in this table needs to change beyond what's marked, stop the iteration and ask the user explicitly.

---

### Iteration 0 — Project skeleton (≈30 min)

**Goal:** a boot-able FastAPI app with no business logic.

Create:
- `backend/requirements.txt` — content from Section 20
- `backend/.env.example` and `backend/.env` — content from Section 4
- `backend/.gitignore` — entries: `.env`, `stox.db`, `__pycache__/`, `*.pyc`, `.pytest_cache/`
- `backend/main.py` — minimal app + CORS middleware + `GET /health` returning `{"status": "ok"}`
- `backend/app/__init__.py`
- `backend/app/config.py` — `pydantic_settings.BaseSettings` reading `ML_DIR`, `DB_PATH`, `CORS_ORIGINS`, `USE_MOCK_PREDICTIONS`
- Empty `__init__.py` in every sub-package: `app/models/`, `app/routers/`, `app/services/`, `app/db/`, `tests/`

**Acceptance:**
- `uvicorn main:app --reload --port 8000` boots without errors.
- `curl http://localhost:8000/health` → 200 `{"status":"ok"}`.
- `http://localhost:8000/docs` renders Swagger UI.
- `curl -H "Origin: http://localhost:3000" -i http://localhost:8000/health` shows `access-control-allow-origin: http://localhost:3000`.

---

### Iteration 1 — Pydantic response models (≈30 min)

**Goal:** every JSON shape the frontend consumes exists as a typed model.

Create exactly as in Section 5:
- `app/models/stocks.py` — `PricePoint`, `StockPrediction`, `StockInfo`, `StockKeyStats`
- `app/models/portfolio.py` — `Position`, `Trade`, `PortfolioSummary`, `PortfolioHistoryPoint`, `PerformanceMetrics`
- `app/models/news.py` — `NewsItem`, `MarketMover`

Every model uses `model_config = ConfigDict(populate_by_name=True)` and camelCase `Field(alias=...)`.

**Acceptance:**
- `python -c "from app.models.stocks import *; from app.models.portfolio import *; from app.models.news import *"` succeeds.
- For each model: `M(**sample).model_dump(by_alias=True)` produces camelCase keys; `M(**sample).model_dump()` produces snake_case.

---

### Iteration 2 — Database layer (≈45 min)

**Goal:** SQLite is created on startup with the four tables.

Create:
- `app/db/schema.sql` — exact DDL from Section 7
- `app/db/database.py` — `aiosqlite` connection helper (`get_db()` FastAPI dependency, `init_db()` that executes `schema.sql`)
- `app/db/seed.py` — placeholder `async def seed_if_empty()` that is currently a no-op
- Wire `init_db()` + `seed_if_empty()` into the `lifespan` in `main.py` (Section 12)

**Acceptance:**
- Delete `stox.db`, restart server: file is recreated.
- `sqlite3 stox.db ".tables"` lists `predictions`, `portfolio_history`, `positions`, `trades`.
- Restarting twice does not error (idempotent — schema uses `CREATE TABLE IF NOT EXISTS`).

---

### Iteration 3 — News + static stock info (≈45 min)

**Goal:** the two endpoints that need neither parquet nor model are live.

Create:
- `app/services/news_service.py` — embed the 20 items from Section 11 as `NEWS_ITEMS`
- `app/services/stock_info_service.py` — embed `STOCK_INFO` and `STOCK_KEY_STATS_STATIC` from Section 10
- `app/routers/news.py` — `GET /news` → `List[NewsItem]`
- `app/routers/stocks.py` (stub) — `GET /stocks/{ticker}/info` → `StockInfo`, 404 if ticker unknown
- Wire both routers into `main.py`

**Acceptance:**
- `GET /news` returns exactly 20 items with camelCase keys (`isLocal`, `timeAgo`).
- `GET /stocks/JKH/info` returns the JKH blurb; `GET /stocks/UNKNOWN/info` → 404.
- Sentiment values are strictly one of `"Positive"`, `"Neutral"`, `"Negative"`.

---

### Iteration 4 — Price service + history / stats / movers (≈1 h)

**Goal:** anything the feature panel can answer is wired up.

Create:
- `app/services/price_service.py` (Section 15)
  - Loads `sl20_feature_panel.parquet` once at startup
  - `get_price_history(ticker, days)` → last N rows with `date`, `close`
  - `get_52w_stats(ticker)` → `high52w`, `low52w`, `avgVolume`
  - `get_market_movers()` → top 5 by `abs(changePercent)`
- Extend `app/routers/stocks.py`:
  - `GET /stocks/{ticker}/history?days=N` — predicted columns set to actual close until Iteration 6 fills them in
  - `GET /stocks/{ticker}/stats` — merge dynamic 52w with static market cap / P/E
- Create `app/routers/market.py` — `GET /market/movers`

**Acceptance:**
- `GET /stocks/JKH/history?days=30` returns 30 `PricePoint`s with valid ISO dates.
- `GET /stocks/JKH/stats` returns numeric `high52w`, `low52w`, `avgVolume`, `marketCap`; `peRatio` is numeric or null (null only for BUKI, VONE per Section 10).
- `GET /market/movers` returns 5 items sorted by `abs(changePercent)` descending.

---

### Iteration 5 — Prediction service in MOCK mode (≈1 h)

**Goal:** `/stocks` and `/stocks/{ticker}/prediction` work end-to-end without invoking the TFT model.

Create:
- `app/services/prediction_service.py` with two code paths gated on `settings.use_mock_predictions`:
  - **Mock path:** deterministic synthetic P10/P50/P90 derived from last close (e.g. `-1.5 %`, `+0.3 %`, `+1.5 %`) — instant, no model load
  - **Real path:** `raise NotImplementedError` (filled in next iteration)
- DB cache read-through against the `predictions` table; insert mock rows on first call (`UNIQUE(date, ticker)` enforces idempotency)
- Signal derivation (`derive_signal` from Section 6)
- Per-ticker `directionalAccuracy` and `meanError`: load once from `ml/models/tft_v1/model_config.json` at startup; if the file is missing or doesn't include per-ticker metrics, fall back to a hardcoded constant (e.g. 0.55 / 0.018) so the contract still serialises
- Extend `app/routers/stocks.py`:
  - `GET /stocks` — predictions for all 20 tickers with 30-day sparkline, sorted alphabetically
  - `GET /stocks/{ticker}/prediction` — single ticker, 404 if unknown

**Acceptance:**
- `GET /stocks` returns 20 items, alphabetically sorted, every field present and camelCase.
- `predictedChangePercent` equals `(p50 - lastClose) / lastClose * 100` to 4 decimal places.
- Second consecutive request returns identical numbers (cache hit).
- Set `USE_MOCK_PREDICTIONS=true` in `.env` for this iteration; default remains `false`.

---

### Iteration 6 — Real model integration (≈1.5 h)

**Goal:** replace mock predictions with real TFT output, cached aggressively.

Tasks:
- Implement the real path in `prediction_service.py` (Section 14 + Section 19):
  ```python
  sys.path.insert(0, str(ml_dir / "src"))
  sys.path.insert(0, str(ml_dir))
  from predict import run_inference
  ```
- Cold-start prefill in `seed.py`: if `predictions` has no row for today, call `run_inference()` once (returns all 20 tickers) and bulk-insert.
- Backfill the last 90 trading days of predictions — required so `/stocks/{ticker}/history` can show predicted P10/P50/P90 alongside actual close. Skip dates the model can't produce (< 60 prior trading days); leave those rows null and the history endpoint will substitute the close.
- Update `/stocks/{ticker}/history` to read predicted columns from the `predictions` table; fall back to close where missing (per Section 6).
- Add a startup log line showing prefill progress (`prefilled 20 predictions for 2026-05-17 in 24.3s`).
- Switch `USE_MOCK_PREDICTIONS` default back to `false`.

**Touch-point gate:** `run_inference` exists at `ml/predict.py:184`. If its return shape or signature differs from Section 19 (`list[dict]` with `ticker`, `as_of_date`, `last_close`, `p10`, `p50`, `p90`, `implied_ret`), **stop and ask the user before editing `ml/predict.py`**.

**Acceptance:**
- Cold start log shows "prefilled N predictions" within ~60 s.
- `GET /stocks` returns identical values across two consecutive requests (cache hit, < 50 ms warm).
- `GET /stocks/JKH/history?days=90` shows non-trivial predicted columns (≠ close) for the most recent ~30 days.
- Toggling `USE_MOCK_PREDICTIONS=true` falls back cleanly without crashing.

---

### Iteration 7 — Paper trading simulator (≈1.5 h)

**Goal:** portfolio tables are populated with 90 days of plausible history.

Create `app/services/portfolio_service.py`:
- `simulate_backtest(start_date, initial_cash=1_000_000)` — walks day by day applying Section 9 rules
- Position sizing constraints:
  - Max 10 % of portfolio value per ticker
  - ≥ LKR 50 000 cash buffer always retained
  - Total daily deployment ≤ 70 % of cash
- Emits trades, positions, and `portfolio_history` rows into SQLite
- Reason strings exact: `"Model BUY signal: P50 predicted +X.XX%"` / `"Model SELL signal: P50 predicted -X.XX%"`

Extend `seed.py`:
- After Iteration 6 prefill, if `trades` table is empty, call `simulate_backtest(today - 90 trading days)`.

**Acceptance:**
- `sqlite3 stox.db "SELECT COUNT(*) FROM portfolio_history"` ≥ 60 (90 calendar days minus weekends).
- `SELECT SUM(shares * avg_buy_price) FROM positions` is positive and `< 1_000_000`.
- At least one BUY and at least one SELL exist in `trades`.
- No position exceeds 10 % of starting capital on its opening date.

---

### Iteration 8 — Portfolio endpoints (≈1 h)

**Goal:** all five `/portfolio/*` endpoints serve the seeded data.

Create `app/routers/portfolio.py` with the five endpoints from Section 6:
- `GET /portfolio/summary` — sum positions, compare today vs yesterday, count today's trades
- `GET /portfolio/history?days=N` — join `portfolio_history` with `sl20_index` from the feature panel (any ticker's row — value is identical across tickers per Section 15)
- `GET /portfolio/positions` — enrich each position with current price + `unrealizedPnL` + `unrealizedPnLPercent` + `positionWeight`
- `GET /portfolio/trades?limit=N` — `ORDER BY date DESC`
- `GET /portfolio/metrics` — `totalReturn`, `maxDrawdown` (rolling-peak), `sharpeRatio` (`mean / std * sqrt(252)`), `winRate` (matched SELL > matching BUY price)

**Acceptance:**
- All five endpoints return 200 with shapes matching Section 5.
- `summary.totalValue` ≈ Σ(positions.currentPrice × shares) + remaining cash (within 1 %).
- `history?days=30` returns exactly 30 items, each with a numeric `sl20Index`.
- `metrics.sharpeRatio` is finite; `winRate ∈ [0, 100]`; `maxDrawdown ≤ 0`.

---

### Iteration 9 — Tests (≈1 h)

**Goal:** a `pytest` run protects every endpoint contract.

Create:
- `tests/conftest.py` — `httpx.AsyncClient` fixture against the app (use `httpx.ASGITransport(app=app)`)
- `tests/test_stocks.py`
  - `/stocks` returns 20 items, every ticker in `SL20_TICKERS`
  - Each item has camelCase keys matching `StockPrediction`
  - Unknown ticker → 404 on `/prediction`, `/info`, `/stats`, `/history`
  - `signal ∈ {"BUY", "HOLD", "SELL"}`
- `tests/test_portfolio.py`
  - Summary fields are numeric and present
  - `/history?days=30` returns 30 items, each with `sl20Index` numeric
  - Positions list `currentPrice × shares` sums to ~`totalValue` (within 5 %)
- `tests/test_news.py`
  - Exactly 20 items
  - Required fields present
  - `sentiment ∈ {"Positive", "Neutral", "Negative"}`
- `tests/test_market.py`
  - 5 movers, sorted by `abs(changePercent)` DESC

**Acceptance:** `pytest tests/ -v` → all green. Coverage target ≥ 70 % on `app/routers/`.

---

### Iteration 10 — Frontend handshake & polish (≈45 min)

**Goal:** the frontend renders every page without mocks.

Tasks (backend side only):
- Walk through each endpoint in Swagger at `http://localhost:8000/docs`; diff field names against `frontend/app/src/lib/api/types.ts` line by line.
- Add `backend/README.md` covering: setup, env vars, run command, common pitfalls (cold start time, parquet path, predict.py path).
- Confirm no endpoint exceeds 1 s on a warm cache; if any does, add a TODO with the bottleneck.

**User action required (not a backend edit):**
- Set in `D:\stox\frontend\app\.env.local`:
  ```
  NEXT_PUBLIC_USE_MOCK=false
  NEXT_PUBLIC_API_URL=http://localhost:8000
  ```
- Restart `npm run dev` in `frontend/app/`.
- **Backend will NOT edit this file.** Surface it to the user as a manual handoff step.

**Acceptance:**
- User flips `NEXT_PUBLIC_USE_MOCK=false`, restarts the Next dev server, and the dashboard / predictions / portfolio / news pages render with real backend data and zero console errors.

---

### Out-of-backend changes the user must approve

At time of writing, none are strictly required. Listed here as a checklist so nothing silently breaks the handoff.

| # | File | Change | Triggered by |
|---|------|--------|--------------|
| A | `frontend/app/.env.local` | Set `NEXT_PUBLIC_USE_MOCK=false`, `NEXT_PUBLIC_API_URL=http://localhost:8000` | Iteration 10 |
| B | `ml/predict.py` | None expected — `run_inference` already at line 184. Only edit if signature diverges from Section 19. | Iteration 6 (gate) |
| C | `ml/data/features/sl20_feature_panel.parquet` | None (read-only) | — |
| D | `ml/models/tft_v1/*` | None (read-only) | — |
| E | `frontend/app/src/lib/api/types.ts` | None — backend conforms to this contract | — |

If any row in the "Change" column turns out to be needed, **stop and ask the user before editing**.

---

## 3. Folder Structure

Create this inside `backend/`:

```
backend/
├── CLAUDE.md                  ← Already exists
├── SPEC.md                    ← This file
├── main.py                    ← FastAPI app entry point (uvicorn target)
├── .env                       ← Local env vars (not committed)
├── .env.example               ← Template (committed)
├── requirements.txt           ← Python deps
├── pyproject.toml             ← (optional) if using uv/poetry
│
├── app/
│   ├── __init__.py
│   ├── config.py              ← Settings (reads .env, paths to ML model/data)
│   ├── models/                ← Pydantic response models (mirror types.ts)
│   │   ├── __init__.py
│   │   ├── stocks.py
│   │   ├── portfolio.py
│   │   └── news.py
│   ├── routers/               ← FastAPI routers, one file per domain
│   │   ├── __init__.py
│   │   ├── stocks.py          ← /stocks, /stocks/{ticker}/...
│   │   ├── portfolio.py       ← /portfolio/...
│   │   ├── news.py            ← /news
│   │   └── market.py          ← /market/movers
│   ├── services/              ← Business logic
│   │   ├── __init__.py
│   │   ├── prediction_service.py   ← Loads model, runs inference, caches results
│   │   ├── portfolio_service.py    ← Paper trading simulator
│   │   ├── price_service.py        ← Reads price history from feature panel
│   │   └── news_service.py         ← Serves static news fixtures
│   └── db/
│       ├── __init__.py
│       ├── database.py        ← SQLite setup (aiosqlite)
│       ├── schema.sql         ← Table definitions
│       └── seed.py            ← Populates DB on first run
│
└── tests/
    ├── test_stocks.py
    ├── test_portfolio.py
    └── test_news.py
```

---

## 4. Environment Config

**`.env.example`:**
```
# Path to the ml/ directory (absolute or relative to backend/)
ML_DIR=../ml

# SQLite database path
DB_PATH=./stox.db

# Allowed frontend origin
CORS_ORIGINS=http://localhost:3000

# Run in mock mode (no model calls, use pre-seeded DB only)
USE_MOCK_PREDICTIONS=false
```

**`app/config.py`** should use `pydantic_settings.BaseSettings` to load these.

---

## 5. Pydantic Response Models

These must **exactly mirror** the TypeScript types in `../frontend/app/src/lib/api/types.ts`.

All models use `model_config = ConfigDict(populate_by_name=True)` and camelCase aliases.

### `app/models/stocks.py`

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class PricePoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    date: str
    close: float
    predicted_p10: float = Field(alias="predictedP10")
    predicted_p50: float = Field(alias="predictedP50")
    predicted_p90: float = Field(alias="predictedP90")

class StockPrediction(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    ticker: str
    name: str
    sector: str
    last_close: float = Field(alias="lastClose")
    predicted_p10: float = Field(alias="predictedP10")
    predicted_p50: float = Field(alias="predictedP50")
    predicted_p90: float = Field(alias="predictedP90")
    predicted_change_percent: float = Field(alias="predictedChangePercent")
    signal: str                          # 'BUY' | 'HOLD' | 'SELL'
    sparkline: list[PricePoint]          # last 30 days of history
    directional_accuracy: float = Field(alias="directionalAccuracy")
    mean_error: float = Field(alias="meanError")

class StockInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    ticker: str
    name: str
    sector: str
    blurb: str

class StockKeyStats(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    high_52w: float = Field(alias="high52w")
    low_52w: float = Field(alias="low52w")
    avg_volume: float = Field(alias="avgVolume")
    market_cap: float = Field(alias="marketCap")
    pe_ratio: Optional[float] = Field(alias="peRatio", default=None)
```

### `app/models/portfolio.py`

```python
class Position(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    ticker: str
    name: str
    shares: float
    avg_buy_price: float = Field(alias="avgBuyPrice")
    current_price: float = Field(alias="currentPrice")
    unrealized_pnl: float = Field(alias="unrealizedPnL")
    unrealized_pnl_percent: float = Field(alias="unrealizedPnLPercent")
    position_weight: float = Field(alias="positionWeight")

class Trade(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    date: str
    ticker: str
    action: str                           # 'BUY' | 'SELL'
    quantity: float
    price: float
    reason: str

class PortfolioSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    total_value: float = Field(alias="totalValue")
    daily_pnl: float = Field(alias="dailyPnL")
    daily_pnl_percent: float = Field(alias="dailyPnLPercent")
    today_trades_count: int = Field(alias="todayTradesCount")
    active_positions_count: int = Field(alias="activePositionsCount")

class PortfolioHistoryPoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    date: str
    value: float
    sl20_index: float = Field(alias="sl20Index")

class PerformanceMetrics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    sharpe_ratio: float = Field(alias="sharpeRatio")
    max_drawdown: float = Field(alias="maxDrawdown")
    total_return: float = Field(alias="totalReturn")
    win_rate: float = Field(alias="winRate")
```

### `app/models/news.py`

```python
class NewsItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    source: str
    is_local: bool = Field(alias="isLocal")
    headline: str
    url: str
    sentiment: str                        # 'Positive' | 'Neutral' | 'Negative'
    time_ago: str = Field(alias="timeAgo")

class MarketMover(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    ticker: str
    name: str
    price: float
    change_percent: float = Field(alias="changePercent")
```

---

## 6. All 12 Endpoints

Use `response_model_by_alias=True` on every endpoint so FastAPI serialises with camelCase aliases.

### Stocks

#### `GET /stocks`
Returns predictions for all 20 SL20 tickers.

```
Response: List[StockPrediction]
```

Logic:
1. For each of the 20 tickers, call `prediction_service.get_latest_prediction(ticker)`
2. Fetch last 30 days of price history per ticker for the sparkline
3. Compute `predictedChangePercent = (p50 - lastClose) / lastClose * 100`
4. Derive signal using the rule below
5. Return list sorted alphabetically by ticker

**Signal derivation rule:**
```python
def derive_signal(predicted_change_percent: float) -> str:
    if predicted_change_percent > 0.5:
        return "BUY"
    elif predicted_change_percent < -0.5:
        return "SELL"
    else:
        return "HOLD"
```

---

#### `GET /stocks/{ticker}/prediction`
Returns prediction for a single ticker.

```
Path param: ticker (e.g. "JKH")
Response: StockPrediction
404 if ticker not in SL20 list
```

Same logic as above but for one ticker.

---

#### `GET /stocks/{ticker}/history`
Returns price history for chart rendering.

```
Query params: days (int, default 90)
Response: List[PricePoint]
```

Logic:
1. Read from the feature panel (`sl20_feature_panel.parquet`) filtered to the ticker
2. Return the last `days` rows with columns: date, close, predictedP10, predictedP50, predictedP90
3. The predicted columns for historical dates come from `db: predictions` table (what the model *would have* predicted — pre-computed during seeding). For dates where no prediction exists, set all three predicted values to the actual close.

---

#### `GET /stocks/{ticker}/info`
Returns static company info.

```
Response: StockInfo
```

This is fully static — hardcode a lookup dict for all 20 tickers. See Section 10 for the data.

---

#### `GET /stocks/{ticker}/stats`
Returns key stats for the sidebar.

```
Response: StockKeyStats
```

Logic:
1. Read 1-year window from feature panel for the ticker
2. Compute: `high52w = max(close)`, `low52w = min(close)`, `avgVolume = mean(volume)`
3. `marketCap` and `peRatio` — hardcode reasonable estimates per ticker (see Section 10). These are not dynamically computable from our data.

---

### Portfolio

#### `GET /portfolio/summary`
Returns current portfolio snapshot.

```
Response: PortfolioSummary
```

Logic:
1. Sum current values of all open positions → `totalValue`
2. Compare today's value to yesterday's → `dailyPnL`, `dailyPnLPercent`
3. Count trades with date = today → `todayTradesCount`
4. Count rows in `positions` table → `activePositionsCount`

---

#### `GET /portfolio/history`
Returns portfolio value over time vs SL20 index.

```
Query params: days (int, default 90)
Response: List[PortfolioHistoryPoint]
```

Logic: Read from `portfolio_history` table in SQLite, join SL20 index value for each date. The SL20 index values come from `sl20_index` column in the feature panel (any ticker's row — it's the same for all).

---

#### `GET /portfolio/positions`
Returns current open positions.

```
Response: List[Position]
```

Logic:
1. Read `positions` table from SQLite
2. For each position, fetch current price from latest prediction
3. Compute `unrealizedPnL = (currentPrice - avgBuyPrice) * shares`
4. Compute `unrealizedPnLPercent = (currentPrice - avgBuyPrice) / avgBuyPrice * 100`
5. Compute `positionWeight = positionValue / totalPortfolioValue * 100`

---

#### `GET /portfolio/trades`
Returns recent trade log.

```
Query params: limit (int, default 10)
Response: List[Trade]
```

Logic: Read from `trades` table, ORDER BY date DESC, LIMIT limit.

---

#### `GET /portfolio/metrics`
Returns aggregate performance metrics.

```
Response: PerformanceMetrics
```

Logic (computed from `portfolio_history` table):
- `totalReturn = (currentValue - initialValue) / initialValue * 100`
- `maxDrawdown` — rolling peak drawdown (standard finance formula)
- `sharpeRatio` — annualised: `(mean_daily_return / std_daily_return) * sqrt(252)`
- `winRate` — from `trades` table: % of SELL trades where `sell_price > buy_price`

---

### News

#### `GET /news`
Returns news feed.

```
Response: List[NewsItem]
```

News is **static mock data** for this version. The sentiment model is deferred.

Return 20 hardcoded news items from `news_service.py`. Items should look realistic:
- Sources: EconomyNext, Daily FT, LBO, Reuters
- Mix of isLocal: true (60%) and false (40%)
- Mix of sentiments: Positive, Neutral, Negative
- Headlines relevant to Sri Lanka equities / macro
- URLs pointing to the real news source domains (don't fabricate specific article URLs — use the homepage as placeholder: `https://economynext.com`, etc.)
- `timeAgo`: relative strings like `"2h ago"`, `"5h ago"`, `"1d ago"`

---

### Market

#### `GET /market/movers`
Returns top 5 biggest movers today.

```
Response: List[MarketMover]
```

Logic:
1. For each of the 20 tickers, compute `changePercent = (todayClose - yesterdayClose) / yesterdayClose * 100`
2. Sort by abs(changePercent) DESC, return top 5

---

## 7. SQLite Database Schema

File: `stox.db` (created on startup if not exists)

```sql
-- Predictions cache (avoids re-running inference on every request)
CREATE TABLE IF NOT EXISTS predictions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    p10         REAL NOT NULL,
    p50         REAL NOT NULL,
    p90         REAL NOT NULL,
    signal      TEXT NOT NULL,
    model_ver   TEXT NOT NULL DEFAULT 'tft_v1',
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(date, ticker)
);

-- Paper trading portfolio history (90+ days, one row per date)
CREATE TABLE IF NOT EXISTS portfolio_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL UNIQUE,
    value       REAL NOT NULL
);

-- Current open positions
CREATE TABLE IF NOT EXISTS positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL UNIQUE,
    shares          REAL NOT NULL,
    avg_buy_price   REAL NOT NULL,
    opened_date     TEXT NOT NULL
);

-- Trade log
CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    action      TEXT NOT NULL,   -- 'BUY' or 'SELL'
    quantity    REAL NOT NULL,
    price       REAL NOT NULL,
    reason      TEXT NOT NULL
);
```

---

## 8. Prediction Service

**`app/services/prediction_service.py`**

This is the most important service. It loads the TFT model checkpoint and calls it.

```python
from pathlib import Path
import sys

class PredictionService:
    def __init__(self, ml_dir: Path):
        self.ml_dir = ml_dir
        self._model = None
        self._cache: dict[str, dict] = {}   # ticker → {p10, p50, p90, signal}

    def _load_model(self):
        """Lazy-load the TFT checkpoint."""
        if self._model is not None:
            return
        # Add ml/src to sys.path so sl20_ml is importable
        sys.path.insert(0, str(self.ml_dir / "src"))
        # Import predict.py's run_inference function directly
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "predict", self.ml_dir / "predict.py"
        )
        predict_mod = importlib.util.load_from_spec(spec)
        spec.loader.exec_module(predict_mod)
        self._predict_fn = predict_mod.run_inference  # must exist in predict.py

    def get_prediction(self, ticker: str, date: str) -> dict:
        """
        Returns {'p10': float, 'p50': float, 'p90': float, 'signal': str}
        Checks DB cache first.
        """
        ...
```

**Important:** `ml/predict.py` must export a callable `run_inference(ticker, date)` that returns `{'p10': float, 'p50': float, 'p90': float}`. Check whether it does — if the current `predict.py` only has a CLI interface (`if __name__ == "__main__":`), add a `run_inference()` function to it.

**Prediction caching strategy:**
- On startup (or via a background task), run inference for all 20 tickers for today's date and store in the `predictions` SQLite table
- On request, read from the table first; only call the model if the prediction is missing
- This means the first cold start may be slow (~30–60 seconds) but subsequent requests are instant

---

## 9. Paper Trading Simulator

**`app/services/portfolio_service.py`**

The paper trading simulator turns signal predictions into virtual trades.

### Initial state (seeded to DB)
- Starting capital: **LKR 1,000,000**
- Start date: **90 trading days ago** from today
- Each day: read the signal for each ticker, execute trades per the rules below

### Trading rules
```
BUY signal  → if not already holding ticker AND cash available:
               buy shares worth min(10% of portfolio value, available cash)
               record trade with reason "Model BUY signal: P50 predicted +X.XX%"

SELL signal → if currently holding ticker:
               sell entire position
               record trade with reason "Model SELL signal: P50 predicted -X.XX%"

HOLD signal → do nothing
```

### Position sizing
- Max position size: 10% of portfolio value per ticker
- Never invest more than 70% of total cash in any single day
- Always keep at least LKR 50,000 in cash as buffer

### Seeding
On first startup (`seed.py`), if the portfolio tables are empty:
1. Generate 90 days of simulated portfolio history using historical predictions
2. For historical dates, use the feature panel's actual close prices to simulate P&L
3. Starting portfolio value = LKR 1,000,000
4. Walk forward day by day applying the trading rules
5. Store the resulting trades, positions, and portfolio value series in SQLite

This means the portfolio always looks "live" with real P&L history even before the backend is connected to fresh daily predictions.

---

## 10. Static Stock Info (for `/stocks/{ticker}/info` and `/stocks/{ticker}/stats`)

Hardcode this in `app/services/price_service.py` or a constants file:

```python
STOCK_INFO = {
    "JKH": {
        "name": "John Keells Holdings PLC",
        "sector": "Diversified",
        "blurb": "Sri Lanka's largest listed conglomerate with interests in transportation, leisure, property, consumer foods, financial services, and IT. JKH is widely regarded as a bellwether for the Sri Lankan economy."
    },
    "COMB": {
        "name": "Commercial Bank of Ceylon PLC",
        "sector": "Banking",
        "blurb": "The largest private sector bank in Sri Lanka by assets, providing retail, corporate, and international banking services. COMB is a key indicator of Sri Lanka's broader credit market health."
    },
    "DIAL": {
        "name": "Dialog Axiata PLC",
        "sector": "Telecommunications",
        "blurb": "Sri Lanka's largest mobile telecommunications provider, offering mobile, broadband, satellite, and digital services. Dialog is a subsidiary of Malaysia's Axiata Group."
    },
    "SAMP": {
        "name": "Sampath Bank PLC",
        "sector": "Banking",
        "blurb": "One of Sri Lanka's leading commercial banks, known for innovation in retail banking and digital financial services."
    },
    "HAYL": {
        "name": "Hayleys PLC",
        "sector": "Diversified",
        "blurb": "A diversified conglomerate with operations in agriculture, manufacturing, transportation, consumer, and IT sectors. Hayleys is one of Sri Lanka's oldest and most respected companies."
    },
    "CTC": {
        "name": "Ceylon Tobacco Company PLC",
        "sector": "Consumer Staples",
        "blurb": "The sole manufacturer and distributor of cigarettes in Sri Lanka, operating under license from British American Tobacco. CTC is known for its high dividend yield."
    },
    "HNB": {
        "name": "Hatton National Bank PLC",
        "sector": "Banking",
        "blurb": "One of Sri Lanka's largest commercial banks, with a strong presence in both urban and rural lending. HNB is the leading bank serving Sri Lanka's plantation sector."
    },
    "LIOC": {
        "name": "Lanka IOC PLC",
        "sector": "Energy",
        "blurb": "Sri Lanka's second largest fuel retailer, a subsidiary of Indian Oil Corporation. LIOC operates petroleum product distribution and retail fuel stations across the island."
    },
    "SPEN": {
        "name": "Aitken Spence PLC",
        "sector": "Diversified",
        "blurb": "A Sri Lankan conglomerate active in tourism, maritime logistics, power generation, printing, and garment manufacturing."
    },
    "DFCC": {
        "name": "DFCC Bank PLC",
        "sector": "Banking",
        "blurb": "Sri Lanka's first development bank, now a full-service commercial bank offering personal, SME, and corporate banking solutions."
    },
    "NTB": {
        "name": "Nations Trust Bank PLC",
        "sector": "Banking",
        "blurb": "A mid-sized commercial bank in Sri Lanka focused on retail and SME banking, known for its American Express card franchise in the country."
    },
    "BUKI": {
        "name": "Bukit Darah PLC",
        "sector": "Diversified",
        "blurb": "The holding company of the Carson Cumberbatch group, with investments in palm oil, beverages, real estate, and financial services."
    },
    "CARG": {
        "name": "Cargills (Ceylon) PLC",
        "sector": "Consumer Staples",
        "blurb": "Sri Lanka's leading food retail chain and FMCG manufacturer, operating the Cargills Food City supermarket network and producing Cargills Magic ice cream and other branded foods."
    },
    "CCS": {
        "name": "Ceylon Cold Stores PLC",
        "sector": "Consumer Staples",
        "blurb": "The manufacturer of Elephant House soft drinks and ice creams, one of Sri Lanka's most iconic consumer brands. A subsidiary of John Keells Holdings."
    },
    "HHL": {
        "name": "Hemas Holdings PLC",
        "sector": "Diversified",
        "blurb": "A diversified company with leading businesses in healthcare, consumer products (Baby Cheramy, Clogard), and transportation."
    },
    "LION": {
        "name": "Lion Brewery (Ceylon) PLC",
        "sector": "Consumer Staples",
        "blurb": "Sri Lanka's largest brewery and the producer of Lion Lager, Carlsberg, and other beer brands. A subsidiary of the Carson Cumberbatch group."
    },
    "MELS": {
        "name": "Melstacorp PLC",
        "sector": "Diversified",
        "blurb": "The holding company of the Distilleries Company of Sri Lanka group, with interests in beverages (arrack), insurance, and telecommunications."
    },
    "TKYO": {
        "name": "Tokyo Cement Company (Lanka) PLC",
        "sector": "Construction Materials",
        "blurb": "Sri Lanka's leading cement manufacturer, producing both ordinary Portland cement and blended cements under the Tokyo Super and Tokyo Supercrete brands."
    },
    "VONE": {
        "name": "Vallibel One PLC",
        "sector": "Diversified",
        "blurb": "A diversified holding company with interests in tiles (Royal Ceramics), aluminium, banking (LB Finance), and leisure."
    },
    "AEL": {
        "name": "Access Engineering PLC",
        "sector": "Construction",
        "blurb": "A leading Sri Lankan construction company specialising in infrastructure, civil engineering, and road construction. Involved in many of the country's major infrastructure projects."
    },
}

# Estimated market cap (LKR millions) and P/E ratios — hardcoded estimates
STOCK_KEY_STATS_STATIC = {
    "JKH":  {"marketCap": 285_000, "peRatio": 18.5},
    "COMB": {"marketCap": 135_000, "peRatio": 8.2},
    "DIAL": {"marketCap": 95_000,  "peRatio": 12.4},
    "SAMP": {"marketCap": 78_000,  "peRatio": 7.1},
    "HAYL": {"marketCap": 42_000,  "peRatio": 11.3},
    "CTC":  {"marketCap": 190_000, "peRatio": 15.8},
    "HNB":  {"marketCap": 110_000, "peRatio": 7.8},
    "LIOC": {"marketCap": 28_000,  "peRatio": 9.2},
    "SPEN": {"marketCap": 38_000,  "peRatio": 13.1},
    "DFCC": {"marketCap": 32_000,  "peRatio": 6.4},
    "NTB":  {"marketCap": 22_000,  "peRatio": 7.9},
    "BUKI": {"marketCap": 18_000,  "peRatio": None},
    "CARG": {"marketCap": 65_000,  "peRatio": 22.1},
    "CCS":  {"marketCap": 88_000,  "peRatio": 19.6},
    "HHL":  {"marketCap": 45_000,  "peRatio": 14.2},
    "LION": {"marketCap": 72_000,  "peRatio": 11.7},
    "MELS": {"marketCap": 35_000,  "peRatio": 8.9},
    "TKYO": {"marketCap": 25_000,  "peRatio": 10.3},
    "VONE": {"marketCap": 20_000,  "peRatio": None},
    "AEL":  {"marketCap": 15_000,  "peRatio": 16.4},
}
```

---

## 11. Static News Fixtures

For `GET /news` return these 20 items (hardcoded in `news_service.py`). The sentiment model is not built yet.

```python
NEWS_ITEMS = [
    {"id": "n01", "source": "EconomyNext", "isLocal": True,  "headline": "CSE benchmark index edges higher on banking sector gains", "url": "https://economynext.com", "sentiment": "Positive", "timeAgo": "1h ago"},
    {"id": "n02", "source": "Daily FT",    "isLocal": True,  "headline": "Sri Lanka central bank holds policy rates steady for third consecutive month", "url": "https://ft.lk", "sentiment": "Neutral", "timeAgo": "2h ago"},
    {"id": "n03", "source": "Reuters",     "isLocal": False, "headline": "Asian markets mixed as Fed rate outlook weighs on sentiment", "url": "https://reuters.com", "sentiment": "Neutral", "timeAgo": "3h ago"},
    {"id": "n04", "source": "LBO",         "isLocal": True,  "headline": "JKH reports strong quarterly earnings driven by leisure recovery", "url": "https://lankabusinessonline.com", "sentiment": "Positive", "timeAgo": "4h ago"},
    {"id": "n05", "source": "EconomyNext", "isLocal": True,  "headline": "Foreign investor net selling continues on CSE for second week", "url": "https://economynext.com", "sentiment": "Negative", "timeAgo": "5h ago"},
    {"id": "n06", "source": "Reuters",     "isLocal": False, "headline": "Oil prices rise on Middle East supply concerns", "url": "https://reuters.com", "sentiment": "Negative", "timeAgo": "6h ago"},
    {"id": "n07", "source": "Daily FT",    "isLocal": True,  "headline": "Dialog Axiata to invest LKR 15bn in 5G infrastructure rollout", "url": "https://ft.lk", "sentiment": "Positive", "timeAgo": "7h ago"},
    {"id": "n08", "source": "LBO",         "isLocal": True,  "headline": "Sri Lanka rupee stable against dollar ahead of IMF review", "url": "https://lankabusinessonline.com", "sentiment": "Neutral", "timeAgo": "8h ago"},
    {"id": "n09", "source": "Reuters",     "isLocal": False, "headline": "Gold hits three-month high on dollar weakness", "url": "https://reuters.com", "sentiment": "Positive", "timeAgo": "10h ago"},
    {"id": "n10", "source": "EconomyNext", "isLocal": True,  "headline": "Commercial Bank posts record profit; dividend declared", "url": "https://economynext.com", "sentiment": "Positive", "timeAgo": "12h ago"},
    {"id": "n11", "source": "Daily FT",    "isLocal": True,  "headline": "Tourism arrivals hit post-crisis high boosting leisure stocks", "url": "https://ft.lk", "sentiment": "Positive", "timeAgo": "1d ago"},
    {"id": "n12", "source": "Reuters",     "isLocal": False, "headline": "VIX spikes as US inflation data beats expectations", "url": "https://reuters.com", "sentiment": "Negative", "timeAgo": "1d ago"},
    {"id": "n13", "source": "LBO",         "isLocal": True,  "headline": "Cargills Ceylon expands retail footprint with 20 new stores", "url": "https://lankabusinessonline.com", "sentiment": "Positive", "timeAgo": "1d ago"},
    {"id": "n14", "source": "EconomyNext", "isLocal": True,  "headline": "CSE suspends trading in two small-cap stocks on disclosure concerns", "url": "https://economynext.com", "sentiment": "Negative", "timeAgo": "1d ago"},
    {"id": "n15", "source": "Reuters",     "isLocal": False, "headline": "S&P 500 closes at record high on tech earnings optimism", "url": "https://reuters.com", "sentiment": "Positive", "timeAgo": "2d ago"},
    {"id": "n16", "source": "Daily FT",    "isLocal": True,  "headline": "Hatton National Bank targets 15% loan growth in FY2025", "url": "https://ft.lk", "sentiment": "Positive", "timeAgo": "2d ago"},
    {"id": "n17", "source": "LBO",         "isLocal": True,  "headline": "IMF approves next tranche of Sri Lanka bailout facility", "url": "https://lankabusinessonline.com", "sentiment": "Positive", "timeAgo": "2d ago"},
    {"id": "n18", "source": "Reuters",     "isLocal": False, "headline": "China factory output slows, raising concerns for Asian exports", "url": "https://reuters.com", "sentiment": "Negative", "timeAgo": "3d ago"},
    {"id": "n19", "source": "EconomyNext", "isLocal": True,  "headline": "Ceylon Tobacco pays special dividend; yield exceeds 8%", "url": "https://economynext.com", "sentiment": "Positive", "timeAgo": "3d ago"},
    {"id": "n20", "source": "Daily FT",    "isLocal": True,  "headline": "Sri Lanka inflation falls to 4.2%, lowest in four years", "url": "https://ft.lk", "sentiment": "Positive", "timeAgo": "4d ago"},
]
```

---

## 12. Main App Entry Point

**`main.py`:**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.routers import stocks, portfolio, news, market
from app.db.database import init_db
from app.db.seed import seed_if_empty

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_if_empty()
    yield

app = FastAPI(title="stoX API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(stocks.router,    prefix="/stocks",    tags=["stocks"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(news.router,      prefix="/news",      tags=["news"])
app.include_router(market.router,    prefix="/market",    tags=["market"])
```

---

## 13. Router Structure

Each router file has this shape:

```python
# app/routers/stocks.py
from fastapi import APIRouter, HTTPException, Depends
from app.models.stocks import StockPrediction, StockInfo, StockKeyStats, PricePoint
from app.services.prediction_service import PredictionService, get_prediction_service
from app.services.price_service import PriceService, get_price_service

router = APIRouter()

SL20_TICKERS = [
    "JKH", "COMB", "DIAL", "SAMP", "HAYL", "CTC", "HNB", "LIOC",
    "SPEN", "DFCC", "NTB", "BUKI", "CARG", "CCS", "HHL", "LION",
    "MELS", "TKYO", "VONE", "AEL"
]

@router.get("", response_model=list[StockPrediction], response_model_by_alias=True)
async def get_all_stocks(
    pred_svc: PredictionService = Depends(get_prediction_service),
    price_svc: PriceService = Depends(get_price_service),
):
    ...

@router.get("/{ticker}/prediction", response_model=StockPrediction, response_model_by_alias=True)
async def get_stock_prediction(
    ticker: str,
    pred_svc: PredictionService = Depends(get_prediction_service),
    price_svc: PriceService = Depends(get_price_service),
):
    if ticker.upper() not in SL20_TICKERS:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not in SL20")
    ...
```

---

## 14. How to Call the ML Model from the Backend

The existing `ml/predict.py` has a CLI interface. You need to add a `run_inference` function that the backend can import directly.

**Add this to `ml/predict.py`:**

```python
def run_inference(ticker: str, date: str) -> dict:
    """
    Public API for the backend. Returns P10/P50/P90 for one ticker on one date.
    
    Args:
        ticker: e.g. 'JKH'
        date:   e.g. '2025-06-01' (must be a date with at least 60 prior trading days)
    
    Returns:
        {'p10': float, 'p50': float, 'p90': float, 'last_close': float}
        All prices in LKR.
    """
    # ... existing inference logic, extracted into this function
```

The backend's `prediction_service.py` then does:

```python
import sys
sys.path.insert(0, str(ml_dir / "src"))
sys.path.insert(0, str(ml_dir))

from predict import run_inference

result = run_inference("JKH", "2025-06-01")
# → {'p10': 178.4, 'p50': 184.1, 'p90': 191.2, 'last_close': 183.5}
```

---

## 15. Feature Panel Access

The feature panel at `ml/data/features/sl20_feature_panel.parquet` contains:
- **71,300 rows** (20 tickers × 3,565 trading days: 2011-01-03 to 2025-12-31)
- Columns include: `ticker`, `date`, `close`, `adj_close`, `volume`, `daily_return`, and ~127 feature columns
- Also contains: `sl20_index`, `usd_lkr`, `vix`, `oil_wti`, `sp500` etc.

Read it via pandas in `price_service.py`:

```python
import pandas as pd
from pathlib import Path

class PriceService:
    def __init__(self, ml_dir: Path):
        panel_path = ml_dir / "data/features/sl20_feature_panel.parquet"
        self._panel = pd.read_parquet(panel_path)
        self._panel["date"] = pd.to_datetime(self._panel["date"])
    
    def get_price_history(self, ticker: str, days: int = 90) -> list[dict]:
        df = self._panel[self._panel["ticker"] == ticker].sort_values("date").tail(days)
        return df[["date", "close"]].to_dict(orient="records")
    
    def get_52w_stats(self, ticker: str) -> dict:
        cutoff = pd.Timestamp.today() - pd.Timedelta(days=365)
        df = self._panel[(self._panel["ticker"] == ticker) & (self._panel["date"] >= cutoff)]
        return {
            "high52w": float(df["close"].max()),
            "low52w": float(df["close"].min()),
            "avgVolume": float(df["volume"].mean()),
        }
```

---

## 16. Running the Backend

```bash
cd D:\stox\backend

# Install deps
pip install -r requirements.txt

# Run dev server
uvicorn main:app --reload --port 8000

# API docs (auto-generated by FastAPI)
# http://localhost:8000/docs
```

**Switch frontend from mock to real:**
Edit `D:\stox\frontend\app\.env.local`:
```
NEXT_PUBLIC_USE_MOCK=false
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 17. Testing

Write tests in `tests/` using `pytest` + `httpx.AsyncClient`:

```bash
cd D:\stox\backend
pytest tests/ -v
```

**Minimum test coverage required:**
- `test_stocks.py`: All 20 tickers return a valid `StockPrediction` from `GET /stocks`; single ticker endpoint returns 404 for unknown tickers; field names match camelCase contract
- `test_portfolio.py`: Summary fields are numeric and present; history returns `days` items; positions list sums to ~totalValue
- `test_news.py`: Returns exactly 20 items; each item has required fields

---

## 18. What Is NOT in Scope for This Build

- **News sentiment model** — deferred. Return static mock news.
- **Real-time price feeds** — CSE data is end-of-day only. No WebSockets.
- **Authentication** — no login, no API keys. This is a demo project.
- **Deployment** — Docker/cloud deployment is out of scope. Local only.
- **Historical prediction backfill beyond 90 days** — seed 90 days only.
- **Re-training** — model is already trained. `train_model.py` is not called by the backend.

---

## 19. `predict.py` Reference

`ml/predict.py` already has a `run_inference()` function you can import directly:

```python
def run_inference(ticker: str | None = None, date: str | None = None) -> list[dict]:
    """
    ticker : 'JKH' or None (all 20 tickers)
    date   : 'YYYY-MM-DD' or None (latest in panel)
    
    Returns list of dicts:
    [{'ticker': 'JKH', 'as_of_date': '2025-06-01', 'last_close': 183.5,
      'p10': 179.2, 'p50': 184.8, 'p90': 191.3, 'implied_ret': 0.0071}, ...]
    """
```

Call it from the backend like this:

```python
import sys
ml_dir = Path(settings.ml_dir).resolve()
sys.path.insert(0, str(ml_dir / "src"))
sys.path.insert(0, str(ml_dir))

from predict import run_inference

# All 20 tickers (use this for the bulk predictions on startup)
all_preds = run_inference()

# Single ticker
jkh = run_inference(ticker="JKH")
```

**Important:** `run_inference()` loads the full feature panel (~71,300 rows) and rebuilds the training dataset on every call. This is slow (~10–30 seconds on CPU). You MUST cache results in the `predictions` SQLite table and only call it during the daily refresh, not on every HTTP request.

---

## 20. Dependencies (`requirements.txt`)

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
aiosqlite>=0.20.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
pandas>=2.2.0
pyarrow>=15.0.0
python-dotenv>=1.0.0
httpx>=0.27.0      # for tests
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

The ML deps (torch, pytorch-forecasting, etc.) are already installed in the same environment as `ml/`. The backend should run in that same Python environment — no separate venv needed unless you prefer isolation.
