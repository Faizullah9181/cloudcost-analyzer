import type { ReactNode } from 'react';
import { Cloud, Github, Cpu, Menu } from 'lucide-react';
import type { HealthStatus, ProviderStatus } from '../types';

interface DashboardLayoutProps {
  children: ReactNode;
  health: HealthStatus | null;
  providers: ProviderStatus[];
  onMenu?: () => void;
}

const PROVIDER_LABEL: Record<string, string> = { aws: 'AWS', azure: 'Azure', gcp: 'GCP', digitalocean: 'DO' };

export default function DashboardLayout({ children, health, providers, onMenu }: DashboardLayoutProps) {
  return (
    <div className="min-h-dvh text-slate-100 flex flex-col">
      <header className="border-b border-slate-800/60 bg-slate-950/70 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-[1400px] mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            {onMenu && (
              <button
                type="button"
                onClick={onMenu}
                className="lg:hidden inline-flex size-9 items-center justify-center rounded-xl border border-slate-800 text-slate-300 hover:border-slate-600"
                aria-label="Open sessions"
              >
                <Menu className="w-4 h-4" />
              </button>
            )}
            <div className="brand-gradient size-9 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg shadow-primary-900/40">
              <Cloud className="w-5 h-5 text-white" />
            </div>
            <div className="min-w-0">
              <h1 className="text-base font-bold leading-tight tracking-tight">
                <span className="text-gradient">CloudCost</span> Analyzer
              </h1>
              <p className="text-[11px] text-slate-400 truncate">AI multi-cloud cost analysis · powered by the Shimo agent</p>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-2 text-[11px]">
            {health ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-slate-300">
                <Cpu className="w-3 h-3 text-primary-400" />
                {health.llm_provider}
                <span className="text-slate-500 hidden xl:inline">· {health.llm_model}</span>
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
            href="https://github.com/Faizullah9181/cloudcost-analyzer"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-800 px-2.5 py-1.5 text-xs text-slate-400 hover:text-slate-100 hover:border-slate-600 transition-colors flex-shrink-0"
            aria-label="Open project repository on GitHub"
          >
            <Github className="w-4 h-4" />
            <span className="hidden sm:inline">GitHub</span>
          </a>
        </div>
      </header>

      <main className="flex-1 max-w-[1400px] mx-auto w-full px-4 py-4">
        {children}
      </main>

      <footer className="border-t border-slate-800/50 py-3">
        <p className="text-center text-[11px] text-slate-500">
          CloudCost Analyzer &mdash; open-source FinOps agent for AWS, Azure, GCP and DigitalOcean
        </p>
      </footer>
    </div>
  );
}
