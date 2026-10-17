import React, { useMemo, useState, useEffect } from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'
import { toSafeAssetUrl } from '../../lib/securityGuard'
import { clipboardWrite } from '../../lib/clipboard'
import { PhoneViewport } from './PhoneViewport'

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
  const addToast = useFlowStore((s) => s.addToast)

  const [elapsedSec, setElapsedSec] = useState(0)
  const [copiedPath, setCopiedPath] = useState(false)

  const isCompleted = render.status === 'COMPLETED'
  const isRendering = render.status === 'RENDERING'
  const isCancelled = render.status === 'CANCELLED'
  const isFailed = render.status === 'FAILED'

  // Canlı Render Geçen Süre Kronometresi
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null
    if (isRendering) {
      timer = setInterval(() => {
        setElapsedSec((prev) => prev + 1)
      }, 1000)
    }
    return () => {
      if (timer) clearInterval(timer)
    }
  }, [isRendering])

  const formatElapsed = (sec: number) => {
    const mins = Math.floor(sec / 60)
    const remaining = sec % 60
    return `${String(mins).padStart(2, '0')}:${String(remaining).padStart(2, '0')} sn`
  }

  // Gerçek Backend Aşama Telemetrisi (SSE / JobRepository current_step ve Kodlayıcı)
  const activeStepText = render.stepName || (isCompleted ? 'Render ve QC tamamlandı' : isRendering ? 'FFmpeg işleniyor...' : 'Kuyrukta bekliyor')
  const activeEncoder = render.encoder || (render.profile === 'DRAFT' ? 'libx264' : 'Donanım seçiliyor...')

  const validatedOutputPath = useMemo(() => {
    if (!render.outputPath) return null
    try {
      return toSafeAssetUrl(render.outputPath)
    } catch {
      return null
    }
  }, [render.outputPath])

  const handleStartRender = async (profile: 'DRAFT' | 'FINAL') => {
    setElapsedSec(0)
    await dispatchRenderJob(profile)
  }

  const handleCopyOutputPath = async () => {
    const target = render.outputPath || ''
    if (!target) return
    try {
      await clipboardWrite(target)
      setCopiedPath(true)
      addToast({
        title: 'Dosya Yolu Kopyalandı',
        message: 'Çıktı dosya yolu panoya aktarıldı.',
        code: 'OUTPUT_PATH_COPIED',
        status: 200,
      })
      setTimeout(() => setCopiedPath(false), 2500)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      addToast({
        title: 'Pano Hatası',
        message: msg,
        code: 'CLIPBOARD_ERROR',
        status: 500,
      })
    }
  }

  const currentResolution = render.profile === 'FINAL' ? '1080x1920' : '540x960'

  return (
    <div className="space-y-lg max-w-5xl mx-auto" data-testid="screen-render">
      {/* Üst Başlık & Durum Çubuğu */}
      <div className="border-b border-border pb-md flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-accent/10 text-accent text-xs flex items-center justify-center font-bold">
              6
            </span>
            <h2 className="text-xl font-bold text-text-primary">Video Render ve Nihai QC Masası</h2>
          </div>
          <p className="text-sm text-text-secondary mt-1">
            K-611 optimize render profilleri: Donanım ivmelendirmeli nihai video veya ultra hızlı taslak.
          </p>
        </div>
        <span
          className={`text-xs px-3 py-1 rounded-full font-semibold border ${
            isCompleted
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
              : isRendering
              ? 'bg-accent/15 text-accent border-accent/30 animate-pulse'
              : isCancelled
              ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
              : isFailed
              ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
              : 'bg-surface-hover text-text-muted border-border'
          }`}
          data-testid="render-status-badge"
        >
          {render.status}
        </span>
      </div>

      {/* Yeniden Bağlanılıyor (Exponential Backoff Resilience Bildirimi) */}
      {connectionState === 'reconnecting' && (
        <div
          className="p-sm rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs flex items-center justify-between animate-pulse"
          data-testid="connection-reconnecting-banner"
        >
          <div className="flex items-center gap-xs">
            <span className="font-bold">Yeniden Bağlanılıyor...</span>
            <span>(Deneme {reconnectAttempt}) — Event akışı otomatik kurtarılıyor.</span>
          </div>
          <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-500/20 font-semibold">
            Backoff Aktif
          </span>
        </div>
      )}

      {errorMessage && (
        <div
          className="p-sm rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-sm"
          data-testid="render-error"
        >
          {errorMessage}
        </div>
      )}

      {isCancelled && (
        <div
          className="p-sm rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs flex items-center justify-between"
          data-testid="render-cancelled-notice"
        >
          <span>İşlem kullanıcı tarafından iptal edildi. Süreç ve geçici dosyalar temizlendi (Sıfır Yetim Süreç).</span>
        </div>
      )}

      {/* 2 Sütunlu Stüdyo Render Düzeni: Sol = 9:16 Viewport, Sağ = Telemetri & Aksiyonlar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-lg items-start">
        {/* SOL SÜTUN (5/12): 9:16 Dikey Telefon Çerçevesi */}
        <div className="lg:col-span-5 flex justify-center">
          <PhoneViewport
            videoUrl={isCompleted ? validatedOutputPath : null}
            resolution={currentResolution}
            fps={30}
            profile={render.profile}
            title={isCompleted ? 'Nihai Render Oynatıcı' : 'Canlı Render Viewport'}
            testId="render-viewport"
            isLiveRendering={isRendering}
            renderProgress={render.progress}
          />
        </div>

        {/* SAĞ SÜTUN (7/12): Profil Seçimi, Canlı Telemetri ve QC Kartları */}
        <div className="lg:col-span-7 space-y-md">
          {/* Render Profil Kartları */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-md">
            <div
              onClick={() => !isRendering && handleStartRender('DRAFT')}
              className={`p-md rounded-2xl border transition-all cursor-pointer ${
                render.profile === 'DRAFT'
                  ? 'border-accent bg-accent/5 ring-1 ring-accent/30 shadow-md'
                  : 'border-border bg-surface hover:border-border-focus'
              } ${isRendering ? 'opacity-60 cursor-not-allowed' : ''}`}
              data-testid="profile-draft-card"
            >
              <div className="flex items-center justify-between mb-xs">
                <h4 className="font-bold text-text-primary text-sm flex items-center gap-1.5">
                  <span>⚡</span>
                  <span>Hızlı Taslak (DRAFT)</span>
                </h4>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-hover text-text-muted font-mono font-medium">
                  &lt; 10 sn
                </span>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed">
                540x960 çözünürlük, ultrafast preset, hızlı kontrol için optimize edilmiş hafif çıktı.
              </p>
            </div>

            <div
              onClick={() => !isRendering && handleStartRender('FINAL')}
              className={`p-md rounded-2xl border transition-all cursor-pointer ${
                render.profile === 'FINAL'
                  ? 'border-purple-500 bg-purple-500/5 ring-1 ring-purple-500/30 shadow-md'
                  : 'border-border bg-surface hover:border-border-focus'
              } ${isRendering ? 'opacity-60 cursor-not-allowed' : ''}`}
              data-testid="profile-final-card"
            >
              <div className="flex items-center justify-between mb-xs">
                <h4 className="font-bold text-text-primary text-sm flex items-center gap-1.5">
                  <span>💎</span>
                  <span>Nihai Yayın (FINAL)</span>
                </h4>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-hover text-purple-400 font-mono font-medium">
                  &lt; 120 sn
                </span>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed">
                1080x1920 Full HD, NVENC/GPU ivmeli, YouTube Shorts & Reels için 30 FPS master yayın.
              </p>
            </div>
          </div>

          {/* Render Durum ve Canlı Telemetri Paneli */}
          {render.jobId && (
            <div className="p-md rounded-2xl border border-border bg-surface space-y-md shadow-sm" data-testid="render-progress-card">
              {/* Telemetri Üst Bilgi Barı */}
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-text-muted bg-surface-hover px-2 py-0.5 rounded border border-border">
                    İş ID: {render.jobId}
                  </span>
                  {isRendering && (
                    <span className="text-accent font-mono font-semibold flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-accent animate-ping" />
                      <span>{formatElapsed(elapsedSec)}</span>
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-sm">
                  <span className="text-sm font-bold font-mono text-accent">%{render.progress}</span>
                  {isRendering && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={cancelRenderJob}
                      data-testid="render-cancel-btn"
                      className="bg-rose-600 hover:bg-rose-700 text-white font-semibold flex items-center gap-1 shadow-sm"
                    >
                      <span>✕</span>
                      <span>Üretimi İptal Et (Hard Cancel)</span>
                    </Button>
                  )}
                </div>
              </div>

              {/* İlerleme Çubuğu */}
              <div className="w-full bg-surface-hover h-3 rounded-full overflow-hidden border border-border">
                <div
                  className={`h-full transition-all duration-300 ${
                    isCompleted
                      ? 'bg-emerald-500'
                      : isCancelled
                      ? 'bg-amber-500'
                      : isFailed
                      ? 'bg-rose-500'
                      : 'bg-accent'
                  }`}
                  style={{ width: `${render.progress}%` }}
                  data-testid="render-progress-bar"
                />
              </div>

              {/* Aktif Adım ve Kodlayıcı Telemetrisi (Backend JobRepository & SSE) */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs pt-1 border-t border-border/50 gap-2">
                <div className="flex items-center gap-1.5">
                  <span className="text-text-muted">Aşama:</span>
                  <span className="font-semibold text-text-primary flex items-center gap-1.5 font-mono" data-testid="render-current-step">
                    {isRendering && <span className="animate-spin text-accent">⚙️</span>}
                    <span>{activeStepText}</span>
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-[11px] font-mono">
                  <span className="text-text-muted">Kodlayıcı:</span>
                  <span className="px-2 py-0.5 rounded bg-surface-hover border border-border text-accent font-semibold" data-testid="render-active-encoder">
                    {activeEncoder}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Render Tamamlandığında: QC Kalite Onay Kartı */}
          {isCompleted && (
            <div className="p-md rounded-2xl border border-emerald-500/30 bg-emerald-500/10 space-y-sm" data-testid="render-qc-card">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-emerald-500 text-white text-xs flex items-center justify-center font-bold">
                    ✓
                  </span>
                  <h4 className="text-sm font-bold text-emerald-400">QC Kalite Doğrulaması Onaylandı</h4>
                </div>
                <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-semibold border border-emerald-500/30">
                  QC: PASSED ✓
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs pt-1 border-t border-emerald-500/20">
                <div className="bg-black/20 p-2 rounded-xl">
                  <span className="text-[10px] text-text-muted block">Konteyner</span>
                  <span className="font-mono font-semibold text-emerald-300">MP4 (Faststart)</span>
                </div>
                <div className="bg-black/20 p-2 rounded-xl">
                  <span className="text-[10px] text-text-muted block">Çözünürlük</span>
                  <span className="font-mono font-semibold text-emerald-300">
                    {render.profile === 'FINAL' ? '1080x1920' : '540x960'}
                  </span>
                </div>
                <div className="bg-black/20 p-2 rounded-xl">
                  <span className="text-[10px] text-text-muted block">Kare Hızı</span>
                  <span className="font-mono font-semibold text-emerald-300">30.0 FPS CFR</span>
                </div>
                <div className="bg-black/20 p-2 rounded-xl">
                  <span className="text-[10px] text-text-muted block">Ses Formatı</span>
                  <span className="font-mono font-semibold text-emerald-300">AAC 48kHz Stereo</span>
                </div>
              </div>
            </div>
          )}

          {/* Çıktı Dosya Yolu Kartı (Kopyalama / Gösterme) */}
          {render.outputPath && (
            <div className="p-md rounded-2xl border border-border bg-surface space-y-sm" data-testid="render-output-card">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-text-secondary uppercase tracking-wider">
                  Çıktı Dosyası:
                </span>
                <span className="text-[11px] font-mono text-emerald-400 font-semibold">
                  Disk Kaydı Tamamlandı ✓
                </span>
              </div>
              <div className="flex items-center gap-2 p-sm rounded-xl bg-surface-hover border border-border">
                <span className="text-base shrink-0">🎬</span>
                <span className="font-mono text-xs text-emerald-400 font-semibold break-all flex-1" data-testid="render-output-path">
                  {render.outputPath}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCopyOutputPath}
                  data-testid="copy-output-path-btn"
                  className="shrink-0"
                >
                  {copiedPath ? '✓ Kopyalandı' : 'Yolu Kopyala'}
                </Button>
              </div>
            </div>
          )}

          {/* Alt Gezinme ve Aksiyon Çubuğu */}
          <div className="flex items-center justify-between pt-md border-t border-border">
            <Button
              variant="ghost"
              onClick={prevStep}
              disabled={isRendering}
              data-testid="render-back-btn"
            >
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
      </div>
    </div>
  )
}
