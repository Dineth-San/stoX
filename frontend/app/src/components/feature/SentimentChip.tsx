import { cn } from '@/lib/utils';
import type { Sentiment } from '@/lib/api/types';

const styles: Record<Sentiment, string> = {
  Positive: 'bg-jade/20 text-jade',
  Neutral: 'bg-surface-2 text-muted-foreground',
  Negative: 'bg-danger/20 text-danger',
};

export function SentimentChip({ sentiment }: { sentiment: Sentiment }) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium',
        styles[sentiment]
      )}
    >
      {sentiment}
    </span>
  );
}
