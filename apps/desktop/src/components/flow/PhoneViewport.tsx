import React, { useMemo } from 'react'
import { toSafeAssetUrl } from '../../lib/securityGuard'

export interface PhoneViewportProps {
  videoUrl?: string | null
  resolution?: string
  fps?: number
  profile?: 'DRAFT' | 'FINAL'
  title?: string
  testId?: string
  isLiveRendering?: boolean
  renderProgress?: number
}

/**
 * 9:16 Dikey Telefon Çerçevesi (Viewport)
 * Gerçekçi akıllı telefon kasası içinde dikey video oynatıcı,
 * çözünürlük ve kare hızı rozetleri.
 * Disk yollarını güvenli Tauri asset:// (https://asset.localhost/...) protokolüne dönüştürür.
 */
export const PhoneViewport: React.FC<PhoneViewportProps> = ({
  videoUrl,
  resolution = '540x960',
  fps = 30,
  profile,
  title = '9:16 Stüdyo Önizleme',
  testId = 'phone-viewport',
  isLiveRendering = false,
  renderProgress = 0,
}) => {
  const isDraft = profile === 'DRAFT' || resolution === '540x960'
  const resolutionLabel = isDraft ? '540x960 Taslak' : '1080x1920 Final'

  const safeVideoUrl = useMemo(() => {
    if (!videoUrl) return null
    try {
      return toSafeAssetUrl(videoUrl)
    } catch {
      return null
    }
  }, [videoUrl])

  return (
    <div className="flex flex-col items-center" data-testid={testId}>
      {/* Üst Rozet Barı */}
      <div className="flex items-center gap-xs mb-3">
        <span
          className="px-2.5 py-1 rounded-full text-[11px] font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shadow-sm"
          data-testid={`${testId}-fps-badge`}
        >
          {fps} FPS
        </span>
        <span
          className={`px-2.5 py-1 rounded-full text-[11px] font-mono font-semibold border shadow-sm ${
            isDraft
              ? 'bg-sky-500/10 text-sky-400 border-sky-500/30'
              : 'bg-purple-500/10 text-purple-400 border-purple-500/30'
          }`}
          data-testid={`${testId}-res-badge`}
        >
          {resolutionLabel}
        </span>
        <span className="px-2.5 py-1 rounded-full text-[11px] font-mono text-text-muted bg-surface-hover border border-border">
          9:16 Dikey
        </span>
      </div>

      {/* Gerçekçi Akıllı Telefon Kasası */}
      <div className="relative w-[260px] sm:w-[280px] h-[480px] sm:h-[520px] rounded-[44px] p-3 bg-gradient-to-b from-neutral-800 via-neutral-900 to-neutral-950 border-4 border-neutral-700/80 shadow-2xl shadow-black/90 ring-1 ring-white/10 select-none">
        {/* Dynamic Island / Kamera Çentiği */}
        <div className="absolute top-4 left-1/2 -translate-x-1/2 w-24 h-4 bg-black rounded-full z-30 flex items-center justify-between px-2.5 border border-white/5 pointer-events-none">
          <div className="w-2 h-2 rounded-full bg-neutral-900 border border-neutral-700" />
          <div className="w-1.5 h-1.5 rounded-full bg-blue-950/80" />
        </div>

        {/* Yan Buton İllüzyonları (Ses & Güç) */}
        <div className="absolute -left-[6px] top-20 w-[3px] h-8 bg-neutral-700 rounded-l-sm" />
        <div className="absolute -left-[6px] top-32 w-[3px] h-8 bg-neutral-700 rounded-l-sm" />
        <div className="absolute -right-[6px] top-24 w-[3px] h-12 bg-neutral-700 rounded-r-sm" />

        {/* İç Ekran Alanı (9:16 Aspect Ratio) */}
        <div className="relative w-full h-full bg-black rounded-[34px] overflow-hidden flex flex-col items-center justify-center border border-neutral-800">
          {safeVideoUrl ? (
            <video
              controls
              playsInline
              src={safeVideoUrl}
              className="w-full h-full object-cover rounded-[34px]"
              data-testid={`${testId}-video`}
            />
          ) : isLiveRendering ? (
            <div className="w-full h-full flex flex-col items-center justify-center p-md text-center bg-gradient-to-b from-neutral-900/90 via-black to-neutral-950 text-white space-y-md">
              <div className="relative w-16 h-16 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-4 border-accent/20 animate-ping" />
                <div className="w-12 h-12 rounded-full border-4 border-accent border-t-transparent animate-spin" />
                <span className="text-xl">⚙️</span>
              </div>
              <div className="space-y-xs">
                <p className="text-sm font-bold text-accent">Render Sürüyor</p>
                <p className="text-xs text-text-muted font-mono">%{renderProgress} Tamamlandı</p>
              </div>
              <div className="w-3/4 bg-white/10 h-1.5 rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent transition-all duration-300"
                  style={{ width: `${renderProgress}%` }}
                />
              </div>
            </div>
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center p-md text-center bg-gradient-to-b from-neutral-900 to-black text-white/80 space-y-sm">
              <span className="text-4xl">🎬</span>
              <p className="text-xs font-semibold text-white/90">{title}</p>
              <p className="text-[11px] text-white/50 max-w-[180px] leading-relaxed">
                9:16 dikey kadrajlama ve altyazı senkronu kontrolü
              </p>
            </div>
          )}

          {/* Alt Çizgi (Home Bar) */}
          <div className="absolute bottom-2 left-1/2 -translate-x-1/2 w-28 h-1 bg-white/30 rounded-full z-20 pointer-events-none" />
        </div>
      </div>
    </div>
  )
}
