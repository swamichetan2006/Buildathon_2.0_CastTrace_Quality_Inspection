import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from 'lucide-react';

export type NotificationType = 'success' | 'error' | 'warning' | 'info';

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message?: string;
  duration?: number;
}

interface NotificationContextType {
  notifications: Notification[];
  showNotification: (type: NotificationType, title: string, message?: string, duration?: number) => void;
  dismissNotification: (id: string) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
  addToast: (type: NotificationType, title: string, message?: string) => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export const NotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const dismissNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const showNotification = useCallback(
    (type: NotificationType, title: string, message?: string, duration: number = 5000) => {
      const id = `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const newNotif: Notification = { id, type, title, message, duration };

      setNotifications((prev) => [...prev, newNotif]);

      if (duration > 0) {
        setTimeout(() => {
          dismissNotification(id);
        }, duration);
      }
    },
    [dismissNotification]
  );

  const success = useCallback((title: string, message?: string) => showNotification('success', title, message), [showNotification]);
  const error = useCallback((title: string, message?: string) => showNotification('error', title, message, 7000), [showNotification]);
  const warning = useCallback((title: string, message?: string) => showNotification('warning', title, message, 6000), [showNotification]);
  const info = useCallback((title: string, message?: string) => showNotification('info', title, message), [showNotification]);

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        showNotification,
        dismissNotification,
        success,
        error,
        warning,
        info,
        addToast: (type: NotificationType, title: string, message?: string) => showNotification(type, title, message),
      }}
    >
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col space-y-2 max-w-md w-full pointer-events-none px-4">
        {notifications.map((notif) => (
          <div
            key={notif.id}
            className={`pointer-events-auto flex items-start p-4 rounded-xl border shadow-xl backdrop-blur-md transition-all animate-in slide-in-from-bottom-2 ${
              notif.type === 'success'
                ? 'bg-slate-900/95 border-emerald-500/40 text-emerald-200'
                : notif.type === 'error'
                ? 'bg-slate-900/95 border-rose-500/40 text-rose-200'
                : notif.type === 'warning'
                ? 'bg-slate-900/95 border-amber-500/40 text-amber-200'
                : 'bg-slate-900/95 border-sky-500/40 text-sky-200'
            }`}
          >
            <div className="flex-shrink-0 mt-0.5">
              {notif.type === 'success' && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
              {notif.type === 'error' && <AlertCircle className="w-5 h-5 text-rose-400" />}
              {notif.type === 'warning' && <AlertTriangle className="w-5 h-5 text-amber-400" />}
              {notif.type === 'info' && <Info className="w-5 h-5 text-sky-400" />}
            </div>
            <div className="ml-3 flex-1">
              <h4 className="text-sm font-semibold text-white">{notif.title}</h4>
              {notif.message && <p className="text-xs text-slate-300 mt-0.5 leading-relaxed">{notif.message}</p>}
            </div>
            <button
              onClick={() => dismissNotification(notif.id)}
              className="ml-3 text-slate-400 hover:text-white transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </NotificationContext.Provider>
  );
};

// oxlint-disable-next-line react/only-export-components
export function useNotification(): NotificationContextType {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotification must be used within a NotificationProvider');
  }
  return context;
}
