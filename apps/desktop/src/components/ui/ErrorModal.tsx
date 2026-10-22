import React from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from './Button/Button'

/**
 * RFC 7807 Problem Details Hata Modalı (K-703)
 * Ham 500 veya stack trace asla kullanıcıya yansıtılmaz.
 */
export const ErrorModal: React.FC = () => {
  const activeModalError = useFlowStore((s) => s.activeModalError)
  const dismissModalError = useFlowStore((s) => s.dismissModalError)

  if (!activeModalError) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
      data-testid="error-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="error-modal-title"
    >
      <div
        className="w-full max-w-md studio-panel border border-destructive/40 rounded-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in-95"
        data-testid="error-modal"
      >
        <div className="h-[2px] w-full bg-destructive" />
        <div className="p-5 space-y-4">
          <div className="flex items-start gap-3.5">
            <div className="w-8 h-8 rounded-md bg-destructive/10 border border-destructive/25 text-destructive flex items-center justify-center shrink-0 font-mono font-semibold text-sm">
              !
            </div>
            <div className="space-y-1 flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <h3
                  id="error-modal-title"
                  className="text-[14px] font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight"
                  data-testid="error-modal-title"
                >
                  {activeModalError.title}
                </h3>
                <span className="text-[10px] px-2 py-0.5 rounded bg-destructive/10 font-mono font-medium text-destructive shrink-0">
                  {activeModalError.code}
                </span>
              </div>
              <p className="text-[12px] text-zinc-500 dark:text-zinc-400 leading-relaxed" data-testid="error-modal-message">
                {activeModalError.message}
              </p>
            </div>
          </div>

          {activeModalError.instance && (
            <div className="text-[11px] font-mono text-zinc-500 studio-recessed px-3 py-1.5 rounded-md">
              Kaynak: {activeModalError.instance}
            </div>
          )}

          <div className="flex items-center justify-between gap-3 pt-2 border-t border-border/70">
            <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">
              RFC 7807 // DIAGNOSTIC FAULT
            </span>
            <Button
              variant="destructive"
              size="sm"
              onClick={dismissModalError}
              data-testid="error-modal-dismiss-btn"
            >
              Anladım, Kapat
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

