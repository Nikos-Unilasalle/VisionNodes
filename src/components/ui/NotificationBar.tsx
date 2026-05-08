import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export interface Notification {
  id: string;
  message: string;
  level?: 'info' | 'error' | 'warning';
  progress?: number | null;
}

interface NotificationBarProps {
  notifications: Notification[];
  dismissNotification: (id: string) => void;
}

const NotificationBar: React.FC<NotificationBarProps> = ({ notifications, dismissNotification }) => {
  if (notifications.length === 0) return null;

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[300] flex flex-col gap-2 w-[500px] max-w-[90vw]">
      {notifications.map(n => {
        const isError = n.level === 'error';
        const isDone  = n.progress !== null && n.progress !== undefined && n.progress >= 1;
        const isRunning = n.progress !== null && n.progress !== undefined && n.progress < 1;
        return (
          <div key={n.id} className={`bg-[#1e2530]/97 backdrop-blur border rounded-xl px-4 py-3 shadow-2xl ${isError ? 'border-red-500/40' : isDone ? 'border-green-500/30' : 'border-white/10'}`}>
            <div className="flex items-center gap-2">
              {isRunning && (
                <svg className="animate-spin shrink-0" width="13" height="13" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="#333" strokeWidth="3"/>
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="#3b82f6" strokeWidth="3" strokeLinecap="round"/>
                </svg>
              )}
              {isError  && <span className="text-red-400 text-[12px] shrink-0">✕</span>}
              {isDone   && <span className="text-green-400 text-[12px] shrink-0">✓</span>}
              <span className={`text-[11px] font-mono flex-1 min-w-0 break-words ${isError ? 'text-red-300' : 'text-white/80'}`}>
                {n.message}
              </span>
              {n.progress !== null && n.progress !== undefined && !isError && (
                <span className="text-[10px] text-white/40 shrink-0 ml-1">{Math.round(n.progress * 100)}%</span>
              )}
              {(isError || isDone) && (
                <button
                  onClick={() => dismissNotification(n.id)}
                  className="ml-2 text-white/30 hover:text-white/70 shrink-0 text-[14px] leading-none transition-colors"
                >×</button>
              )}
            </div>
            {n.progress !== null && n.progress !== undefined && (
              <div className="mt-2 h-1 rounded-full bg-white/10 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${isError ? 'bg-red-500' : isDone ? 'bg-green-500' : 'bg-blue-500'}`}
                  style={{ width: `${Math.min(100, Math.round(n.progress * 100))}%` }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default NotificationBar;
