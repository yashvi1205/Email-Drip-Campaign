import { useCallback, useRef, useState } from 'react';

export type ToastType = 'info' | 'success' | 'error' | 'warning';

export interface Toast {
  id: number;
  message: string;
  type: ToastType;
  ts: number;
}

export interface UseToastsReturn {
  toasts: Toast[];
  addToast: (message: string, type?: ToastType) => void;
}

export function useToasts(): UseToastsReturn {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<number, NodeJS.Timeout>>(new Map());

  const addToast = useCallback((message: string, type: ToastType = 'info') => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((prev) => [...prev, { id, message, type, ts: Date.now() }]);

    if (timers.current.has(id)) {
      clearTimeout(timers.current.get(id)!);
    }

    const t = setTimeout(() => {
      setToasts((prev) => prev.filter((x) => x.id !== id));
      timers.current.delete(id);
    }, 5000);

    timers.current.set(id, t);
  }, []);

  return { toasts, addToast };
}
