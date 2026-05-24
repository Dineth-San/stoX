# News Sentiment — Build Plan

> Implementation guide for the news sentiment model that adjusts the TFT's P10/P90 bands at inference time.

---

## 1. Goal

Build a **daily per-ticker sentiment score** for each of the 20 SL20 stocks, derived from financial news, and use it to **adjust the TFT's P10/P50/P90 prediction bands at inference time** — *without retraining the TFT*.

The sentiment model is a **post-hoc adjustment layer**. The TFT remains the source of truth for the base forecast; sentiment shifts and widens the band based on recent news flow.

---

## 2. Data sources

| Source | Coverage | How to fetch | Notes |
|--------|----------|--------------|-------|
| **CSE official announcements** | Per-ticker corporate filings, earnings, dividends, board decisions | CSE paid API/portal (user has membership) — confirm exact endpoint | Highest signal-to-noise. These are the events that actually move prices. |
| **Almas site** *(USER TO CONFIRM EXACT URL)* | Local SL financial news, market commentary | RSS feed if available, otherwise BeautifulSoup scrape | If "Almas" was a misremembering, likely candidates: `adaderana.lk`, `ft.lk` (Daily FT), `echelon.lk`, `dailymirror.lk/business` |
| *(Optional later)* GDELT | Global news mentioning SL economy / tickers | Free GDELT 2.0 API | Already wired in `pipeline.yaml` paths — broad coverage, noisy |

**Action item for user:** Before Claude Code starts, confirm:
1. CSE API endpoint and auth method
2. The exact URL of the "Almas" site (and whether it's RSS-accessible or needs scraping)

---

## 3. Pipeline stages

Implement as four scripts in `ml/`, mirroring the existing price/macro/market pipeline pattern:

### Stage 1 — Ingestion (`ml/build_news_ingest.py`)
- Fetch raw news from CSE + Almas
- Save raw HTML/JSON to `ml/data/raw/news/cse/` and `ml/data/raw/news/local/`
- Idempotent: only fetch dates not already present
- Schema written to parquet: `[timestamp, source, ticker_mentioned (nullable), headline, body, url]`

### Stage 2 — Cleaning & ticker tagging (`ml/build_news_clean.py`)
- Deduplicate (URL hash + headline near-match via fuzzy matching)
- **Ticker tagging:** identify which SL20 tickers are mentioned via:
  - Exact ticker match (e.g. "JKH")
  - Company name match (e.g. "John Keells Holdings" → JKH)
  - Sector mentions get assigned to all tickers in the sector
- Drop articles with no SL20 mention
- Output: `ml/data/cleaned/news.parquet`

### Stage 3 — Sentiment scoring (`ml/build_news_sentiment.py`)
- **Model:** [FinBERT](https://huggingface.co/ProsusAI/finbert) — pretrained on financial news, 3-class (positive/negative/neutral)
- Run on headline + first 200 words of body
- Output per article: `[sentiment_score ∈ [-1, +1], confidence ∈ [0, 1]]`
- `sentiment_score = P(positive) - P(negative)` (signed scalar)
- Batched inference on CPU is fine — FinBERT is small (~110M params, ~30 articles/sec)
- Cache scores per article URL so re-runs are fast

### Stage 4 — Daily aggregation (`ml/build_news_features.py`)
For each `(date, ticker)` pair, compute:

| Feature | Formula | Why |
|---------|---------|-----|
| `news_sentiment` | weighted mean of article sentiments, weighted by confidence | The core signal |
| `news_volume` | count of articles in last 1 day | High volume = market focus on this ticker |
| `news_volume_7d` | count over last 7 days | Smoothed attention |
| `news_dispersion` | std of sentiment across articles | High dispersion = mixed signals = more uncertainty |
| `news_momentum` | sentiment_today − rolling mean (7-day) | Sudden tone shifts |
| `days_since_news` | days since last article mentioning ticker | Decays the signal when nothing is happening |

Output: `ml/data/features/news_features.parquet`, then merged into the main `sl20_feature_panel.parquet` by `build_features.py`.

---

## 4. How sentiment adjusts the TFT prediction

This is the **critical integration point**. Implementation lives in `backend/app/services/prediction_service.py`.

### The formula

For each ticker on each prediction day, after the TFT outputs `[P10, P50, P90]` (calibrated by conformal δ), we apply:

```
recent_vol     = stdev(last 20 days of log returns)   # ticker's natural daily volatility
sentiment      = news_sentiment for (ticker, as_of_date), default 0 if no news
dispersion     = news_dispersion, default 0
volume_factor  = min(1.0, news_volume_7d / 5)         # cap influence when few articles

α = 0.30   # how much sentiment shifts P50  (tune on val)
β = 0.20   # how much sentiment widens band (tune on val)

# Directional shift of all three bands
shift   = α × sentiment × recent_vol × volume_factor

# Extra uncertainty widening from disagreement
widen   = β × dispersion × recent_vol × volume_factor

P10_adj = P10 + shift − widen
P50_adj = P50 + shift                # P50 only shifts, never widens
P90_adj = P90 + shift + widen
```

### What this does intuitively
- **Strongly positive news** (e.g. earnings beat) → all three bands shift up
- **Strongly negative news** (e.g. fraud allegation) → all three bands shift down
- **Conflicting articles** (some bullish, some bearish) → band widens; uncertainty up
- **No news at all** → no adjustment; falls back to pure TFT output
- **Caps at `volume_factor=1`** when ≥5 articles in 7 days → prevents over-reaction to a single rumour

### Why α=0.30, β=0.20 as starting values
These cap maximum sentiment-driven shift at ~30% of one daily σ. For a 2% vol stock that's a ±0.6% band shift — meaningful but not dominant. Final values are **tuned on the validation set** to maximise calibrated coverage at 90% (same target as conformal δ).

### Calibration script (`ml/calibrate_sentiment.py`)
1. Run TFT on validation set → get P10/P50/P90
2. Grid-search α ∈ [0, 0.1, 0.2, …, 0.6] and β ∈ [0, 0.1, 0.2, 0.3] (24 combinations)
3. Apply adjustment, recompute coverage and MAE
4. Pick (α, β) that **maintains ≥90% coverage AND minimises MAE** vs the no-sentiment baseline
5. Write `α`, `β` to `models/tft_v1/model_config.json` under `sentiment_calibration`
6. `prediction_service.py` reads these at inference

If no (α, β) improves MAE, **set them to 0** and document that sentiment didn't add signal. This is a real outcome — it's listed as a known risk in `backend/01_project_scope_1.md`.

---

## 5. End-to-end output schema

What the user sees in the frontend prediction card after the sentiment layer:

```json
{
  "ticker": "JKH",
  "as_of_date": "2025-12-30",
  "last_close": 21.10,
  "p10": 20.72,           // ← post-sentiment-adjusted
  "p50": 21.10,
  "p90": 21.63,
  "sentiment": {
    "score": 0.42,         // [-1, +1], +0.42 = mildly positive
    "label": "positive",
    "volume_7d": 8,
    "top_headline": "John Keells Holdings reports 18% earnings beat for Q3",
    "adjustment_lkr": 0.08  // how much shift this added to P50, in LKR
  }
}
```

The `sentiment` block is **purely informational** for the user — the actual P10/P50/P90 are already post-adjustment. The frontend can show a sentiment chip and the headline that drove the score.

---

## 6. Implementation order (suggested)

| Step | Task | Files | Effort |
|------|------|-------|--------|
| 1 | Confirm data sources (CSE + Almas URLs) | this doc | 5 min — user task |
| 2 | Build ingestion script | `build_news_ingest.py`, `src/sl20_ml/ingestion/news.py` | ~2 hrs |
| 3 | Build cleaning + ticker tagging | `build_news_clean.py`, `src/sl20_ml/cleaning/clean_news.py` | ~2 hrs (most logic is ticker matching) |
| 4 | Add FinBERT sentiment scoring | `build_news_sentiment.py`, `src/sl20_ml/sentiment/finbert.py` | ~1 hr (mostly boilerplate around HF transformers) |
| 5 | Daily aggregation → features | `build_news_features.py` | ~1 hr |
| 6 | Wire into `build_features.py` so panel includes news features | `build_features.py` | ~30 min |
| 7 | Implement adjustment formula in backend | `backend/app/services/prediction_service.py` | ~1 hr |
| 8 | Calibrate (α, β) on val set | `calibrate_sentiment.py` | ~1 hr |
| 9 | Add `sentiment` block to prediction response | `backend/app/models/stocks.py`, `routers/stocks.py` | ~30 min |
| 10 | Update frontend prediction card to show sentiment chip + headline | `frontend/src/...` | ~1 hr |

**Total ~10 hours of focused work.** Most complexity is in ingestion (every source is different) and ticker tagging (lots of edge cases).

---

## 7. File locations (where everything lives)

```
ml/
├── build_news_ingest.py              ← new — fetches raw news
├── build_news_clean.py               ← new — dedupes, tags tickers
├── build_news_sentiment.py           ← new — FinBERT scoring
├── build_news_features.py            ← new — daily aggregation
├── calibrate_sentiment.py            ← new — tunes (α, β) on val
├── src/sl20_ml/
│   ├── ingestion/
│   │   └── news.py                   ← new — CSE + Almas fetchers
│   ├── cleaning/
│   │   └── clean_news.py             ← new — dedup + ticker tagging
│   └── sentiment/
│       ├── __init__.py               ← new module
│       └── finbert.py                ← new — FinBERT wrapper
└── data/
    ├── raw/news/
    │   ├── cse/                      ← CSE announcements (already in pipeline.yaml)
    │   └── local/                    ← Almas / other local sources (rename from gdelt/)
    ├── cleaned/news.parquet          ← already in pipeline.yaml
    └── features/news_features.parquet ← new

backend/app/services/
└── prediction_service.py             ← edit — apply sentiment adjustment

models/tft_v1/model_config.json       ← edit — add `sentiment_calibration: {alpha, beta}`
```

---

## 8. Success criteria

The sentiment layer is **successful** if, after calibration on the validation set:

1. **Coverage stays ≥ 90%** on test — must not break the conformal guarantee
2. **Test MAE improves by ≥ 3%** vs the TFT-only baseline (currently 0.0115)
3. **Directional accuracy improves by ≥ 2 percentage points** on days with `news_volume_7d ≥ 3` (the days where sentiment actually has signal)
4. **No regression on days with no news** — adjustment must be zero when `news_volume = 0`

If criteria 2 and 3 fail but criterion 1 holds, ship with α=β=0 and keep the data pipeline running — adding sentiment as a *transparent feature* in the UI without it influencing predictions. The data is still valuable for users to see why the model is uncertain.

---

## 9. What this plan deliberately does NOT do

- **No TFT retraining.** Sentiment is post-hoc — keeps the existing model frozen.
- **No custom sentiment model training.** FinBERT is pretrained on finance; training our own would need labelled Sri Lankan financial corpus we don't have.
- **No real-time sentiment.** Daily batch is fine — predictions are next-day anyway.
- **No multi-language.** Sinhala/Tamil news ignored for v1. Most CSE-relevant coverage is in English. Could add later if signal is missing.
- **No social media** (Twitter/X, Reddit). Out of scope — noise:signal ratio is poor for thin markets like CSE.
