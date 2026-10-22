import React, { useMemo, useState, useEffect } from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'
import { toSafeAssetUrl } from '../../lib/securityGuard'
import { clipboardWrite } from '../../lib/clipboard'
import { PhoneViewport } from './PhoneViewport'

const CARD_CLS =
  'p-6 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs'

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
  const activeStepText =
    render.stepName ||
    (isCompleted ? 'Render ve QC tamamlandı' : isRendering ? 'FFmpeg işleniyor...' : 'Kuyrukta bekliyor')
  const activeEncoder =
    render.encoder || (render.profile === 'DRAFT' ? 'libx264' : 'Donanım seçiliyor...')

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
    <div className="space-y-6 max-w-5xl mx-auto py-2 animate-in fade-in duration-200" data-testid="screen-render">
      {/* 1. Üst Başlık & Durum Çubuğu */}
      <div className={CARD_CLS}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  isCompleted
                    ? 'bg-emerald-500'
                    : isRendering
                    ? 'bg-indigo-500 animate-ping'
                    : isCancelled
                    ? 'bg-amber-500'
                    : isFailed
                    ? 'bg-rose-500'
                    : 'bg-zinc-400'
                }`}
              />
              <span className="text-[11px] font-mono font-medium tracking-wider uppercase text-indigo-600 dark:text-indigo-400">
                AŞAMA 06 // FFMPEG MASTER RENDER VE DAĞITIM
              </span>
            </div>
            <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight">
              Video Render ve Nihai QC Masası
            </h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              Donanım hızlandırmalı FFmpeg motoru ile yüksek kaliteli 9:16 Shorts master videosunu derleyin.
            </p>
          </div>

          <span
            className={`text-xs px-3.5 py-1.5 rounded-full font-mono font-medium border shrink-0 inline-flex items-center gap-1.5 ${
              isCompleted
                ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/60'
                : isRendering
                ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-800/60 animate-pulse'
                : isCancelled
                ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800/60'
                : isFailed
                ? 'bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 border-rose-200 dark:border-rose-800/60'
                : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700'
            }`}
            data-testid="render-status-badge"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isCompleted
                  ? 'bg-emerald-500'
                  : isRendering
                  ? 'bg-indigo-500 animate-ping'
                  : isCancelled
                  ? 'bg-amber-500'
                  : isFailed
                  ? 'bg-rose-500'
                  : 'bg-zinc-400'
              }`}
            />
            {render.status}
          </span>
        </div>
      </div>

      {/* Yeniden Bağlanılıyor (Exponential Backoff Resilience Bildirimi) */}
      {connectionState === 'reconnecting' && (
        <div
          className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 text-amber-800 dark:text-amber-300 text-xs font-mono flex items-center justify-between animate-pulse"
          data-testid="connection-reconnecting-banner"
        >
          <div className="flex items-center gap-2">
            <span className="font-semibold">Yeniden Bağlanılıyor...</span>
            <span>(Deneme {reconnectAttempt}) — Event akışı otomatik kurtarılıyor.</span>
          </div>
          <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-900/40 border border-amber-300 dark:border-amber-700 font-semibold">
            Backoff Aktif
          </span>
        </div>
      )}

      {/* Hata Bildirimi */}
      {errorMessage && (
        <div
          className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800/60 text-rose-700 dark:text-rose-300 text-xs font-mono flex items-center gap-2"
          data-testid="render-error"
        >
          <svg className="w-4 h-4 shrink-0 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>{errorMessage}</span>
        </div>
      )}

      {/* İptal Bildirimi */}
      {isCancelled && (
        <div
          className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 text-amber-800 dark:text-amber-300 text-xs font-mono flex items-center justify-between"
          data-testid="render-cancelled-notice"
        >
          <span>İşlem kullanıcı tarafından iptal edildi. Süreç ve geçici dosyalar temizlendi (Sıfır Yetim Süreç).</span>
        </div>
      )}

      {/* 2. 2 Sütunlu Stüdyo Render Düzeni: Sol = 9:16 Viewport, Sağ = Telemetri & Aksiyonlar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* SOL SÜTUN (5/12): 9:16 Dikey Telefon Çerçevesi */}
        <div className={`lg:col-span-5 flex justify-center ${CARD_CLS}`}>
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
        <div className="lg:col-span-7 space-y-4">
          {/* Render Profil Kartları */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div
              onClick={() => !isRendering && handleStartRender('DRAFT')}
              className={`p-4 rounded-xl border transition-all cursor-pointer ${
                render.profile === 'DRAFT'
                  ? 'border-indigo-500/80 bg-indigo-50/20 dark:bg-indigo-950/30 shadow-xs'
                  : 'border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/70 hover:bg-zinc-50 dark:hover:bg-zinc-800/50'
              } ${isRendering ? 'opacity-60 cursor-not-allowed' : ''}`}
              data-testid="profile-draft-card"
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm flex items-center gap-1.5">
                  <svg className="w-4 h-4 text-indigo-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span>Hızlı Taslak (DRAFT)</span>
                </h4>
                <span className="text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-900/60">
                  &lt; 10 sn
                </span>
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
                540×960 çözünürlük, ultrafast preset, hızlı denetim için optimize edilmiş hafif çıktı.
              </p>
            </div>

            <div
              onClick={() => !isRendering && handleStartRender('FINAL')}
              className={`p-4 rounded-xl border transition-all cursor-pointer ${
                render.profile === 'FINAL'
                  ? 'border-emerald-500/80 bg-emerald-50/20 dark:bg-emerald-950/30 shadow-xs'
                  : 'border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/70 hover:bg-zinc-50 dark:hover:bg-zinc-800/50'
              } ${isRendering ? 'opacity-60 cursor-not-allowed' : ''}`}
              data-testid="profile-final-card"
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm flex items-center gap-1.5">
                  <svg className="w-4 h-4 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>Nihai Yayın (FINAL)</span>
                </h4>
                <span className="text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900/60">
                  &lt; 120 sn
                </span>
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
                1080×1920 Full HD, donanım ivmeli, Shorts &amp; Reels için 30 FPS master yayın.
              </p>
            </div>
          </div>

          {/* Render Durum ve Canlı Telemetri Paneli */}
          {render.jobId && (
            <div className={`${CARD_CLS} space-y-4`} data-testid="render-progress-card">
              {/* Telemetri Üst Bilgi Barı */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-zinc-700 dark:text-zinc-300 bg-zinc-100 dark:bg-zinc-800 px-3 py-1 rounded-lg border border-zinc-200 dark:border-zinc-700 text-xs">
                    İş ID: {render.jobId}
                  </span>
                  {isRendering && (
                    <span className="text-indigo-600 dark:text-indigo-400 font-mono font-medium flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-indigo-500 animate-ping" />
                      <span>{formatElapsed(elapsedSec)}</span>
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  <span className="text-base font-bold font-mono text-indigo-600 dark:text-indigo-400">
                    %{render.progress}
                  </span>
                  {isRendering && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={cancelRenderJob}
                      data-testid="render-cancel-btn"
                      className="cursor-pointer text-xs"
                    >
                      <span>✕</span>
                      <span>Üretimi İptal Et (Hard Cancel)</span>
                    </Button>
                  )}
                </div>
              </div>

              {/* İlerleme Çubuğu */}
              <div className="w-full bg-zinc-100 dark:bg-zinc-800 h-2.5 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${
                    isCompleted
                      ? 'bg-emerald-500'
                      : isCancelled
                      ? 'bg-amber-500'
                      : isFailed
                      ? 'bg-rose-500'
                      : 'bg-indigo-600'
                  }`}
                  style={{ width: `${render.progress}%` }}
                  data-testid="render-progress-bar"
                />
              </div>

              {/* Aktif Adım ve Kodlayıcı Telemetrisi */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs pt-3 border-t border-zinc-100 dark:border-zinc-800 gap-2 font-mono">
                <div className="flex items-center gap-2">
                  <span className="text-zinc-400 uppercase text-[10px]">AŞAMA:</span>
                  <span className="font-medium text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5" data-testid="render-current-step">
                    {isRendering && (
                      <span className="w-2 h-2 rounded-full bg-indigo-500 animate-ping" />
                    )}
                    <span>{activeStepText}</span>
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="text-zinc-400 uppercase text-[10px]">KODLAYICI:</span>
                  <span className="px-2.5 py-0.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-indigo-600 dark:text-indigo-400 border border-zinc-200 dark:border-zinc-700 font-semibold" data-testid="render-active-encoder">
                    {activeEncoder}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Render Tamamlandığında: QC Kalite Onay Kartı */}
          {isCompleted && (
            <div className="p-5 rounded-2xl border border-emerald-200 dark:border-emerald-800/60 bg-emerald-50/30 dark:bg-emerald-950/20 space-y-3.5" data-testid="render-qc-card">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-900/60 text-emerald-600 dark:text-emerald-400 text-xs flex items-center justify-center font-bold">
                    ✓
                  </span>
                  <h4 className="text-sm font-bold text-emerald-800 dark:text-emerald-300">
                    QC Kalite Doğrulaması Onaylandı
                  </h4>
                </div>
                <span className="text-[10px] font-mono px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-300 dark:border-emerald-800">
                  QC: PASSED ✓
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs pt-2 border-t border-emerald-200 dark:border-emerald-850">
                <div className="bg-white/80 dark:bg-zinc-900/80 p-2.5 rounded-xl border border-zinc-200/80 dark:border-zinc-800">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase block">KONTEYNER</span>
                  <span className="font-mono font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5 block">MP4 (Faststart)</span>
                </div>
                <div className="bg-white/80 dark:bg-zinc-900/80 p-2.5 rounded-xl border border-zinc-200/80 dark:border-zinc-800">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase block">ÇÖZÜNÜRLÜK</span>
                  <span className="font-mono font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5 block">
                    {render.profile === 'FINAL' ? '1080x1920' : '540x960'}
                  </span>
                </div>
                <div className="bg-white/80 dark:bg-zinc-900/80 p-2.5 rounded-xl border border-zinc-200/80 dark:border-zinc-800">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase block">KARE HIZI</span>
                  <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400 mt-0.5 block">30.0 FPS CFR</span>
                </div>
                <div className="bg-white/80 dark:bg-zinc-900/80 p-2.5 rounded-xl border border-zinc-200/80 dark:border-zinc-800">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase block">SES FORMATI</span>
                  <span className="font-mono font-semibold text-indigo-600 dark:text-indigo-400 mt-0.5 block">AAC 48kHz Stereo</span>
                </div>
              </div>
            </div>
          )}

          {/* Çıktı Dosya Yolu Kartı */}
          {render.outputPath && (
            <div className={`${CARD_CLS} space-y-3`} data-testid="render-output-card">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="font-semibold text-zinc-500 uppercase">
                  ÇIKTI DOSYASI (MASTER OUTPUT):
                </span>
                <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                  Disk Kaydı Tamamlandı ✓
                </span>
              </div>
              <div className="flex items-center gap-2.5 p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/60 border border-zinc-200 dark:border-zinc-700/80">
                <svg className="w-4 h-4 text-emerald-500 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                  <rect x="2.5" y="4.5" width="14" height="15" rx="2" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 9.5l5-3v11l-5-3" />
                </svg>
                <span className="font-mono text-xs text-zinc-800 dark:text-zinc-200 font-medium break-all flex-1" data-testid="render-output-path">
                  {render.outputPath}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCopyOutputPath}
                  data-testid="copy-output-path-btn"
                  className="shrink-0 cursor-pointer text-xs"
                >
                  {copiedPath ? '✓ Kopyalandı' : 'Yolu Kopyala'}
                </Button>
              </div>
            </div>
          )}

          {/* Alt Gezinme ve Aksiyon Çubuğu */}
          <div className="flex items-center justify-between pt-4 border-t border-zinc-200 dark:border-zinc-800">
            <Button
              variant="ghost"
              onClick={prevStep}
              disabled={isRendering}
              data-testid="render-back-btn"
            >
              ← Önizlemeye Dön
            </Button>
            <div className="flex items-center gap-3">
              {isCompleted && (
                <Button variant="outline" onClick={resetFlow} data-testid="render-reset-btn" className="cursor-pointer">
                  Yeni Akış Başlat ↺
                </Button>
              )}
              {!isRendering && (
                <Button
                  variant="primary"
                  onClick={() => handleStartRender(render.profile)}
                  isLoading={isLoading}
                  data-testid="render-start-btn"
                  className="cursor-pointer"
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
