import { notFound } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, ExternalLink } from 'lucide-react';
import {
  getStockPredictions,
  getStockHistory,
  getNewsFeed,
  getStockInfo,
  getStockKeyStats,
} from '@/lib/api/client';
import { SignalBadge } from '@/components/feature/SignalBadge';
import { SentimentChip } from '@/components/feature/SentimentChip';
import { PredictionChart } from '@/components/charts/PredictionChart';
import { cn } from '@/lib/utils';

interface Props {
  params: { ticker: string };
}

export default async function StockDetailPage({ params }: Props) {
  const ticker = params.ticker.toUpperCase();

  let data;
  try {
    data = await Promise.all([
      getStockPredictions(ticker),
      getStockHistory(ticker, 90),
      getNewsFeed(),
      getStockInfo(ticker),
      getStockKeyStats(ticker),
    ]);
  } catch {
    notFound();
  }

  const [prediction, history, allNews, info, keyStats] = data;
  const news = allNews.slice(0, 4);
  const positive = prediction.predictedChangePercent >= 0;
  const sign = positive ? '+' : '';

  return (
    <div className="h-full flex flex-col gap-3">

      {/* Breadcrumb */}
      <div className="shrink-0 flex items-center gap-2">
        <Link
          href="/predictions"
          className="flex items-center gap-1.5 text-muted-foreground hover:text-white transition-colors text-sm"
        >
          <ArrowLeft size={14} />
          Predictions
        </Link>
        <span className="text-border">/</span>
        <span className="font-mono text-sm font-semibold text-golden">{ticker}</span>
      </div>

      {/* Two-column layout */}
      <div className="flex gap-4 flex-1 min-h-0">

        {/* ── Left column 65% ─────────────────────────────────────────── */}
        <div className="flex-[13] min-w-0 flex flex-col gap-3">

          {/* Stock header */}
          <div className="shrink-0 bg-surface rounded-lg border border-border p-4">
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              <span className="font-mono text-xl font-bold text-golden">{ticker}</span>
              <span className="text-lg font-semibold text-white">{info.name}</span>
              <span className="px-2 py-0.5 rounded bg-surface-2 border border-border text-xs text-muted-foreground">
                {info.sector}
              </span>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">{info.blurb}</p>
          </div>

          {/* Price chart */}
          <div className="flex-1 min-h-0 bg-surface rounded-lg border border-border p-4 flex flex-col">
            <div className="flex items-center justify-between mb-3 shrink-0">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                90-Day Price History + Prediction Overlay
              </p>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-4 h-px bg-[#F5F5F5]" /> Actual
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-4 h-px bg-golden border-dashed border-t border-golden" /> P50 Predicted
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-4 h-2 bg-golden/20 rounded-sm" /> P10–P90
                </span>
              </div>
            </div>
            <div className="flex-1 min-h-0">
              <PredictionChart
                history={history}
                tomorrowP10={prediction.predictedP10}
                tomorrowP50={prediction.predictedP50}
                tomorrowP90={prediction.predictedP90}
              />
            </div>
          </div>

          {/* Accuracy metrics */}
          <div className="shrink-0 bg-surface rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-widest text-muted-foreground mb-3">
              Prediction Accuracy — Last 30 Days
            </p>
            <div className="grid grid-cols-3 gap-6">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Directional Accuracy</p>
                <p className="font-mono text-xl font-bold text-white">{prediction.directionalAccuracy}%</p>
                <p className="text-xs text-muted-foreground mt-0.5">of days correct direction</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Mean Price Error</p>
                <p className="font-mono text-xl font-bold text-white">{prediction.meanError}%</p>
                <p className="text-xs text-muted-foreground mt-0.5">avg |P50 − actual| / actual</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Today&apos;s Signal</p>
                <div className="mt-1">
                  <SignalBadge signal={prediction.signal} />
                </div>
                <p className="text-xs text-muted-foreground mt-1">model recommendation</p>
              </div>
            </div>
          </div>

        </div>

        {/* ── Right column 35% ────────────────────────────────────────── */}
        <div className="flex-[7] min-w-0 flex flex-col gap-3">

          {/* Tomorrow's prediction */}
          <div className="shrink-0 bg-surface rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-widest text-muted-foreground mb-3">
              Tomorrow&apos;s Prediction
            </p>
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="font-mono text-3xl font-bold text-white">
                  LKR {prediction.predictedP50.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </p>
                <p className={cn('font-mono text-sm mt-1', positive ? 'text-jade' : 'text-danger')}>
                  {sign}{prediction.predictedChangePercent.toFixed(2)}% vs today&apos;s close
                </p>
              </div>
              <SignalBadge signal={prediction.signal} />
            </div>
            <div className="bg-surface-2 rounded-md p-3 space-y-1">
              <p className="text-xs text-muted-foreground">Confidence Range (P10 – P90)</p>
              <p className="font-mono text-sm text-white">
                LKR {prediction.predictedP10.toFixed(2)}{' '}
                <span className="text-muted-foreground">–</span>{' '}
                LKR {prediction.predictedP90.toFixed(2)}
              </p>
              <p className="text-xs text-muted-foreground">
                Today&apos;s close:{' '}
                <span className="text-white font-mono">
                  LKR {prediction.lastClose.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </p>
            </div>
          </div>

          {/* Key statistics */}
          <div className="shrink-0 bg-surface rounded-lg border border-border p-4">
            <p className="text-xs uppercase tracking-widest text-muted-foreground mb-3">Key Statistics</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3">
              {([
                ['52w High', `LKR ${keyStats.high52w.toFixed(2)}`],
                ['52w Low',  `LKR ${keyStats.low52w.toFixed(2)}`],
                ['Avg Volume', keyStats.avgVolume.toLocaleString('en-US')],
                ['Market Cap', `LKR ${(keyStats.marketCap / 1e9).toFixed(1)}B`],
                ['P/E Ratio', keyStats.peRatio != null ? keyStats.peRatio.toFixed(1) : 'N/A'],
              ] as [string, string][]).map(([label, value]) => (
                <div key={label}>
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="font-mono text-sm text-white mt-0.5">{value}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Recent news */}
          <div className="flex-1 min-h-0 bg-surface rounded-lg border border-border p-4 flex flex-col overflow-hidden">
            <p className="text-xs uppercase tracking-widest text-muted-foreground mb-3 shrink-0">Recent News</p>
            <div className="flex-1 overflow-y-auto space-y-1">
              {news.map((item) => (
                <a
                  key={item.id}
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-2 p-2 -mx-2 rounded hover:bg-surface-2 transition-colors group"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                      <span className="text-xs font-medium text-muted-foreground">{item.source}</span>
                      <span className={cn(
                        'text-[10px] px-1 py-0.5 rounded',
                        item.isLocal ? 'bg-surface-2 text-muted-foreground' : 'bg-surface-2 text-golden'
                      )}>
                        {item.isLocal ? 'LOCAL' : 'GLOBAL'}
                      </span>
                      <SentimentChip sentiment={item.sentiment} />
                    </div>
                    <p className="text-sm text-white truncate leading-snug">{item.headline}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{item.timeAgo}</p>
                  </div>
                  <ExternalLink
                    size={13}
                    className="text-muted-foreground shrink-0 mt-0.5 group-hover:text-golden transition-colors"
                  />
                </a>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
