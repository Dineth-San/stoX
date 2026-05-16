\# stoX — Claude Code Project Brief



\## What this project is

stoX is a full-stack web application that predicts next-day closing prices for 

stocks in the S\&P SL20 index (Colombo Stock Exchange) using a machine learning 

model, and runs an automated paper trading simulator based on those predictions.

This brief covers the FRONTEND only. The backend and ML model are built 

separately and integrated later.



\## Current task

Build the complete Next.js frontend for stoX using mock data. The API client 

is abstracted so that swapping mock data for the real backend later requires 

only changing a single config flag — no component changes.



\---



\## Tech stack

\- Next.js 14 (App Router, TypeScript)

\- Tailwind CSS

\- shadcn/ui for UI primitives

\- Recharts for all charts

\- Zustand for client state

\- lucide-react for icons

\- No MSW — mock data comes from static TypeScript fixtures



\---



\## Color palette — apply strictly

| Token         | Hex       | Usage |

|---------------|-----------|-------|

| Background    | #000000   | Primary page background |

| Surface       | #0D0D0D   | Cards, panels, sidebars |

| Surface-2     | #1A1A1A   | Nested cards, table rows, inputs |

| Border        | #2A2A2A   | All borders and dividers |

| Golden-Brown  | #C9922A   | Primary accent, CTAs, active nav, highlights |

| Golden-muted  | #8A6420   | Secondary gold, hover states |

| Jade-Green    | #3DAA6E   | Positive values, BUY signals, gains |

| Jade-muted    | #2A7A4E   | Subtle positive indicators |

| White         | #F5F5F5   | Primary text |

| Muted         | #888888   | Secondary text, labels |

| Danger        | #E05252   | SELL signals, losses, negative P\&L |



Recharts colors must use these tokens via CSS variables. No blue, no purple, 

no default Recharts palette.



\---



\## Typography

\- Font: Geist (Next.js default) — keep it

\- Stock tickers: always monospace, uppercase, golden-brown color

\- Numbers (prices, P\&L): monospace font

\- Positive values: jade-green  |  Negative values: #E05252  |  Neutral: white



\---



\## Layout rules

\- Top horizontal navbar — fixed, full width, black background, 64px height

\- Page content area: full height minus navbar (calc(100vh - 64px))

\- vertical scrolling is ok on any page 

&#x20; Use internal scroll containers (overflow-y-auto) inside sections if needed 

\- Max content width: 1440px, centered

\- Page padding: 24px horizontal, 20px vertical

\- Footer disclaimer on every page — fixed at bottom, 40px height, 

&#x20; black background, muted text, never overlaps content



\---



\## Navbar — "stoX"

\- Left: Logo text "stoX" in golden-brown, bold, 24px, slightly italic

\- Center: Navigation links — Dashboard | Predictions | Portfolio | News

\- Right: A "LIVE" badge (pulsing green dot + text) and current Sri Lanka time 

&#x20; (Asia/Colombo timezone, updates every second)

\- Active page: golden-brown underline on the nav link

\- No hamburger menu — desktop only for v1



\---



\## Pages



\### 1. Dashboard  (/dashboard or / )

Summary of everything in one viewport. Three sections in a grid:



Top row — 4 stat cards (equal width):

&#x20; - Total Portfolio Value (LKR, large number)

&#x20; - Daily P\&L (LKR + percentage, colored green/red)

&#x20; - Today's Trades (count of BUY/SELL executed today)

&#x20; - Active Positions (count of stocks currently held)



Middle row — 2 panels side by side:

&#x20; Left (60% width): Portfolio value over time — line chart, last 90 days

&#x20; Right (40% width): Top movers today — list of 5 stocks from SL20 with 

&#x20;   ticker, price, and % change (positive jade-green, negative red)



Bottom row — 1 full-width panel:

&#x20; Today's signal summary — a compact row per stock showing ticker + 

&#x20; BUY/HOLD/SELL badge for all 20 SL20 stocks. Grid layout, 5 columns.



\### 2. Predictions  (/predictions)

Shows next-day predictions for all 20 SL20 stocks.

Layout: full-width table with internal scroll if needed.



Table columns:

&#x20; - Ticker (monospace, golden-brown)

&#x20; - Company name

&#x20; - Last close price (LKR)

&#x20; - Predicted next-day price (P50, LKR)

&#x20; - Confidence range (P10 – P90, shown as a small range bar)

&#x20; - Predicted change % (colored)

&#x20; - Signal badge: BUY (jade-green) | HOLD (muted) | SELL (red)

&#x20; - Accuracy mini-chart: a sparkline (last 30 days) showing predicted vs 

&#x20;   actual close. This is a tiny inline Recharts LineChart, \~100px wide



Clicking a row opens the stock detail page.



\### 3. Stock Detail  (/predictions/\[ticker])

Full detail for one stock. No scrolling — all panels fit viewport.



Layout: 2 columns

&#x20; Left column (65%):

&#x20;   - Stock name, ticker, sector badge, company blurb (2–3 sentences)

&#x20;   - Main chart: 90-day price history + prediction overlay

&#x20;     The chart shows: actual close (white line), P50 predicted (gold dashed 

&#x20;     line), P10–P90 shaded band (gold at 15% opacity)

&#x20;     The rightmost point shows tomorrow's prediction fan extending forward

&#x20;   - Below chart: prediction accuracy metrics 

&#x20;     (directional accuracy %, mean error, last 30 days)



&#x20; Right column (35%):

&#x20;   - Tomorrow's prediction card: big P50 price, P10–P90 range, signal badge

&#x20;   - Key stats: 52-week high/low, avg volume, market cap, P/E ratio

&#x20;   - Recent news: max 4 items — headline text only (truncated to 1 line) + 

&#x20;     source tag + sentiment chip (Positive/Neutral/Negative) + link icon 

&#x20;     that opens the original article. No article content reproduced.



\### 4. Portfolio  (/portfolio)

Shows the paper trading simulator's state.



Layout: 2 columns



&#x20; Left column (55%):

&#x20;   - Portfolio value chart: area chart, 90 days, compare to SL20 index line

&#x20;   - Below: performance metrics row 

&#x20;     (Sharpe ratio, max drawdown, total return %, win rate %)



&#x20; Right column (45%):

&#x20;   - Current positions table: ticker, shares held, avg buy price, 

&#x20;     current price, unrealized P\&L (LKR + %), position weight %

&#x20;   - Below: Recent trades list — last 10 trades with date, ticker, 

&#x20;     action (BUY/SELL), quantity, price, reason (one-line model rationale)



\### 5. News  (/news)

Minimal — headlines only, no content reproduction.



Layout: clean list, max 20 items visible without scrolling (internal scroll ok)

Each item:

&#x20; - Source tag (EconomyNext / Daily FT / LBO / Reuters)

&#x20; - LOCAL or GLOBAL badge

&#x20; - Headline text (clicking opens original article in new tab)

&#x20; - Sentiment chip: Positive (jade-green) | Neutral (muted) | Negative (red)

&#x20; - Time ago (e.g. "3h ago")

&#x20; 

Top of page: aggregate sentiment bar showing overall market sentiment today 

split into local 60% weight and global 40% weight.



\---



\## Mock data layer



File: src/lib/mock/fixtures.ts  (and index files per domain)



The mock data must feel realistic. Use real SL20 tickers and company names.

Generate enough history to make charts look good (90 days).



\### SL20 tickers to use (all 20):

JKH, COMB, DIAL, SAMP, HAYL, CTC, HNB, LIOC, SPEN, DFCC,

NTB, BUKI, CARG, CCS, HHL, LION, MELS, TKYO, VONE, AEL



\### Realistic price ranges per stock (LKR):

\- JKH: 180–230, COMB: 90–120, DIAL: 12–18, SAMP: 65–90, HNB: 160–200

\- CTC: 1100–1350, HAYL: 75–100, LIOC: 55–75, SPEN: 62–85, DFCC: 60–80

\- NTB: 80–110, BUKI: 65–85, CARG: 210–260, CCS: 400–500, HHL: 75–100

\- LION: 650–800, MELS: 55–75, TKYO: 18–28, VONE: 20–30, AEL: 10–16



\### Mock data to generate:

1\. 90-day daily price history per stock (random walk within ranges above)

2\. For each day: predicted P10, P50, P90 (P50 close to actual, spread \~3–5%)

3\. BUY/HOLD/SELL signals (roughly 20% BUY, 60% HOLD, 20% SELL distribution)

4\. Portfolio history: starting LKR 1,000,000, 90-day value line

5\. Current positions: 4–6 stocks currently held

6\. Last 10 trades with dates, tickers, actions, quantities, prices

7\. 20 news headlines (mix of local/global, varied sentiment)

8\. Company info: name, sector, blurb per ticker



\### API client abstraction:

File: src/lib/api/client.ts



Export async functions:

&#x20; getPortfolioSummary()

&#x20; getPortfolioHistory(days: number)

&#x20; getPositions()

&#x20; getRecentTrades(limit: number)

&#x20; getSL20Stocks()

&#x20; getStockPredictions(ticker: string)

&#x20; getStockHistory(ticker: string, days: number)

&#x20; getNewsFeed()

&#x20; getMarketMovers()



In mock mode (USE\_MOCK\_DATA=true in env), these return fixture data with a 

simulated 300ms delay (feels like a real API). In real mode, they hit the 

FastAPI backend. The flag lives in .env.local:



&#x20; NEXT\_PUBLIC\_USE\_MOCK=true

&#x20; NEXT\_PUBLIC\_API\_URL=http://localhost:8000



No component ever imports from fixtures directly — always via client.ts.



\---



\## Footer disclaimer (every page)

Fixed at bottom, 40px height:

"stoX is a research and demonstration project. Predictions are generated by an 

ML model and do not constitute financial advice. Paper trading uses virtual 

capital only. Past performance does not indicate future results."

Text: muted color, 11px, centered.



\---



\## File/folder structure to create

frontend/

├── src/

│   ├── app/

│   │   ├── layout.tsx              # root layout with navbar + footer

│   │   ├── page.tsx                # redirects to /dashboard

│   │   ├── dashboard/page.tsx

│   │   ├── predictions/

│   │   │   ├── page.tsx

│   │   │   └── \[ticker]/page.tsx

│   │   ├── portfolio/page.tsx

│   │   └── news/page.tsx

│   ├── components/

│   │   ├── layout/

│   │   │   ├── Navbar.tsx

│   │   │   └── Footer.tsx

│   │   ├── ui/                     # shadcn components go here

│   │   ├── charts/

│   │   │   ├── PortfolioChart.tsx

│   │   │   ├── PredictionChart.tsx

│   │   │   └── SparklineChart.tsx

│   │   └── feature/

│   │       ├── StatCard.tsx

│   │       ├── SignalBadge.tsx

│   │       ├── SentimentChip.tsx

│   │       ├── StockRow.tsx

│   │       └── TradeItem.tsx

│   ├── lib/

│   │   ├── api/

│   │   │   ├── client.ts

│   │   │   └── types.ts

│   │   └── mock/

│   │       ├── fixtures.ts

│   │       └── generators.ts

│   ├── hooks/

│   │   └── useSriLankaTime.ts

│   └── styles/

│       └── globals.css             # CSS variables for color tokens



\---



\## Build order (follow this sequence exactly)

1\. Project init: npx create-next-app, install deps, configure tailwind + shadcn

2\. globals.css: define all CSS variable tokens from the color palette above

3\. Mock data layer: types.ts → generators.ts → fixtures.ts → client.ts

4\. Layout: Navbar.tsx → Footer.tsx → root layout.tsx

5\. Shared components: StatCard, SignalBadge, SentimentChip

6\. Chart components: PortfolioChart, PredictionChart, SparklineChart

7\. Dashboard page

8\. Predictions list page

9\. Stock detail page

10\. Portfolio page

11\. News page

12\. Final pass: verify no page scrolls, verify color tokens used consistently,

&#x20;   verify disclaimer appears on every page



\---



\## Important constraints — never violate these

\- Every color must come from the CSS variable tokens, never hardcoded hex

\- No page-level vertical scroll — fit everything in calc(100vh - 104px) 

&#x20; (64px navbar + 40px footer)

\- No component imports from fixtures.ts directly — always through client.ts

\- Recharts must use the defined color tokens, never default colors

\- All prices display with LKR prefix and comma-formatted numbers

\- All percentages show + or - sign explicitly

\- News headlines link to original source (target="\_blank") — never reproduce 

&#x20; article body text

\- TypeScript strict mode — no 'any' types

