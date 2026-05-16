import { cn } from '@/lib/utils';
import type { Trade } from '@/lib/api/types';

export function TradeItem({ trade }: { trade: Trade }) {
  const isBuy = trade.action === 'BUY';
  return (
    <div className="flex items-start gap-3 py-3 border-b border-border last:border-0">
      <span
        className={cn(
          'mt-0.5 shrink-0 px-2 py-0.5 rounded text-xs font-semibold font-mono',
          isBuy ? 'bg-jade/20 text-jade' : 'bg-danger/20 text-danger'
        )}
      >
        {trade.action}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-sm font-semibold text-golden">{trade.ticker}</span>
          <span className="text-xs text-muted-foreground shrink-0">{trade.date}</span>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">
          {trade.quantity} shares @ LKR{' '}
          {trade.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
        <p className="text-xs text-white/50 mt-0.5 truncate">{trade.reason}</p>
      </div>
    </div>
  );
}
