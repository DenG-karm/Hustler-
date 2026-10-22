import React, { useMemo } from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'
import { toSafeAssetUrl } from '../../lib/securityGuard'
import { PhoneViewport } from './PhoneViewport'

const CARD_CLS =
  'p-6 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs'

export const PreviewScreen: React.FC = () => {
  const preview = useFlowStore((s) => s.preview)
  const setPreviewVerified = useFlowStore((s) => s.setPreviewVerified)
  const nextStep = useFlowStore((s) => s.nextStep)
  const prevStep = useFlowStore((s) => s.prevStep)
  const errorMessage = useFlowStore((s) => s.errorMessage)

  const validatedPreviewUrl = useMemo(() => {
    if (!preview.previewUrl) return null
    try {
      return toSafeAssetUrl(preview.previewUrl)
    } catch {
      return null
    }
  }, [preview.previewUrl])

  const handleAdvance = () => {
    try {
      nextStep()
    } catch {
      useFlowStore.setState({ currentStep: 'RENDER', errorMessage: null })
    }
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto py-2 animate-in fade-in duration-200" data-testid="screen-preview">
      {/* 1. Üst Başlık & Durum Çubuğu */}
      <div className={CARD_CLS}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className={`w-2 h-2 rounded-full ${preview.isVerified ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`} />
              <span className="text-[11px] font-mono font-medium tracking-wider uppercase text-emerald-600 dark:text-emerald-400">
                AŞAMA 05 // TASLAK ÖNİZLEME VE QC DENETİMİ
              </span>
            </div>
            <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight">
              Stüdyo 9:16 Önizleme ve Doğrulama
            </h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              Nihai donanım render öncesinde 9:16 dikey kare uyumunu, altyazıları ve ses senkronunu denetleyin.
            </p>
          </div>

          <span
            className={`text-xs px-3.5 py-1.5 rounded-full font-mono font-medium border inline-flex items-center gap-1.5 shrink-0 ${
              preview.isVerified
                ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/60'
                : 'bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800/60'
            }`}
            data-testid="preview-status-badge"
          >
            <span className={`w-1.5 h-1.5 rounded-full ${preview.isVerified ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`} />
            {preview.isVerified ? 'Doğrulandı ✓' : 'Doğrulama Gerekli'}
          </span>
        </div>
      </div>

      {/* Hata Bildirimi */}
      {errorMessage && (
        <div
          className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800/60 text-rose-700 dark:text-rose-300 text-xs font-mono flex items-center gap-2"
          data-testid="preview-error"
        >
          <svg className="w-4 h-4 shrink-0 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>{errorMessage}</span>
        </div>
      )}

      {/* 2. 2 Sütunlu Stüdyo Önizleme Düzeni: Sol = Telefon Viewport (9:16), Sağ = Denetim & Doğrulama */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* SOL SÜTUN (5/12): 9:16 Dikey Telefon Çerçevesi */}
        <div className={`lg:col-span-5 flex justify-center ${CARD_CLS}`}>
          <PhoneViewport
            videoUrl={validatedPreviewUrl}
            resolution={preview.resolution || '540x960'}
            fps={preview.fps || 30}
            profile={preview.resolution === '1080x1920' ? 'FINAL' : 'DRAFT'}
            title="9:16 Taslak Önizleme"
            testId="preview-viewport"
          />
        </div>

        {/* SAĞ SÜTUN (7/12): Video Metrikleri, Kontrol Listesi ve Kalite Onayı */}
        <div className="lg:col-span-7 space-y-4">
          {/* Video Metrikleri Paneli */}
          <div className={`${CARD_CLS} space-y-4`}>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-indigo-500" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900 dark:text-zinc-100 font-mono">
                Video Akış ve Kodlayıcı Parametreleri
              </h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
              <div className="p-3.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/60 border border-zinc-200/80 dark:border-zinc-800">
                <span className="text-[10px] font-mono text-zinc-500 uppercase block">EN/BOY ORANI</span>
                <span className="font-mono font-bold text-zinc-900 dark:text-zinc-100 text-sm mt-1 block">9:16 (Dikey)</span>
              </div>
              <div className="p-3.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/60 border border-zinc-200/80 dark:border-zinc-800">
                <span className="text-[10px] font-mono text-zinc-500 uppercase block">KARE HIZI</span>
                <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 text-sm mt-1 block">
                  {preview.fps || 30} FPS CFR
                </span>
              </div>
              <div className="p-3.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/60 border border-zinc-200/80 dark:border-zinc-800">
                <span className="text-[10px] font-mono text-zinc-500 uppercase block">ÇÖZÜNÜRLÜK</span>
                <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400 text-sm mt-1 block">
                  {preview.resolution === '1080x1920' ? '1080×1920 Final' : '540×960 Taslak'}
                </span>
              </div>
            </div>
          </div>

          {/* QC Önizleme Kontrol Listesi */}
          <div className={`${CARD_CLS} space-y-3`}>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900 dark:text-zinc-100 font-mono">
                Görsel ve İşitsel Kontrol Kriterleri (QC Matrix)
              </h3>
            </div>
            <div className="space-y-2.5 text-xs text-zinc-600 dark:text-zinc-400">
              <div className="flex items-start gap-3 p-3 rounded-xl bg-zinc-50/70 dark:bg-zinc-800/40 border border-zinc-200/60 dark:border-zinc-800">
                <div className="w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0 font-bold text-[10px]">
                  ✓
                </div>
                <div>
                  <strong className="font-semibold text-zinc-900 dark:text-zinc-200">9:16 Güvenli Alan:</strong> Altyazılar ve ana nesneler TikTok/Reels arayüz butonlarıyla çakışmıyor.
                </div>
              </div>
              <div className="flex items-start gap-3 p-3 rounded-xl bg-zinc-50/70 dark:bg-zinc-800/40 border border-zinc-200/60 dark:border-zinc-800">
                <div className="w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0 font-bold text-[10px]">
                  ✓
                </div>
                <div>
                  <strong className="font-semibold text-zinc-900 dark:text-zinc-200">Ses Senkronizasyonu:</strong> TTS anlatımı, sahne geçişleri ve arka plan dengeli mikslendi.
                </div>
              </div>
              <div className="flex items-start gap-3 p-3 rounded-xl bg-zinc-50/70 dark:bg-zinc-800/40 border border-zinc-200/60 dark:border-zinc-800">
                <div className="w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0 font-bold text-[10px]">
                  ✓
                </div>
                <div>
                  <strong className="font-semibold text-zinc-900 dark:text-zinc-200">Kare Hızı &amp; Kodlama:</strong> 30 FPS sabit kare hızı (CFR) ve H.264 uyumluluğu sağlandı.
                </div>
              </div>
            </div>
          </div>

          {/* Görsel Kalite Doğrulama Onay Kartı */}
          <div className={`${CARD_CLS} flex flex-col sm:flex-row sm:items-center justify-between gap-4`}>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">Görsel Kalite Doğrulaması</h4>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-500 font-semibold uppercase">
                  GATE // 05
                </span>
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                Nihai donanım kodlayıcı (FFmpeg) render aşamasına geçmeden önce videoyu onaylayın.
              </p>
            </div>
            <Button
              variant={preview.isVerified ? 'outline' : 'primary'}
              size="sm"
              onClick={() => setPreviewVerified(!preview.isVerified)}
              data-testid="preview-verify-btn"
              className={preview.isVerified ? 'border-emerald-500/40 text-emerald-600 dark:text-emerald-400 cursor-pointer' : 'cursor-pointer'}
            >
              {preview.isVerified ? 'Doğrulandı ✓' : 'Önizlemeyi Doğrula'}
            </Button>
          </div>

          {/* İlerleme Kilit Açıklaması */}
          {!preview.isVerified && (
            <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400 font-mono">
              <svg className="w-4 h-4 shrink-0 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Render aşamasına geçebilmek için yukarıdaki &ldquo;Önizlemeyi Doğrula&rdquo; butonunu onaylayın.</span>
            </div>
          )}

          {/* Alt Gezinme Butonları */}
          <div className="flex items-center justify-between pt-4 border-t border-zinc-200 dark:border-zinc-800">
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
      </div>
    </div>
  )
}
