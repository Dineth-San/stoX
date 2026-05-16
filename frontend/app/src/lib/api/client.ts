import type {
  PortfolioSummary,
  PortfolioHistoryPoint,
  Position,
  Trade,
  StockPrediction,
  StockInfo,
  StockKeyStats,
  PricePoint,
  NewsItem,
  MarketMover,
  PerformanceMetrics,
} from './types';

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === 'true';
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

async function fromMock<T>(loader: () => T): Promise<T> {
  await delay(300);
  return loader();
}

async function fromApi<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status} for ${path}`);
  return res.json() as Promise<T>;
}

// ─── API functions ────────────────────────────────────────────────────────────

export async function getPortfolioSummary(): Promise<PortfolioSummary> {
  if (USE_MOCK) {
    const { PORTFOLIO_SUMMARY } = await import('@/lib/mock/fixtures');
    return fromMock(() => PORTFOLIO_SUMMARY);
  }
  return fromApi('/portfolio/summary');
}

export async function getPortfolioHistory(days: number): Promise<PortfolioHistoryPoint[]> {
  if (USE_MOCK) {
    const { PORTFOLIO_HISTORY } = await import('@/lib/mock/fixtures');
    return fromMock(() => PORTFOLIO_HISTORY.slice(-days));
  }
  return fromApi(`/portfolio/history?days=${days}`);
}

export async function getPositions(): Promise<Position[]> {
  if (USE_MOCK) {
    const { POSITIONS } = await import('@/lib/mock/fixtures');
    return fromMock(() => POSITIONS);
  }
  return fromApi('/portfolio/positions');
}

export async function getRecentTrades(limit: number): Promise<Trade[]> {
  if (USE_MOCK) {
    const { RECENT_TRADES } = await import('@/lib/mock/fixtures');
    return fromMock(() => RECENT_TRADES.slice(0, limit));
  }
  return fromApi(`/portfolio/trades?limit=${limit}`);
}

export async function getSL20Stocks(): Promise<StockPrediction[]> {
  if (USE_MOCK) {
    const { buildStockPredictions } = await import('@/lib/mock/fixtures');
    return fromMock(() => buildStockPredictions());
  }
  return fromApi('/stocks');
}

export async function getStockPredictions(ticker: string): Promise<StockPrediction> {
  if (USE_MOCK) {
    const { buildStockPredictions } = await import('@/lib/mock/fixtures');
    return fromMock(() => {
      const found = buildStockPredictions().find((s) => s.ticker === ticker);
      if (!found) throw new Error(`Unknown ticker: ${ticker}`);
      return found;
    });
  }
  return fromApi(`/stocks/${ticker}/prediction`);
}

export async function getStockHistory(ticker: string, days: number): Promise<PricePoint[]> {
  if (USE_MOCK) {
    const { PRICE_HISTORIES } = await import('@/lib/mock/fixtures');
    return fromMock(() => {
      const history = PRICE_HISTORIES[ticker];
      if (!history) throw new Error(`Unknown ticker: ${ticker}`);
      return history.slice(-days);
    });
  }
  return fromApi(`/stocks/${ticker}/history?days=${days}`);
}

export async function getStockInfo(ticker: string): Promise<StockInfo> {
  if (USE_MOCK) {
    const { STOCK_INFO } = await import('@/lib/mock/fixtures');
    return fromMock(() => {
      const info = STOCK_INFO[ticker];
      if (!info) throw new Error(`Unknown ticker: ${ticker}`);
      return info;
    });
  }
  return fromApi(`/stocks/${ticker}/info`);
}

export async function getStockKeyStats(ticker: string): Promise<StockKeyStats> {
  if (USE_MOCK) {
    const { KEY_STATS } = await import('@/lib/mock/fixtures');
    return fromMock(() => {
      const stats = KEY_STATS[ticker];
      if (!stats) throw new Error(`Unknown ticker: ${ticker}`);
      return stats;
    });
  }
  return fromApi(`/stocks/${ticker}/stats`);
}

export async function getNewsFeed(): Promise<NewsItem[]> {
  if (USE_MOCK) {
    const { NEWS_ITEMS } = await import('@/lib/mock/fixtures');
    return fromMock(() => NEWS_ITEMS);
  }
  return fromApi('/news');
}

export async function getMarketMovers(): Promise<MarketMover[]> {
  if (USE_MOCK) {
    const { MARKET_MOVERS } = await import('@/lib/mock/fixtures');
    return fromMock(() => MARKET_MOVERS);
  }
  return fromApi('/market/movers');
}

export async function getPerformanceMetrics(): Promise<PerformanceMetrics> {
  if (USE_MOCK) {
    const { PERFORMANCE_METRICS } = await import('@/lib/mock/fixtures');
    return fromMock(() => PERFORMANCE_METRICS);
  }
  return fromApi('/portfolio/metrics');
}
