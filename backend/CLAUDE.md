# stoX Backend — Claude Code Project Brief

> Read this file first. It tells you everything you need to know to build the backend from scratch.

---

## What You Are Building

A **FastAPI backend** for stoX, a stock prediction platform for the Sri Lankan stock market (S&P SL20 index, Colombo Stock Exchange).

The ML model is already trained and saved. The frontend is already scaffolded with mock data. **Your job is to build the API that connects them.**

The frontend will stop using mock data the moment `NEXT_PUBLIC_USE_MOCK=false` is set in its `.env.local`. It will hit this backend at `http://localhost:8000`. Every endpoint must return JSON that exactly matches the TypeScript types in `../frontend/app/src/lib/api/types.ts`.

---

## Repository Layout (what already exists)

```
D:\stox\
├── ml/
│   ├── src/sl20_ml/              ← Python package (importable)
│   ├── data/
│   │   ├── raw/                  ← CSE price CSVs, FRED macro CSVs
│   │   ├── processed/            ← Cleaned OHLCV parquet
│   │   └── features/
│   │       └── sl20_feature_panel.parquet  ← 71,300 rows × 130 cols (main feature store)
│   ├── models/
│   │   └── tft_v1/
│   │       ├── best-v1.ckpt      ← Trained model weights (~3.2 MB)
│   │       └── model_config.json ← Hyperparams + metrics
│   ├── predict.py                ← Inference: ticker + date → P10/P50/P90
│   ├── configs/pipeline.yaml     ← All config (paths, model params, split dates)
│   └── pyproject.toml            ← Python deps (pytorch-forecasting, lightning, etc.)
│
├── frontend/
│   └── app/src/lib/api/
│       ├── types.ts              ← CANONICAL TypeScript types (copy these to backend)
│       └── client.ts             ← All 12 endpoints the backend must implement
│
├── backend/                      ← YOU ARE BUILDING THIS
│   ├── CLAUDE.md                 ← This file
│   └── SPEC.md                   ← Detailed specification (read this next)
│
└── docs/
    ├── 00-project-overview.md
    ├── 01-ml-data-pipeline.md
    └── 02-ml-model.md
```

---

## Read Next

1. **`SPEC.md`** (in this folder) — complete backend spec: folder structure, all 12 endpoints, data layer, paper trading logic, deployment
2. **`../frontend/app/src/lib/api/types.ts`** — the exact JSON shapes every endpoint must return
3. **`../frontend/app/src/lib/api/client.ts`** — which URLs map to which types
4. **`../ml/predict.py`** — the inference script you'll call to get predictions
5. **`../ml/models/tft_v1/model_config.json`** — model version info

---

## Tech Stack Decision

Use **Python / FastAPI** (not Go). Reasons:
- The ML model inference (`predict.py`) is Python — the backend can call it directly without a subprocess
- The feature panel and prediction pipeline are all Python/pandas
- Simpler integration: one language, one environment

```
Python 3.12+
FastAPI 0.111+          ← web framework
uvicorn[standard]       ← ASGI server
SQLite (via aiosqlite)  ← serving database for predictions + portfolio
pandas                  ← for data reads/transforms
pydantic v2             ← response models (FastAPI uses it natively)
python-dotenv           ← env config
```

---

## Key Constraints

- **No news in this version.** The news/sentiment feature is deferred. For now, `GET /news` returns a hardcoded set of realistic-looking mock news items (see SPEC.md).
- **Paper trading only.** All portfolio data (positions, trades, P&L) comes from the paper trading simulator, not a real brokerage. The simulator runs on the ML model's signals.
- **The ML model is already trained.** Do not re-train. Load `best-v1.ckpt` and call it.
- **Prices in LKR.** All price values in API responses are in Sri Lankan Rupees.
- **The frontend expects exact field names** from `types.ts` — use camelCase in JSON responses (FastAPI does this with `response_model_by_alias=True` or Pydantic aliases).
- **CORS must be enabled** — the frontend runs on `http://localhost:3000`.
