import type { AnalysisResult } from '../types';
import CostChart from './CostChart';
import ServiceBreakdown from './ServiceBreakdown';
import { DollarSign, TrendingUp, Lightbulb, Calendar } from 'lucide-react';

interface AnalysisCardProps {
  data: AnalysisResult;
}

export default function AnalysisCard({ data }: AnalysisCardProps) {
  return (
    <div className="space-y-4 animate-fade-in">
      {/* Summary */}
      <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700/50">
        <p className="text-gray-200 leading-relaxed text-sm">{data.summary}</p>
      </div>

      {/* Stats Row */}
      {data.total_cost > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard
            icon={<DollarSign className="w-4 h-4 text-green-400" />}
            label="Total Cost"
            value={`$${data.total_cost.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
          />
          <StatCard
            icon={<Calendar className="w-4 h-4 text-blue-400" />}
            label="Period"
            value={data.period || 'Current'}
          />
          <StatCard
            icon={<TrendingUp className="w-4 h-4 text-purple-400" />}
            label="Services"
            value={String(data.service_breakdown.length)}
          />
          <StatCard
            icon={<Lightbulb className="w-4 h-4 text-yellow-400" />}
            label="Tips"
            value={String(data.recommendations.length)}
          />
        </div>
      )}

      {/* Charts */}
      {(data.service_breakdown.length > 0 || data.time_series.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {data.service_breakdown.length > 0 && (
            <CostChart
              type={data.time_series.length > 0 ? 'pie' : data.chart_type}
              serviceBreakdown={data.service_breakdown}
              timeSeries={[]}
              title="Cost by Service"
            />
          )}
          {data.time_series.length > 0 && (
            <CostChart
              type="area"
              serviceBreakdown={[]}
              timeSeries={data.time_series}
              title="Cost Over Time"
            />
          )}
        </div>
      )}

      {/* Service Table */}
      {data.service_breakdown.length > 0 && (
        <ServiceBreakdown services={data.service_breakdown} />
      )}

      {/* Recommendations */}
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
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700/50">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs text-gray-400">{label}</span>
      </div>
      <p className="text-sm font-semibold text-gray-100 truncate">{value}</p>
    </div>
  );
}
