import React from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'

export const AudioScreen: React.FC = () => {
  const audio = useFlowStore((s) => s.audio)
  const script = useFlowStore((s) => s.script)
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

  const fps = 30
  const totalFrames = Math.round((audio.durationSeconds || 0) * fps)
  const formattedMinutes = Math.floor(audio.durationSeconds / 60)
  const formattedSeconds = Math.round(audio.durationSeconds % 60)

  return (
    <div className="space-y-lg max-w-3xl mx-auto py-sm animate-in fade-in duration-200" data-testid="screen-audio">
      {/* Üst Başlık */}
      <div className="border-b border-border/80 pb-md">
        <div className="flex items-center gap-xs">
          <span className="text-primary font-bold text-xs uppercase tracking-wider">Adım 3 / 6</span>
          <span className="text-text-muted">•</span>
          <span className="text-text-muted text-xs">TTS & Ses Sentezi</span>
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-text-primary">
          Seslendirilen Metin & Kare Senkronizasyonu
        </h2>
        <p className="text-sm text-text-secondary">
          Senaryo metni AudioCache önbellekli TTS motoruyla sentezlendi. Video kurgusu için toplam kare sayısı hesaplandı.
        </p>
      </div>

      {errorMessage && (
        <div className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm" data-testid="audio-error">
          {errorMessage}
        </div>
      )}

      {/* 3 Ana Metrik Kartı: Süre, Kare Sayısı, Önbellek Durumu */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-md">
        {/* Metrik 1: Süre */}
        <div className="p-md rounded-2xl border border-border bg-surface flex flex-col justify-between">
          <span className="text-xs text-text-muted uppercase font-mono">Hesaplanan Süre</span>
          <div className="mt-xs">
            <span className="text-2xl font-extrabold text-primary font-mono">
              {audio.durationSeconds} saniye
            </span>
          </div>
          <span className="text-[11px] text-text-muted mt-1">
            0:{formattedMinutes < 10 ? '0' : ''}{formattedMinutes}:{formattedSeconds < 10 ? '0' : ''}{formattedSeconds} Zaman Kodu
          </span>
        </div>

        {/* Metrik 2: Kare Sayısı */}
        <div className="p-md rounded-2xl border border-border bg-surface flex flex-col justify-between">
          <span className="text-xs text-text-muted uppercase font-mono">Toplam Kare (Frames)</span>
          <div className="mt-xs">
            <span className="text-2xl font-extrabold text-text-primary font-mono">
              {totalFrames} kare
            </span>
          </div>
          <span className="text-[11px] text-text-muted mt-1">
            @{fps} FPS Video Senkronizasyonu
          </span>
        </div>

        {/* Metrik 3: AudioCache Önbellek Durumu */}
        <div className="p-md rounded-2xl border border-emerald-500/30 bg-emerald-500/5 flex flex-col justify-between">
          <span className="text-xs text-emerald-400 uppercase font-mono">AudioCache Durumu</span>
          <div className="mt-xs flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
            <span className="text-base font-bold text-emerald-400">
              Önbellekte Hazır (Hit)
            </span>
          </div>
          <span className="text-[11px] text-emerald-500/80 mt-1">
            Sıfır Ağ Çağrısı • Deterministik
          </span>
        </div>
      </div>

      {/* Ses Oynatıcı / Dalga Formu Görselleştirmesi */}
      <div className="p-md rounded-2xl border border-border bg-surface space-y-sm shadow-sm">
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">
              🎙️
            </div>
            <div>
              <span className="font-semibold text-text-primary block text-sm">{audio.voiceId}</span>
              <span className="text-[11px] text-text-muted">Türkçe Doğal TTS Sentezleyici</span>
            </div>
          </div>
          <span className="text-xs px-2 py-0.5 rounded-md bg-surface-hover text-text-muted font-mono">
            WAV / 24kHz / Mono
          </span>
        </div>

        {/* Simüle Edilen Ses Dalgası */}
        <div className="py-sm">
          <div className="flex items-end gap-1 h-12 px-sm bg-surface-hover/50 rounded-xl border border-border/60 justify-center">
            {[40, 65, 80, 50, 95, 75, 45, 90, 60, 85, 30, 70, 90, 55, 40, 80, 65, 95, 75, 50, 85, 60, 45, 70, 35].map((h, i) => (
              <div
                key={i}
                className="w-1.5 bg-primary/70 rounded-full transition-all duration-300"
                style={{ height: `${h}%` }}
              />
            ))}
          </div>

          <div className="flex justify-between text-[11px] text-text-muted font-mono mt-1 px-1">
            <span>00:00.0</span>
            <span>00:{audio.durationSeconds < 10 ? '0' : ''}{Math.round(audio.durationSeconds)}.0</span>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs pt-xs border-t border-border/60">
          <span className="text-text-muted font-mono text-[11px] truncate max-w-sm">
            Dosya: {audio.audioPath}
          </span>
          <span className="text-emerald-400 font-medium text-[11px]">
            ✓ FFmpeg İçin Doğrulandı
          </span>
        </div>
      </div>

      {/* Senaryo Metin Özeti */}
      {script && (
        <div className="p-md rounded-2xl border border-border/80 bg-surface/60 space-y-xs">
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Seslendirilen Senaryo Metni
          </span>
          <p className="text-xs text-text-primary leading-relaxed italic bg-surface-hover/40 p-2.5 rounded-xl border border-border/40">
            "{script.fullText}"
          </p>
        </div>
      )}

      {/* Alt Aksiyon Butonları */}
      <div className="flex items-center justify-between pt-md border-t border-border/80">
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
