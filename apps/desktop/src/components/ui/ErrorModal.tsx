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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-md"
      data-testid="error-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="error-modal-title"
    >
      <div
        className="w-full max-w-md bg-surface border border-destructive/40 rounded-2xl p-lg shadow-2xl space-y-md animate-in fade-in zoom-in-95"
        data-testid="error-modal"
      >
        <div className="flex items-start gap-md">
          <div className="w-10 h-10 rounded-xl bg-destructive/15 text-destructive flex items-center justify-center shrink-0 font-bold text-lg">
            !
          </div>
          <div className="space-y-xs flex-1">
            <div className="flex items-center justify-between">
              <h3
                id="error-modal-title"
                className="text-base font-bold text-text-primary"
                data-testid="error-modal-title"
              >
                {activeModalError.title}
              </h3>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-hover font-mono text-destructive">
                {activeModalError.code}
              </span>
            </div>
            <p className="text-sm text-text-secondary leading-relaxed" data-testid="error-modal-message">
              {activeModalError.message}
            </p>
          </div>
        </div>

        {activeModalError.instance && (
          <div className="text-[11px] font-mono text-text-muted bg-surface-hover p-xs rounded border border-border">
            Kaynak: {activeModalError.instance}
          </div>
        )}

        <div className="flex items-center justify-end gap-sm pt-xs border-t border-border">
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
  )
}
