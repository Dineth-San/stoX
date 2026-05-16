# stoX — ML Data Pipeline

Builds the feature dataset for next-day closing price prediction on the S&P SL20 index (Colombo Stock Exchange).

## Quick start

```bash
# 1. Install dependencies
uv sync

# 2. Copy and fill environment variables
cp .env.example .env
# Edit .env — add FRED_API_KEY at minimum

# 3. Run the full pipeline (order matters)
python build_prices.py        # Phase 1+2: CSE daily prices
python build_market.py        # Phase 1+2: Market indices + ratios
# ... Phase 3-6 scripts added as pipeline progresses

# 4. Run tests
pytest tests/ -v
```

## Folder structure

```
ml/
├── pyproject.toml              # Project definition + dependencies (uv)
├── .env.example                # Required env variable names (copy to .env)
├── configs/
│   └── pipeline.yaml           # ALL settings: tickers, dates, paths, thresholds
├── src/
│   └── sl20_ml/
│       ├── ingestion/          # Phase 1: Read raw source files
│       ├── cleaning/           # Phase 2: Normalize, flag, deduplicate
│       ├── alignment/          # Phase 3: Join onto trading calendar
│       ├── features/           # Phase 4: Engineer model features
│       ├── validation/         # Phase 5: Schema + look-ahead bias checks
│       └── utils/              # Shared helpers (config loader, etc.)
├── tests/                      # pytest test suite — one file per phase
├── notebooks/                  # Exploratory notebooks (not part of pipeline)
├── data/
│   ├── raw/                    # Source files — never modified after placement
│   │   ├── cse/                # CSE Excel/CSV files (manual placement)
│   │   ├── cbsl/               # CBSL macro data (manual placement)
│   │   ├── fred/               # FRED data (fetched by ingestion script)
│   │   ├── news/               # GDELT + RSS feeds
│   │   └── fundamentals/       # Quarterly financials (manual placement)
│   ├── cleaned/                # Phase 2 outputs (Parquet)
│   ├── aligned/                # Phase 3 output: sl20_daily_panel.parquet
│   └── features/               # Phase 6 output: sl20_feature_panel.parquet
└── models/                     # Trained model artifacts
```

## Phase status

See `PIPELINE_STATUS.md` for current progress and what's done.

## Configuration

Everything is driven by `configs/pipeline.yaml` — no hardcoded values in scripts.
Key sections:

- `tickers.sl20` — the 20 SL20 ticker symbols
- `dates` — historical range + train/val/test split cutoffs
- `paths` — all file locations relative to `ml/`
- `cleaning` — thresholds for flagging/dropping rows
- `features` — window sizes and model parameters
- `feature_toggles` — turn feature groups on/off without touching code

## Data versioning (DVC)

```bash
dvc status        # Check which data files are out of sync
dvc repro         # Re-run any stage whose inputs have changed
dvc push          # Push data to remote (configure remote in .dvc/config)
```

## Experiment tracking (MLflow)

```bash
mlflow ui         # Open tracking UI at http://localhost:5000
```

## Running tests

```bash
pytest tests/ -v                         # All tests
pytest tests/test_cleaning.py -v        # Phase 2 only
pytest tests/ -v --tb=short             # Short traceback
```
