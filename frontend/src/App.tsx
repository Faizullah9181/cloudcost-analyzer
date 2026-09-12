import { useCallback, useEffect, useRef, useState } from 'react';
import { Download, Layers, PanelLeft, ClipboardCopy } from 'lucide-react';
import type {
  CloudProvider,
  HealthStatus,
  Message,
  ProviderStatus,
  SessionMessage,
  SessionSummary,
} from './types';
import DashboardLayout from './components/DashboardLayout';
import SessionSidebar from './components/SessionSidebar';
import SessionSetup, { type SessionSetupState } from './components/SessionSetup';
import ChatInput from './components/ChatInput';
import MessageList from './components/MessageList';
import EmptyState from './components/EmptyState';
import CopyButton from './components/CopyButton';
import { conversationToMarkdown } from './utils/format';
import {
  ApiError,
  compressSession,
  createSession,
  deleteSession,
  exportSessionUrl,
  fetchHealth,
  fetchProviders,
  fetchSuggestions,
  getMessages,
  getSession,
  listSessions,
  normalizeAnalysis,
  sendChat,
} from './api/client';

const LLM_PROVIDERS = ['bedrock', 'openai', 'anthropic', 'gemini', 'ollama', 'unsloth'];

function toMessage(m: SessionMessage): Message {
  return {
    id: m.id,
    role: m.role,
    content: m.content,
    data: m.role === 'assistant' ? normalizeAnalysis(m.analysis) : undefined,
    timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
    error: m.tags.includes('error'),
  };
}

function defaultSessionName(): string {
  return `Session ${new Date().toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`;
}

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [providerStatus, setProviderStatus] = useState<ProviderStatus[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [activeSession, setActiveSession] = useState<SessionSummary | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [setup, setSetup] = useState<SessionSetupState>({ name: '', providers: ['aws'], llm: 'bedrock', context: {} });
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshSessions = useCallback(async () => {
    try {
      const list = await listSessions();
      setSessions(list);
      return list;
    } catch {
      return [] as SessionSummary[];
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth()
      .then((h) => {
        setHealth(h);
        setSetup((s) => ({ ...s, llm: h.llm_provider || s.llm }));
      })
      .catch(() => setHealth(null));
    fetchProviders()
      .then((p) => {
        setProviderStatus(p.providers);
        const configured = p.providers.filter((x) => x.configured).map((x) => x.name);
        if (configured.length > 0) setSetup((s) => ({ ...s, providers: configured as CloudProvider[] }));
      })
      .catch(() => setProviderStatus([]));
    fetchSuggestions().then(setSuggestions);
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const selectSession = useCallback(async (session: SessionSummary) => {
    setActiveSession(session);
    setNotice(null);
    setDrawerOpen(false);
    setHistoryLoading(true);
    try {
      const history = await getMessages(session.id);
      setMessages(history.messages.map(toMessage));
    } catch (error) {
      setMessages([]);
      setNotice(error instanceof Error ? error.message : 'Could not load session history');
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  // Deep link: /?session=<id> opens that session directly.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('session');
    if (!id) return;
    getSession(id)
      .then((session) => void selectSession(session))
      .catch(() => setNotice(`Session ${id} was not found`));
  }, [selectSession]);

  const startNewSession = useCallback(() => {
    setActiveSession(null);
    setMessages([]);
    setNotice(null);
    setDrawerOpen(false);
  }, []);

  const ensureSession = useCallback(async (): Promise<SessionSummary> => {
    if (activeSession) return activeSession;
    if (setup.providers.length === 0) throw new Error('Select at least one cloud provider');
    const context: Record<string, Record<string, string>> = {};
    for (const provider of setup.providers) {
      const ctx = Object.fromEntries(Object.entries(setup.context[provider] ?? {}).filter(([, v]) => v.trim()));
      if (Object.keys(ctx).length > 0) context[provider] = ctx;
    }
    const created = await createSession({
      name: setup.name.trim() || defaultSessionName(),
      cloud_providers: setup.providers,
      llm_provider: setup.llm,
      connection_context: context,
    });
    setActiveSession(created);
    setSetup((s) => ({ ...s, name: '' }));
    void refreshSessions();
    return created;
  }, [activeSession, setup, refreshSessions]);

  const handleSubmit = useCallback(async (query: string) => {
    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: query, timestamp: new Date() };
    const loadingMsg: Message = { id: crypto.randomUUID(), role: 'assistant', content: '', loading: true, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setLoading(true);
    setNotice(null);

    try {
      const session = await ensureSession();
      const res = await sendChat(session.id, query);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                loading: false,
                content: res.success ? res.message : res.error || res.message || 'Analysis failed',
                data: res.success && res.data ? res.data : undefined,
                error: !res.success,
                toolCalls: res.tool_calls,
              }
            : m,
        ),
      );
      const compression = res.memory?.compression as { compressed_messages?: number } | null | undefined;
      if (compression?.compressed_messages) {
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: 'system', content: 'Context compressed', timestamp: new Date() },
        ]);
      }
      const list = await refreshSessions();
      const updated = list.find((s) => s.id === session.id);
      if (updated) setActiveSession(updated);
    } catch (error) {
      const detail =
        error instanceof ApiError
          ? error.message
          : error instanceof Error && error.message
            ? error.message
            : 'Failed to reach the backend. Is it running?';
      setMessages((prev) =>
        prev.map((m) => (m.id === loadingMsg.id ? { ...m, loading: false, content: detail, error: true } : m)),
      );
    } finally {
      setLoading(false);
    }
  }, [ensureSession, refreshSessions]);

  const handleCompress = useCallback(async () => {
    if (!activeSession) return;
    try {
      const result = await compressSession(activeSession.id);
      setNotice(
        result.compressed_messages > 0
          ? `Compressed ${result.compressed_messages} messages into a summary.`
          : 'Nothing to compress yet.',
      );
      await refreshSessions();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Compression failed');
    }
  }, [activeSession, refreshSessions]);

  const handleDelete = useCallback(async (session: SessionSummary) => {
    if (!window.confirm(`Archive session "${session.name}"?`)) return;
    try {
      await deleteSession(session.id);
      if (activeSession?.id === session.id) startNewSession();
      await refreshSessions();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not archive the session');
    }
  }, [activeSession, refreshSessions, startNewSession]);

  const activeProviders = activeSession
    ? Object.entries(activeSession.cloud_providers).filter(([, on]) => on).map(([name]) => name.toUpperCase())
    : [];

  return (
    <DashboardLayout health={health} providers={providerStatus} onMenu={() => setDrawerOpen(true)}>
      {drawerOpen && (
        <div className="fixed inset-0 z-[60] lg:hidden">
          <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-80 max-w-[85vw] p-3">
            <SessionSidebar
              sessions={sessions}
              activeId={activeSession?.id ?? null}
              loading={sessionsLoading}
              onSelect={(s) => void selectSession(s)}
              onNew={startNewSession}
              onDelete={(s) => void handleDelete(s)}
              onClose={() => setDrawerOpen(false)}
            />
          </div>
        </div>
      )}
      <div className="flex gap-4 h-[calc(100dvh-132px)]">
        {sidebarOpen && (
          <div className="hidden lg:block w-72 flex-shrink-0">
            <SessionSidebar
              sessions={sessions}
              activeId={activeSession?.id ?? null}
              loading={sessionsLoading}
              onSelect={(s) => void selectSession(s)}
              onNew={startNewSession}
              onDelete={(s) => void handleDelete(s)}
            />
          </div>
        )}

        <div className="flex flex-col flex-1 min-w-0 gap-3">
          <div className="flex items-center gap-2 text-xs text-slate-400 whitespace-nowrap">
            <button
              type="button"
              onClick={() => setSidebarOpen((v) => !v)}
              className="hidden lg:inline-flex items-center gap-1 rounded-lg border border-slate-800 px-2 py-1 hover:border-slate-600 transition-colors"
              aria-label="Toggle session list"
            >
              <PanelLeft className="w-3.5 h-3.5" />
            </button>
            {activeSession ? (
              <>
                <span className="text-slate-200 font-medium truncate max-w-[40vw] sm:max-w-none">{activeSession.name}</span>
                <span className="hidden md:inline text-slate-600">·</span>
                <span className="hidden md:inline">{activeProviders.join(', ')}</span>
                <span className="hidden md:inline text-slate-600">·</span>
                <span className="hidden md:inline">{activeSession.llm_provider}</span>
                <span className="hidden lg:inline text-slate-600">·</span>
                <span className="hidden lg:inline">{activeSession.message_count} messages</span>
                <span className="ml-auto flex items-center gap-2 flex-shrink-0">
                  <CopyButton
                    text={() => conversationToMarkdown(messages, activeSession.name)}
                    label="Copy chat"
                    icon={<ClipboardCopy className="w-3.5 h-3.5" />}
                    successMessage="Conversation copied as Markdown"
                    title="Copy the whole conversation as Markdown"
                  />
                  <button
                    type="button"
                    onClick={() => void handleCompress()}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-800 px-2 py-1 hover:border-slate-600 transition-colors"
                    title="Summarise older turns to keep the context small"
                  >
                    <Layers className="w-3.5 h-3.5" /> Compress
                  </button>
                  <a
                    href={exportSessionUrl(activeSession.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-800 px-2 py-1 hover:border-slate-600 transition-colors"
                    title="Export session JSON"
                  >
                    <Download className="w-3.5 h-3.5" /> Export
                  </a>
                </span>
              </>
            ) : (
              <span>New session · configure below, then ask a question</span>
            )}
          </div>

          {notice && (
            <div className="rounded-xl border border-amber-800/50 bg-amber-950/30 px-4 py-2 text-xs text-amber-200 flex items-center justify-between gap-3">
              <span>{notice}</span>
              <button type="button" onClick={() => setNotice(null)} className="text-amber-400 hover:text-amber-200">dismiss</button>
            </div>
          )}

          {!activeSession && (
            <SessionSetup
              value={setup}
              onChange={setSetup}
              providerStatus={providerStatus}
              llmProviders={LLM_PROVIDERS}
              disabled={loading}
            />
          )}

          <div className="glass flex-1 overflow-y-auto custom-scrollbar rounded-2xl px-4 py-4">
            {historyLoading ? (
              <p className="text-sm text-slate-500">Loading history…</p>
            ) : messages.length === 0 ? (
              <EmptyState />
            ) : (
              <MessageList messages={messages} />
            )}
            <div ref={bottomRef} />
          </div>

          <ChatInput
            onSubmit={(q) => void handleSubmit(q)}
            loading={loading}
            suggestions={messages.length === 0 ? suggestions : []}
          />
        </div>
      </div>
    </DashboardLayout>
  );
}
