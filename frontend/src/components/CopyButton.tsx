import { useState, type ReactNode } from 'react';
import { Check, Copy } from 'lucide-react';
import { copyText } from '../utils/clipboard';
import { useToast } from '../hooks/useToast';

interface CopyButtonProps {
  /** Text to copy, or a function producing it lazily. */
  text: string | (() => string);
  label?: string;
  successMessage?: string;
  icon?: ReactNode;
  className?: string;
  size?: 'xs' | 'sm';
  title?: string;
}

export default function CopyButton({ text, label, successMessage, icon, className = '', size = 'xs', title }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const { notify } = useToast();

  const handleClick = async () => {
    const value = typeof text === 'function' ? text() : text;
    const ok = await copyText(value);
    if (ok) {
      setCopied(true);
      notify(successMessage ?? (label ? `${label} copied` : 'Copied to clipboard'));
      window.setTimeout(() => setCopied(false), 1500);
    } else {
      notify('Clipboard is not available in this browser', 'error');
    }
  };

  const sizing = size === 'sm' ? 'px-2.5 py-1.5 text-xs' : 'px-2 py-1 text-[11px]';
  return (
    <button
      type="button"
      onClick={() => void handleClick()}
      title={title ?? (label ? `Copy ${label.toLowerCase()}` : 'Copy')}
      aria-label={title ?? (label ? `Copy ${label.toLowerCase()}` : 'Copy')}
      className={`inline-flex items-center gap-1 rounded-lg border border-slate-700/80 bg-slate-900/70 text-slate-400 hover:text-slate-100 hover:border-slate-500 transition-colors ${sizing} ${className}`}
    >
      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : icon ?? <Copy className="w-3.5 h-3.5" />}
      {label && <span>{copied ? 'Copied' : label}</span>}
    </button>
  );
}
