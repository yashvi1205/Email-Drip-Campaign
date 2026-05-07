import { useCallback, useRef, useState } from 'react';

export function useToasts() {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const addToast = useCallback((message, type = 'info') => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((prev) => [...prev, { id, message, type, ts: Date.now() }]);

    if (timers.current.has(id)) clearTimeout(timers.current.get(id));
    const t = setTimeout(() => {
      setToasts((prev) => prev.filter((x) => x.id !== id));
      timers.current.delete(id);
    }, 5000);
    timers.current.set(id, t);
  }, []);

  return { toasts, addToast };
}

