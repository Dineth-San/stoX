# stoX — Project Overview

> Read this file first. It explains what stoX is, why it exists, and how all the pieces fit together.

---

## What is stoX?

stoX is a **stock prediction platform for the Sri Lankan stock market** — specifically the **S&P SL20 index**, which is the top 20 companies listed on the Colombo Stock Exchange (CSE).

The goal is simple: given everything we know about a stock up to today, **predict where its price will be tomorrow**, and give an honest estimate of how uncertain that prediction is.

It's a full-stack product:
- A **machine learning model** that does the actual prediction
- A **web dashboard** where you can see those predictions, explore stocks, and track a portfolio

---

## The 20 SL20 Stocks

These are the tickers the system tracks:

`JKH` · `COMB` · `DIAL` · `SAMP` · `HAYL` · `CTC` · `HNB` · `LIOC` · `SPEN` · `DFCC` · `NTB` · `BUKI` · `CARG` · `CCS` · `HHL` · `LION` · `MELS` · `TKYO` · `VONE` · `AEL`

Data goes back to **2011**, giving us about 14 years of history to train on.

---

## How the Prediction Works (Plain English)

1. Every day, for each stock, we collect: the closing price, trading volume, technical signals (like momentum and volatility), and macro context (USD/LKR rate, global oil price, etc.)

2. We feed the **last 60 trading days** of all that data into an AI model.

3. The model outputs **three numbers** for the next day's closing price:
   - **P10** — there's only a 10% chance the price will be *below* this
   - **P50** — the model's best single guess (the median prediction)
   - **P90** — there's only a 10% chance the price will be *above* this

   The gap between P10 and P90 is the model's "I'm not sure" zone. A wide band means high uncertainty; a narrow band means confident.

---

## Project Structure

```
stoX/
├── ml/                   ← The Python ML pipeline (all the AI work)
│   ├── src/sl20_ml/      ← All the Python source code (importable package)
│   ├── data/             ← Raw, cleaned, and feature data (large files, tracked by DVC)
│   ├── models/           ← Saved AI model files
│   ├── configs/          ← Settings file (pipeline.yaml)
│   ├── tests/            ← Automated tests
│   ├── build_*.py        ← Scripts to run each pipeline step
│   └── train_model.py    ← Script to train the AI model
│
├── frontend/             ← The Next.js web dashboard
│   └── app/
│       └── src/
│           ├── app/      ← Pages (dashboard, predictions, portfolio, news)
│           └── components/ ← Reusable UI components
│
└── docs/                 ← You are here — these documentation files
    ├── 00-project-overview.md    ← Start here
    ├── 01-ml-data-pipeline.md   ← How we get and prepare the data
    ├── 02-ml-model.md            ← How the AI model works
    └── 03-frontend.md            ← The web dashboard
```

---

## What's Been Built So Far

| Area | Status | What it does |
|------|--------|-------------|
| Data ingestion | ✅ Done | Downloads/reads CSE price files, macro data |
| Data cleaning | ✅ Done | Fixes prices for stock splits, dividends, etc. |
| Feature engineering | ✅ Done | Computes 130 ML-ready signals from raw data |
| Feature validation | ✅ Done | Checks data quality automatically |
| ML model (TFT) | ✅ Trained | Predicts next-day prices with P10/P50/P90 |
| Web dashboard | 🔄 Scaffold | Pages built with mock data, needs real backend |
| Backend API | ❌ Not started | Will serve predictions to the frontend |

---

## Key Technologies (don't worry if these are new)

| Name | What it is | Where it's used |
|------|-----------|----------------|
| **Python** | Programming language | All ML work |
| **PyTorch** | AI/deep learning framework | The model itself |
| **pytorch-forecasting** | Library built on PyTorch for time-series AI | Building and training the TFT model |
| **pandas** | Python data manipulation library | Working with tables of data |
| **DVC** | "Data Version Control" — like git but for large data files | Tracking datasets without putting them in git |
| **MLflow** | Tracks ML experiments (logs metrics per training run) | Seeing how training went |
| **Next.js** | React framework for web apps | The frontend dashboard |
| **TypeScript** | Typed version of JavaScript | Frontend code |
| **Tailwind CSS** | CSS utility framework | Frontend styling |
| **shadcn/ui** | UI component library | Frontend buttons, tables, cards |

---

## Read Next

→ **[01-ml-data-pipeline.md](./01-ml-data-pipeline.md)** — How we get and prepare the data  
→ **[02-ml-model.md](./02-ml-model.md)** — How the AI model actually works  
→ **[03-frontend.md](./03-frontend.md)** — The web dashboard  
