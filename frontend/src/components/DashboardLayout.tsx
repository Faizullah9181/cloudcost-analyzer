import type { ReactNode } from 'react';
import { Cloud, Github, Cpu } from 'lucide-react';
import type { HealthStatus, ProviderStatus } from '../types';

interface DashboardLayoutProps {
  children: ReactNode;
  health: HealthStatus | null;
  providers: ProviderStatus[];
}

const PROVIDER_LABEL: Record<string, string> = { aws: 'AWS', azure: 'Azure', gcp: 'GCP', digitalocean: 'DO' };

export default function DashboardLayout({ children, health, providers }: DashboardLayoutProps) {
  return (
    <div className="min-h-dvh bg-slate-950 text-slate-100 flex flex-col">
      <header className="border-b border-slate-800/60 bg-slate-950/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="size-9 rounded-lg bg-primary-600/20 border border-primary-500/30 flex items-center justify-center flex-shrink-0">
              <Cloud className="w-5 h-5 text-primary-400" />
            </div>
            <div className="min-w-0">
              <h1 className="text-base font-bold text-slate-100">Shimo</h1>
              <p className="text-[11px] text-slate-400 truncate">Multi-cloud cost analysis agent</p>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-2 text-[11px]">
            {health ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-slate-300">
                <Cpu className="w-3 h-3 text-primary-400" />
                {health.llm_provider}
                <span className="text-slate-500">· {health.llm_model}</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-red-900/60 bg-red-950/40 px-2.5 py-1 text-red-300">
                Backend offline
              </span>
            )}
            {providers.map((p) => (
              <span
                key={p.name}
                title={p.configured ? 'Credentials configured' : 'Not configured'}
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 ${
                  p.configured ? 'border-emerald-900/60 bg-emerald-950/40 text-emerald-300' : 'border-slate-800 bg-slate-900/60 text-slate-500'
                }`}
              >
                <span className={`size-1.5 rounded-full ${p.configured ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                {PROVIDER_LABEL[p.name] ?? p.name}
              </span>
            ))}
          </div>

          <a
            href="https://github.com/Faizullah9181/Cloud-Analytics"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-500 hover:text-slate-300 transition-colors flex-shrink-0"
            aria-label="Open project repository"
          >
            <Github className="w-5 h-5" />
          </a>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-4">
        {children}
      </main>

      <footer className="border-t border-slate-800/50 py-3">
        <p className="text-center text-[11px] text-slate-500">
          Shimo &mdash; natural language cost analysis for AWS, Azure, GCP and DigitalOcean
        </p>
      </footer>
    </div>
  );
}
