import type { ReactNode } from 'react';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';
import type { CostBreakdown } from '../types';
import { money } from '../utils/format';

interface ServiceBreakdownProps {
  services: CostBreakdown[];
  currency?: string;
  action?: ReactNode;
}

export default function ServiceBreakdown({ services, currency = 'USD', action }: ServiceBreakdownProps) {
  const maxCost = Math.max(0, ...services.map((s) => s.cost));

  return (
    <div className="glass rounded-2xl p-5">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h3 className="text-sm font-semibold text-slate-200">Service breakdown</h3>
        {action}
      </div>
      <div className="space-y-3">
        {services.slice(0, 15).map((svc) => (
          <div key={svc.service} className="flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1 gap-3">
                <span className="text-xs text-slate-300 truncate" title={svc.service}>{svc.service}</span>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-xs font-mono text-slate-100">{money(svc.cost, currency)}</span>
                  {svc.change !== 0 && (
                    <span className={`text-xs flex items-center gap-0.5 ${svc.change > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                      {svc.change > 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                      {Math.abs(svc.change).toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-1.5">
                <div
                  className="brand-gradient h-1.5 rounded-full transition-all duration-500"
                  style={{ width: `${maxCost > 0 ? (svc.cost / maxCost) * 100 : 0}%` }}
                />
              </div>
            </div>
            <span className="text-xs text-slate-500 w-12 text-right">{svc.percentage.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
