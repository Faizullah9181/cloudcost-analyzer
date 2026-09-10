import type {
  AnalysisResult,
  ChatResponse,
  CompressResponse,
  HealthStatus,
  MessagesResponse,
  ProvidersResponse,
  QueryResponse,
  SessionCreatePayload,
  SessionSummary,
} from '../types';

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) || '/api';

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === 'string') detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg?: string }) => d.msg).join('; ');
    } catch {
      /* ignore body parse errors */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const fetchHealth = () => request<HealthStatus>('/health');
export const fetchProviders = () => request<ProvidersResponse>('/providers');

export async function fetchSuggestions(): Promise<string[]> {
  try {
    const data = await request<{ suggestions: string[] }>('/suggestions');
    return data.suggestions || [];
  } catch {
    return [];
  }
}

export const listSessions = (limit = 30) => request<SessionSummary[]>(`/sessions?limit=${limit}`);
export const getSession = (id: string) => request<SessionSummary>(`/sessions/${id}`);
export const createSession = (payload: SessionCreatePayload) =>
  request<SessionSummary>('/sessions', { method: 'POST', body: JSON.stringify(payload) });
export const renameSession = (id: string, name: string) =>
  request<SessionSummary>(`/sessions/${id}`, { method: 'PATCH', body: JSON.stringify({ name }) });
export const deleteSession = (id: string, hard = false) =>
  request<void>(`/sessions/${id}${hard ? '?hard=true' : ''}`, { method: 'DELETE' });
export const getMessages = (id: string, limit = 200) => request<MessagesResponse>(`/sessions/${id}/messages?limit=${limit}`);
export const sendChat = (id: string, query: string) =>
  request<ChatResponse>(`/sessions/${id}/chat`, { method: 'POST', body: JSON.stringify({ query }) });
export const compressSession = (id: string) => request<CompressResponse>(`/sessions/${id}/compress`, { method: 'POST' });
export const exportSessionUrl = (id: string) => `${API_BASE}/sessions/${id}/export`;

export async function analyzeQuery(query: string, sessionId?: string): Promise<QueryResponse> {
  try {
    return await request<QueryResponse>('/analyze', {
      method: 'POST',
      body: JSON.stringify({ query, session_id: sessionId ?? null }),
    });
  } catch (error) {
    return { success: false, data: null, error: error instanceof Error ? error.message : 'Analysis failed' };
  }
}

/** Fill defaults so partial analyses stored with messages render safely. */
export function normalizeAnalysis(partial: Partial<AnalysisResult> | null | undefined): AnalysisResult | undefined {
  if (!partial) return undefined;
  return {
    summary: partial.summary ?? '',
    total_cost: Number(partial.total_cost ?? 0),
    currency: partial.currency ?? 'USD',
    period: partial.period ?? '',
    providers: partial.providers ?? {},
    service_breakdown: partial.service_breakdown ?? [],
    time_series: partial.time_series ?? [],
    top_costs: partial.top_costs ?? [],
    recommendations: partial.recommendations ?? [],
    raw_response: partial.raw_response ?? '',
    chart_type: partial.chart_type ?? 'bar',
    query_type: partial.query_type ?? 'analysis',
    a2ui_messages: partial.a2ui_messages ?? [],
  };
}
