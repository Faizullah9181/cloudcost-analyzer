import { useState, type FormEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface ChatInputProps {
  onSubmit: (query: string) => void;
  loading: boolean;
  suggestions: string[];
  placeholder?: string;
}

export default function ChatInput({ onSubmit, loading, suggestions, placeholder }: ChatInputProps) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    onSubmit(trimmed);
    setQuery('');
  };

  return (
    <div className="w-full">
      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {suggestions.slice(0, 6).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onSubmit(s)}
              disabled={loading}
              className="text-xs bg-slate-900 hover:bg-slate-800 text-slate-300 px-3 py-1.5 rounded-full border border-slate-700 transition-colors disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-3 rounded-2xl border border-slate-800 bg-slate-950/70 backdrop-blur p-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder ?? "Ask about your cloud costs… e.g. 'Compare my AWS and Azure spend this month'"}
          disabled={loading}
          className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-50 text-sm"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="bg-primary-600 hover:bg-primary-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-5 py-3 rounded-xl flex items-center gap-2 transition-colors font-medium text-sm"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          Analyze
        </button>
      </form>
    </div>
  );
}
