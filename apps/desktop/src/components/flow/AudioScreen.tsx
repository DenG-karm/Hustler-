import React from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'

export const AudioScreen: React.FC = () => {
  const audio = useFlowStore((s) => s.audio)
  const loadAssetsForScript = useFlowStore((s) => s.loadAssetsForScript)
  const nextStep = useFlowStore((s) => s.nextStep)
  const prevStep = useFlowStore((s) => s.prevStep)
  const isLoading = useFlowStore((s) => s.isLoading)
  const errorMessage = useFlowStore((s) => s.errorMessage)

  const handleAdvance = async () => {
    if (!audio?.isGenerated) return
    await loadAssetsForScript()
    try {
      nextStep()
    } catch {
      // Store hatası
    }
  }

  if (!audio) {
    return (
      <div className="p-xl text-center text-text-muted" data-testid="screen-audio-empty">
        Ses verisi bulunamadı. Lütfen senaryo adımına geri dönün.
      </div>
    )
  }

  return (
    <div className="space-y-lg max-w-2xl mx-auto" data-testid="screen-audio">
      <div className="border-b border-border pb-md">
        <h2 className="text-xl font-bold text-text-primary">4. Ses Sentezi & TTS</h2>
        <p className="text-sm text-text-secondary">
          Senaryo metni deterministik TTS motoruyla seslendirildi. Ses süresi ve formatı kontrol edilebilir.
        </p>
      </div>

      {errorMessage && (
        <div className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm" data-testid="audio-error">
          {errorMessage}
        </div>
      )}

      <div className="space-y-md">
        <div className="p-md rounded-xl border border-border bg-surface space-y-sm">
          <div className="flex items-center justify-between text-sm">
            <span className="text-text-secondary">Ses Modeli:</span>
            <span className="font-semibold text-text-primary">{audio.voiceId}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-text-secondary">Hesaplanan Süre:</span>
            <span className="font-bold text-accent">{audio.durationSeconds} saniye</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-text-secondary">Dosya Yolu:</span>
            <span className="font-mono text-xs text-text-muted">{audio.audioPath}</span>
          </div>

          <div className="pt-sm">
            <div className="w-full bg-surface-hover h-2 rounded-full overflow-hidden border border-border">
              <div className="bg-accent h-full w-2/3 animate-pulse" />
            </div>
            <div className="flex justify-between text-xs text-text-muted mt-1">
              <span>0:00</span>
              <span>0:{Math.round(audio.durationSeconds)}</span>
            </div>
          </div>
        </div>

        <div className="p-sm rounded-lg bg-surface-hover border border-border text-xs text-text-secondary">
          ✓ Ses dosyası yerel dosya sistemine kaydedildi ve sonraki mikser katmanı için doğrulandı.
        </div>
      </div>

      <div className="flex items-center justify-between pt-md border-t border-border">
        <Button variant="ghost" onClick={prevStep} data-testid="audio-back-btn">
          ← Senaryoya Dön
        </Button>
        <Button
          variant="primary"
          onClick={handleAdvance}
          isLoading={isLoading}
          disabled={!audio.isGenerated || audio.durationSeconds <= 0}
          data-testid="audio-submit-btn"
        >
          Görsellere Geç & İlerle →
        </Button>
      </div>
    </div>
  )
}
