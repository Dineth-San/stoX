# stoX — The Frontend Dashboard

> The web interface that shows stock predictions, portfolio analytics, and market news.

---

## What's Been Built

A **Next.js 14** web application with a full set of pages and components. Currently runs on **mock data** (realistic fake data generated in the browser). It's waiting for a backend API to be built before it can show real predictions.

Think of it as the shell of the product — everything looks and works correctly, but the numbers it shows aren't real yet.

---

## How to Run It

```bash
cd frontend/app
npm install        # first time only
npm run dev        # starts the dev server

# Open http://localhost:3000
```

---

## Pages

### `/dashboard` — Market Overview
The main landing page. Shows:
- All 20 SL20 tickers in a table with today's price, daily change, and a sparkline (a tiny chart of recent price movement)
- Key market stats at the top (total market cap, average return, volatility index)
- Signal badges: **BUY** / **HOLD** / **SELL** based on the model's P50 prediction vs current price

**Relevant file:** `frontend/app/src/app/dashboard/page.tsx`

---

### `/predictions` — Predictions Table
A detailed table of TFT model predictions for all 20 tickers. Shows:
- P10 / P50 / P90 prices for tomorrow
- The uncertainty range (P90 − P10) — wider = less certain
- Directional signal (up/down arrow)
- Confidence level based on quantile band width

**Relevant files:**
- `frontend/app/src/app/predictions/page.tsx`
- `frontend/app/src/app/predictions/PredictionsTable.tsx`

---

### `/predictions/[ticker]` — Individual Stock View
Click any ticker to see a full detail page:
- A forecast chart showing P10/P50/P90 as a shaded band
- Historical price chart
- Feature importance (which inputs the model weighted most)
- Recent news sentiment for that ticker

**Relevant file:** `frontend/app/src/app/predictions/[ticker]/page.tsx`

---

### `/portfolio` — Portfolio Tracker
Track a personal portfolio against predictions:
- Holdings table (shares, average cost, current value)
- Portfolio value chart over time
- Unrealised P&L

**Relevant file:** `frontend/app/src/app/portfolio/page.tsx`

---

### `/news` — News Feed
Market news affecting SL20 stocks:
- News items with sentiment chips (positive / negative / neutral)
- Filtered by ticker

**Relevant file:** `frontend/app/src/app/news/page.tsx`

---

## Key Components

```
frontend/app/src/components/
│
├── charts/
│   ├── PredictionChart.tsx   ← The P10/P50/P90 band chart (Recharts)
│   ├── SparklineChart.tsx    ← Tiny 30-day price chart in table rows
│   └── PortfolioChart.tsx    ← Portfolio value over time
│
├── feature/
│   ├── StockRow.tsx          ← One row in the predictions/dashboard table
│   ├── StatCard.tsx          ← A KPI card (e.g. "JKH — LKR 183.50 ▲ 1.2%")
│   ├── SignalBadge.tsx       ← The BUY / HOLD / SELL coloured badge
│   ├── SentimentChip.tsx     ← News sentiment indicator (green/red/grey dot)
│   └── TradeItem.tsx         ← A single trade in portfolio history
│
└── layout/
    ├── Navbar.tsx            ← Top navigation bar
    └── Footer.tsx            ← Footer
```

---

## How Data Currently Works

Right now, all data is **mocked** — generated in-browser with realistic but fake numbers. The mock data layer lives in:

```
frontend/app/src/lib/
├── mock/
│   ├── fixtures.ts     ← Static mock data (tickers, company names, etc.)
│   └── generators.ts   ← Functions that generate fake price series, predictions
└── api/
    ├── client.ts       ← The API client (currently calls mock data, will call real backend)
    └── types.ts        ← TypeScript type definitions for all data structures
```

When the backend API is ready, you only need to update `client.ts` to point at the real endpoints. All the pages and components stay the same.

---

## Tech Stack

| Tool | Version | What it does |
|------|---------|-------------|
| **Next.js** | 14 | React framework, handles routing, server/client rendering |
| **TypeScript** | 5 | Typed JavaScript — catches bugs before they happen |
| **Tailwind CSS** | 3 | Utility CSS classes — write styling directly in HTML |
| **shadcn/ui** | latest | Pre-built UI components (buttons, tables, cards, dialogs) |
| **Recharts** | 2 | Chart library used for prediction bands and sparklines |

---

## What's Not Built Yet

| Feature | Status |
|---------|--------|
| Real API connection | ❌ Needs backend (FastAPI or similar) |
| Authentication / login | ❌ Not started |
| Real portfolio persistence | ❌ Mock only |
| Real news integration | ❌ Mock only |
| Mobile responsiveness | 🔄 Basic, needs polish |

---

## Relevant Files (Full Map)

```
frontend/
└── app/
    ├── package.json                   ← Dependencies (Next.js, Tailwind, Recharts...)
    ├── tailwind.config.ts             ← Tailwind configuration
    ├── tsconfig.json                  ← TypeScript configuration
    ├── next.config.mjs               ← Next.js configuration
    └── src/
        ├── app/
        │   ├── layout.tsx             ← Root layout (Navbar, fonts, global CSS)
        │   ├── page.tsx               ← Root page (redirects to /dashboard)
        │   ├── globals.css            ← Global styles
        │   ├── dashboard/page.tsx     ← Market overview
        │   ├── predictions/
        │   │   ├── page.tsx           ← All-tickers predictions table
        │   │   ├── PredictionsTable.tsx ← Table component
        │   │   └── [ticker]/page.tsx  ← Individual stock detail
        │   ├── portfolio/page.tsx     ← Portfolio tracker
        │   └── news/page.tsx          ← News feed
        ├── components/
        │   ├── charts/                ← Chart components (Recharts)
        │   ├── feature/               ← Domain-specific UI components
        │   └── layout/                ← Navbar, Footer
        ├── hooks/
        │   └── useSriLankaTime.ts     ← Hook for SL timezone display
        └── lib/
            ├── utils.ts               ← Shared utility functions
            ├── api/client.ts          ← API client (swap mock → real here)
            ├── api/types.ts           ← All TypeScript data types
            ├── mock/fixtures.ts       ← Static mock data
            └── mock/generators.ts    ← Mock data generators
```

---

→ **Back to: [00-project-overview.md](./00-project-overview.md)**
