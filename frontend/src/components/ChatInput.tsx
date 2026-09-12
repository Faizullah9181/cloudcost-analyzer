import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Send, Loader2, ClipboardPaste, Sparkles } from 'lucide-react';
import { canReadClipboard, readClipboardText } from '../utils/clipboard';
import { useToast } from '../hooks/useToast';

interface ChatInputProps {
  onSubmit: (query: string) => void;
  loading: boolean;
  suggestions: string[];
  placeholder?: string;
}

export default function ChatInput({ onSubmit, loading, suggestions, placeholder }: ChatInputProps) {
  const [query, setQuery] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { notify } = useToast();

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [query]);

  const submit = () => {
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    onSubmit(trimmed);
    setQuery('');
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handlePaste = async () => {
    const text = await readClipboardText();
    if (text === null) {
      notify('Clipboard read is not permitted here. Use Ctrl/Cmd+V instead.', 'info');
      return;
    }
    setQuery((prev) => (prev ? `${prev}${prev.endsWith(' ') ? '' : ' '}${text}` : text));
    textareaRef.current?.focus();
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
              className="group inline-flex items-center gap-1.5 text-xs glass hover:border-primary-500/60 text-slate-300 hover:text-slate-100 px-3 py-1.5 rounded-full transition-colors disabled:opacity-50"
            >
              <Sparkles className="w-3 h-3 text-primary-400 group-hover:text-primary-300" />
              {s}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="glass flex items-end gap-2 rounded-2xl p-2 pl-3 focus-within:border-primary-500/60 focus-within:shadow-glow transition-shadow">
        <textarea
          ref={textareaRef}
          rows={1}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder ?? "Ask about your cloud costs… e.g. 'Compare my AWS and Azure spend this month'"}
          disabled={loading}
          className="flex-1 resize-none bg-transparent py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none disabled:opacity-50 max-h-44 custom-scrollbar"
        />
        {canReadClipboard && (
          <button
            type="button"
            onClick={() => void handlePaste()}
            disabled={loading}
            title="Paste from clipboard"
            aria-label="Paste from clipboard"
            className="mb-0.5 inline-flex size-9 items-center justify-center rounded-xl text-slate-400 hover:text-slate-100 hover:bg-slate-800/80 transition-colors disabled:opacity-50"
          >
            <ClipboardPaste className="w-4 h-4" />
          </button>
        )}
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="mb-0.5 brand-gradient hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 py-2 rounded-xl flex items-center gap-2 transition-opacity font-medium text-sm"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          <span className="hidden sm:inline">Analyze</span>
        </button>
      </form>
      <p className="mt-1.5 px-2 text-[11px] text-slate-600">Enter to send · Shift+Enter for a new line</p>
    </div>
  );
}
