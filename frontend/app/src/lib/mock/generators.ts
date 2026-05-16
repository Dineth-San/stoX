import type { PricePoint, PortfolioHistoryPoint, Signal, Sentiment } from '@/lib/api/types';

function createRng(seed: number): () => number {
  let s = seed >>> 0;
  return function () {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function seedFromString(str: string): number {
  return str.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
}

function tradingDatesBack(fromDate: Date, days: number): Date[] {
  const dates: Date[] = [];
  let remaining = days;
  const cursor = new Date(fromDate);
  while (remaining > 0) {
    const dow = cursor.getDay();
    if (dow !== 0 && dow !== 6) {
      dates.unshift(new Date(cursor));
      remaining--;
    }
    cursor.setDate(cursor.getDate() - 1);
  }
  return dates;
}

export function generatePriceHistory(
  ticker: string,
  min: number,
  max: number,
  days = 90
): PricePoint[] {
  const rng = createRng(seedFromString(ticker));
  const today = new Date('2026-05-01');
  const dates = tradingDatesBack(today, days);

  const mid = (min + max) / 2;
  let price = mid + (rng() - 0.5) * (max - min) * 0.4;

  return dates.map((d) => {
    // Mean-reverting random walk
    const drift = (mid - price) * 0.025;
    const vol = (max - min) * 0.013;
    price = Math.max(min * 0.97, Math.min(max * 1.03, price + drift + (rng() * 2 - 1) * vol));
    price = Math.round(price * 100) / 100;

    const predError = (rng() - 0.5) * price * 0.02;
    const spread = price * (0.03 + rng() * 0.02);
    const p50 = Math.round((price + predError) * 100) / 100;

    return {
      date: d.toISOString().split('T')[0],
      close: price,
      predictedP10: Math.round((p50 - spread) * 100) / 100,
      predictedP50: p50,
      predictedP90: Math.round((p50 + spread) * 100) / 100,
    };
  });
}

export function generatePortfolioHistory(days = 90): PortfolioHistoryPoint[] {
  const rng = createRng(42);
  const today = new Date('2026-05-01');
  const dates = tradingDatesBack(today, days);

  let value = 1_000_000;
  let sl20 = 100;

  return dates.map((d) => {
    const portfolioChange = (rng() - 0.46) * 0.018;
    const indexChange = (rng() - 0.47) * 0.012;
    value = Math.round(value * (1 + portfolioChange));
    sl20 = Math.round(sl20 * (1 + indexChange) * 1000) / 1000;
    return { date: d.toISOString().split('T')[0], value, sl20Index: sl20 };
  });
}

export function pickSignal(rng: () => number): Signal {
  const r = rng();
  if (r < 0.2) return 'BUY';
  if (r < 0.8) return 'HOLD';
  return 'SELL';
}

export function pickSentiment(rng: () => number): Sentiment {
  const r = rng();
  if (r < 0.4) return 'Positive';
  if (r < 0.7) return 'Neutral';
  return 'Negative';
}

export function computeAccuracy(history: PricePoint[]): { directionalAccuracy: number; meanError: number } {
  if (history.length < 2) return { directionalAccuracy: 0, meanError: 0 };

  let correct = 0;
  let totalError = 0;

  for (let i = 1; i < history.length; i++) {
    const prev = history[i - 1];
    const curr = history[i];
    const actualDir = curr.close > prev.close;
    const predDir = curr.predictedP50 > prev.close;
    if (actualDir === predDir) correct++;
    totalError += Math.abs(curr.predictedP50 - curr.close) / curr.close;
  }

  return {
    directionalAccuracy: Math.round((correct / (history.length - 1)) * 1000) / 10,
    meanError: Math.round((totalError / (history.length - 1)) * 10000) / 100,
  };
}
