# stoX — Feature Panel Data Dictionary

**Panel:** `sl20_feature_panel.parquet`  
**Shape:** 71,300 rows × 130 columns  
**Date range:** 2011-01-03 → 2025-12-31  
**Tickers:** 20 SL20 stocks  

Columns are grouped by source.  `Nullable` = Y means the column contains NaN for non-trading days or warm-up periods at the start of each ticker's history.

## Identity

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `date` | datetime64[ns] | N | CSE trading date |
| `ticker` | object | N | SL20 ticker symbol |
| `split` | object | N | Time-based split: train / val / test |

## Prices

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `open` | float64 | Y | Opening price (LKR) |
| `high` | float64 | Y | Intraday high price (LKR) |
| `low` | float64 | Y | Intraday low price (LKR) |
| `close` | float64 | Y | Closing price (LKR) |
| `adj_close` | float64 | Y | Backward-adjusted close (anchored to latest price) |
| `volume` | float64 | Y | Shares traded |
| `turnover` | float64 | Y | Turnover value (LKR mn) |
| `trades` | float64 | Y | Number of trades |
| `daily_return` | float64 | Y | (close - prev_close) / prev_close |
| `ohlc_inconsistent` | object | Y | Flag: OHLC data inconsistency detected |
| `suspicious_move` | object | Y | Flag: |daily_return| > 50% threshold |

## Market

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `aspi` | float64 | N | All Share Price Index |
| `mpi` | float64 | Y | Milanka Price Index |
| `sl20_index` | float64 | Y | S&P SL20 Index level |
| `astri` | float64 | N | All Share Total Return Index |
| `mtri` | float64 | Y | Milanka Total Return Index |
| `sl20_tri` | float64 | Y | S&P SL20 Total Return Index |
| `market_per` | float64 | Y | Market price-to-earnings ratio |
| `market_pbv` | float64 | Y | Market price-to-book-value ratio |
| `market_dy` | float64 | Y | Market dividend yield (%) |
| `equity_turnover_mn` | float64 | N | Total equity market turnover (LKR mn) |
| `shares_traded_000` | float64 | N | Total shares traded (thousands) |
| `trades_equity` | float64 | N | Total equity trade count |
| `market_cap_mn` | float64 | N | Total market capitalisation (LKR mn) |
| `sector_bfi` | float64 | N | Banking Finance & Insurance sector index |
| `sector_bft` | float64 | N | Beverages Food & Tobacco sector index |
| `sector_cp` | float64 | N | Chemicals & Pharmaceuticals sector index |
| `sector_ce` | float64 | N | Construction & Engineering sector index |
| `sector_div` | float64 | N | Diversified Holdings sector index |
| `sector_ft` | float64 | N | Footwear & Textiles sector index |
| `sector_hlt` | float64 | N | Healthcare sector index |
| `sector_ht` | float64 | N | Hotels & Travel sector index |
| `sector_inv` | float64 | N | Investment Trusts sector index |
| `sector_it` | float64 | N | Information Technology sector index |
| `sector_lp` | float64 | N | Land & Property sector index |
| `sector_mfg` | float64 | N | Manufacturing sector index |
| `sector_mtr` | float64 | N | Motors sector index |
| `sector_oil` | float64 | N | Oil Palms sector index |
| `sector_plt` | float64 | Y | Plantations sector index |
| `sector_pe` | float64 | N | Power & Energy sector index |
| `sector_srv` | float64 | N | Services sector index |
| `sector_ss` | float64 | N | Store Supplies sector index |
| `sector_tel` | float64 | N | Telecommunication sector index |
| `sector_trd` | float64 | N | Trading sector index |
| `tri_bfi` | float64 | N | BFI sector Total Return Index |
| `tri_bft` | float64 | N | BFT sector Total Return Index |
| `tri_cp` | float64 | N | CP sector Total Return Index |
| `tri_ce` | float64 | N | CE sector Total Return Index |
| `tri_div` | float64 | N | Diversified sector Total Return Index |
| `tri_ft` | float64 | N | FT sector Total Return Index |
| `tri_hlt` | float64 | N | Healthcare sector Total Return Index |
| `tri_ht` | float64 | N | Hotels & Travel sector Total Return Index |
| `tri_inv` | float64 | N | Investment Trusts sector Total Return Index |
| `tri_it` | float64 | N | IT sector Total Return Index |
| `tri_lp` | float64 | N | Land & Property sector Total Return Index |
| `tri_mfg` | float64 | N | Manufacturing sector Total Return Index |
| `tri_mtr` | float64 | N | Motors sector Total Return Index |
| `tri_oil` | float64 | N | Oil Palms sector Total Return Index |
| `tri_plt` | float64 | Y | Plantations sector Total Return Index |
| `tri_pe` | float64 | N | Power & Energy sector Total Return Index |
| `tri_srv` | float64 | N | Services sector Total Return Index |
| `tri_ss` | float64 | N | Store Supplies sector Total Return Index |
| `tri_tel` | float64 | N | Telecommunication sector Total Return Index |
| `tri_trd` | float64 | N | Trading sector Total Return Index |
| `debt_corp_000` | float64 | Y | Corporate debt traded (thousands LKR) |
| `debt_govt_000` | float64 | Y | Government debt traded (thousands LKR) |
| `funds_turnover_000` | float64 | Y | Unit trusts turnover (thousands LKR) |

## CBSL

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `usd_lkr` | float64 | N | USD/LKR exchange rate (daily, ffilled weekends) |
| `sdf_rate` | float64 | N | Standing Deposit Facility rate (%) |
| `slf_rate` | float64 | N | Standing Lending Facility rate (%) |
| `policy_rate_mid` | float64 | N | Policy rate midpoint = (SDF + SLF) / 2 (%) |

## FRED

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `oil_wti` | float64 | N | WTI crude oil price (USD/barrel) |
| `sp500` | float64 | N | S&P 500 index level |
| `vix` | float64 | N | CBOE VIX volatility index |
| `us_10y_yield` | float64 | N | US 10-year Treasury yield (%) |
| `dxy` | float64 | N | USD Dollar Index (DXY) |
| `gold` | float64 | N | Gold spot price (USD/troy oz) |

## GDP/WDI

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `gdp_growth_pct` | float64 | Y | Sri Lanka real GDP growth rate (% annual, World Bank) |
| `gdp_constant_usd` | float64 | Y | Sri Lanka real GDP constant 2015 USD (World Bank) |
| `inflation_pct` | float64 | Y | CPI inflation rate (% annual, World Bank) |
| `unemployment_pct` | float64 | Y | Unemployment rate (% of labour force, World Bank) |
| `gdp_days_stale` | float64 | Y | Calendar days since last annual GDP update (look-ahead guard) |

## Features

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `ret_5d` | float64 | Y | 5-trading-day cumulative return = close[t]/close[t-5]-1 |
| `ret_10d` | float64 | Y | 10-day cumulative return |
| `ret_20d` | float64 | Y | 20-day cumulative return (~1 month) |
| `ret_60d` | float64 | Y | 60-day cumulative return (~1 quarter) |
| `vol_5d` | float64 | Y | 5-day rolling std of daily_return |
| `vol_10d` | float64 | Y | 10-day rolling std of daily_return |
| `vol_20d` | float64 | Y | 20-day rolling std of daily_return |
| `vol_60d` | float64 | Y | 60-day rolling std of daily_return |
| `price_to_52w_high` | float64 | Y | close / 252-day rolling max close (0→1) |
| `price_to_52w_low` | float64 | Y | close / 252-day rolling min close (≥1) |
| `rsi_14` | float64 | Y | RSI(14) — Wilder's Relative Strength Index [0, 100] |
| `macd` | float64 | Y | MACD line = EMA(12) - EMA(26) |
| `macd_signal` | float64 | Y | MACD signal line = EMA(9) of MACD line |
| `macd_hist` | float64 | Y | MACD histogram = MACD - signal |
| `bb_upper` | float64 | Y | Bollinger Band upper = SMA(20) + 2σ |
| `bb_lower` | float64 | Y | Bollinger Band lower = SMA(20) - 2σ |
| `bb_pct` | float64 | Y | %B = (close - bb_lower) / (bb_upper - bb_lower) |
| `bb_width` | float64 | Y | Bandwidth = (bb_upper - bb_lower) / SMA(20) |
| `atr_14` | float64 | Y | ATR(14) using Wilder's EWM smoothing |
| `obv` | float64 | N | On-Balance Volume (cumulative signed volume) |
| `obv_ma_20` | float64 | Y | 20-day SMA of OBV |
| `volume_ratio_20d` | float64 | Y | volume / 20-day MA of volume (surge indicator) |
| `xs_zscore_daily_return` | float64 | Y | Cross-sectional z-score of daily_return (across 20 tickers, per day) |
| `xs_rank_daily_return` | float64 | Y | Cross-sectional percentile rank of daily_return (0→1] |
| `xs_zscore_ret_5d` | float64 | Y | Cross-sectional z-score of ret_5d |
| `xs_rank_ret_5d` | float64 | Y | Cross-sectional percentile rank of ret_5d (0→1] |
| `xs_zscore_ret_10d` | float64 | Y | Cross-sectional z-score of ret_10d |
| `xs_rank_ret_10d` | float64 | Y | Cross-sectional percentile rank of ret_10d (0→1] |
| `xs_zscore_ret_20d` | float64 | Y | Cross-sectional z-score of ret_20d |
| `xs_rank_ret_20d` | float64 | Y | Cross-sectional percentile rank of ret_20d (0→1] |
| `xs_zscore_vol_20d` | float64 | Y | Cross-sectional z-score of vol_20d |
| `xs_rank_vol_20d` | float64 | Y | Cross-sectional percentile rank of vol_20d (0→1] |
| `xs_zscore_rsi_14` | float64 | Y | Cross-sectional z-score of rsi_14 |
| `xs_rank_rsi_14` | float64 | Y | Cross-sectional percentile rank of rsi_14 (0→1] |
| `xs_zscore_volume` | float64 | Y | Cross-sectional z-score of volume |
| `xs_rank_volume` | float64 | Y | Cross-sectional percentile rank of volume (0→1] |

## Calendar

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `day_of_week` | int32 | N | Day of week: 0=Monday, 4=Friday |
| `month` | int32 | N | Calendar month (1–12) |
| `quarter` | int32 | N | Calendar quarter (1–4) |
| `is_month_end` | int64 | N | 1 if last calendar day of month, else 0 |
| `is_quarter_end` | int64 | N | 1 if last calendar day of quarter, else 0 |
| `trading_day_of_month` | int64 | N | Ordinal position among trading days within the month |

## Quality

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `gdp_stale_flag` | int64 | N | 1 if gdp_days_stale > 395 days (> 1 year + 1 month) |

## Target

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `target_next_close` | float64 | Y | Next trading day's close price (the prediction target) |
| `target_next_return` | float64 | Y | (target_next_close / close) - 1 |
