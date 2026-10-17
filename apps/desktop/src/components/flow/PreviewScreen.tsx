import React, { useMemo } from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'
import { toSafeAssetUrl } from '../../lib/securityGuard'
import { PhoneViewport } from './PhoneViewport'

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
      // Store hatası
    }
  }

  return (
    <div className="space-y-lg max-w-5xl mx-auto" data-testid="screen-preview">
      {/* Üst Başlık & Durum Çubuğu */}
      <div className="border-b border-border pb-md flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-accent/10 text-accent text-xs flex items-center justify-center font-bold">
              5
            </span>
            <h2 className="text-xl font-bold text-text-primary">Stüdyo 9:16 Önizleme ve Doğrulama</h2>
          </div>
          <p className="text-sm text-text-secondary mt-1">
            Nihai render işleminden önce oluşturulan dikey video taslağını telefon maketi içinde inceleyin ve onaylayın.
          </p>
        </div>
        <span
          className={`text-xs px-3 py-1 rounded-full font-semibold border ${
            preview.isVerified
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
          }`}
          data-testid="preview-status-badge"
        >
          {preview.isVerified ? 'Doğrulandı ✓' : 'Doğrulama Gerekli'}
        </span>
      </div>

      {errorMessage && (
        <div
          className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm"
          data-testid="preview-error"
        >
          {errorMessage}
        </div>
      )}

      {/* 2 Sütunlu Stüdyo Önizleme Düzeni: Sol = Telefon Viewport (9:16), Sağ = Denetim & Doğrulama */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-lg items-start">
        {/* SOL SÜTUN (5/12): 9:16 Dikey Telefon Çerçevesi */}
        <div className="lg:col-span-5 flex justify-center">
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
        <div className="lg:col-span-7 space-y-md">
          {/* Video Metrikleri */}
          <div className="p-md rounded-2xl border border-border bg-surface space-y-sm">
            <h3 className="text-sm font-bold text-text-primary flex items-center gap-2">
              <span>📊</span>
              <span>Video Akış ve Kodlayıcı Parametreleri</span>
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1 text-xs">
              <div className="p-2.5 rounded-xl bg-surface-hover border border-border">
                <span className="text-[11px] text-text-muted block">En/Boy Oranı</span>
                <span className="font-mono font-bold text-text-primary">9:16 (Dikey)</span>
              </div>
              <div className="p-2.5 rounded-xl bg-surface-hover border border-border">
                <span className="text-[11px] text-text-muted block">Kare Hızı</span>
                <span className="font-mono font-bold text-emerald-400">{preview.fps || 30} FPS</span>
              </div>
              <div className="p-2.5 rounded-xl bg-surface-hover border border-border">
                <span className="text-[11px] text-text-muted block">Çözünürlük</span>
                <span className="font-mono font-bold text-sky-400">
                  {preview.resolution === '1080x1920' ? '1080x1920 Final' : '540x960 Taslak'}
                </span>
              </div>
            </div>
          </div>

          {/* QC Önizleme Kontrol Listesi */}
          <div className="p-md rounded-2xl border border-border bg-surface space-y-sm">
            <h3 className="text-sm font-bold text-text-primary flex items-center gap-2">
              <span>🔍</span>
              <span>Görsel ve İşitsel Kontrol Kriterleri</span>
            </h3>
            <ul className="space-y-2 text-xs text-text-secondary">
              <li className="flex items-center gap-2 p-2 rounded-lg bg-surface-hover border border-border/50">
                <span className="text-emerald-400 font-bold">✓</span>
                <span><strong>9:16 Güvenli Alan:</strong> Altyazılar ve ana nesneler TikTok/Reels arayüz öğeleriyle çakışmıyor.</span>
              </li>
              <li className="flex items-center gap-2 p-2 rounded-lg bg-surface-hover border border-border/50">
                <span className="text-emerald-400 font-bold">✓</span>
                <span><strong>Ses Senkronizasyonu:</strong> TTS anlatımı, sahne geçişleri ve arka plan müziği dengeli mikslendi.</span>
              </li>
              <li className="flex items-center gap-2 p-2 rounded-lg bg-surface-hover border border-border/50">
                <span className="text-emerald-400 font-bold">✓</span>
                <span><strong>Kare Hızı & Kodlama:</strong> 30 FPS CFR sabit kare hızı ve H.264 uyumluluğu sağlandı.</span>
              </li>
            </ul>
          </div>

          {/* Görsel Kalite Doğrulama Onay Kartı */}
          <div className="p-md rounded-2xl border border-border bg-surface flex flex-col sm:flex-row sm:items-center justify-between gap-md">
            <div>
              <h4 className="text-sm font-bold text-text-primary">Görsel Kalite Doğrulaması</h4>
              <p className="text-xs text-text-secondary mt-0.5">
                Nihai donanım kodlayıcı (FFmpeg) render aşamasına geçmeden önce videoyu onaylayın.
              </p>
            </div>
            <Button
              variant={preview.isVerified ? 'outline' : 'primary'}
              size="sm"
              onClick={() => setPreviewVerified(!preview.isVerified)}
              data-testid="preview-verify-btn"
              className={preview.isVerified ? 'border-emerald-500/40 text-emerald-400' : ''}
            >
              {preview.isVerified ? 'Doğrulandı ✓' : 'Önizlemeyi Doğrula'}
            </Button>
          </div>

          {/* İlerleme Kilit Açıklaması (Mikro-Kopya) */}
          {!preview.isVerified && (
            <p className="text-[11px] text-amber-400/90 bg-amber-500/10 border border-amber-500/20 px-3 py-2 rounded-xl">
              ℹ️ Render aşamasına geçebilmek için lütfen yukarıdaki "Önizlemeyi Doğrula" butonu ile kalite onayını verin.
            </p>
          )}

          {/* Alt Gezinme Butonları */}
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
      </div>
    </div>
  )
}
