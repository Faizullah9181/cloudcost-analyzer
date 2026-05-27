import { useState, useEffect, useRef, useCallback } from 'react';
import type { Message } from './types';
import DashboardLayout from './components/DashboardLayout';
import ChatInput from './components/ChatInput';
import MessageList from './components/MessageList';
import { analyzeQuery, fetchSuggestions } from './api/client';

const CLOUD_PROVIDERS = [
  { value: 'aws', label: 'AWS' },
  { value: 'azure', label: 'Azure' },
  { value: 'gcp', label: 'GCP' },
  { value: 'digitalocean', label: 'DigitalOcean' },
];

const AUTH_METHODS = [
  { value: 'access_key', label: 'Access Key / Secret' },
  { value: 'iam_role', label: 'IAM Role / Managed Identity' },
  { value: 'sso', label: 'SSO / Federated Login' },
  { value: 'service_account', label: 'Service Account / JSON Key' },
  { value: 'api_token', label: 'API Token' },
];

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [provider, setProvider] = useState('aws');
  const [accountId, setAccountId] = useState('');
  const [iamPrincipal, setIamPrincipal] = useState('');
  const [authMethod, setAuthMethod] = useState('access_key');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchSuggestions().then(setSuggestions);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const buildConnectionContext = useCallback(() => {
    const details = [
      `Cloud provider: ${provider}`,
      `Auth method: ${authMethod}`,
      accountId.trim() ? `Account/Subscription/Project ID: ${accountId.trim()}` : '',
      iamPrincipal.trim() ? `IAM principal or role: ${iamPrincipal.trim()}` : '',
    ].filter(Boolean);

    return `Connection context:\n${details.join('\n')}`;
  }, [provider, authMethod, accountId, iamPrincipal]);

  const handleSubmit = useCallback(async (query: string) => {
    const contextualQuery = `${buildConnectionContext()}\n\nUser request: ${query}`;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
      timestamp: new Date(),
    };

    const loadingMsg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      loading: true,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setLoading(true);

    try {
      const res = await analyzeQuery(contextualQuery);

      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                loading: false,
                content: res.success && res.data ? res.data.summary : (res.error || 'Analysis failed'),
                data: res.success && res.data ? res.data : undefined,
              }
            : m
        )
      );
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, loading: false, content: 'Failed to connect to the server. Please check your backend is running.' }
            : m
        )
      );
    } finally {
      setLoading(false);
    }
  }, [buildConnectionContext]);

  return (
    <DashboardLayout>
      <div className="flex flex-col h-[calc(100dvh-140px)] gap-4">
        <section className="sticky top-2 z-20 rounded-2xl border border-primary-500/40 bg-slate-950/90 shadow-lg shadow-primary-900/20 backdrop-blur px-4 py-4">
          <div className="flex items-center justify-between gap-3 mb-3">
            <h2 className="text-base font-semibold text-slate-100 text-balance">Chat Connection Setup</h2>
            <span className="text-xs text-primary-300">Required for accurate cloud analysis</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-slate-400">Cloud provider</span>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {CLOUD_PROVIDERS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-slate-400">Account / Subscription / Project ID</span>
              <input
                type="text"
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                placeholder="e.g. 123456789012 or my-gcp-project"
                className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-slate-400">IAM principal / role</span>
              <input
                type="text"
                value={iamPrincipal}
                onChange={(e) => setIamPrincipal(e.target.value)}
                placeholder="e.g. arn:aws:iam::123...:role/CostReadOnly"
                className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-slate-400">Connection method</span>
              <select
                value={authMethod}
                onChange={(e) => setAuthMethod(e.target.value)}
                className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {AUTH_METHODS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </section>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto pb-4 custom-scrollbar rounded-2xl border border-slate-800 bg-slate-950/50 backdrop-blur px-4 py-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="size-16 rounded-2xl bg-primary-600/10 border border-primary-500/30 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-slate-100 mb-2 text-balance">Cloud Cost Copilot</h2>
              <p className="text-sm text-slate-400 max-w-md text-pretty">
                Select provider, account context, IAM role, and connection method above, then ask cost questions in plain English.
                You will get breakdowns, trends, and optimization recommendations.
              </p>
            </div>
          ) : (
            <MessageList messages={messages} />
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="pt-1">
          <ChatInput onSubmit={handleSubmit} loading={loading} suggestions={messages.length === 0 ? suggestions : []} />
        </div>
      </div>
    </DashboardLayout>
  );
}
