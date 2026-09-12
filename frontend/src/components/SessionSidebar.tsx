import { Plus, Trash2, MessageSquare, Layers, X } from 'lucide-react';
import type { SessionSummary } from '../types';

interface SessionSidebarProps {
  sessions: SessionSummary[];
  activeId: string | null;
  loading: boolean;
  onSelect: (session: SessionSummary) => void;
  onNew: () => void;
  onDelete: (session: SessionSummary) => void;
  onClose?: () => void;
}

const PROVIDER_SHORT: Record<string, string> = { aws: 'AWS', azure: 'AZ', gcp: 'GCP', digitalocean: 'DO' };

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
    ' ' + date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

export default function SessionSidebar({ sessions, activeId, loading, onSelect, onNew, onDelete, onClose }: SessionSidebarProps) {
  return (
    <aside className="glass flex flex-col h-full rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-3 py-3 border-b border-slate-800/70">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Sessions</span>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={onNew}
            className="brand-gradient inline-flex items-center gap-1 text-xs text-white px-2.5 py-1.5 rounded-lg hover:opacity-90 transition-opacity"
          >
            <Plus className="w-3.5 h-3.5" /> New
          </button>
          {onClose && (
            <button type="button" onClick={onClose} className="lg:hidden inline-flex size-7 items-center justify-center rounded-lg text-slate-400 hover:text-slate-100" aria-label="Close">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
        {loading && sessions.length === 0 && <p className="text-xs text-slate-500 px-2 py-3">Loading sessions…</p>}
        {!loading && sessions.length === 0 && (
          <p className="text-xs text-slate-500 px-2 py-3">No sessions yet. Your first question creates one.</p>
        )}
        {sessions.map((session) => {
          const active = session.id === activeId;
          const providers = Object.entries(session.cloud_providers)
            .filter(([, enabled]) => enabled)
            .map(([name]) => PROVIDER_SHORT[name] ?? name.toUpperCase());
          return (
            <div
              key={session.id}
              className={`group relative rounded-xl border px-3 py-2.5 cursor-pointer transition-colors ${
                active
                  ? 'border-primary-500/60 bg-primary-600/15 shadow-inner'
                  : 'border-transparent hover:border-slate-700 hover:bg-slate-900/60'
              }`}
              onClick={() => onSelect(session)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter') onSelect(session); }}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm text-slate-100 truncate flex-1">{session.name}</p>
                <button
                  type="button"
                  aria-label="Archive session"
                  onClick={(e) => { e.stopPropagation(); onDelete(session); }}
                  className="opacity-60 sm:opacity-0 sm:group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-opacity"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="mt-1 flex items-center gap-2 text-[11px] text-slate-500">
                <span className="inline-flex items-center gap-1"><MessageSquare className="w-3 h-3" />{session.message_count}</span>
                {session.compression_count > 0 && (
                  <span className="inline-flex items-center gap-1" title="Context compressions"><Layers className="w-3 h-3" />{session.compression_count}</span>
                )}
                <span className="truncate">{providers.join(' · ')}</span>
                <span className="ml-auto whitespace-nowrap">{formatDate(session.updated_at)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
