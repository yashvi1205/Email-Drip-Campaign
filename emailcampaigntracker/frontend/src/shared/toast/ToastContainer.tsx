import { AnimatePresence, motion } from 'framer-motion';
import React from 'react';
import { Activity, Clock, AlertCircle } from 'lucide-react';
import { Toast } from './useToasts';

interface ToastContainerProps {
  toasts: Toast[];
}

export default function ToastContainer({ toasts }: ToastContainerProps) {
  return (
    <div className="toast-container">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className={`toast toast-${toast.type}`}
          >
            {toast.type === 'success' && <Activity size={18} />}
            {toast.type === 'error' && <AlertCircle size={18} />}
            {toast.type === 'info' && <Clock size={18} />}
            {toast.type === 'warning' && <AlertCircle size={18} />}
            <span>{toast.message}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
