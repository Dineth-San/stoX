'use client';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { SignalBadge } from '@/components/feature/SignalBadge';
import { SparklineChart } from '@/components/charts/SparklineChart';
import type { StockPrediction } from '@/lib/api/types';

function RangeBar({ p10, p50, p90 }: { p10: number; p50: number; p90: number }) {
  const span = p50 * 0.08;
  const lo = p50 - span;
  const hi = p50 + span;
  const range = hi - lo;
  const pct = (v: number) => Math.min(100, Math.max(0, ((v - lo) / range) * 100));
  return (
    <div className="relative w-full h-1 bg-[#454444] rounded-full">
      <div
        className="absolute h-full bg-golden/50 rounded-full"
        style={{ left: `${pct(p10)}%`, width: `${pct(p90) - pct(p10)}%` }}
      />
      <div
        className="absolute top-[-3px] h-[7px] w-[2px] bg-golden rounded-full"
        style={{ left: `${pct(p50)}%` }}
      />
    </div>
  );
}

export function PredictionsTable({ stocks }: { stocks: StockPrediction[] }) {
  const router = useRouter();

  return (
    <table className="w-full table-fixed border-collapse">
      <colgroup>
        <col className="w-[76px]" />   {/* Ticker */}
        <col className="w-[175px]"/>   {/* Company — fills remaining */}
        <col className="w-[108px]" />  {/* Last Close */}
        <col className="w-[108px]" />  {/* P50 Target */}
        <col className="w-[160px]" />  {/* Range */}
        <col className="w-[75px]" />   {/* Change */}
        <col className="w-[75px]" />   {/* Signal */}
        <col className="w-[128px]" />  {/* Accuracy */}
      </colgroup>

      <thead>
        <tr>
          {[
            { label: 'Ticker',         align: 'text-left'  },
            { label: 'Company',        align: 'text-left'  },
            { label: 'Last Close',     align: 'text-right' },
            { label: 'P50 Target',     align: 'text-right' },
            { label: 'Range P10-P90',  align: 'text-center'  },
            { label: 'Change',         align: 'text-right' },
            { label: 'Signal',         align: 'text-left'  },
            { label: 'Accuracy 30d',   align: 'text-left'  },
          ].map(({ label, align }) => (
            <th
              key={label}
              className={cn(
                // Added sticky and background classes here:
                'sticky top-0 z-10 bg-surface border-b border-border',
                'px-3 py-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground',
                align
              )}
            >
              {label}
            </th>
          ))}
        </tr>
      </thead>

      <tbody>
        {stocks.map((stock) => {
          const positive = stock.predictedChangePercent >= 0;
          return (
            <tr
              key={stock.ticker}
              onClick={() => router.push(`/predictions/${stock.ticker}`)}
              className="border-b border-border hover:bg-surface-2 cursor-pointer transition-colors"
            >
              <td className="px-3 py-3">
                <span className="font-mono text-sm font-bold text-golden">{stock.ticker}</span>
              </td>

              <td className="px-3 py-3 min-w-0">
                <p className="text-sm text-white truncate">{stock.name}</p>
                <p className="text-[11px] text-muted-foreground truncate">{stock.sector}</p>
              </td>

              <td className="px-3 py-3 text-right">
                <span className="font-mono text-sm text-white">
                  {stock.lastClose.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </td>

              <td className="px-3 py-3 text-right">
                <span className="font-mono text-sm text-white">
                  {stock.predictedP50.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </td>

              <td className="px-3 py-3">
                <RangeBar p10={stock.predictedP10} p50={stock.predictedP50} p90={stock.predictedP90} />
                <p className="font-mono text-[10px] text-muted-foreground mt-1 leading-none text-right">
                  {stock.predictedP10.toFixed(2)} – {stock.predictedP90.toFixed(2)}
                </p>
              </td>

              <td className="px-3 py-3 text-right">
                <span className={cn('font-mono text-sm font-semibold', positive ? 'text-jade' : 'text-danger')}>
                  {positive ? '+' : ''}{stock.predictedChangePercent.toFixed(2)}%
                </span>
              </td>

              <td className="px-3 py-3">
                <SignalBadge signal={stock.signal} />
              </td>

              <td className="px-3 py-3">
                <div className="h-8 w-full min-w-[60px]">
                  <SparklineChart data={stock.sparkline} />
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
