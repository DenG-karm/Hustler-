import React, { useMemo, useState } from 'react'
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
 * 9:16 Dikey Referans Monitörü & Safe-Zone Rehberli Telefon Çerçevesi (Viewport)
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
  const [showSafeZones, setShowSafeZones] = useState(true)
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
      {/* Üst Telemetri & Safe-Zone Rehber Barı */}
      <div className="flex flex-wrap items-center justify-center gap-1.5 mb-3">
        <span
          className="px-2 py-0.5 rounded-md text-[10px] font-mono font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
          data-testid={`${testId}-fps-badge`}
        >
          {fps} FPS
        </span>
        <span
          className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-medium ${
            isDraft
              ? 'bg-zinc-200/80 dark:bg-zinc-800/80 text-teal-600 dark:text-teal-400'
              : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
          }`}
          data-testid={`${testId}-res-badge`}
        >
          {resolutionLabel}
        </span>
        <button
          type="button"
          onClick={() => setShowSafeZones((prev) => !prev)}
          className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-medium transition-colors cursor-pointer outline-none ring-0 focus:outline-none focus:ring-0 ${
            showSafeZones
              ? 'bg-zinc-200/80 dark:bg-zinc-800/80 text-zinc-900 dark:text-zinc-100'
              : 'bg-transparent text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/40'
          }`}
          title="TikTok / Shorts / Reels 9:16 Güvenli Alan (Safe-Zone) Kılavuzunu Aç/Kapat"
        >
          9:16 SAFE-ZONE {showSafeZones ? 'AÇIK' : 'KAPALI'}
        </button>
      </div>

      {/* Endüstriyel 9:16 Referans Monitör Kasası */}
      <div className="relative w-[264px] sm:w-[284px] h-[484px] sm:h-[520px] rounded-[36px] p-2.5 bg-gradient-to-b from-zinc-800 via-zinc-900 to-zinc-950 border border-zinc-700/80 shadow-2xl shadow-black/90 select-none">
        {/* Üst Kamera & Sensör Yuvası */}
        <div className="absolute top-4 left-1/2 -translate-x-1/2 w-20 h-3.5 bg-black rounded-full z-30 flex items-center justify-between px-2 border border-white/10 pointer-events-none">
          <div className="w-1.5 h-1.5 rounded-full bg-zinc-800 border border-zinc-600" />
          <div className="w-1.5 h-1.5 rounded-full bg-teal-400/70" />
        </div>

        {/* Yan Donanım Butonları */}
        <div className="absolute -left-[3px] top-20 w-[2px] h-8 bg-zinc-600 rounded-l-sm" />
        <div className="absolute -left-[3px] top-32 w-[2px] h-8 bg-zinc-600 rounded-l-sm" />
        <div className="absolute -right-[3px] top-24 w-[2px] h-12 bg-zinc-600 rounded-r-sm" />

        {/* İç Ekran Alanı (9:16 Aspect Ratio) */}
        <div className="relative w-full h-full bg-black rounded-[28px] overflow-hidden flex flex-col items-center justify-center border border-zinc-800">
          {safeVideoUrl ? (
            <video
              controls
              playsInline
              src={safeVideoUrl}
              className="w-full h-full object-cover rounded-[28px]"
              data-testid={`${testId}-video`}
            />
          ) : isLiveRendering ? (
            <div className="w-full h-full flex flex-col items-center justify-center p-4 text-center bg-gradient-to-b from-zinc-900/95 via-black to-zinc-950 text-zinc-100 space-y-4">
              <div className="relative w-16 h-16 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-2 border-teal-400/25 animate-ping" />
                <div className="w-12 h-12 rounded-full border-2 border-teal-400 border-t-transparent animate-spin" />
                <svg className="w-5 h-5 text-teal-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div className="space-y-1">
                <p className="text-xs font-mono font-semibold text-teal-400 uppercase tracking-wider">Render Sürüyor</p>
                <p className="text-xs text-zinc-400 font-mono">%{renderProgress} Tamamlandı</p>
              </div>
              <div className="w-3/4 bg-zinc-800 h-1.5 rounded-full overflow-hidden">
                <div
                  className="h-full bg-teal-400 transition-all duration-300"
                  style={{ width: `${renderProgress}%` }}
                />
              </div>
            </div>
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center p-4 text-center bg-gradient-to-b from-zinc-900 via-zinc-950 to-black text-zinc-100 space-y-2.5">
              <div className="w-11 h-11 rounded-lg border border-teal-500/25 bg-teal-500/10 flex items-center justify-center text-teal-400">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75}>
                  <rect x="5" y="2" width="14" height="20" rx="2.5" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 9l5 3-5 3V9z" />
                </svg>
              </div>
              <p className="text-[13px] font-semibold text-zinc-100 tracking-tight">{title}</p>
              <p className="text-[11px] text-zinc-500 max-w-[180px] leading-relaxed">
                9:16 dikey kadrajlama, altyazı güvenli alanı ve kare senkronu
              </p>
            </div>
          )}

          {/* 9:16 Broadcast Safe-Zone & Rule-of-Thirds Kılavuz Katmanı */}
          {showSafeZones && (
            <div className="absolute inset-0 pointer-events-none z-10">
              {/* Üst Sistem / Başlık Güvenli Dışı Alan */}
              <div className="absolute top-0 left-0 right-0 h-12 border-b border-dashed border-teal-400/30 bg-black/20 flex items-end justify-between px-3 pb-1">
                <span className="text-[8px] font-mono text-teal-400/70 uppercase">TOP UI ZONE</span>
                <span className="text-[8px] font-mono text-teal-400/70">1080x1920</span>
              </div>

              {/* Sağ Etkileşim İkon Sütunu (Beğeni / Yorum / Paylaş) */}
              <div className="absolute right-2 top-1/3 bottom-24 w-9 border border-dashed border-teal-400/30 rounded bg-black/25 flex flex-col items-center justify-around py-2">
                <span className="w-3.5 h-3.5 rounded-full border border-teal-400/40" />
                <span className="w-3.5 h-3.5 rounded-full border border-teal-400/40" />
                <span className="w-3.5 h-3.5 rounded-full border border-teal-400/40" />
                <span className="text-[7px] font-mono text-teal-400/70">UI</span>
              </div>

              {/* Merkez Altyazı Güvenli Bölgesi (Subtitle Safe Area) */}
              <div className="absolute left-4 right-13 bottom-24 h-16 border border-teal-400/45 bg-teal-500/5 rounded flex flex-col items-center justify-center px-2">
                <span className="text-[8px] font-mono text-teal-300/80 uppercase tracking-widest">
                  ALTYAZI GÜVENLİ ALANI (SAFE-ZONE)
                </span>
              </div>

              {/* Alt Açıklama & Ses Şeridi Alanı */}
              <div className="absolute bottom-0 left-0 right-0 h-20 border-t border-dashed border-teal-400/30 bg-black/30 flex items-start justify-between px-3 pt-1.5">
                <span className="text-[8px] font-mono text-teal-400/70 uppercase">CAPTION / CTA OVERLAY ZONE</span>
                <span className="text-[8px] font-mono text-emerald-400/80">SAFE</span>
              </div>
            </div>
          )}

          {/* Alt Çizgi (Home Bar) */}
          <div className="absolute bottom-2 left-1/2 -translate-x-1/2 w-24 h-1 bg-white/30 rounded-full z-20 pointer-events-none" />
        </div>
      </div>
    </div>
  )
}

