import type { ReactNode } from 'react';
import type { AnalysisResult } from '../types';
import CostChart from './CostChart';
import ServiceBreakdown from './ServiceBreakdown';
import CopyButton from './CopyButton';
import { analysisToMarkdown, breakdownToMarkdown, money } from '../utils/format';
import { DollarSign, TrendingUp, Lightbulb, Calendar, Braces, Cloud, Table2, FileText } from 'lucide-react';

interface AnalysisCardProps {
  data: AnalysisResult;
}

const PROVIDER_LABEL: Record<string, string> = { aws: 'AWS', azure: 'Azure', gcp: 'GCP', digitalocean: 'DigitalOcean' };
const TYPE_LABEL: Record<string, string> = {
  costs: 'Cost analysis',
  trend: 'Trend',
  forecast: 'Forecast',
  comparison: 'Comparison',
  inventory: 'Inventory',
  optimization: 'Optimization',
  analysis: 'Analysis',
};

export default function AnalysisCard({ data }: AnalysisCardProps) {
  const providerEntries = Object.entries(data.providers ?? {});
  const servicesChart = data.chart_type === 'pie' ? 'pie' : 'bar';
  const trendChart = data.chart_type === 'line' ? 'line' : 'area';
  const exportJson = () =>
    JSON.stringify(
      { ...data, a2ui_messages: undefined, raw_response: undefined },
      (_key, value) => (value === undefined ? undefined : value),
      2,
    );

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="glass rounded-2xl rounded-tl-md p-5 border-l-2 border-l-primary-500/70">
        <div className="flex items-start justify-between gap-3 mb-2">
          <span className="inline-flex items-center rounded-full bg-primary-600/15 border border-primary-500/30 px-2 py-0.5 text-[11px] font-medium text-primary-200">
            {TYPE_LABEL[data.query_type] ?? 'Analysis'}
          </span>
          <div className="flex flex-wrap gap-1.5">
            <CopyButton text={data.summary} label="Summary" successMessage="Summary copied" />
            <CopyButton text={() => analysisToMarkdown(data)} label="Markdown" icon={<FileText className="w-3.5 h-3.5" />} successMessage="Markdown report copied" />
            <CopyButton text={exportJson} label="JSON" icon={<Braces className="w-3.5 h-3.5" />} successMessage="Analysis JSON copied" />
          </div>
        </div>
        <p className="text-slate-100 leading-relaxed text-sm whitespace-pre-wrap">{data.summary}</p>
      </div>

      {(data.total_cost > 0 || data.service_breakdown.length > 0) && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={<DollarSign className="w-4 h-4 text-emerald-400" />} label="Total cost" value={money(data.total_cost, data.currency)} accent />
          <StatCard icon={<Calendar className="w-4 h-4 text-sky-400" />} label="Period" value={data.period || 'Current'} />
          <StatCard icon={<TrendingUp className="w-4 h-4 text-violet-400" />} label="Services" value={String(data.service_breakdown.length)} />
          <StatCard icon={<Lightbulb className="w-4 h-4 text-amber-400" />} label="Recommendations" value={String(data.recommendations.length)} />
        </div>
      )}

      {providerEntries.length > 1 && (
        <div className="glass rounded-2xl p-4">
          <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2"><Cloud className="w-4 h-4 text-primary-400" /> By provider</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {providerEntries.map(([name, totals]) => (
              <div key={name} className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
                <p className="text-xs text-slate-400">{PROVIDER_LABEL[name] ?? name}</p>
                <p className="text-sm font-semibold text-slate-100">{money(totals.total, data.currency)}</p>
                {data.total_cost > 0 && (
                  <div className="mt-2 h-1.5 w-full rounded-full bg-slate-800">
                    <div className="h-1.5 rounded-full brand-gradient" style={{ width: `${Math.min(100, (totals.total / data.total_cost) * 100)}%` }} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {(data.service_breakdown.length > 0 || data.time_series.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {data.service_breakdown.length > 0 && (
            <CostChart type={servicesChart} serviceBreakdown={data.service_breakdown} timeSeries={[]} title="Cost by service" currency={data.currency} />
          )}
          {data.time_series.length > 0 && (
            <CostChart type={trendChart} serviceBreakdown={[]} timeSeries={data.time_series} title="Cost over time" currency={data.currency} />
          )}
        </div>
      )}

      {data.service_breakdown.length > 0 && (
        <ServiceBreakdown
          services={data.service_breakdown}
          currency={data.currency}
          action={<CopyButton text={() => breakdownToMarkdown(data)} label="Copy table" icon={<Table2 className="w-3.5 h-3.5" />} successMessage="Table copied as Markdown" />}
        />
      )}

      {data.recommendations.length > 0 && (
        <div className="glass rounded-2xl p-5 border-l-2 border-l-amber-400/70">
          <div className="flex items-center justify-between gap-3 mb-3">
            <h3 className="text-sm font-semibold text-amber-300 flex items-center gap-2">
              <Lightbulb className="w-4 h-4" />
              Optimization recommendations
            </h3>
            <CopyButton text={() => data.recommendations.map((r) => `- ${r}`).join('\n')} title="Copy recommendations" successMessage="Recommendations copied" />
          </div>
          <ul className="space-y-2">
            {data.recommendations.map((rec, i) => (
              <li key={i} className="text-sm text-slate-200 flex gap-3">
                <span className="mt-0.5 inline-flex size-5 flex-shrink-0 items-center justify-center rounded-full bg-amber-400/15 text-[11px] font-semibold text-amber-300">{i + 1}</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(data.a2ui_messages?.length ?? 0) > 0 && (
        <details className="glass rounded-2xl p-4">
          <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-200 flex items-center gap-2">
            <Braces className="w-4 h-4 text-primary-300" />
            A2UI payload ({data.a2ui_messages.length} messages)
          </summary>
          <div className="mt-3 flex justify-end">
            <CopyButton text={() => JSON.stringify(data.a2ui_messages, null, 2)} label="Copy A2UI" successMessage="A2UI payload copied" />
          </div>
          <pre className="mt-2 max-h-72 overflow-auto text-[11px] leading-relaxed font-mono bg-slate-950/70 border border-slate-800 rounded-xl p-3 text-slate-200 custom-scrollbar">
            {JSON.stringify(data.a2ui_messages, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, accent }: { icon: ReactNode; label: string; value: string; accent?: boolean }) {
  return (
    <div className={`glass rounded-xl p-3 ${accent ? 'border-emerald-800/50' : ''}`}>
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs text-slate-400">{label}</span>
      </div>
      <p className="text-sm font-semibold text-slate-100 truncate" title={value}>{value}</p>
    </div>
  );
}
