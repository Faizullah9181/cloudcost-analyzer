import type { ReactNode } from 'react';
import { Cloud, Github } from 'lucide-react';

interface DashboardLayoutProps {
  children: ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="min-h-dvh bg-slate-950 text-slate-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800/60 bg-slate-950/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-lg bg-primary-600/20 border border-primary-500/30 flex items-center justify-center">
              <Cloud className="w-5 h-5 text-primary-400" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-100 text-balance">Cloud Analytics</h1>
              <p className="text-[11px] text-slate-400">Multi-cloud cost intelligence cockpit</p>
            </div>
          </div>
          <a
            href="https://github.com/Faizullah9181/Cloud-Analytics"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-500 hover:text-slate-300 transition-colors"
            aria-label="Open project repository"
          >
            <Github className="w-5 h-5" />
          </a>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-6">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/50 py-3">
        <p className="text-center text-[11px] text-slate-500 text-pretty">
          Cloud Analytics &mdash; Natural language AWS cost analysis
        </p>
      </footer>
    </div>
  );
}
