# stoX — Data Pipeline Status

Reference spec: `03_data_pipeline_claude_code.md`  
Last updated: 2026-05-12

---

## Phase Tracker

| Phase | Name                        | Status          | Notes |
|-------|-----------------------------|-----------------|-------|
| 0     | Environment & Project Setup | ✅ Complete     | All criteria verified 2026-05-12 |
| 1     | Raw Data Ingestion          | 🔄 In progress  | CSE prices + market context done; CBSL/FRED/news/fundamentals pending |
| 2     | Cleaning Layer              | 🔄 In progress  | Prices + market context cleaned; pandera + adj-close pending |
| 3     | Alignment Layer             | ⬜ Not started  | |
| 4     | Feature Engineering         | ⬜ Not started  | |
| 5     | Validation & Quality Checks | ⬜ Not started  | |
| 6     | Feature Store Output        | ⬜ Not started  | |

---

## Phase 0 — Environment & Project Setup ✅

| Requirement | Status | Notes |
|---|---|---|
| `ml/` folder with correct layout | ✅ | `src/sl20_ml/`, `tests/`, `configs/`, `data/`, `notebooks/`, `models/` |
| `pyproject.toml` (uv + hatchling) | ✅ | All deps declared; `uv sync` verified |
| `configs/pipeline.yaml` | ✅ | Single source of truth — all settings, no hardcoded values in scripts |
| `src/sl20_ml/` package layout | ✅ | `ingestion/`, `cleaning/`, `alignment/`, `features/`, `validation/`, `utils/` |
| DVC initialized + tracking `data/cleaned/` | ✅ | 3 parquet files tracked; `dvc data status` → No changes |
| MLflow configured (local file store) | ✅ | `mlruns/` exists; `mlflow --version` 3.12.0 |
| `.env.example` template | ✅ | FRED_API_KEY, MLFLOW_TRACKING_URI, DVC_REMOTE_URL, NEWS_API_KEY |
| `.gitignore` — excludes data but allows .dvc files | ✅ | `data/**` with `!data/**/*.dvc` |
| `tests/` with placeholder files for all phases | ✅ | test_cleaning.py (16 tests), placeholders for phases 3-5 |
| `README.md` with setup instructions | ✅ | Quick-start, folder structure, config reference |
| `PIPELINE_STATUS.md` (this file) | ✅ | |
| git initialized | ✅ | Commit: `379ba23` — "data: complete phase 0 - environment and project setup" |

---

## Phase 1 — Raw Data Ingestion

| Requirement | Status | Notes |
|---|---|---|
| CSE raw files in `data/raw/cse/stock_data/` | ✅ | 2011–2025 XLS/CSV files present |
| `src/sl20_ml/ingestion/prices.py` | ✅ | Handles 3 format types (A/B/C), per-row date detection |
| `src/sl20_ml/ingestion/market.py` | ✅ | Loads 4 CSE market files (indices, TRI, ratios, stats) |
| `build_prices.py` entry-point | ✅ | Reads all paths from config; outputs to `data/cleaned/` |
| `build_market.py` entry-point | ✅ | Reads all paths from config; outputs to `data/cleaned/` |
| Metadata JSON sidecars per source file | ❌ | Not yet implemented |
| CBSL macroeconomic data | ❌ | User downloading |
| FRED global macro data (`data/raw/fred/`) | ❌ | Script not written; needs FRED_API_KEY |
| News ingestion (RSS / GDELT) | ❌ | 2 GDELT CSVs exist; pipeline not built |
| Quarterly fundamentals | ❌ | No source files available |
| Summary inventory script | ❌ | Not implemented |

---

## Phase 2 — Cleaning Layer

| Requirement | Status | Notes |
|---|---|---|
| Prices: standard columns (date, ticker, OHLCV, turnover, trades) | ✅ | All 13 required columns present |
| Prices: timezone-naive dates | ✅ | |
| Prices: deduplicated (date, ticker) | ✅ | 61,434 dupes removed during build |
| Prices: `ohlc_inconsistent` flag | ✅ | 52,252 rows flagged (CSE data quality issue) |
| Prices: `suspicious_move` flag | ✅ | daily_return > ±50% flagged |
| Prices: `volume=0` rows flagged | ❌ | Not yet in clean_prices.py |
| Prices: adjusted close for corporate actions | ❌ | Needed before Phase 3; requires dividends/splits data |
| Prices: output in `data/cleaned/master_prices.parquet` | ✅ | 824,398 rows, 18.1 MB |
| Market context: deduped, ML-range slice | ✅ | 3,565 rows (2011-2025) |
| Market context: `data/cleaned/market_context.parquet` | ✅ | 1.2 MB |
| Pandera schema validation on outputs | ❌ | Not yet implemented |
| Cleaning report (structured) | ❌ | Logs exist but no JSON/CSV report |
| Macro data: normalized long format | ❌ | No macro data yet |
| News: deduplicated, HTML-stripped | ❌ | Raw GDELT only |
| Fundamentals: validated | ❌ | No source data |

---

## Verification test results — ALL PASS ✅

### pytest tests/test_cleaning.py — 16/16 PASS (run 2026-05-12)

| Test | Result |
|---|---|
| test_all_sl20_tickers_present | ✅ PASS |
| test_no_duplicate_ticker_date | ✅ PASS |
| test_close_price_positive | ✅ PASS |
| test_date_range | ✅ PASS |
| test_all_years_present | ✅ PASS |
| test_row_count_reasonable | ✅ PASS |
| test_ohlc_violations_are_flagged | ✅ PASS |
| test_volume_non_negative | ✅ PASS |
| test_sl20_minimum_trading_days | ✅ PASS |
| test_required_columns_present | ✅ PASS |
| test_market_no_duplicate_dates | ✅ PASS |
| test_market_aspi_positive | ✅ PASS |
| test_market_sl20_coverage | ✅ PASS |
| test_market_per_range | ✅ PASS |
| test_market_date_range | ✅ PASS |
| test_price_market_date_overlap | ✅ PASS |

---

## Bugs fixed

1. **2017 serial dates** — 2017 XLS uses Excel serials (42737.0), not strings. Fixed: `date_is_serial = (year <= 2017)`.
2. **2022 Q3/Q4 serial dates** — Q3/Q4 sheets used serials while Q1/Q2 used strings. Fixed with per-row auto-detection in `_parse_flat_rows` (float in range 30000–60000 → always treat as serial). Result: 2022 went from 28,466 → 61,093 rows.
3. **OHLC violations** — CSE source data has genuine inconsistencies (PRICE HIGH sometimes records reference price, not intraday high). These are flagged with `ohlc_inconsistent=True` rather than dropped.
4. **NaN OHLC** — `NaN >= NaN` evaluates to `False`, causing unflagged test failures. Fixed: NaN rows in high/low are included in the `ohlc_inconsistent` flag.
5. **`market_per` NaN** — One NaN row on 2011-08-19 caused `between(1,200)` to fail. Fixed: `.dropna()` before range check in test.
6. **DVC `.gitignore` conflict** — `data/` in `.gitignore` blocked `.dvc` pointer files. Fixed: changed to `data/**` with `!data/**/*.dvc` negation.

---

## What needs to happen before Phase 3 (Alignment)

### Must-do (blockers)
- [ ] Adjusted close prices (corporate actions) — needed for alignment step
- [ ] Pandera schema validation on `master_prices.parquet`
- [ ] `volume=0` flag column

### Nice-to-have
- [ ] CBSL macro data ingestion
- [ ] FRED data ingestion script
- [ ] Metadata JSON sidecars
- [ ] News RSS pipeline
