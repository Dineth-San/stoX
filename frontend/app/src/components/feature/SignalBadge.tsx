import { cn } from '@/lib/utils';
import type { Signal } from '@/lib/api/types';

const styles: Record<Signal, string> = {
  BUY: 'bg-jade/20 text-jade border border-jade/30',
  HOLD: 'bg-surface-2 text-muted-foreground border border-border',
  SELL: 'bg-danger/20 text-danger border border-danger/30',
};

export function SignalBadge({ signal }: { signal: Signal }) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold font-mono tracking-wide',
        styles[signal]
      )}
    >
      {signal}
    </span>
  );
}
