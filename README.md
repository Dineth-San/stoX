# stoX

A full-stack stock prediction platform for the Sri Lankan market — specifically the **S&P SL20 index** (top 20 companies on the Colombo Stock Exchange).

The model predicts tomorrow's closing price for each stock and gives an honest uncertainty band — not just a single number, but a **P10 / P50 / P90** interval so you can see how confident the model actually is.

---

## What it does

- Ingests 14 years of CSE price data (2011–2025) and macro context (USD/LKR, VIX, oil, policy rates, etc.)
- Trains a **Temporal Fusion Transformer** to predict next-day log returns with calibrated uncertainty
- Exposes a **FastAPI backend** with endpoints for predictions, price history, news, and paper trading
- Serves a **Next.js dashboard** where you can browse the SL20 stocks, see forecasts, and track a portfolio

---

## Project structure

```
stoX/
├── ml/                          ← Python ML pipeline
│   ├── src/sl20_ml/             ← Importable package (features, model, utils)
│   │   ├── model/
│   │   │   ├── dataset.py       ← TimeSeriesDataSet construction + feature prep
│   │   │   ├── tft_model.py     ← TFT builder (from_dataset wrapper)
│   │   │   ├── evaluate.py      ← MAE, RMSE, DA, quantile coverage metrics
│   │   │   └── conformal.py     ← CQR post-hoc calibration (90% coverage guarantee)
│   │   └── features/
│   │       └── engineer.py      ← Per-ticker technicals + cross-sectional + macro
│   ├── configs/pipeline.yaml    ← All hyperparameters and file paths
│   ├── train_model.py           ← Training entry point
│   ├── predict.py               ← Inference: ticker + date → P10/P50/P90 in LKR
│   ├── eval_checkpoint.py       ← Evaluate a saved checkpoint without retraining
│   ├── colab_train.ipynb        ← One-click GPU training on Google Colab T4
│   ├── build_*.py               ← Data pipeline stages (prices → features)
│   └── models/tft_v1/
│       ├── best.ckpt            ← Saved model weights (tracked by DVC, not git)
│       └── model_config.json    ← Hyperparameters + metrics (in git)
│
├── backend/                     ← FastAPI REST API
│   ├── main.py                  ← App entry point
│   ├── app/
│   │   ├── routers/             ← stocks, market, news, portfolio
│   │   ├── services/            ← prediction service, price service, paper trading
│   │   └── db/                  ← SQLite layer (aiosqlite)
│   └── tests/                   ← 40 pytest tests
│
├── frontend/                    ← Next.js 14 dashboard
│   └── src/
│
└── docs/                        ← Plain-English documentation
    ├── 00-project-overview.md
    ├── 01-ml-data-pipeline.md
    └── 02-ml-model.md
```

---

## The ML model

**Model:** Temporal Fusion Transformer (`pytorch-forecasting` v1.7)

| Setting | Value |
|---------|-------|
| Encoder (history window) | 90 trading days |
| Prediction horizon | 1 day |
| Hidden size | 128 |
| Attention heads | 8 |
| Dropout | 0.2 |
| Target | `log(next_close / close)` — log return |
| Output | P10, P50, P90 quantiles |

**Calibration:** After training, split conformal prediction (CQR, Romano-Patterson-Candès 2019) is applied on the validation set to guarantee exactly **90% coverage** on val, and approximately 90% on test under exchangeability. A single scalar `conformal_delta` is stored in `model_config.json` and applied at inference.

**Current metrics (test set, 2023–2025):**

| Metric | Value |
|--------|-------|
| Quantile coverage (calibrated) | 91.2% |
| Quantile coverage (raw model) | 85.5% |
| MAE | 1.15% log-return |
| RMSE | 1.83% log-return |
| Directional accuracy | 43.1% |

**Data splits:**
- Train: 2011–2020
- Validation: 2021 (used for conformal calibration)
- 2022 excluded (SL economic crisis — once-per-decade regime)
- Test: 2023–2025

---

## Quick start

### 1. ML — run inference locally

```bash
cd ml
pip install -e .
python predict.py                          # all 20 SL20 tickers
python predict.py --ticker JKH             # single ticker
python predict.py --format json            # JSON output
```

### 2. ML — retrain on Colab (GPU)

Open `ml/colab_train.ipynb` in Google Colab with a T4 GPU runtime.
Run cells top to bottom. Expected training time: 60–90 min.

> Before retraining, rebuild the feature panel locally:
> ```bash
> python build_alignment.py
> python build_features.py
> ```
> Upload the resulting `ml/data/features/sl20_feature_panel.parquet` to Google Drive.

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

The first startup seeds the database (~30–60 s). Subsequent restarts are fast (~5 s).

**Environment variables** (create `backend/.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./stox.db` | SQLite path |
| `ML_DIR` | `../ml` | Path to the `ml/` folder |
| `USE_MOCK_PREDICTIONS` | `false` | Skip TFT and use mock data (faster for frontend dev) |

### 4. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

---

## API routes

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/stocks` | All 20 SL20 tickers with metadata |
| `GET` | `/stocks/{ticker}` | Single stock detail |
| `GET` | `/stocks/{ticker}/history` | OHLCV price history |
| `GET` | `/stocks/{ticker}/prediction` | P10/P50/P90 forecast for next trading day |
| `GET` | `/market/summary` | Market-wide stats (ASPI, SL20, breadth) |
| `GET` | `/market/movers` | Top gainers and losers |
| `GET` | `/news` | Latest news feed |
| `GET` | `/portfolio` | Paper trading portfolio state |
| `POST` | `/portfolio/trade` | Execute a paper trade |
| `GET` | `/portfolio/history` | Trade history |
| `GET` | `/portfolio/performance` | Portfolio P&L over time |

---

## Data pipeline stages

Run these in order from the `ml/` directory to rebuild all data from raw CSE files:

```bash
python build_prices.py       # OHLCV cleaning and adjustment
python build_macro.py        # USD/LKR, policy rates, FRED macro (VIX, oil, S&P500)
python build_market.py       # ASPI, SL20 index, market P/E, foreign flow
python build_alignment.py    # Join all sources to a single daily panel
python build_features.py     # Engineer 135 features (technicals, cross-sectional, macro)
python train_model.py        # Train TFT (use Colab for GPU)
```

MLflow experiment tracking runs locally in `ml/mlruns/`. View with:

```bash
cd ml && mlflow ui    # then open http://localhost:5000
```

---

## Tech stack

| Layer | Tech |
|-------|------|
| ML model | Python, PyTorch, pytorch-forecasting, Lightning |
| Data pipeline | pandas, numpy, scikit-learn |
| Experiment tracking | MLflow |
| Backend | Python, FastAPI, aiosqlite, Pydantic |
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Training infrastructure | Google Colab T4 GPU |
| Data versioning | DVC |

---

## Documentation

Detailed plain-English documentation lives in `docs/`:

- [`docs/00-project-overview.md`](docs/00-project-overview.md) — what stoX is and how the pieces fit
- [`docs/01-ml-data-pipeline.md`](docs/01-ml-data-pipeline.md) — the data pipeline from raw CSE files to features
- [`docs/02-ml-model.md`](docs/02-ml-model.md) — the TFT model, training, and results explained in plain English
