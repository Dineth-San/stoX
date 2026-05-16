import { cn } from '@/lib/utils';

interface StatCardProps {
  label: string;
  value: string;
  subValue?: string;
  subValueColor?: 'positive' | 'negative' | 'neutral';
  icon?: React.ReactNode;
}

const subColorMap: Record<string, string> = {
  positive: 'text-jade',
  negative: 'text-danger',
  neutral: 'text-muted-foreground',
};

export function StatCard({
  label,
  value,
  subValue,
  subValueColor = 'neutral',
  icon,
}: StatCardProps) {
  return (
    <div className="bg-surface rounded-lg border border-border p-5 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">{label}</p>
        {icon && <span className="text-muted-foreground">{icon}</span>}
      </div>
      <p className="text-2xl font-mono font-semibold text-white mt-1">{value}</p>
      {subValue && (
        <p className={cn('text-sm font-mono', subColorMap[subValueColor])}>{subValue}</p>
      )}
    </div>
  );
}
