export type Signal = 'BUY' | 'HOLD' | 'SELL';
export type Sentiment = 'Positive' | 'Neutral' | 'Negative';

export interface StockInfo {
  ticker: string;
  name: string;
  sector: string;
  blurb: string;
}

export interface PricePoint {
  date: string;
  close: number;
  predictedP10: number;
  predictedP50: number;
  predictedP90: number;
}

export interface StockPrediction {
  ticker: string;
  name: string;
  sector: string;
  lastClose: number;
  predictedP10: number;
  predictedP50: number;
  predictedP90: number;
  predictedChangePercent: number;
  signal: Signal;
  sparkline: PricePoint[];
  directionalAccuracy: number;
  meanError: number;
}

export interface StockKeyStats {
  high52w: number;
  low52w: number;
  avgVolume: number;
  marketCap: number;
  peRatio: number | null;
}

export interface Position {
  ticker: string;
  name: string;
  shares: number;
  avgBuyPrice: number;
  currentPrice: number;
  unrealizedPnL: number;
  unrealizedPnLPercent: number;
  positionWeight: number;
}

export interface Trade {
  date: string;
  ticker: string;
  action: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  reason: string;
}

export interface PortfolioSummary {
  totalValue: number;
  dailyPnL: number;
  dailyPnLPercent: number;
  todayTradesCount: number;
  activePositionsCount: number;
}

export interface PortfolioHistoryPoint {
  date: string;
  value: number;
  sl20Index: number;
}

export interface PerformanceMetrics {
  sharpeRatio: number;
  maxDrawdown: number;
  totalReturn: number;
  winRate: number;
}

export interface NewsItem {
  id: string;
  source: string;
  isLocal: boolean;
  headline: string;
  url: string;
  sentiment: Sentiment;
  timeAgo: string;
}

export interface MarketMover {
  ticker: string;
  name: string;
  price: number;
  changePercent: number;
}
