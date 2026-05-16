import { cn } from '@/lib/utils';
import type { MarketMover } from '@/lib/api/types';

export function StockRow({ ticker, name, price, changePercent }: MarketMover) {
  const positive = changePercent >= 0;
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border last:border-0">
      <div>
        <span className="font-mono text-sm font-semibold text-golden uppercase">{ticker}</span>
        <p className="text-xs text-muted-foreground mt-0.5">{name}</p>
      </div>
      <div className="text-right">
        <p className="font-mono text-sm text-white">
          LKR {price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
        <p className={cn('font-mono text-xs font-semibold mt-0.5', positive ? 'text-jade' : 'text-danger')}>
          {positive ? '+' : ''}{changePercent.toFixed(2)}%
        </p>
      </div>
    </div>
  );
}
