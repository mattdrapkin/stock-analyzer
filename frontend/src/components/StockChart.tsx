import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';

interface PriceDataPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface StockChartProps {
  data: PriceDataPoint[];
}

interface ChartDataPoint extends PriceDataPoint {
  formattedDate: string;
  ma20: number | null;
  ma50: number | null;
  percentChange: number;
}

// Custom dot component for big mover days
const BigMoverDot = (props: any) => {
  const { cx, cy, payload } = props;
  const percentChange = payload?.percentChange || 0;
  const isBigMover = Math.abs(percentChange) >= 3;

  if (!isBigMover) return null;

  return (
    <circle
      cx={cx}
      cy={cy}
      r={4}
      fill={percentChange > 0 ? '#10b981' : '#ef4444'}
      stroke="#fff"
      strokeWidth={1.5}
    />
  );
};

// Custom tooltip components (defined outside to avoid recreation on render)
const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200">
        <p className="text-sm font-medium text-slate-900 mb-2">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} className="text-sm" style={{ color: entry.color }}>
            {entry.name}: ${entry.value.toFixed(2)}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

const VolumeTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200">
        <p className="text-sm font-medium text-slate-900 mb-2">{label}</p>
        <p className="text-sm text-indigo-600">
          Volume: {(payload[0].value / 1000000).toFixed(2)}M
        </p>
      </div>
    );
  }
  return null;
};

const StockChart: React.FC<StockChartProps> = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-slate-50 rounded-lg">
        <p className="text-slate-500">No price data available</p>
      </div>
    );
  }

  // Format data for charts
  const chartData = data.map((point) => ({
    ...point,
    formattedDate: new Date(point.date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    }),
  }));

  // Calculate moving averages and percent change
  const dataWithMA: ChartDataPoint[] = chartData.map((point, index) => ({
    ...point,
    ma20: index >= 19
      ? chartData.slice(index - 19, index + 1).reduce((sum, p) => sum + p.close, 0) / 20
      : null,
    ma50: index >= 49
      ? chartData.slice(index - 49, index + 1).reduce((sum, p) => sum + p.close, 0) / 50
      : null,
    percentChange: index > 0
      ? ((point.close - chartData[index - 1].close) / chartData[index - 1].close) * 100
      : 0,
  }));

  return (
    <div className="space-y-6">
      {/* Price Chart with Moving Averages */}
      <div>
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Price History</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={dataWithMA}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="formattedDate"
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => `$${value.toFixed(0)}`}
              domain={['auto', 'auto']}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Line
              type="monotone"
              dataKey="close"
              stroke="#4f46e5"
              strokeWidth={2}
              dot={false}
              name="Close Price"
              activeDot={<BigMoverDot />}
            />
            {dataWithMA.some((d) => d.ma20 !== null) && (
              <Line
                type="monotone"
                dataKey="ma20"
                stroke="#f59e0b"
                strokeWidth={1.5}
                dot={false}
                name="20-day MA"
              />
            )}
            {dataWithMA.some((d) => d.ma50 !== null) && (
              <Line
                type="monotone"
                dataKey="ma50"
                stroke="#10b981"
                strokeWidth={1.5}
                dot={false}
                name="50-day MA"
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Volume Chart */}
      <div>
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Trading Volume</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="formattedDate"
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => `${(value / 1000000).toFixed(0)}M`}
            />
            <Tooltip content={<VolumeTooltip />} />
            <Bar dataKey="volume" fill="#6366f1" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default StockChart;
