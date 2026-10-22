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
      className="fixed bottom-9 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
      data-testid="toast-container"
    >
      {toasts.map((toast) => {
        const isSuccess = toast.status === 200 && !toast.code?.includes('WARNING')
        const isWarning = toast.code?.includes('WARNING')
        const toneClasses = isSuccess
          ? 'border-emerald-500/30 text-emerald-600 dark:text-emerald-400'
          : isWarning
            ? 'border-warning/40 text-warning'
            : 'border-destructive/35 text-destructive'
        const ledColor = isSuccess ? 'bg-emerald-400' : isWarning ? 'bg-warning' : 'bg-destructive'

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto p-3.5 rounded-lg border studio-panel backdrop-blur bg-surface/95 transition-all animate-in slide-in-from-bottom-2 ${toneClasses}`}
            data-testid={`toast-${toast.id}`}
            role="alert"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-2.5 min-w-0">
                <span className={`w-2 h-2 rounded-full mt-1 shrink-0 ${ledColor}`} />
                <div className="space-y-0.5 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <h4 className="text-[12px] font-semibold text-zinc-900 dark:text-zinc-100 truncate">{toast.title}</h4>
                    {toast.code && (
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-zinc-200/80 dark:bg-zinc-800/80 text-zinc-500 dark:text-zinc-400 shrink-0">
                        {toast.code}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-zinc-500 dark:text-zinc-400 leading-snug">{toast.message}</p>
                </div>
              </div>
              <button
                onClick={() => dismissToast(toast.id)}
                className="text-zinc-500 hover:text-zinc-200 text-xs px-1.5 py-0.5 rounded-md hover:bg-zinc-800/40 font-mono transition-colors shrink-0 outline-none ring-0 focus:outline-none focus:ring-0"
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

