import { ArrowUpRight, ArrowDownRight } from 'lucide-react';
import type { CostBreakdown } from '../types';

interface ServiceBreakdownProps {
  services: CostBreakdown[];
  currency?: string;
}

export default function ServiceBreakdown({ services, currency = 'USD' }: ServiceBreakdownProps) {
  const maxCost = Math.max(0, ...services.map((s) => s.cost));

  return (
    <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700/50">
      <h3 className="text-sm font-semibold text-gray-300 mb-4">Service Breakdown</h3>
      <div className="space-y-3">
        {services.slice(0, 15).map((svc) => (
          <div key={svc.service} className="flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1 gap-3">
                <span className="text-xs text-gray-300 truncate" title={svc.service}>{svc.service}</span>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-xs font-mono text-gray-200">
                    {currency} {svc.cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                  {svc.change !== 0 && (
                    <span className={`text-xs flex items-center gap-0.5 ${svc.change > 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {svc.change > 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                      {Math.abs(svc.change).toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-1.5">
                <div
                  className="bg-primary-500 h-1.5 rounded-full transition-all duration-500"
                  style={{ width: `${maxCost > 0 ? (svc.cost / maxCost) * 100 : 0}%` }}
                />
              </div>
            </div>
            <span className="text-xs text-gray-500 w-12 text-right">{svc.percentage.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
