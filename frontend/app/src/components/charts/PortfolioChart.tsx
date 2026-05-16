'use client';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { PortfolioHistoryPoint } from '@/lib/api/types';

function fmtDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function fmtValue(v: number) {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  return `${(v / 1_000).toFixed(0)}K`;
}

interface Props {
  data: PortfolioHistoryPoint[];
  showIndex?: boolean;
}

export function PortfolioChart({ data, showIndex = false }: Props) {
  const tickInterval = Math.max(1, Math.floor(data.length / 7));

  // Normalize SL20 index to the same starting value as the portfolio
  // so both series can share one Y axis for comparison
  const baseValue = data[0]?.value ?? 1;
  const baseSL20  = data[0]?.sl20Index ?? 1;
  const chartData = showIndex
    ? data.map((d) => ({ ...d, sl20Norm: (d.sl20Index / baseSL20) * baseValue }))
    : data;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="portfolioFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#C9922A" stopOpacity={0.28} />
            <stop offset="95%" stopColor="#C9922A" stopOpacity={0}    />
          </linearGradient>
          <linearGradient id="indexFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#3DAA6E" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#3DAA6E" stopOpacity={0}    />
          </linearGradient>
        </defs>

        <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" vertical={false} />

        <XAxis
          dataKey="date"
          tickFormatter={fmtDate}
          interval={tickInterval}
          tick={{ fill: '#888888', fontSize: 11, fontFamily: 'var(--font-geist-mono)' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={fmtValue}
          tick={{ fill: '#888888', fontSize: 11, fontFamily: 'var(--font-geist-mono)' }}
          axisLine={false}
          tickLine={false}
          width={58}
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
            `LKR ${Number(value).toLocaleString('en-US', { minimumFractionDigits: 0 })}`,
            name === 'value' ? 'Portfolio' : 'SL20 Index',
          ]}
          itemStyle={{ color: '#F5F5F5', fontFamily: 'var(--font-geist-mono)' }}
        />

        <Area
          type="monotone"
          dataKey="value"
          stroke="#C9922A"
          strokeWidth={2}
          fill="url(#portfolioFill)"
          dot={false}
          activeDot={{ r: 4, fill: '#C9922A', strokeWidth: 0 }}
        />

        {showIndex && (
          <Area
            type="monotone"
            dataKey="sl20Norm"
            stroke="#3DAA6E"
            strokeWidth={1.5}
            strokeDasharray="4 3"
            fill="url(#indexFill)"
            dot={false}
            activeDot={{ r: 3, fill: '#3DAA6E', strokeWidth: 0 }}
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}
