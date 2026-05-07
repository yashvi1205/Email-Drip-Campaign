import { AnimatePresence, motion } from 'framer-motion';
import React from 'react';
import { Activity, Clock, Database } from 'lucide-react';

void motion;

export default function ToastContainer({ toasts }) {
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
            {toast.type === 'error' && <Database size={18} />}
            {toast.type === 'info' && <Clock size={18} />}
            <span>{toast.message}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

