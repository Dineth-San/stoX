# stoX — The ML Data Pipeline

> How raw stock data goes from Excel files downloaded from the CSE website all the way to a clean, feature-rich dataset ready to train the AI model on.

---

## The Big Picture

Training an AI model on stock data requires a lot of preparation. You can't just throw raw prices at it. Here's the journey data takes:

```
Raw files (Excel, CSVs)
       ↓  Phase 1: Ingestion
Clean parquet files
       ↓  Phase 2: Cleaning + Adjustment
master_prices.parquet
       ↓  Phase 3: Alignment
sl20_daily_panel.parquet
       ↓  Phase 4: Feature Engineering
sl20_feature_panel.parquet  ← this is what the AI model trains on
       ↓  Phase 5: Validation
validation_report.md  ← automated quality checks
```

Each step is a separate Python script. You run them in order, once.

---

## What is a Parquet file?

A `.parquet` file is just a table — like an Excel spreadsheet — but stored in a format that computers can read extremely fast. Think of it as a high-performance CSV. You can open them with Python (pandas) or tools like DuckDB.

We don't commit parquet files to git because they're large (100MB+). Instead we use **DVC** — it stores a tiny `.dvc` "pointer" file in git that says "the real file lives here on disk." Anyone with the DVC cache can download the actual data.

---

## Phase 1 — Ingestion

**Script:** `ml/build_prices.py`, `ml/build_macro.py`, `ml/build_market.py`  
**Source code:** `ml/src/sl20_ml/ingestion/`

This phase reads raw data from various sources and converts it into clean parquet files.

### Data sources we pull from:

**CSE (Colombo Stock Exchange) price files**
- Two big Excel files covering 2011–2020 and 2021–2025
- Contains: open, high, low, close, volume for every trading day
- Source: `ml/src/sl20_ml/ingestion/prices.py`

**Corporate actions** (same CSE Excel files)
- Bonus issues, rights issues, share splits, dividends
- These matter because if a company issues a 1-for-1 bonus, the price halves overnight — that's not a 50% crash, it's just more shares. We need to correct for this.
- Source: `ml/src/sl20_ml/ingestion/corporate_actions.py`

**CBSL (Central Bank of Sri Lanka)**
- USD/LKR exchange rate (daily)
- Monetary policy rates (standing deposit rate, lending rate)
- Source: `ml/src/sl20_ml/ingestion/cbsl.py`

**FRED (Federal Reserve Economic Data)**
- Global macro: crude oil price (WTI), S&P 500, VIX (fear index), gold price
- These global factors affect Sri Lankan stocks (e.g. oil price affects LIOC directly)
- Source: `ml/src/sl20_ml/ingestion/fred.py`

**World Bank GDP data**
- Sri Lanka GDP growth rate (annual %)
- CPI inflation (annual %)
- These are annual numbers that get forward-filled across the year
- Source: `ml/src/sl20_ml/ingestion/gdp.py`

**CSE market data**
- ASPI (All Share Price Index) and SL20 index levels
- Market-wide P/E ratio
- Source: `ml/src/sl20_ml/ingestion/market.py`

---

## Phase 2 — Cleaning & Price Adjustment

**Script:** Part of `ml/build_prices.py`  
**Source code:** `ml/src/sl20_ml/cleaning/`

Raw data has problems. This phase fixes them.

### What gets cleaned:

**Impossible prices removed**
- Any closing price of zero or negative is dropped
- Rows where the same price is repeated for 30+ consecutive days are flagged (likely a data error or trading halt)

**Corporate action adjustment (the important one)**

Imagine LION stock is trading at LKR 100. The company announces a 2-for-1 bonus issue (every shareholder gets one extra share for free). After the issue, the price drops to ~LKR 50 — not because the company lost value, but because there are now twice as many shares.

If we don't correct this, the model sees a 50% price crash and learns the wrong thing.

We compute an **adjusted close** (`adj_close`) that accounts for:
- Bonus issues (free share giveaways)
- Rights issues (discounted share offers)
- Share splits (e.g. one LKR 10 share becomes 10 LKR 1 shares)
- Cash dividends (price drops on ex-dividend date)

The adjustment is applied in reverse — working backwards from today so that all historical prices are on a comparable basis.

**Output:** `data/cleaned/master_prices.parquet` — one row per (ticker, date), with both the original close and the adjusted close.

---

## Phase 3 — Panel Alignment

**Script:** `ml/build_alignment.py`  
**Source code:** `ml/src/sl20_ml/alignment/`

We now have prices and macro data in separate files, with different frequencies (prices: daily, GDP: annual, policy rate: monthly). This phase joins everything into one big table.

**The result:** `data/aligned/sl20_daily_panel.parquet`

- **71,300 rows** (20 tickers × ~3,565 trading days)
- Each row is one ticker on one trading day
- Macro data (monthly, annual) is forward-filled to daily — the last known value is carried forward until a new one arrives

**Calendar features added here:**
- `day_of_week` (0=Monday, 4=Friday)
- `month`, `quarter`
- `is_month_end`, `is_quarter_end` (these often coincide with fund rebalancing)
- `trading_day_of_month` (1st trading day, 2nd, etc.)

---

## Phase 4 — Feature Engineering

**Script:** `ml/build_features.py`  
**Source code:** `ml/src/sl20_ml/features/engineer.py`

This is the biggest step. We take the raw aligned panel and compute **130 features** — signals the AI model can learn from. Everything is computed strictly from *past data only* (no peeking at future prices).

### Feature groups:

**Price & Return features**
| Feature | What it means |
|---------|--------------|
| `log_close` | Natural log of the closing price — makes prices more stationary (removes exponential trends) |
| `daily_return` | % change from yesterday's close to today's |
| `ret_5d` / `ret_10d` / `ret_20d` / `ret_60d` | % return over 5, 10, 20, 60 trading days |

**Volatility features**
| Feature | What it means |
|---------|--------------|
| `vol_5d` / `vol_20d` / `vol_60d` | Rolling standard deviation of daily returns — how much the stock has been jumping around recently |

**Technical indicators**
These are formulas traders have used for decades. The model learns which ones are useful.

| Feature | What it means |
|---------|--------------|
| `rsi_14` | Relative Strength Index (14 days) — ranges 0–100. Above 70: possibly overbought. Below 30: possibly oversold. |
| `macd` / `macd_hist` | Moving Average Convergence Divergence — momentum signal based on the gap between two moving averages |
| `bb_pct` / `bb_width` | Bollinger Bands — where the price sits within its recent range, and how wide that range is |
| `atr_14` | Average True Range — average daily price swing over 14 days (a pure volatility measure) |
| `obv_ma_20` | On-Balance Volume moving average — whether volume is flowing into or out of the stock |
| `volume_ratio_20d` | Today's volume vs the 20-day average — a spike in volume often signals something is happening |
| `price_to_52w_high` | How close the stock is to its 52-week high (1.0 = at the high, 0.5 = 50% below it) |

**Cross-sectional features**
These compare each stock *against the other 19 stocks* on the same day. This gives the model a sense of relative performance.

| Feature | What it means |
|---------|--------------|
| `xs_zscore_daily_return` | Is today's return unusually high or low *relative to other SL20 stocks today*? |
| `xs_rank_ret_20d` | Rank of this stock's 20-day return among all 20 SL20 stocks (0=worst, 1=best) |
| `xs_zscore_rsi_14` | Is this stock's RSI unusually high/low compared to others? |

**Macro features** (same for all tickers on a given day)
`usd_lkr`, `policy_rate_mid`, `vix`, `oil_wti`, `sp500`, `gold`, `gdp_growth_pct`, `inflation_pct`, `aspi`, `sl20_index`, `market_per`

**The target (what we're predicting)**
`target_next_close` — the actual closing price of this stock on the *next* trading day. The model uses this during training to learn from its mistakes. At inference time (making real predictions), this column doesn't exist yet.

**Output:** `data/features/sl20_feature_panel.parquet`
- 71,300 rows × 130 columns
- 65,379 rows kept after dropping rows where the next-day price doesn't exist yet

---

## Phase 5 — Validation

**Script:** `ml/build_validation.py`  
**Source code:** `ml/src/sl20_ml/validation/`

Before feeding data to the AI, we run automated quality checks to catch problems.

**Checks performed:**
- **Null rate**: No column should have more than 5% missing values for price/technical features
- **Range violations**: RSI must be 0–100, prices must be positive, etc.
- **Staleness**: Monthly macro data forward-filled more than 35 days is flagged
- **Cross-sectional sanity**: The z-score features should be centred near zero across all tickers

**Outputs:**
- `ml/data/features/validation_report.md` — human-readable pass/fail report
- `ml/data/features/data_dictionary.md` — description of all 130 columns
- `ml/data/features/feature_stats.parquet` — mean, std, null%, min, max per column

---

## The Train/Val/Test Split

The data is split by **time** (never randomly — that would be cheating):

| Split | Date range | Purpose |
|-------|-----------|---------|
| **Train** | 2011–2021 | The model learns from this (46,875 samples) |
| **Validation** | 2022 | Used during training to check if the model is improving (4,451 samples) |
| **Test** | 2023–2025 | Final evaluation — the model never sees this during training (14,053 samples) |

We split by time because in real life, you always train on the past and predict the future. If you trained on data from 2025 and tested on 2018, you'd be cheating.

---

## Relevant Files

```
ml/
├── build_prices.py               ← Run first: ingestion + cleaning → master_prices.parquet
├── build_macro.py                ← Run second: macro ingestion → cbsl/fred/gdp parquets
├── build_market.py               ← Run third: market indices → market_context.parquet
├── build_alignment.py            ← Run fourth: join everything → sl20_daily_panel.parquet
├── build_features.py             ← Run fifth: compute features → sl20_feature_panel.parquet
├── build_validation.py           ← Run sixth: quality checks → validation_report.md
│
├── src/sl20_ml/
│   ├── ingestion/
│   │   ├── prices.py             ← Reads CSE Excel price files
│   │   ├── corporate_actions.py  ← Reads bonus/rights/split/dividend data
│   │   ├── cbsl.py               ← CBSL exchange rates and policy rates
│   │   ├── fred.py               ← FRED global macro (oil, S&P500, VIX, gold)
│   │   ├── gdp.py                ← World Bank GDP/CPI
│   │   └── market.py             ← CSE market indices and ratios
│   ├── cleaning/
│   │   ├── clean_prices.py       ← Price validation and adj_close computation
│   │   ├── clean_macro.py        ← Macro data cleaning and forward-fill
│   │   └── clean_market.py       ← Market index cleaning
│   ├── alignment/
│   │   ├── align.py              ← Joins all data sources into one panel
│   │   └── calendar.py           ← Adds calendar features (day of week, month, etc.)
│   ├── features/
│   │   └── engineer.py           ← Computes all 130 features
│   └── validation/
│       ├── checks.py             ← Individual quality check functions
│       ├── report.py             ← Generates the markdown report
│       └── schema.py             ← Expected column types and ranges
│
├── configs/pipeline.yaml         ← All settings (dates, tickers, file paths, windows)
│
└── data/
    ├── cleaned/*.dvc             ← DVC pointers for cleaned parquets
    ├── aligned/*.dvc             ← DVC pointer for the panel
    └── features/*.dvc            ← DVC pointers for feature panel and stats
```

---

→ **Next: [02-ml-model.md](./02-ml-model.md)** — How the AI model actually works
