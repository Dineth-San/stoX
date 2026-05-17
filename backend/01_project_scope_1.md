# Project Scope — Sri Lankan Stock Prediction & Paper Trading Platform

**Version:** 1.0
**Date:** April 2026
**Status:** Scope locked, data pipeline phase next

---

## 1. Project Summary

A full-stack web application that predicts next-day closing prices for stocks listed in the S&P SL20 index of the Colombo Stock Exchange (CSE), and uses those predictions to drive an automated paper trading simulator. Predictions are probabilistic (price intervals, not single numbers) and incorporate price history, company fundamentals, Sri Lankan macroeconomics, global macroeconomics, and news sentiment.

The system is intended as a research, learning, and demonstration project. It is **not** a real trading platform and explicitly does not provide financial advice.

---

## 2. Goals & Success Criteria

### Primary goals

- Build a probabilistic time-series ML model that beats naive baselines on next-day closing price prediction for S&P SL20 stocks
- Translate model predictions into BUY/HOLD/SELL signals
- Simulate trading those signals through a custom-built paper trading engine starting with LKR 1,000,000 virtual capital
- Present everything through a full-stack web application

### Success criteria

- **Modeling:** Beat the persistence baseline (tomorrow = today) on directional accuracy and RMSE on a held-out test set across at least 15 of the 20 SL20 stocks
- **Calibration:** 90% prediction intervals contain the true price ~90% of the time on test data
- **Paper trading:** Strategy produces a positive Sharpe ratio over a 12-month walk-forward backtest (zero-cost simplification for v1)
- **Application:** End-to-end working web app where a user can view predictions, see portfolio status, and watch the simulator run on schedule

### Non-goals (explicitly out of scope)

- Real money trading
- Intraday or high-frequency prediction (< daily resolution)
- Stocks outside the S&P SL20 index
- Options, futures, derivatives, or short selling
- Mobile app (web-responsive only)
- Multi-user accounts with isolated portfolios in v1 (single shared simulator is fine)
- Personalized financial advice or recommendations to specific users

---

## 3. System Components

The project breaks into five logical components:

### 3.1 Data Pipeline
Ingests, cleans, aligns, and stores all input data needed for model training and inference. Detailed in `02_data_pipeline.md`.

### 3.2 ML Model
Three-tier modeling stack:
- **Tier 1 — Baselines:** Persistence, moving average, ARIMA
- **Tier 2 — Strong baseline:** LightGBM with engineered features
- **Tier 3 — Main model:** Temporal Fusion Transformer (TFT) producing quantile forecasts (P10, P50, P90)

Model trained on historical data, evaluated with walk-forward validation, retrained weekly or monthly via scheduled job.

### 3.3 Paper Trading Engine
Custom-built simulator since no CSE paper trading API exists.
- Virtual portfolio: cash + per-stock positions, starting at LKR 1,000,000
- Strategy layer: converts model's probabilistic output into discrete BUY/HOLD/SELL action per stock per day
- Execution simulator: assumes orders fill at next day's opening price
- Transaction costs: zero-cost simplification for v1, realistic CSE fees in v2
- Risk management: max position size per stock, max concurrent positions
- Backtest harness: replay strategy on historical predictions before "live" simulation

### 3.4 Web Application
Full-stack app with:
- **Backend:** REST API serving predictions, portfolio state, charts, news feed
- **Frontend:** Dashboard showing per-stock predictions with confidence intervals, portfolio value over time, current positions, recent trades, news sentiment overview
- **Scheduled jobs:** Daily data refresh, daily prediction run, daily simulated trades
- Tech choices to be finalized in next planning phase (likely FastAPI + React or Next.js)

### 3.5 Monitoring & Disclaimer Layer
- Logs all predictions and actual outcomes for drift monitoring
- Clear, prominent disclaimers throughout the UI that this is not financial advice
- Visible model accuracy metrics so users can judge prediction quality themselves

---

## 4. Deliverables

Concrete artifacts that must exist at project completion:

### 4.1 Code & infrastructure deliverables

- Git repository with clean structure (`data/`, `src/`, `notebooks/`, `models/`, `tests/`, `app/`)
- Python environment definition (using `uv` or `poetry`)
- Reproducible training pipeline — single command from raw data to trained model
- Daily inference job (script + scheduler config)
- Web application source code — backend + frontend
- Deployment configuration (Docker Compose at minimum; cloud deployment optional)
- Test suite covering data pipeline integrity and core paper trading logic

### 4.2 Data deliverables

- Cleaned, aligned, version-controlled dataset covering S&P SL20 stocks with all input features
- Data dictionary documenting every feature, its source, frequency, and update logic
- Reproducible data pipeline scripts (raw → processed → feature store)

### 4.3 Model deliverables

- Trained baseline models (persistence, ARIMA) — saved as artifacts
- Trained LightGBM model with hyperparameters logged
- Trained TFT model with hyperparameters logged
- Evaluation report comparing all models across all 20 stocks
- Model card documenting intended use, limitations, training data, and evaluation results

### 4.4 Paper trading deliverables

- Backtest report: 12-month walk-forward Sharpe, max drawdown, hit rate, total return vs SL20 buy-and-hold benchmark
- Live paper trading log starting from project deployment
- Strategy documentation: exact rules for converting predictions to trades

### 4.5 Web app deliverables

- Hosted (or locally runnable) dashboard with the features listed in 3.4
- API documentation (OpenAPI/Swagger)

### 4.6 Documentation deliverables

- Project README with setup instructions
- This scope document (`01_project_scope.md`)
- Data pipeline document (`02_data_pipeline.md`)
- Architecture document (to be written in next phase)
- Final project report covering methodology, results, limitations, and lessons learned

---

## 5. Phased Roadmap

| Phase | Focus | Approx. duration | Output |
|-------|-------|------------------|--------|
| 0 | Planning & scope | Done | Scope + data pipeline docs |
| 1 | Data acquisition & pipeline | 1–2 weeks | Unified dataset for SL20 |
| 2 | EDA & baselines | 1 week | Baseline models + evaluation harness |
| 3 | LightGBM model | 1 week | Strong tabular baseline |
| 4 | TFT model | 2–3 weeks | Probabilistic main model |
| 5 | Paper trading engine | 1–2 weeks | Simulator + backtest |
| 6 | Web application | 2–3 weeks | Full-stack working app |
| 7 | Polish & deployment | 1 week | Hosted, documented, demo-ready |

Total: roughly 9–13 weeks of focused work, assuming compute (M4 Mac + Colab) and data access proceed without major blockers.

---

## 6. Technical Stack

### Core ML
- **Language:** Python 3.11+
- **Deep learning:** PyTorch + `pytorch-forecasting` (for TFT)
- **Tabular ML:** LightGBM, scikit-learn
- **Classical time series:** `statsmodels`, `darts`
- **NLP:** HuggingFace `transformers` (FinBERT for sentiment)
- **Hyperparameter tuning:** Optuna
- **Experiment tracking:** MLflow or Weights & Biases
- **Data versioning:** DVC

### Data
- **Wrangling:** `pandas`, `polars`
- **Storage:** Parquet files (raw + processed), DuckDB or SQLite for query layer, optional TimescaleDB later
- **Pipeline orchestration:** Prefect (lighter weight than Airflow)

### Web app (tentative — finalize next phase)
- **Backend:** FastAPI
- **Frontend:** React or Next.js
- **Charts:** Recharts or Plotly
- **Auth:** Skipped for v1 (single-user demo); add later if needed
- **Database:** PostgreSQL for portfolio state, predictions log

### Deployment
- **Containerization:** Docker + Docker Compose
- **Hosting:** Local-first; optionally Railway / Fly.io / DigitalOcean for demo
- **Scheduling:** Prefect or system cron

---

## 7. Constraints & Assumptions

### Constraints
- Free or low-cost data sources only
- Single developer, part-time effort
- Compute: M4 MacBook (primary) + Colab free tier (parallel runs)
- Sri Lanka market only (S&P SL20)

### Key assumptions
- CSE data request will be approved within 1–2 weeks
- 2023–2026 daily price data can be obtained through one of the three pipeline options described in `02_data_pipeline.md`
- Quarterly fundamentals can be parsed from PDFs with reasonable effort
- News RSS feeds remain accessible and stable
- M4 unified memory (assumed 16GB+) is sufficient for TFT training on 20-stock daily data

---

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| CSE data delivery delayed or incomplete | Medium | High | Have Yahoo Finance + scraping fallback ready |
| Model fails to beat persistence baseline | Medium | Medium | Ship LightGBM with honest reporting; framing as a learning project |
| News sentiment adds no signal | High | Low | Easy to drop the feature without breaking the pipeline |
| 2022 crisis distorts training | High | Medium | Walk-forward validation; report regime-specific metrics |
| Paper trading looks great in bull market only | High | Medium | Report risk-adjusted metrics, not just total return |
| Web app scope creeps beyond ML focus | Medium | Medium | Cap web app at the features in 3.4; no auth in v1 |
| Quarterly fundamentals provide minimal lift | High | Low | Keep weight low; ship without if extraction is too painful |

---

## 9. Ethical & Legal Considerations

- **Financial advice disclaimer** must be visible on every page of the web app
- **Not a trading recommendation system** — predictions are research output, not signals to act on with real money
- **Data licensing:** Verify CSE data usage terms before publishing the project publicly; some exchanges restrict redistribution
- **Model honesty:** Display real out-of-sample accuracy metrics; do not cherry-pick favorable backtest periods
- **News scraping:** Respect `robots.txt` and rate limits; cite sources

---

## 10. Open Questions for Next Planning Phase

- Web app stack final choice (FastAPI + React vs Next.js full-stack)
- Hosting strategy (local-only vs deployed)
- How to handle SL20 index membership changes over the historical training period
- Whether to build a "paper trading leaderboard" feature comparing strategy variants
- v2 scope: realistic CSE transaction costs, multi-user support, intraday updates
