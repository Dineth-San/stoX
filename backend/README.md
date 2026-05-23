# stoX Backend

FastAPI REST API powering the stoX Sri Lankan stock prediction platform (S&P SL20 index).

---

## Quick start

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

The first startup takes **30–60 s** while the TFT model loads and seeds the database.
Subsequent restarts are faster (~5 s) because the DB is already seeded.

Interactive docs: <http://localhost:8000/docs>

---

## Environment variables

Create `backend/.env` (or set these in your shell):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./stox.db` | SQLite path |
| `ML_DIR` | `../ml` | Path to the `ml/` folder containing `predict.py` and the parquet data |
| `USE_MOCK_PREDICTIONS` | `false` | Set `true` to skip TFT inference and use deterministic mock predictions (fast, useful for frontend dev) |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of allowed CORS origins |

---

## Project layout

```
backend/
├── main.py                  # FastAPI app + lifespan (startup/shutdown)
├── app/
│   ├── config.py            # pydantic-settings BaseSettings
│   ├── db/
│   │   ├── database.py      # aiosqlite helpers, get_db() dependency
│   │   └── seed.py          # idempotent seeder (3-stage: predictions → backfill → backtest)
│   ├── models/              # Pydantic v2 response models (camelCase aliases)
│   ├── routers/             # One file per route group
│   │   ├── stocks.py        # /stocks/*
│   │   ├── market.py        # /market/movers
│   │   ├── news.py          # /news
│   │   └── portfolio.py     # /portfolio/*
│   └── services/
│       ├── price_service.py      # Reads parquet panel; exposes price history, movers, 52w stats
│       ├── prediction_service.py # Caches TFT predictions in SQLite; falls back to mock
│       ├── portfolio_service.py  # Paper-trading backtest simulator
│       ├── stock_info_service.py # Static company info + key stats
│       └── refresh_service.py   # (Iteration 11) daily prediction refresh
├── tests/
│   ├── conftest.py          # Session-scoped AsyncClient fixture
│   ├── test_market.py
│   ├── test_news.py
│   ├── test_portfolio.py
│   └── test_stocks.py
└── pytest.ini
```

---

## Running tests

```bash
cd backend
python -m pytest tests/ -v
```

All 40 tests run against an in-process ASGI app (no live server needed).
The first run loads the TFT model and seeds the DB — allow ~60 s.
Subsequent runs complete in under 5 s.

---

## Static data / daily refresh

**Known limitation:** the feature panel (`ml/data/features/sl20_feature_panel.parquet`)
is a static snapshot ending on **2025-12-31**. Until the daily pipeline
(Iteration 11) is running, predictions always reflect the last date in
the panel regardless of the current date.

The backend is stateless with respect to data: to get fresh predictions,
regenerate the parquet file and restart the server. The seed logic is
idempotent — rows that already exist are skipped.

CSE data constraint: end-of-day prices only (no WebSocket or intraday feed).

---

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Startup hangs for 30–60 s | TFT model first load + full seeding | Normal — wait it out |
| `RuntimeError: PriceService not initialised` | Services accessed before lifespan completes | Never import and call service singletons outside the lifespan context; tests use the conftest fixture which manually calls `init_*()` |
| `ModuleNotFoundError: predict` | `ML_DIR` points to wrong path | Set `ML_DIR` to the directory containing `predict.py` and the `models/` folder |
| Port 8000 already in use | Stale uvicorn process | `Get-Process python \| Stop-Process -Force` (PowerShell) or `pkill -f uvicorn` (bash) |
| `CORS` errors in browser | Frontend origin not in allow-list | Add the frontend URL to `CORS_ORIGINS` in `.env` |
| `USE_MOCK_PREDICTIONS=true` gives fast but constant signals | Mock hash is seeded by ticker + date | Expected behaviour — signals do vary day-to-day, but are deterministic for a given (ticker, date) pair |
