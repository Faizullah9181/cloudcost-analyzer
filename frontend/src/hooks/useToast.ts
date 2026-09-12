import { createContext, useContext } from 'react';

export type ToastKind = 'success' | 'info' | 'error';

export interface ToastApi {
  notify: (message: string, kind?: ToastKind) => void;
}

export const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error('useToast must be used inside <ToastProvider>');
  return api;
}
