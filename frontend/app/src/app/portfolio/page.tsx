import {
  getPortfolioHistory,
  getPositions,
  getRecentTrades,
  getPerformanceMetrics,
} from '@/lib/api/client';
import { PortfolioChart } from '@/components/charts/PortfolioChart';
import { TradeItem } from '@/components/feature/TradeItem';
import { cn } from '@/lib/utils';

export default async function PortfolioPage() {
  const [history, positions, trades, metrics] = await Promise.all([
    getPortfolioHistory(90),
    getPositions(),
    getRecentTrades(10),
    getPerformanceMetrics(),
  ]);

  const totalValue = positions.reduce(
    (sum, p) => sum + p.shares * p.currentPrice,
    0
  );

  return (
    <div className="flex flex-col gap-4">

      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-lg font-semibold text-white">Portfolio</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Paper trading simulator · Virtual capital only · LKR{' '}
            {totalValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} AUM
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-px bg-golden" /> Portfolio
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-px bg-jade" /> SL20 Index
          </span>
        </div>
      </div>

      {/* Two-column layout — natural height, page scrolls */}
      <div className="flex gap-4 items-start">

        {/* ── Left 55% ─────────────────────────────────────────────────── */}
        <div className="flex-[11] min-w-0 flex flex-col gap-4">

          {/* Portfolio value chart — explicit height */}
          <div className="bg-surface rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-widest text-muted-foreground mb-3">
              Portfolio Value vs SL20 Index — 90 Days
            </p>
            <div className="h-[320px]">
              <PortfolioChart data={history} showIndex />
            </div>
          </div>

          {/* Performance metrics */}
          <div className="bg-surface rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-widest text-muted-foreground mb-3">Performance Metrics</p>
            <div className="grid grid-cols-4 gap-3">
              {([
                { label: 'Sharpe Ratio',  value: metrics.sharpeRatio.toFixed(2),                                               color: 'text-jade'           },
                { label: 'Max Drawdown',  value: `${metrics.maxDrawdown.toFixed(1)}%`,                                         color: 'text-danger'         },
                { label: 'Total Return',  value: `${metrics.totalReturn >= 0 ? '+' : ''}${metrics.totalReturn.toFixed(2)}%`,   color: metrics.totalReturn >= 0 ? 'text-jade' : 'text-danger' },
                { label: 'Win Rate',      value: `${metrics.winRate.toFixed(1)}%`,                                             color: 'text-white'          },
              ]).map(({ label, value, color }) => (
                <div key={label} className="bg-surface-2 rounded-md p-3">
                  <p className="text-xs text-muted-foreground mb-1">{label}</p>
                  <p className={cn('font-mono text-xl font-bold', color)}>{value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Right 45% ─────────────────────────────────────────────────── */}
        <div className="flex-[9] min-w-0 flex flex-col gap-4">

          {/* Positions table */}
          <div className="bg-surface rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-widest text-muted-foreground mb-3">
              Current Positions
            </p>
            <table className="w-full">
              <thead>
                <tr>
                  {['Ticker', 'Shares', 'Avg Buy', 'Current', 'Unreal. P&L', 'Weight'].map((h) => (
                    <th
                      key={h}
                      className="text-left text-xs uppercase tracking-widest text-muted-foreground pb-2 pr-3 last:pr-0 font-semibold"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.map((pos) => {
                  const pnlPos = pos.unrealizedPnL >= 0;
                  return (
                    <tr key={pos.ticker} className="border-t border-border">
                      <td className="py-2.5 pr-3">
                        <p className="font-mono text-sm font-semibold text-golden">{pos.ticker}</p>
                        <p className="text-[11px] text-muted-foreground truncate max-w-[90px]">{pos.name}</p>
                      </td>
                      <td className="py-2.5 pr-3 font-mono text-sm text-white">{pos.shares}</td>
                      <td className="py-2.5 pr-3 font-mono text-sm text-white">{pos.avgBuyPrice.toFixed(2)}</td>
                      <td className="py-2.5 pr-3 font-mono text-sm text-white">{pos.currentPrice.toFixed(2)}</td>
                      <td className="py-2.5 pr-3">
                        <p className={cn('font-mono text-sm', pnlPos ? 'text-jade' : 'text-danger')}>
                          {pnlPos ? '+' : ''}
                          {pos.unrealizedPnL.toLocaleString('en-US', {
                            minimumFractionDigits: 0,
                            maximumFractionDigits: 0,
                          })}
                        </p>
                        <p className={cn('font-mono text-[11px]', pnlPos ? 'text-jade' : 'text-danger')}>
                          {pnlPos ? '+' : ''}{pos.unrealizedPnLPercent.toFixed(2)}%
                        </p>
                      </td>
                      <td className="py-2.5 font-mono text-sm text-muted-foreground">
                        {pos.positionWeight.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Recent trades */}
          <div className="bg-surface rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Recent Trades</p>
            <div>
              {trades.map((trade) => (
                <TradeItem key={`${trade.date}-${trade.ticker}-${trade.action}`} trade={trade} />
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
