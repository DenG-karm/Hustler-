import React from 'react'
import { useFlowStore } from '../../store/flowStore'

/**
 * Toast Bildirim Konteyneri (K-703)
 * LLM döngü uyarıları, doğrulama mesajları ve ağ durumlarını gösterir.
 */
export const ToastContainer: React.FC = () => {
  const toasts = useFlowStore((s) => s.toasts)
  const dismissToast = useFlowStore((s) => s.dismissToast)

  if (toasts.length === 0) return null

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-sm max-w-sm w-full pointer-events-none"
      data-testid="toast-container"
    >
      {toasts.map((toast) => {
        const isWarning = toast.code?.includes('WARNING') || toast.status === 200
        return (
          <div
            key={toast.id}
            className={`pointer-events-auto p-md rounded-xl border shadow-lg backdrop-blur bg-surface/95 transition-all animate-in slide-in-from-bottom-2 ${
              isWarning ? 'border-warning/50 text-warning' : 'border-destructive/40 text-destructive'
            }`}
            data-testid={`toast-${toast.id}`}
            role="alert"
          >
            <div className="flex items-start justify-between gap-sm">
              <div className="space-y-0.5">
                <h4 className="text-xs font-bold text-text-primary">{toast.title}</h4>
                <p className="text-xs text-text-secondary leading-snug">{toast.message}</p>
              </div>
              <button
                onClick={() => dismissToast(toast.id)}
                className="text-text-muted hover:text-text-primary text-xs px-1 rounded transition-colors"
                aria-label="Kapat"
                data-testid={`toast-close-${toast.id}`}
              >
                ✕
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
