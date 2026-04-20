import type { QueryResponse } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export async function analyzeQuery(query: string): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    return { success: false, data: null, error: err.detail || 'Analysis failed' };
  }

  return res.json();
}

export async function fetchSuggestions(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE}/suggestions`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.suggestions || [];
  } catch {
    return [];
  }
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}
