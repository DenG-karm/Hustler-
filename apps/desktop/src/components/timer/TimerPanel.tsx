/**
 * Hustler Desktop — Süre Paneli & 15 Dk SLA İzleme Bileşeni (K-707)
 *
 * MİMARİ KURAL: KESİNLİKLE SETINTERVAL / SETTIMEOUT KULLANILMAZ.
 * Zaman akışı tamamen Tauri IPC ('hustler:timer') olaylarından beslenir.
 * SLA Durumları:
 * - ON_TRACK: Yeşil / Nötr (%80 altı)
 * - WARNING: Sarı (%80 - %100 arası)
 * - BREACHED: Kırmızı (> 15 dakika)
 */

import React, { useEffect } from 'react'
import {
  useTimerStore,
  formatDuration,
  type SlaStatus,
} from '../../store/timerStore'

export const TimerPanel: React.FC = () => {
  const elapsedSeconds = useTimerStore((s) => s.elapsedSeconds)
  const remainingSeconds = useTimerStore((s) => s.remainingSeconds)
  const targetDurationSeconds = useTimerStore((s) => s.targetDurationSeconds)
  const status = useTimerStore((s) => s.status)
  const slaStatus = useTimerStore((s) => s.slaStatus)
  const currentStep = useTimerStore((s) => s.currentStep)
  const errorMessage = useTimerStore((s) => s.errorMessage)
  const subscribeToTimerBridge = useTimerStore((s) => s.subscribeToTimerBridge)

  // Tauri Event Bridge aboneliği (Tek Gerçek Kaynak: Olay akışı)
  // KESİNLİKLE LOKAL SETINTERVAL ÇALIŞTIRILMAZ.
  useEffect(() => {
    let active = true
    let unlisten: (() => void) | null = null

    subscribeToTimerBridge().then((fn) => {
      if (typeof fn === 'function') {
        if (!active) {
          fn()
        } else {
          unlisten = fn
        }
      }
    })

    return () => {
      active = false
      if (typeof unlisten === 'function') {
        unlisten()
      }
    }
  }, [subscribeToTimerBridge])

  // İlerleme yüzdesi (%0 - %100)
  const progressRatio = Math.min(100, Math.round((elapsedSeconds / targetDurationSeconds) * 100))

  // SLA Durum Renkleri & Metinleri
  const slaStyles: Record<SlaStatus, { badge: string; border: string; text: string; label: string; bar: string }> = {
    ON_TRACK: {
      badge: 'bg-success/15 text-success border-success/30',
      border: 'border-border hover:border-success/30',
      text: 'text-success',
      label: 'SLA Hedefinde (15 dk)',
      bar: 'bg-success',
    },
    WARNING: {
      badge: 'bg-warning/20 text-warning border-warning/40 animate-pulse',
      border: 'border-warning/40 bg-warning/5',
      text: 'text-warning',
      label: 'Dikkat: %80 Süre Eşiği Aşıldı',
      bar: 'bg-warning',
    },
    BREACHED: {
      badge: 'bg-destructive/20 text-destructive border-destructive/40 font-bold',
      border: 'border-destructive/50 bg-destructive/5',
      text: 'text-destructive',
      label: 'SLA İhlali: 15 Dakika Aşıldı!',
      bar: 'bg-destructive',
    },
  }

  const currentSla = slaStyles[slaStatus]

  return (
    <div
      className={`p-md rounded-xl border bg-surface transition-all shadow-sm ${currentSla.border}`}
      data-testid="timer-panel"
    >
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-sm mb-xs">
        {/* Başlık ve SLA Durum Rozeti */}
        <div className="flex items-center gap-sm">
          <div className="flex items-center gap-xs">
            <span className="text-base" role="img" aria-label="Kronometre">⏱️</span>
            <span className="text-xs font-bold text-text-primary tracking-tight uppercase">
              Üretim Kronometresi
            </span>
          </div>

          <span
            className={`text-[10px] px-sm py-0.5 rounded-full font-semibold border ${currentSla.badge}`}
            data-testid="timer-sla-badge"
          >
            {currentSla.label}
          </span>
        </div>

        {/* Durum Rozeti & Adım */}
        <div className="flex items-center gap-xs text-[11px]">
          {currentStep && (
            <span
              className="px-xs py-0.5 rounded bg-surface-hover text-text-muted font-mono"
              data-testid="timer-step-badge"
            >
              Adım: {currentStep}
            </span>
          )}

          <span
            className={`px-sm py-0.5 rounded font-mono font-medium ${
              status === 'RUNNING'
                ? 'bg-accent/15 text-accent'
                : status === 'COMPLETED'
                ? 'bg-success/15 text-success'
                : status === 'STOPPED'
                ? 'bg-surface-hover text-text-muted'
                : status === 'ERROR'
                ? 'bg-destructive/15 text-destructive'
                : 'bg-surface-hover text-text-muted'
            }`}
            data-testid="timer-status-badge"
          >
            {status === 'RUNNING'
              ? 'Çalışıyor'
              : status === 'COMPLETED'
              ? 'Tamamlandı ✓'
              : status === 'STOPPED'
              ? 'Durduruldu'
              : status === 'ERROR'
              ? 'Hata'
              : 'Hazır'}
          </span>
        </div>
      </div>

      {/* Süre Sayacı Göstergesi */}
      <div className="grid grid-cols-3 gap-xs py-xs text-center border-y border-border-subtle my-xs">
        <div>
          <span className="text-[10px] text-text-muted block">Geçen Süre</span>
          <span
            className={`text-lg font-mono font-bold ${currentSla.text}`}
            data-testid="timer-elapsed-display"
          >
            {formatDuration(elapsedSeconds)}
          </span>
        </div>

        <div>
          <span className="text-[10px] text-text-muted block">Kalan Süre</span>
          <span
            className="text-lg font-mono font-bold text-text-primary"
            data-testid="timer-remaining-display"
          >
            {formatDuration(remainingSeconds)}
          </span>
        </div>

        <div>
          <span className="text-[10px] text-text-muted block">Hedef (SLA)</span>
          <span
            className="text-lg font-mono font-bold text-text-muted"
            data-testid="timer-target-display"
          >
            {formatDuration(targetDurationSeconds)}
          </span>
        </div>
      </div>

      {/* 15 Dakika İlerleme Çubuğu */}
      <div className="space-y-1 pt-xs">
        <div className="flex justify-between text-[10px] text-text-muted font-mono">
          <span>%0</span>
          <span>%80 Uyarı (12 dk)</span>
          <span>%100 Hedef (15 dk)</span>
        </div>

        <div
          className="w-full h-2 rounded-full bg-surface-hover overflow-hidden border border-border-subtle relative"
          data-testid="timer-progress-track"
        >
          {/* %80 Uyarı Çizgisi */}
          <div className="absolute left-[80%] top-0 bottom-0 w-0.5 bg-warning/50 z-10" />

          {/* İlerleme Dolgusu */}
          <div
            className={`h-full transition-all duration-300 ${currentSla.bar}`}
            style={{ width: `${progressRatio}%` }}
            data-testid="timer-progress-fill"
          />
        </div>
      </div>

      {/* Hata Bildirimi */}
      {status === 'ERROR' && errorMessage && (
        <div
          className="mt-xs p-xs rounded bg-destructive/10 border border-destructive/20 text-destructive text-xs"
          data-testid="timer-error-message"
        >
          Hata: {errorMessage}
        </div>
      )}
    </div>
  )
}
