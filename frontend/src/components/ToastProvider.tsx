import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react';
import { Check, Info, AlertTriangle } from 'lucide-react';
import { ToastContext, type ToastKind } from '../hooks/useToast';

interface ToastState {
  message: string;
  kind: ToastKind;
}

export default function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState | null>(null);
  const timer = useRef<number | null>(null);

  const notify = useCallback((message: string, kind: ToastKind = 'success') => {
    setToast({ message, kind });
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setToast(null), 1800);
  }, []);

  const api = useMemo(() => ({ notify }), [notify]);
  const Icon = toast?.kind === 'error' ? AlertTriangle : toast?.kind === 'info' ? Info : Check;
  const tone =
    toast?.kind === 'error'
      ? 'border-red-800/60 bg-red-950/80 text-red-100'
      : toast?.kind === 'info'
        ? 'border-slate-700 bg-slate-900/90 text-slate-100'
        : 'border-emerald-800/60 bg-emerald-950/80 text-emerald-100';

  return (
    <ToastContext.Provider value={api}>
      {children}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className={`fixed bottom-6 left-1/2 z-[100] -translate-x-1/2 animate-toast inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm shadow-xl backdrop-blur ${tone}`}
        >
          <Icon className="w-4 h-4" />
          {toast.message}
        </div>
      )}
    </ToastContext.Provider>
  );
}
