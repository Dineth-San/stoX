# stoX — Data Pipeline Status

Reference spec: `03_data_pipeline_claude_code.md`  
Last updated: 2026-05-12

---

## Phase Tracker

| Phase | Name                        | Status          | Notes |
|-------|-----------------------------|-----------------|-------|
| 0     | Environment & Project Setup | 🔄 In progress  | Partial structure exists; DVC/MLflow/uv/configs missing |
| 1     | Raw Data Ingestion          | 🔄 In progress  | CSE data present; CBSL/FRED/news/fundamentals missing |
| 2     | Cleaning Layer              | 🔄 In progress  | Prices + market context cleaned; pandera + adj-close missing |
| 3     | Alignment Layer             | ⬜ Not started  | |
| 4     | Feature Engineering         | ⬜ Not started  | |
| 5     | Validation & Quality Checks | ⬜ Not started  | |
| 6     | Feature Store Output        | ⬜ Not started  | |

---

## What exists right now vs what the spec requires

### Phase 0 — Environment & Project Setup

| Requirement | Status | Notes |
|---|---|---|
| `ml/` folder exists | ✅ | |
| `pyproject.toml` (with `uv`) | ❌ | Have `requirements.txt` instead |
| DVC initialized + tracking `data/` | ❌ | Not set up |
| MLflow configured (local) | ❌ | Not set up |
| `.env.example` template | ❌ | Missing |
| `configs/pipeline.yaml` | ❌ | Missing — values hardcoded in scripts |
| Correct `src/sl20_ml/` package layout | ❌ | Have `src/data/loaders/` instead |
| `data/raw/cse/`, `data/cleaned/`, `data/aligned/`, `data/features/` | ❌ | Have `data/stock_data/` and `processed/` |
| `tests/` folder with test files | ❌ | Missing |
| `models/` folder | ❌ | Missing |
| `notebooks/` folder | ✅ | Exists (empty) |
| `README.md` | ❌ | Missing |

### Phase 1 — Raw Data Ingestion

| Requirement | Status | Notes |
|---|---|---|
| CSE raw files in `data/raw/cse/` | 🔄 | Files exist in `data/stock_data/` (wrong path) |
| Metadata JSON sidecars per source file | ❌ | Missing |
| Ingestion scripts (read + validate only, no transform) | 🔄 | Current scripts combine ingestion + cleaning |
| CBSL macroeconomic data | ❌ | User still downloading |
| FRED global macro data | ❌ | Script not written |
| News RSS ingestion | ❌ | GDELT CSVs exist; RSS pipeline not built |
| Quarterly fundamentals | ❌ | No source files available |
| All scripts importable as functions | 🔄 | Partial |
| Summary inventory script | ❌ | Missing |

### Phase 2 — Cleaning Layer

| Requirement | Status | Notes |
|---|---|---|
| Prices: standard columns (date, ticker, open, high, low, close, volume) | ✅ | Done |
| Prices: timezone-naive dates | ✅ | Done |
| Prices: deduplicated (date, ticker) | ✅ | Done — 61,434 dupes removed |
| Prices: volume=0 rows flagged | ❌ | Missing — spec says flag, not drop |
| Prices: adjusted close for corporate actions | ❌ | Not done — needed for Step 3 |
| Prices: output in `data/cleaned/` | ❌ | Currently in `processed/` |
| Pandera schema validation on output | ❌ | Not implemented |
| Cleaning report (rows in/out/dropped per reason) | 🔄 | Partial — logs exist but no structured report |
| Market context: deduped, ML-range slice | ✅ | Done |
| Macro data: normalized long format | ❌ | No macro data yet |
| News: deduplicated, HTML-stripped | ❌ | Raw GDELT only |
| Fundamentals: validated | ❌ | No source data |

---

## Verification test results (run 2026-05-12) — ALL PASS ✅

### master_prices.parquet — 17/17 PASS

| Check | Result | Detail |
|---|---|---|
| All 20 SL20 tickers present | ✅ PASS | 20/20 |
| No duplicate (ticker, date) | ✅ PASS | 0 dupes |
| All close > 0 | ✅ PASS | min = 0.1 |
| Date range 2011–2025 | ✅ PASS | 2011-01-03 to 2025-12-31 |
| All 15 years present | ✅ PASS | [2011..2025] |
| Row count 800k–900k | ✅ PASS | 824,398 rows |
| High >= Low (unflagged rows) | ✅ PASS | 52,252 OHLC-inconsistent rows flagged and excluded |
| High >= Close (unflagged rows) | ✅ PASS | same |
| Low <= Close (unflagged rows) | ✅ PASS | same |
| Volume >= 0 | ✅ PASS | 0 negatives |
| All SL20 tickers 1500+ trading days | ✅ PASS | min = 2,098 (MELS — listed after 2011) |
| 2022 has full year data | ✅ PASS | DIAL: 231 days (was 107 before fix) |
| market: no duplicate dates | ✅ PASS | |
| market: ASPI > 0 | ✅ PASS | |
| market: sl20_index >= 90% coverage | ✅ PASS | 90.0% |
| market: market_per in range 1–200 | ✅ PASS | 4.5 to 29.5 |
| Price/market date overlap > 3400 | ✅ PASS | 3,565 common dates |

### Bugs fixed during this session
1. **2022 Q3/Q4 serial dates** — Q3/Q4 sheets used Excel serial numbers while Q1/Q2 used strings. Fixed with per-row auto-detection in `_parse_flat_rows`. Result: 2022 went from 28,466 → 61,093 rows.
2. **OHLC violations** — CSE source data has genuine inconsistencies (PRICE HIGH sometimes records reference price not intraday high). These are flagged with `ohlc_inconsistent=True` column rather than dropped.

---

## What needs to happen before moving to Phase 3

### Must-do (blockers)
- [ ] Phase 0: Set up `pyproject.toml`, `configs/pipeline.yaml`, folder structure, DVC, MLflow
- [ ] Fix 2022 Q3/Q4 serial date parsing bug
- [ ] Add `ohlc_inconsistent` flag column to prices
- [ ] Move processed outputs to `data/cleaned/` (spec-required location)
- [ ] Add pandera schema validation
- [ ] Rename `src/data/` package to `src/sl20_ml/` with correct submodules

### Nice-to-have (not blockers for Phase 3)
- [ ] CBSL macro data (user downloading)
- [ ] FRED data ingestion script
- [ ] News RSS pipeline
- [ ] Metadata JSON sidecars
