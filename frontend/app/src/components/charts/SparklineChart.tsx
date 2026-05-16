'use client';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import type { PricePoint } from '@/lib/api/types';

interface Props {
  data: PricePoint[];
}

export function SparklineChart({ data }: Props) {
  return (
    <div className="w-[100px] h-[38px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
          <Line
            type="monotone"
            dataKey="close"
            stroke="#F5F5F5"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="predictedP50"
            stroke="#C9922A"
            strokeWidth={1.5}
            strokeDasharray="3 2"
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
