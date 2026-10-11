import React from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'

export const PreviewScreen: React.FC = () => {
  const preview = useFlowStore((s) => s.preview)
  const setPreviewVerified = useFlowStore((s) => s.setPreviewVerified)
  const nextStep = useFlowStore((s) => s.nextStep)
  const prevStep = useFlowStore((s) => s.prevStep)
  const errorMessage = useFlowStore((s) => s.errorMessage)

  const handleAdvance = () => {
    try {
      nextStep()
    } catch {
      // Store hatası
    }
  }

  return (
    <div className="space-y-lg max-w-xl mx-auto" data-testid="screen-preview">
      <div className="border-b border-border pb-md flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">6. Taslak Önizleme</h2>
          <p className="text-sm text-text-secondary">
            Nihai render işleminden önce oluşturulan taslak videoyu kontrol edip doğrulayın.
          </p>
        </div>
        <span
          className={`text-xs px-sm py-xs rounded font-semibold ${
            preview.isVerified
              ? 'bg-success/15 text-success border border-success/30'
              : 'bg-warning/15 text-warning border border-warning/30'
          }`}
          data-testid="preview-status-badge"
        >
          {preview.isVerified ? 'Doğrulandı ✓' : 'Doğrulama Gerekli'}
        </span>
      </div>

      {errorMessage && (
        <div className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm" data-testid="preview-error">
          {errorMessage}
        </div>
      )}

      {/* 9:16 Vertical Video Preview Container */}
      <div className="flex flex-col items-center">
        <div className="w-[240px] h-[426px] rounded-2xl border-2 border-border bg-black flex flex-col items-center justify-center relative overflow-hidden shadow-lg">
          <div className="absolute top-3 left-3 px-2 py-0.5 rounded bg-black/60 text-[10px] text-white">
            {preview.resolution} • {preview.fps} FPS
          </div>

          <div className="text-center p-md space-y-sm">
            <span className="text-3xl">🎬</span>
            <p className="text-xs text-white/80 font-medium">9:16 Önizleme Oynatıcı</p>
            <p className="text-[10px] text-white/50 font-mono line-clamp-1">{preview.previewUrl ?? 'Taslak video'}</p>
          </div>

          <div className="absolute bottom-3 inset-x-3">
            <div className="h-1 bg-white/20 rounded-full overflow-hidden">
              <div className="h-full bg-accent w-1/2" />
            </div>
          </div>
        </div>
      </div>

      <div className="p-md rounded-xl border border-border bg-surface flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold text-text-primary">Görsel Kalite Doğrulaması</h4>
          <p className="text-xs text-text-secondary">Render aşamasına geçmeden önce videoyu onaylayın.</p>
        </div>
        <Button
          variant={preview.isVerified ? 'outline' : 'primary'}
          size="sm"
          onClick={() => setPreviewVerified(!preview.isVerified)}
          data-testid="preview-verify-btn"
        >
          {preview.isVerified ? 'Doğrulandı ✓' : 'Önizlemeyi Doğrula'}
        </Button>
      </div>

      <div className="flex items-center justify-between pt-md border-t border-border">
        <Button variant="ghost" onClick={prevStep} data-testid="preview-back-btn">
          ← Görsellere Dön
        </Button>
        <Button
          variant="primary"
          onClick={handleAdvance}
          disabled={!preview.isVerified}
          data-testid="preview-submit-btn"
        >
          Render Ekranına Geç →
        </Button>
      </div>
    </div>
  )
}
