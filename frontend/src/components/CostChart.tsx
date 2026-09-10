import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area, LineChart, Line, Legend,
} from 'recharts';
import type { CostBreakdown, TimeSeriesPoint } from '../types';

const COLORS = [
  '#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b',
  '#ef4444', '#ec4899', '#14b8a6', '#f97316', '#6366f1',
  '#84cc16', '#a855f7',
];

interface CostChartProps {
  type: string;
  serviceBreakdown: CostBreakdown[];
  timeSeries: TimeSeriesPoint[];
  title: string;
  currency?: string;
}

const tooltipStyle = {
  contentStyle: { background: '#1f2937', border: '1px solid #374151', borderRadius: '8px', fontSize: '12px' },
  labelStyle: { color: '#9ca3af' },
};

function shortName(name: string): string {
  return name.replace('Amazon ', '').replace('AWS ', '').replace('Microsoft.', '').replace('Google ', '');
}

export default function CostChart({ type, serviceBreakdown, timeSeries, title, currency = 'USD' }: CostChartProps) {
  const format = (value: unknown) => `${currency} ${Number(value ?? 0).toFixed(2)}`;
  return (
    <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700/50">
      <h3 className="text-sm font-semibold text-gray-300 mb-4">{title}</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          {renderChart(type, serviceBreakdown, timeSeries, format)}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function renderChart(
  type: string,
  services: CostBreakdown[],
  timeSeries: TimeSeriesPoint[],
  format: (value: unknown) => string,
) {
  if (type === 'pie' && services.length > 0) {
    const data = services.slice(0, 10).map((s) => ({ name: shortName(s.service), value: s.cost }));
    return (
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={90}
          paddingAngle={2}
          dataKey="value"
          labelLine={false}
          fontSize={10}
          label={({ name, percent }) => `${String(name).split(' ').slice(-1)[0]} ${((percent ?? 0) * 100).toFixed(0)}%`}
        >
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip {...tooltipStyle} formatter={(value) => [format(value), 'Cost']} />
      </PieChart>
    );
  }

  if (type === 'bar' && services.length > 0) {
    const data = services.slice(0, 10).map((s) => ({ name: shortName(s.service), cost: s.cost }));
    return (
      <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis type="number" tick={{ fill: '#9ca3af', fontSize: 11 }} tickFormatter={(v) => `${v}`} />
        <YAxis type="category" dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} width={110} />
        <Tooltip {...tooltipStyle} formatter={(value) => [format(value), 'Cost']} />
        <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Bar>
      </BarChart>
    );
  }

  if ((type === 'area' || type === 'line') && timeSeries.length > 0) {
    const data = timeSeries.map((p) => ({ date: p.date.length > 7 ? p.date.slice(5) : p.date, cost: p.cost, service: p.service }));
    const Chart = type === 'area' ? AreaChart : LineChart;
    return (
      <Chart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis dataKey="date" tick={{ fill: '#9ca3af', fontSize: 11 }} />
        <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} tickFormatter={(v) => `${v}`} />
        <Tooltip {...tooltipStyle} formatter={(value) => [format(value), 'Cost']} />
        <Legend />
        {type === 'area' ? (
          <Area type="monotone" dataKey="cost" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={2} />
        ) : (
          <Line type="monotone" dataKey="cost" stroke="#3b82f6" strokeWidth={2} dot={{ fill: '#3b82f6', r: 3 }} />
        )}
      </Chart>
    );
  }

  if (services.length > 0) {
    const data = services.slice(0, 10).map((s) => ({ name: shortName(s.service), cost: s.cost }));
    return (
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
        <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} tickFormatter={(v) => `${v}`} />
        <Tooltip {...tooltipStyle} formatter={(value) => [format(value), 'Cost']} />
        <Bar dataKey="cost" radius={[4, 4, 0, 0]}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Bar>
      </BarChart>
    );
  }

  return <BarChart data={[]}><Bar dataKey="cost" /></BarChart>;
}
