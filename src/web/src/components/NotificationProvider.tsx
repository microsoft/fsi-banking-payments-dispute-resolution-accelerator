/**
 * Global toast notification system using Fluent UI Toaster.
 *
 * Usage:
 *   const { notifySuccess, notifyWarning, notifyError, notifyInfo } = useNotifications();
 *   notifySuccess('Case approved', 'Case CASE-001 moved to approved status.');
 */
import {
  Link,
  Toast,
  ToastBody,
  ToastTitle,
  Toaster,
  useId,
  useToastController,
  type ToastIntent,
} from '@fluentui/react-components';
import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react';

interface NotificationContextType {
  notifySuccess: (title: string, body?: string) => void;
  notifyWarning: (title: string, body?: string) => void;
  notifyError: (title: string, body?: string) => void;
  notifyInfo: (title: string, body?: string) => void;
}

const NotificationContext = createContext<NotificationContextType | null>(null);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const toasterId = useId('global-toaster');
  const { dispatchToast, dismissToast } = useToastController(toasterId);

  const notify = useCallback(
    (intent: ToastIntent, title: string, body?: string) => {
      const toastId = `toast-${Date.now()}`;
      dispatchToast(
        <Toast>
          <ToastTitle action={<Link onClick={() => dismissToast(toastId)}>✕</Link>}>{title}</ToastTitle>
          {body && <ToastBody>{body}</ToastBody>}
        </Toast>,
        { toastId, intent, timeout: intent === 'error' ? 8000 : 5000, position: 'top-end' }
      );
    },
    [dispatchToast, dismissToast]
  );

  const value = useMemo<NotificationContextType>(
    () => ({
      notifySuccess: (title, body) => notify('success', title, body),
      notifyWarning: (title, body) => notify('warning', title, body),
      notifyError: (title, body) => notify('error', title, body),
      notifyInfo: (title, body) => notify('info', title, body),
    }),
    [notify]
  );

  return (
    <NotificationContext.Provider value={value}>
      <Toaster toasterId={toasterId} />
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications(): NotificationContextType {
  const ctx = useContext(NotificationContext);
  if (!ctx) {
    throw new Error('useNotifications must be used within <NotificationProvider>');
  }
  return ctx;
}
