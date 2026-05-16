'use client';
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import type { PricePoint } from '@/lib/api/types';

interface Props {
  history: PricePoint[];
  tomorrowP10: number;
  tomorrowP50: number;
  tomorrowP90: number;
}

interface ChartPoint {
  date: string;
  close: number | undefined;
  p50: number;
  bandHigh: number;
  bandLow: number;
}

function fmtDate(v: string) {
  if (v === 'Tomorrow') return 'Tomorrow';
  return new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function fmtPrice(v: number) {
  if (v >= 1000) return `${(v / 1000).toFixed(1)}K`;
  return v.toFixed(1);
}

const NAME_MAP: Record<string, string> = {
  close: 'Actual Close',
  p50: 'Predicted P50',
  bandHigh: 'P90 Upper',
  bandLow: 'P10 Lower',
};

export function PredictionChart({ history, tomorrowP10, tomorrowP50, tomorrowP90 }: Props) {
  const chartData: ChartPoint[] = [
    ...history.map((p) => ({
      date: p.date,
      close: p.close,
      p50: p.predictedP50,
      bandHigh: p.predictedP90,
      bandLow: p.predictedP10,
    })),
    {
      date: 'Tomorrow',
      close: undefined,
      p50: tomorrowP50,
      bandHigh: tomorrowP90,
      bandLow: tomorrowP10,
    },
  ];

  const tickInterval = Math.max(1, Math.floor(history.length / 7));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={chartData} margin={{ top: 4, right: 20, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" vertical={false} />

        <XAxis
          dataKey="date"
          tickFormatter={(v) => fmtDate(String(v))}
          interval={tickInterval}
          tick={{ fill: '#888888', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={fmtPrice}
          tick={{ fill: '#888888', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={62}
          domain={['auto', 'auto']}
        />

        <Tooltip
          contentStyle={{
            backgroundColor: '#0D0D0D',
            border: '1px solid #2A2A2A',
            borderRadius: '6px',
            fontSize: 12,
          }}
          labelStyle={{ color: '#888888', marginBottom: 4 }}
          labelFormatter={(label) => fmtDate(String(label))}
          formatter={(value, name) => [
            `LKR ${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
            NAME_MAP[String(name)] ?? String(name),
          ]}
          itemStyle={{ color: '#F5F5F5' }}
          filterNull={false}
        />

        {/* P10–P90 confidence band — upper fill then erase below P10 */}
        <Area
          type="monotone"
          dataKey="bandHigh"
          stroke="none"
          fill="#C9922A"
          fillOpacity={0.15}
          legendType="none"
        />
        <Area
          type="monotone"
          dataKey="bandLow"
          stroke="none"
          fill="#0D0D0D"
          fillOpacity={1}
          legendType="none"
        />

        {/* P50 predicted — gold dashed, extends to tomorrow */}
        <Line
          type="monotone"
          dataKey="p50"
          stroke="#C9922A"
          strokeWidth={1.5}
          strokeDasharray="5 3"
          dot={false}
          activeDot={{ r: 3, fill: '#C9922A', strokeWidth: 0 }}
        />

        {/* Actual close — white solid, stops at last historical point */}
        <Line
          type="monotone"
          dataKey="close"
          stroke="#F5F5F5"
          strokeWidth={2}
          dot={false}
          connectNulls={false}
          activeDot={{ r: 4, fill: '#F5F5F5', strokeWidth: 0 }}
        />

        {/* Separator at "Tomorrow" */}
        <ReferenceLine
          x="Tomorrow"
          stroke="#2A2A2A"
          strokeDasharray="4 3"
          label={{ value: 'pred →', position: 'insideTopLeft', fill: '#888888', fontSize: 10 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
