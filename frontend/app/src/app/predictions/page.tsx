import { getSL20Stocks } from '@/lib/api/client';
import { PredictionsTable } from './PredictionsTable';

export default async function PredictionsPage() {
  const stocks = await getSL20Stocks();

  const buys  = stocks.filter((s) => s.signal === 'BUY').length;
  const sells = stocks.filter((s) => s.signal === 'SELL').length;
  const holds = stocks.filter((s) => s.signal === 'HOLD').length;

  return (
    <div className="flex flex-col gap-4">

      {/* Header row */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-lg font-semibold text-white">Next-Day Predictions</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            S&amp;P SL20 · Generated for 2026-05-02 · {stocks.length} stocks
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <span className="text-jade">{buys} BUY</span>
          <span className="text-muted-foreground">{holds} HOLD</span>
          <span className="text-danger">{sells} SELL</span>
        </div>
      </div>

      {/* Table — page scrolls, no inner overflow */}
      <div className="rounded-lg border border-border bg-surface overflow-x-hidden">
        <PredictionsTable stocks={stocks} />
      </div>

    </div>
  );
}
