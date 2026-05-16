import type {
  StockInfo,
  PricePoint,
  Signal,
  Position,
  Trade,
  PortfolioSummary,
  PortfolioHistoryPoint,
  PerformanceMetrics,
  NewsItem,
  MarketMover,
  StockKeyStats,
} from '@/lib/api/types';
import {
  generatePriceHistory,
  generatePortfolioHistory,
  pickSignal,
  computeAccuracy,
} from './generators';

// ─── Stock metadata ─────────────────────────────────────────────────────────

export const STOCK_INFO: Record<string, StockInfo> = {
  JKH:  { ticker: 'JKH',  name: 'John Keells Holdings',      sector: 'Diversified',            blurb: "Sri Lanka's largest listed conglomerate spanning transportation, leisure, property, consumer foods, retail, and financial services across South Asia." },
  COMB: { ticker: 'COMB', name: 'Commercial Bank of Ceylon', sector: 'Banking',                blurb: "The largest private-sector commercial bank in Sri Lanka with an extensive domestic branch network and international presence in Bangladesh and Myanmar." },
  DIAL: { ticker: 'DIAL', name: 'Dialog Axiata',             sector: 'Telecommunications',     blurb: "Sri Lanka's leading mobile communications provider, delivering 4G/5G, broadband, and digital services to over 15 million subscribers nationwide." },
  SAMP: { ticker: 'SAMP', name: 'Sampath Bank',              sector: 'Banking',                blurb: "One of Sri Lanka's most digitally innovative commercial banks, known for its strong retail franchise and mobile-first banking products." },
  HAYL: { ticker: 'HAYL', name: 'Hayleys',                   sector: 'Diversified',            blurb: "A diversified conglomerate with interests in agriculture, purification, power, and consumer products operating across 12 countries." },
  CTC:  { ticker: 'CTC',  name: 'Ceylon Tobacco Company',    sector: 'Consumer Staples',       blurb: "A subsidiary of British American Tobacco and the sole cigarette manufacturer in Sri Lanka, holding a dominant and regulated market position." },
  HNB:  { ticker: 'HNB',  name: 'Hatton National Bank',      sector: 'Banking',                blurb: "One of Sri Lanka's largest licensed commercial banks, serving retail, SME, and corporate clients through over 250 branches and 450 ATMs." },
  LIOC: { ticker: 'LIOC', name: 'Lanka IOC',                 sector: 'Energy',                 blurb: "A subsidiary of Indian Oil Corporation, Lanka IOC operates petroleum retail outlets and handles fuel distribution across Sri Lanka." },
  SPEN: { ticker: 'SPEN', name: 'Aitken Spence',             sector: 'Diversified',            blurb: "A diversified conglomerate with core businesses in tourism, maritime services, logistics, and strategic investments across South and Southeast Asia." },
  DFCC: { ticker: 'DFCC', name: 'DFCC Bank',                 sector: 'Banking',                blurb: "Sri Lanka's first development bank, now a full-service commercial bank offering retail, corporate, and project financing to individuals and businesses." },
  NTB:  { ticker: 'NTB',  name: 'Nations Trust Bank',        sector: 'Banking',                blurb: "A fast-growing commercial bank focused on digital innovation, offering personal finance, credit cards, and SME lending to the urban market." },
  BUKI: { ticker: 'BUKI', name: 'Bukit Darah',               sector: 'Diversified',            blurb: "A holding company with stakes in agribusiness, manufacturing, and consumer products, with operations in Sri Lanka and across Asia." },
  CARG: { ticker: 'CARG', name: 'Cargo Boat Development',    sector: 'Transport & Logistics',  blurb: "Sri Lanka's leading cargo handling and logistics company, providing stevedoring, warehousing, and supply chain solutions at major ports." },
  CCS:  { ticker: 'CCS',  name: 'Ceylon Cold Stores',        sector: 'Consumer',               blurb: "Home of the iconic Elephant House brand, producing beverages, ice cream, and frozen foods for the Sri Lankan market since 1866." },
  HHL:  { ticker: 'HHL',  name: 'Hemas Holdings',            sector: 'Healthcare & Consumer',  blurb: "A diversified group with leading positions in healthcare, personal care, and leisure, operating hospitals, pharma distribution, and FMCG brands." },
  LION: { ticker: 'LION', name: 'Lion Brewery',              sector: 'Beverages',              blurb: "The largest brewery in Sri Lanka, producing Lion Lager and premium beer brands distributed islandwide and exported to regional markets." },
  MELS: { ticker: 'MELS', name: 'Melstacorp',                sector: 'Diversified',            blurb: "A major conglomerate with interests in beverage distribution, financial services, telecommunications, and plantations across Sri Lanka." },
  TKYO: { ticker: 'TKYO', name: 'Tokyo Cement',              sector: 'Construction Materials', blurb: "One of Sri Lanka's leading cement manufacturers, producing a range of cement and building material products under the Tokyo Super brand." },
  VONE: { ticker: 'VONE', name: 'Vallibel One',              sector: 'Diversified',            blurb: "A diversified holding company with investments in manufacturing, financial services, leisure, and consumer goods sectors across Sri Lanka." },
  AEL:  { ticker: 'AEL',  name: 'Access Engineering',        sector: 'Construction',           blurb: "A leading civil engineering and construction company in Sri Lanka with a strong track record in roads, bridges, and infrastructure development." },
};

export const PRICE_RANGES: Record<string, [number, number]> = {
  JKH: [180, 230], COMB: [90, 120],  DIAL: [12, 18],   SAMP: [65, 90],
  HAYL: [75, 100], CTC:  [1100, 1350], HNB: [160, 200], LIOC: [55, 75],
  SPEN: [62, 85],  DFCC: [60, 80],   NTB:  [80, 110],  BUKI: [65, 85],
  CARG: [210, 260], CCS: [400, 500], HHL:  [75, 100],  LION: [650, 800],
  MELS: [55, 75],  TKYO: [18, 28],   VONE: [20, 30],   AEL:  [10, 16],
};

// ─── Price histories (90 trading days) ──────────────────────────────────────

export const PRICE_HISTORIES: Record<string, PricePoint[]> = Object.fromEntries(
  Object.keys(PRICE_RANGES).map((ticker) => [
    ticker,
    generatePriceHistory(ticker, PRICE_RANGES[ticker][0], PRICE_RANGES[ticker][1]),
  ])
);

// ─── Today's signals ─────────────────────────────────────────────────────────

function signalRng(ticker: string) {
  let s = (ticker.charCodeAt(0) * 31 + ticker.charCodeAt(1) * 17 + 99) >>> 0;
  return () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
}

export const SIGNALS: Record<string, Signal> = Object.fromEntries(
  Object.keys(STOCK_INFO).map((ticker) => [ticker, pickSignal(signalRng(ticker))])
);

// ─── Key stats per stock ─────────────────────────────────────────────────────

export const KEY_STATS: Record<string, StockKeyStats> = Object.fromEntries(
  Object.keys(PRICE_RANGES).map((ticker) => {
    const history = PRICE_HISTORIES[ticker];
    const closes = history.map((p) => p.close);
    const high = Math.max(...closes);
    const low = Math.min(...closes);
    const [min, max] = PRICE_RANGES[ticker];
    const mid = (min + max) / 2;
    return [
      ticker,
      {
        high52w: Math.round(high * 1.06 * 100) / 100,
        low52w: Math.round(low * 0.94 * 100) / 100,
        avgVolume: Math.round(500_000 + mid * 1200),
        marketCap: Math.round(mid * (50_000_000 + mid * 200_000)),
        peRatio: ticker === 'LIOC' ? null : Math.round((8 + Math.random() * 20) * 10) / 10,
      },
    ];
  })
);

// ─── Portfolio history ────────────────────────────────────────────────────────

export const PORTFOLIO_HISTORY: PortfolioHistoryPoint[] = generatePortfolioHistory(90);

// ─── Current positions ────────────────────────────────────────────────────────

const POSITION_TICKERS = ['JKH', 'LION', 'CTC', 'HNB', 'DIAL', 'SAMP'] as const;
const POSITION_BUYS: Record<string, { shares: number; avgBuyPrice: number }> = {
  JKH:  { shares: 50,  avgBuyPrice: 192.50 },
  LION: { shares: 8,   avgBuyPrice: 712.00 },
  CTC:  { shares: 2,   avgBuyPrice: 1195.00 },
  HNB:  { shares: 35,  avgBuyPrice: 174.25 },
  DIAL: { shares: 250, avgBuyPrice: 13.80 },
  SAMP: { shares: 80,  avgBuyPrice: 72.50 },
};

function buildPositions(): Position[] {
  const totalValue = POSITION_TICKERS.reduce((sum, ticker) => {
    const { shares } = POSITION_BUYS[ticker];
    const currentPrice = PRICE_HISTORIES[ticker].at(-1)!.close;
    return sum + shares * currentPrice;
  }, 0);

  return POSITION_TICKERS.map((ticker) => {
    const { shares, avgBuyPrice } = POSITION_BUYS[ticker];
    const currentPrice = PRICE_HISTORIES[ticker].at(-1)!.close;
    const unrealizedPnL = Math.round((currentPrice - avgBuyPrice) * shares * 100) / 100;
    const unrealizedPnLPercent =
      Math.round(((currentPrice - avgBuyPrice) / avgBuyPrice) * 10000) / 100;
    const positionWeight = Math.round(((shares * currentPrice) / totalValue) * 10000) / 100;
    return {
      ticker,
      name: STOCK_INFO[ticker].name,
      shares,
      avgBuyPrice,
      currentPrice,
      unrealizedPnL,
      unrealizedPnLPercent,
      positionWeight,
    };
  });
}

export const POSITIONS: Position[] = buildPositions();

// ─── Recent trades ────────────────────────────────────────────────────────────

export const RECENT_TRADES: Trade[] = [
  { date: '2026-04-30', ticker: 'SAMP', action: 'BUY',  quantity: 20, price: 76.25, reason: 'Model signals breakout above 30-day moving average with high confidence.' },
  { date: '2026-04-29', ticker: 'MELS', action: 'SELL', quantity: 40, price: 68.10, reason: 'P50 prediction below current price; risk-adjusted return unfavorable.' },
  { date: '2026-04-28', ticker: 'DIAL', action: 'BUY',  quantity: 100, price: 14.20, reason: 'Undervalued vs. sector peers; P10 upside outweighs P90 downside risk.' },
  { date: '2026-04-25', ticker: 'HNB',  action: 'BUY',  quantity: 15, price: 177.50, reason: 'Strong Q1 results; model predicts +3.8% next session with BUY signal.' },
  { date: '2026-04-24', ticker: 'TKYO', action: 'SELL', quantity: 60, price: 22.80, reason: 'Directional accuracy for TKYO dropped below 55% threshold; de-risking.' },
  { date: '2026-04-23', ticker: 'CTC',  action: 'BUY',  quantity: 1,  price: 1205.00, reason: 'Defensive play; CTC shows low correlation to market downturn signals.' },
  { date: '2026-04-22', ticker: 'JKH',  action: 'BUY',  quantity: 20, price: 196.00, reason: 'Portfolio rebalance; JKH weight fell below 10% target allocation.' },
  { date: '2026-04-17', ticker: 'COMB', action: 'SELL', quantity: 30, price: 109.50, reason: 'Model detects mean-reversion setup; SELL signal confirmed by P90 ceiling.' },
  { date: '2026-04-16', ticker: 'HAYL', action: 'SELL', quantity: 25, price: 88.75, reason: 'Trailing stop triggered after 4.2% drawdown from peak position price.' },
  { date: '2026-04-15', ticker: 'LION', action: 'BUY',  quantity: 3,  price: 725.00, reason: 'Dividend announcement catalyst; model confidence interval tightened to +2.1%.' },
];

// ─── Portfolio summary ────────────────────────────────────────────────────────

const latestPortfolio = PORTFOLIO_HISTORY.at(-1)!;
const prevPortfolio   = PORTFOLIO_HISTORY.at(-2)!;

export const PORTFOLIO_SUMMARY: PortfolioSummary = {
  totalValue: latestPortfolio.value,
  dailyPnL: latestPortfolio.value - prevPortfolio.value,
  dailyPnLPercent:
    Math.round(((latestPortfolio.value - prevPortfolio.value) / prevPortfolio.value) * 10000) / 100,
  todayTradesCount: 2,
  activePositionsCount: POSITIONS.length,
};

// ─── Performance metrics ──────────────────────────────────────────────────────

export const PERFORMANCE_METRICS: PerformanceMetrics = {
  sharpeRatio: 1.42,
  maxDrawdown: -8.3,
  totalReturn: Math.round(((latestPortfolio.value - 1_000_000) / 1_000_000) * 10000) / 100,
  winRate: 62.5,
};

// ─── News feed ────────────────────────────────────────────────────────────────

const newsRng = (() => {
  let s = 12345 >>> 0;
  return () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
})();

export const NEWS_ITEMS: NewsItem[] = [
  { id: 'n1',  source: 'EconomyNext', isLocal: true,  headline: 'John Keells Holdings reports 18% revenue growth in Q1 2026', url: 'https://economynext.com/john-keells-holdings-q1-2026-results', sentiment: 'Positive',  timeAgo: '1h ago' },
  { id: 'n2',  source: 'Daily FT',    isLocal: true,  headline: 'Central Bank holds policy rates steady amid inflation concerns', url: 'https://ft.lk/front-page/central-bank-rates-2026', sentiment: 'Neutral',   timeAgo: '2h ago' },
  { id: 'n3',  source: 'EconomyNext', isLocal: true,  headline: 'Dialog Axiata expands 5G coverage to 70% of Western Province', url: 'https://economynext.com/dialog-axiata-5g-western-province', sentiment: 'Positive',  timeAgo: '3h ago' },
  { id: 'n4',  source: 'Reuters',     isLocal: false, headline: 'Global equity markets rally on Fed rate cut expectations', url: 'https://reuters.com/markets/global-equity-rally-fed-2026', sentiment: 'Positive',  timeAgo: '4h ago' },
  { id: 'n5',  source: 'LBO',         isLocal: true,  headline: 'Colombo Stock Exchange introduces new circuit breaker rules', url: 'https://lbo.lk/biz/cse-circuit-breaker-rules-2026', sentiment: 'Neutral',   timeAgo: '5h ago' },
  { id: 'n6',  source: 'Daily FT',    isLocal: true,  headline: 'Ceylon Tobacco reports declining volumes as excise duty rises', url: 'https://ft.lk/business/ctc-volumes-excise-duty', sentiment: 'Negative',  timeAgo: '6h ago' },
  { id: 'n7',  source: 'EconomyNext', isLocal: true,  headline: 'Lion Brewery announces 12% dividend increase for FY2025', url: 'https://economynext.com/lion-brewery-dividend-fy2025', sentiment: 'Positive',  timeAgo: '7h ago' },
  { id: 'n8',  source: 'Reuters',     isLocal: false, headline: "Sri Lanka's GDP growth revised down to 3.2% for 2026", url: 'https://reuters.com/world/asia-pacific/sri-lanka-gdp-2026', sentiment: 'Negative',  timeAgo: '8h ago' },
  { id: 'n9',  source: 'LBO',         isLocal: true,  headline: 'Hatton National Bank launches new digital lending platform', url: 'https://lbo.lk/biz/hnb-digital-lending-2026', sentiment: 'Positive',  timeAgo: '9h ago' },
  { id: 'n10', source: 'Daily FT',    isLocal: true,  headline: 'Commercial Bank of Ceylon posts record profits in Q4 2025', url: 'https://ft.lk/business/comb-record-profits-q4-2025', sentiment: 'Positive',  timeAgo: '10h ago' },
  { id: 'n11', source: 'Reuters',     isLocal: false, headline: 'Global oil prices surge 8% on OPEC+ production cuts', url: 'https://reuters.com/business/energy/oil-prices-opec-2026', sentiment: 'Negative',  timeAgo: '11h ago' },
  { id: 'n12', source: 'EconomyNext', isLocal: true,  headline: 'Hayleys Group acquires controlling stake in logistics firm', url: 'https://economynext.com/hayleys-logistics-acquisition-2026', sentiment: 'Positive',  timeAgo: '12h ago' },
  { id: 'n13', source: 'Reuters',     isLocal: false, headline: 'US Federal Reserve signals two rate cuts in 2026', url: 'https://reuters.com/markets/us-fed-rate-cuts-2026', sentiment: 'Positive',  timeAgo: '13h ago' },
  { id: 'n14', source: 'LBO',         isLocal: true,  headline: 'CSE All Share Index hits 3-year high on foreign inflows', url: 'https://lbo.lk/biz/cse-allshare-3year-high', sentiment: 'Positive',  timeAgo: '14h ago' },
  { id: 'n15', source: 'Daily FT',    isLocal: true,  headline: 'Lanka IOC margins under pressure as rupee depreciates slightly', url: 'https://ft.lk/business/lioc-margins-rupee-2026', sentiment: 'Negative',  timeAgo: '16h ago' },
  { id: 'n16', source: 'EconomyNext', isLocal: true,  headline: 'Sampath Bank digital transactions up 45% year-on-year', url: 'https://economynext.com/sampath-bank-digital-growth-2026', sentiment: 'Positive',  timeAgo: '18h ago' },
  { id: 'n17', source: 'Reuters',     isLocal: false, headline: 'Emerging market sell-off drags Asian equities lower', url: 'https://reuters.com/markets/emerging-market-selloff-asia', sentiment: 'Negative',  timeAgo: '20h ago' },
  { id: 'n18', source: 'LBO',         isLocal: true,  headline: 'DFCC Bank completes LKR 5bn rights issue, oversubscribed by 2.3x', url: 'https://lbo.lk/biz/dfcc-rights-issue-2026', sentiment: 'Positive',  timeAgo: '22h ago' },
  { id: 'n19', source: 'Daily FT',    isLocal: true,  headline: 'Aitken Spence Hotels report record tourist arrivals in Q1 2026', url: 'https://ft.lk/business/aitken-spence-hotels-q1-2026', sentiment: 'Positive',  timeAgo: '1d ago' },
  { id: 'n20', source: 'EconomyNext', isLocal: true,  headline: 'Tokyo Cement faces headwinds from rising energy and fuel costs', url: 'https://economynext.com/tokyo-cement-energy-costs-2026', sentiment: 'Negative',  timeAgo: '1d ago' },
];

// suppress unused warning — rng used to create varied data above
void newsRng;

// ─── Market movers (top 5 by abs change) ─────────────────────────────────────

export function buildMarketMovers(): { movers: MarketMover[]; all: MarketMover[] } {
  const all: MarketMover[] = Object.keys(PRICE_HISTORIES).map((ticker) => {
    const hist = PRICE_HISTORIES[ticker];
    const today = hist.at(-1)!.close;
    const yesterday = hist.at(-2)!.close;
    return {
      ticker,
      name: STOCK_INFO[ticker].name,
      price: today,
      changePercent: Math.round(((today - yesterday) / yesterday) * 10000) / 100,
    };
  });

  const movers = [...all]
    .sort((a, b) => Math.abs(b.changePercent) - Math.abs(a.changePercent))
    .slice(0, 5);

  return { movers, all };
}

export const { movers: MARKET_MOVERS, all: ALL_STOCKS_TODAY } = buildMarketMovers();

// ─── Prediction summary for each ticker ──────────────────────────────────────

export function buildStockPredictions() {
  return Object.keys(STOCK_INFO).map((ticker) => {
    const history = PRICE_HISTORIES[ticker];
    const last = history.at(-1)!;
    const { directionalAccuracy, meanError } = computeAccuracy(history.slice(-30));
    return {
      ticker,
      name: STOCK_INFO[ticker].name,
      sector: STOCK_INFO[ticker].sector,
      lastClose: last.close,
      predictedP10: last.predictedP10,
      predictedP50: last.predictedP50,
      predictedP90: last.predictedP90,
      predictedChangePercent: Math.round(((last.predictedP50 - last.close) / last.close) * 10000) / 100,
      signal: SIGNALS[ticker],
      sparkline: history.slice(-30),
      directionalAccuracy,
      meanError,
    };
  });
}
