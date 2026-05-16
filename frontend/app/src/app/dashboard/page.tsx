import {
  getPortfolioSummary,
  getPortfolioHistory,
  getMarketMovers,
  getSL20Stocks,
} from '@/lib/api/client';
import { StatCard } from '@/components/feature/StatCard';
import { SignalBadge } from '@/components/feature/SignalBadge';
import { StockRow } from '@/components/feature/StockRow';
import { PortfolioChart } from '@/components/charts/PortfolioChart';
import { Briefcase, TrendingUp, TrendingDown, ArrowRightLeft } from 'lucide-react';
import Link from 'next/link';

export default async function DashboardPage() {
  const [summary, history, movers, stocks] = await Promise.all([
    getPortfolioSummary(),
    getPortfolioHistory(90),
    getMarketMovers(),
    getSL20Stocks(),
  ]);

  const pnlPositive = summary.dailyPnL >= 0;
  const pnlSign = pnlPositive ? '+' : '';

  // Dashboard fits in viewport: 100vh − 64px navbar − 20px pt-5 − 80px footer = calc(100vh − 164px)
  return (
    <div className="min-h-[calc(100vh-164px)] flex flex-col gap-4">

      {/* ── Top row: stat cards ─────────────────────────────────────── */}
      <div className="grid grid-cols-4 gap-4 shrink-0">
        <StatCard
          label="Portfolio Value"
          value={`LKR ${summary.totalValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          icon={<Briefcase size={15} />}
        />
        <StatCard
          label="Daily P&L"
          value={`${pnlSign}LKR ${Math.abs(summary.dailyPnL).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          subValue={`${pnlSign}${summary.dailyPnLPercent.toFixed(2)}%`}
          subValueColor={pnlPositive ? 'positive' : 'negative'}
          icon={pnlPositive ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
        />
        <StatCard
          label="Today's Trades"
          value={String(summary.todayTradesCount)}
          subValue="executed today"
          icon={<ArrowRightLeft size={15} />}
        />
        <StatCard
          label="Active Positions"
          value={String(summary.activePositionsCount)}
          subValue="stocks held"
          icon={<Briefcase size={15} />}
        />
      </div>

      {/* ── Middle row: chart + movers ──────────────────────────────── */}
      <div className="flex gap-4 flex-1 min-h-[350px]">

        {/* Portfolio chart — 60% */}
        <div className="flex-[3] min-w-0 bg-surface rounded-lg border border-border p-4 flex flex-col">
          <p className="text-xs uppercase tracking-widest text-muted-foreground mb-3 shrink-0">
            Portfolio Value — Last 90 Days
          </p>
          <div className="flex-1 min-h-0">
            <PortfolioChart data={history} />
          </div>
        </div>

        {/* Top movers — 40% */}
        <div className="flex-[2] min-w-0 bg-surface rounded-lg border border-border p-4 flex flex-col">
          <p className="text-xs uppercase tracking-widest text-muted-foreground mb-3 shrink-0">
            Top Movers Today
          </p>
          <div className="flex-1 overflow-y-auto">
            {movers.map((mover) => (
              <Link key={mover.ticker} href={`/predictions/${mover.ticker}`}>
                <StockRow {...mover} />
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* ── Bottom row: signal summary ──────────────────────────────── */}
      <div className="shrink-0 bg-surface rounded-lg border border-border p-4">
        <p className="text-xs uppercase tracking-widest text-muted-foreground mb-3">
          Today&apos;s Signals — SL20
        </p>
        <div className="grid grid-cols-5 gap-2">
          {stocks.map((stock) => (
            <Link
              key={stock.ticker}
              href={`/predictions/${stock.ticker}`}
              className="flex items-center justify-between bg-surface-2 rounded px-3 py-2 border border-transparent hover:border-border hover:bg-[#222222] transition-colors"
            >
              <span className="font-mono text-sm font-semibold text-golden">{stock.ticker}</span>
              <SignalBadge signal={stock.signal} />
            </Link>
          ))}
        </div>
      </div>

    </div>
  );
}
