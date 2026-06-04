import React from 'react';
import {
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { BasketTickerResult } from '../api';

interface BasketAnalyticsProps {
  results: BasketTickerResult[];
}

// Custom tooltip components (defined outside to avoid recreation on render)
interface IndustryData {
  name: string;
  value: number;
  avgChange: number;
  tickers: string[];
}

interface TooltipPayload {
  payload: IndustryData;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
}

const SectorTooltip = ({ active, payload }: CustomTooltipProps) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200">
        <p className="text-sm font-medium text-slate-900 mb-1">{data.name}</p>
        <p className="text-sm text-slate-600">Count: {data.value}</p>
        <p className="text-sm text-slate-600">Avg Change: {data.avgChange?.toFixed(2) ?? 'N/A'}%</p>
        <p className="text-xs text-slate-500 mt-1">
          {data.tickers.slice(0, 3).join(', ')}
          {data.tickers.length > 3 && '...'}
        </p>
      </div>
    );
  }
  return null;
};

const SectorPerformanceTooltip = ({ active, payload }: CustomTooltipProps) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const color = data.avgChange >= 0 ? '#10b981' : '#ef4444';
    return (
      <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200">
        <p className="text-sm font-medium text-slate-900 mb-1">{data.name}</p>
        <p className="text-sm" style={{ color }}>
          Avg Change: {data.avgChange.toFixed(2)}%
        </p>
        <p className="text-xs text-slate-500 mt-1">
          {data.tickers.slice(0, 3).join(', ')}
          {data.tickers.length > 3 && '...'}
        </p>
      </div>
    );
  }
  return null;
};

interface PerformanceData {
  ticker: string;
  change: number;
  direction: 'up' | 'down';
}

interface PerformanceTooltipProps {
  active?: boolean;
  payload?: { payload: PerformanceData }[];
}

const PerformanceTooltip = ({ active, payload }: PerformanceTooltipProps) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const color = data.direction === 'up' ? '#10b981' : '#ef4444';
    return (
      <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200">
        <p className="text-sm font-medium text-slate-900 mb-1">{data.ticker}</p>
        <p className="text-sm" style={{ color }}>
          {data.change.toFixed(2)}%
        </p>
      </div>
    );
  }
  return null;
};

const BasketAnalytics: React.FC<BasketAnalyticsProps> = ({ results }) => {
  if (!results || results.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-slate-50 rounded-lg">
        <p className="text-slate-500">No basket data available</p>
      </div>
    );
  }

  // Group by industry
  const industryData = results.reduce((acc: Record<string, { industry: string; count: number; totalChange: number; tickers: string[] }>, result) => {
    const industry = result.industry || 'Unknown';
    if (!acc[industry]) {
      acc[industry] = { industry, count: 0, totalChange: 0, tickers: [] };
    }
    acc[industry].count += 1;
    if (result.total_change_pct !== null) {
      acc[industry].totalChange += result.total_change_pct;
    }
    acc[industry].tickers.push(result.ticker);
    return acc;
  }, {});

  const industryArray = Object.values(industryData)
    .map((i) => ({
      name: i.industry,
      value: i.count,
      avgChange: i.count > 0 ? i.totalChange / i.count : 0,
      tickers: i.tickers,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10); // Top 10 industries

  // Performance distribution
  const performanceData = results.map((r) => ({
    ticker: r.ticker,
    change: r.total_change_pct ?? 0,
    direction: r.direction,
  }));

  return (
    <div className="space-y-8">
      {/* Industry Breakdown */}
      {industryArray.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Industry Breakdown (Top 10)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={industryArray} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                type="number"
                stroke="#64748b"
                fontSize={12}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                stroke="#64748b"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                width={120}
              />
              <Tooltip content={<SectorTooltip />} />
              <Bar dataKey="value" fill="#10b981" radius={[0, 2, 2, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Industry Performance */}
      {industryArray.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Industry Performance (Top 10)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={industryArray} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                type="number"
                stroke="#64748b"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `${value.toFixed(0)}%`}
              />
              <YAxis
                type="category"
                dataKey="name"
                stroke="#64748b"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                width={120}
              />
              <Tooltip content={<SectorPerformanceTooltip />} />
              <Bar dataKey="avgChange" radius={[0, 2, 2, 0]}>
                {industryArray.map((entry, index) => (
                  <Cell 
                    key={`industry-perf-${index}`} 
                    fill={entry.avgChange >= 0 ? '#10b981' : '#ef4444'} 
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Performance Distribution */}
      <div>
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Performance Distribution</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={performanceData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="ticker"
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              angle={-45}
              textAnchor="end"
              height={80}
            />
            <YAxis
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => `${value.toFixed(0)}%`}
            />
            <Tooltip content={<PerformanceTooltip />} />
            <Bar
              dataKey="change"
              fill="#4f46e5"
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Summary Statistics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-emerald-50 p-4 rounded-xl border border-emerald-100">
          <p className="text-emerald-600 text-xs font-bold uppercase mb-1">Winners</p>
          <p className="text-2xl font-bold text-emerald-700">
            {results.filter((r) => r.direction === 'up').length}
          </p>
        </div>
        <div className="bg-rose-50 p-4 rounded-xl border border-rose-100">
          <p className="text-rose-600 text-xs font-bold uppercase mb-1">Losers</p>
          <p className="text-2xl font-bold text-rose-700">
            {results.filter((r) => r.direction === 'down').length}
          </p>
        </div>
        <div className="bg-indigo-50 p-4 rounded-xl border border-indigo-100">
          <p className="text-indigo-600 text-xs font-bold uppercase mb-1">Avg Change</p>
          <p className="text-2xl font-bold text-indigo-700">
            {(results.reduce((sum, r) => sum + (r.total_change_pct ?? 0), 0) / results.length).toFixed(2)}%
          </p>
        </div>
        <div className="bg-purple-50 p-4 rounded-xl border border-purple-100">
          <p className="text-purple-600 text-xs font-bold uppercase mb-1">Best Performer</p>
          <p className="text-lg font-bold text-purple-700">
            {results
              .filter((r) => r.total_change_pct !== null)
              .reduce((best, r) => (r.total_change_pct! > best.total_change_pct! ? r : best))
              .ticker}
          </p>
        </div>
      </div>
    </div>
  );
};

export default BasketAnalytics;
