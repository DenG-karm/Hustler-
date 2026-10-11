import React from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'

export const RenderScreen: React.FC = () => {
  const render = useFlowStore((s) => s.render)
  const dispatchRenderJob = useFlowStore((s) => s.dispatchRenderJob)
  const cancelRenderJob = useFlowStore((s) => s.cancelRenderJob)
  const connectionState = useFlowStore((s) => s.connectionState)
  const reconnectAttempt = useFlowStore((s) => s.reconnectAttempt)
  const resetFlow = useFlowStore((s) => s.resetFlow)
  const prevStep = useFlowStore((s) => s.prevStep)
  const isLoading = useFlowStore((s) => s.isLoading)
  const errorMessage = useFlowStore((s) => s.errorMessage)

  const handleStartRender = async (profile: 'DRAFT' | 'FINAL') => {
    await dispatchRenderJob(profile)
  }

  const isCompleted = render.status === 'COMPLETED'
  const isRendering = render.status === 'RENDERING'
  const isCancelled = render.status === 'CANCELLED'
  const isFailed = render.status === 'FAILED'

  return (
    <div className="space-y-lg max-w-2xl mx-auto" data-testid="screen-render">
      <div className="border-b border-border pb-md flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">7. Video Render Motoru</h2>
          <p className="text-sm text-text-secondary">
            K-611 optimize render profilleri: Donanım ivmelendirmeli nihai video veya ultra hızlı taslak.
          </p>
        </div>
        <span
          className={`text-xs px-sm py-xs rounded font-semibold ${
            isCompleted
              ? 'bg-success/15 text-success border border-success/30'
              : isRendering
              ? 'bg-accent/15 text-accent border border-accent/30'
              : isCancelled
              ? 'bg-warning/15 text-warning border border-warning/30'
              : isFailed
              ? 'bg-destructive/15 text-destructive border border-destructive/30'
              : 'bg-surface-hover text-text-muted border border-border'
          }`}
          data-testid="render-status-badge"
        >
          {render.status}
        </span>
      </div>

      {/* Yeniden Bağlanılıyor (Exponential Backoff Resilience Bildirimi) */}
      {connectionState === 'reconnecting' && (
        <div
          className="p-sm rounded-lg bg-warning/15 border border-warning/30 text-warning text-xs flex items-center justify-between animate-pulse"
          data-testid="connection-reconnecting-banner"
        >
          <div className="flex items-center gap-xs">
            <span className="font-bold">Yeniden Bağlanılıyor...</span>
            <span>(Deneme {reconnectAttempt}) — Event akışı otomatik kurtarılıyor.</span>
          </div>
          <span className="text-[10px] uppercase font-mono">Backoff Aktif</span>
        </div>
      )}

      {errorMessage && (
        <div
          className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm"
          data-testid="render-error"
        >
          {errorMessage}
        </div>
      )}

      {isCancelled && (
        <div
          className="p-sm rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs flex items-center justify-between"
          data-testid="render-cancelled-notice"
        >
          <span>İşlem kullanıcı tarafından iptal edildi. Süreç ve geçici dosyalar temizlendi (Sıfır Yetim Süreç).</span>
        </div>
      )}

      {/* Render Profil Kartları */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
        <div
          onClick={() => !isRendering && handleStartRender('DRAFT')}
          className={`p-md rounded-xl border transition-all cursor-pointer ${
            render.profile === 'DRAFT'
              ? 'border-accent bg-accent/5'
              : 'border-border bg-surface hover:border-border-focus'
          } ${isRendering ? 'opacity-60 cursor-not-allowed' : ''}`}
          data-testid="profile-draft-card"
        >
          <div className="flex items-center justify-between mb-xs">
            <h4 className="font-bold text-text-primary text-sm">Hızlı Taslak (DRAFT)</h4>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-hover text-text-muted font-mono">&lt; 10 sn</span>
          </div>
          <p className="text-xs text-text-secondary">540x960 çözünürlük, ultrafast preset, hızlı kontrol.</p>
        </div>

        <div
          onClick={() => !isRendering && handleStartRender('FINAL')}
          className={`p-md rounded-xl border transition-all cursor-pointer ${
            render.profile === 'FINAL'
              ? 'border-accent bg-accent/5'
              : 'border-border bg-surface hover:border-border-focus'
          } ${isRendering ? 'opacity-60 cursor-not-allowed' : ''}`}
          data-testid="profile-final-card"
        >
          <div className="flex items-center justify-between mb-xs">
            <h4 className="font-bold text-text-primary text-sm">Nihai Yayın (FINAL)</h4>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-hover text-accent font-mono">&lt; 120 sn</span>
          </div>
          <p className="text-xs text-text-secondary">1080x1920 Full HD, NVENC/GPU ivmeli, YouTube Shorts yayını.</p>
        </div>
      </div>

      {/* Render Durum ve İlerleme Paneli */}
      {render.jobId && (
        <div className="p-md rounded-xl border border-border bg-surface space-y-md" data-testid="render-progress-card">
          <div className="flex items-center justify-between text-xs">
            <span className="font-mono text-text-muted">İş ID: {render.jobId}</span>
            <div className="flex items-center gap-sm">
              <span className="font-bold text-accent">%{render.progress}</span>
              {isRendering && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={cancelRenderJob}
                  data-testid="render-cancel-btn"
                >
                  İptal Et ✕
                </Button>
              )}
            </div>
          </div>

          <div className="w-full bg-surface-hover h-3 rounded-full overflow-hidden border border-border">
            <div
              className={`h-full transition-all duration-300 ${
                isCompleted ? 'bg-success' : isCancelled ? 'bg-warning' : isFailed ? 'bg-destructive' : 'bg-accent'
              }`}
              style={{ width: `${render.progress}%` }}
              data-testid="render-progress-bar"
            />
          </div>

          {render.outputPath && (
            <div className="p-sm rounded-lg bg-surface-hover border border-border flex items-center justify-between text-xs">
              <span className="text-text-secondary">Çıktı Dosyası:</span>
              <span className="font-mono text-success font-semibold">{render.outputPath}</span>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between pt-md border-t border-border">
        <Button variant="ghost" onClick={prevStep} disabled={isRendering} data-testid="render-back-btn">
          ← Önizlemeye Dön
        </Button>
        <div className="flex items-center gap-sm">
          {isCompleted && (
            <Button variant="outline" onClick={resetFlow} data-testid="render-reset-btn">
              Yeni Akış Başlat ↺
            </Button>
          )}
          {!isRendering && (
            <Button
              variant="primary"
              onClick={() => handleStartRender(render.profile)}
              isLoading={isLoading}
              data-testid="render-start-btn"
            >
              Render Başlat
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
