import { useState, type FormEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface ChatInputProps {
  onSubmit: (query: string) => void;
  loading: boolean;
  suggestions: string[];
}

export default function ChatInput({ onSubmit, loading, suggestions }: ChatInputProps) {
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
        <div className="flex flex-wrap gap-2 mb-4">
          {suggestions.slice(0, 5).map((s) => (
            <button
              key={s}
              onClick={() => { setQuery(s); onSubmit(s); }}
              disabled={loading}
              className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1.5 rounded-full border border-gray-700 transition-colors disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask about your AWS costs... e.g. 'What's my total spend this month?'"
          disabled={loading}
          className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-50 text-sm"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="bg-primary-600 hover:bg-primary-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white px-5 py-3 rounded-xl flex items-center gap-2 transition-colors font-medium text-sm"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          Analyze
        </button>
      </form>
    </div>
  );
}
