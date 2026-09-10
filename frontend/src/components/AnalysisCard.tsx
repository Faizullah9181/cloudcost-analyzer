import type { ReactNode } from 'react';
import type { AnalysisResult } from '../types';
import CostChart from './CostChart';
import ServiceBreakdown from './ServiceBreakdown';
import { DollarSign, TrendingUp, Lightbulb, Calendar, Braces, Cloud } from 'lucide-react';

interface AnalysisCardProps {
  data: AnalysisResult;
}

const PROVIDER_LABEL: Record<string, string> = { aws: 'AWS', azure: 'Azure', gcp: 'GCP', digitalocean: 'DigitalOcean' };

function money(value: number, currency: string): string {
  return `${currency} ${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function AnalysisCard({ data }: AnalysisCardProps) {
  const providerEntries = Object.entries(data.providers ?? {});
  const servicesChart = data.chart_type === 'pie' ? 'pie' : 'bar';
  const trendChart = data.chart_type === 'line' ? 'line' : 'area';

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700/50">
        <p className="text-gray-200 leading-relaxed text-sm whitespace-pre-wrap">{data.summary}</p>
      </div>

      {(data.total_cost > 0 || data.service_breakdown.length > 0) && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={<DollarSign className="w-4 h-4 text-green-400" />} label="Total Cost" value={money(data.total_cost, data.currency)} />
          <StatCard icon={<Calendar className="w-4 h-4 text-blue-400" />} label="Period" value={data.period || 'Current'} />
          <StatCard icon={<TrendingUp className="w-4 h-4 text-purple-400" />} label="Services" value={String(data.service_breakdown.length)} />
          <StatCard icon={<Lightbulb className="w-4 h-4 text-yellow-400" />} label="Tips" value={String(data.recommendations.length)} />
        </div>
      )}

      {providerEntries.length > 1 && (
        <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
          <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2"><Cloud className="w-4 h-4" /> By provider</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {providerEntries.map(([name, totals]) => (
              <div key={name} className="rounded-lg border border-gray-700/50 bg-gray-900/40 p-3">
                <p className="text-xs text-gray-400">{PROVIDER_LABEL[name] ?? name}</p>
                <p className="text-sm font-semibold text-gray-100">{money(totals.total, data.currency)}</p>
                {data.total_cost > 0 && (
                  <p className="text-[11px] text-gray-500">{((totals.total / data.total_cost) * 100).toFixed(1)}% of total</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {(data.service_breakdown.length > 0 || data.time_series.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {data.service_breakdown.length > 0 && (
            <CostChart type={servicesChart} serviceBreakdown={data.service_breakdown} timeSeries={[]} title="Cost by Service" currency={data.currency} />
          )}
          {data.time_series.length > 0 && (
            <CostChart type={trendChart} serviceBreakdown={[]} timeSeries={data.time_series} title="Cost Over Time" currency={data.currency} />
          )}
        </div>
      )}

      {data.service_breakdown.length > 0 && <ServiceBreakdown services={data.service_breakdown} currency={data.currency} />}

      {data.recommendations.length > 0 && (
        <div className="bg-gray-800/50 rounded-xl p-5 border border-yellow-800/30">
          <h3 className="text-sm font-semibold text-yellow-400 mb-3 flex items-center gap-2">
            <Lightbulb className="w-4 h-4" />
            Optimization Recommendations
          </h3>
          <ul className="space-y-2">
            {data.recommendations.map((rec, i) => (
              <li key={i} className="text-sm text-gray-300 flex gap-2">
                <span className="text-yellow-500 mt-0.5">&#8226;</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(data.a2ui_messages?.length ?? 0) > 0 && (
        <details className="bg-gray-800/50 rounded-xl p-4 border border-primary-800/40">
          <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-300 flex items-center gap-2">
            <Braces className="w-4 h-4 text-primary-300" />
            A2UI payload ({data.a2ui_messages.length} messages)
          </summary>
          <pre className="mt-3 max-h-72 overflow-auto text-[11px] leading-relaxed bg-gray-900/70 border border-gray-700 rounded-lg p-3 text-gray-200 custom-scrollbar">
            {JSON.stringify(data.a2ui_messages, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700/50">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs text-gray-400">{label}</span>
      </div>
      <p className="text-sm font-semibold text-gray-100 truncate" title={value}>{value}</p>
    </div>
  );
}
