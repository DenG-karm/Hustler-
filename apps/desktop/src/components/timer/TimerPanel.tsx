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
      badge: 'bg-success/10 text-success border-success/20',
      border: 'border-border/80',
      text: 'text-emerald-600 dark:text-emerald-400',
      label: 'SLA Hedefinde (15 dk)',
      bar: 'bg-emerald-400',
    },
    WARNING: {
      badge: 'bg-warning/15 text-warning border-warning/35 animate-pulse',
      border: 'border-warning/35 bg-warning/5',
      text: 'text-warning',
      label: 'Dikkat: %80 Süre Eşiği Aşıldı',
      bar: 'bg-warning',
    },
    BREACHED: {
      badge: 'bg-destructive/15 text-destructive border-destructive/35 font-semibold',
      border: 'border-destructive/45 bg-destructive/5',
      text: 'text-destructive',
      label: 'SLA İhlali: 15 Dakika Aşıldı!',
      bar: 'bg-destructive',
    },
  }

  const currentSla = slaStyles[slaStatus]

  return (
    <div
      className={`px-4 py-2 rounded-xl border bg-white dark:bg-zinc-900 shadow-2xs transition-colors ${currentSla.border}`}
      data-testid="timer-panel"
    >
      <div className="flex flex-wrap items-center justify-between gap-sm">
        {/* SOL: Başlık & SLA Durum Rozeti */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5">
            <svg
              className="w-3.5 h-3.5 text-teal-500 dark:text-teal-400 shrink-0"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.75}
              aria-hidden="true"
            >
              <circle cx="12" cy="13" r="8" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4l2.5 2.5M9 2h6" />
            </svg>
            <span className="text-[11px] font-mono font-medium text-zinc-700 dark:text-zinc-200 tracking-wide uppercase">
              TIMECODE // SLA
            </span>
          </div>

          <span
            className={`text-[10px] px-2 py-0.5 rounded font-mono font-medium border ${currentSla.badge}`}
            data-testid="timer-sla-badge"
          >
            {currentSla.label}
          </span>
        </div>

        {/* ORTA: Dijital Timecode Göstergesi (Geçen / Kalan / Hedef) + Lineer SLA Barı */}
        <div className="flex items-center gap-3 flex-1 max-w-xl mx-auto justify-center">
          <div className="flex items-center gap-3 px-2.5 py-1 rounded-md bg-zinc-100 dark:bg-zinc-900 border border-border/80 font-mono text-xs">
            <div className="flex items-baseline gap-1.5">
              <span className="text-[9px] uppercase text-zinc-500">GEÇEN</span>
              <span
                className={`text-xs font-mono font-semibold ${currentSla.text}`}
                data-testid="timer-elapsed-display"
              >
                {formatDuration(elapsedSeconds)}
              </span>
            </div>

            <span className="text-zinc-700">/</span>

            <div className="flex items-baseline gap-1.5">
              <span className="text-[9px] uppercase text-zinc-500">KALAN</span>
              <span
                className="text-xs font-mono font-semibold text-zinc-900 dark:text-zinc-100"
                data-testid="timer-remaining-display"
              >
                {formatDuration(remainingSeconds)}
              </span>
            </div>

            <span className="text-zinc-700">/</span>

            <div className="flex items-baseline gap-1.5">
              <span className="text-[9px] uppercase text-zinc-500">HEDEF</span>
              <span
                className="text-xs font-mono font-medium text-zinc-500"
                data-testid="timer-target-display"
              >
                {formatDuration(targetDurationSeconds)}
              </span>
            </div>
          </div>

          {/* Kompakt 15 Dakika İlerleme Çubuğu */}
          <div className="hidden sm:flex flex-col flex-1 min-w-[140px] max-w-[210px] gap-1">
            <div className="flex justify-between text-[9px] text-zinc-500 font-mono leading-none">
              <span>%0</span>
              <span>%80 Uyarı (12 dk)</span>
              <span>%100 Hedef (15 dk)</span>
            </div>
            <div
              className="w-full h-1.5 rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden relative"
              data-testid="timer-progress-track"
            >
              {/* %80 Uyarı Çizgisi */}
              <div className="absolute left-[80%] top-0 bottom-0 w-0.5 bg-warning/70 z-10" />
              {/* İlerleme Dolgusu */}
              <div
                className={`h-full transition-all duration-300 ${currentSla.bar}`}
                style={{ width: `${progressRatio}%` }}
                data-testid="timer-progress-fill"
              />
            </div>
          </div>
        </div>

        {/* SAĞ: Aktif Adım & Durum Rozeti */}
        <div className="flex items-center gap-1.5 text-[11px]">
          {currentStep && (
            <span
              className="px-2 py-0.5 rounded bg-zinc-200/70 dark:bg-zinc-800/70 text-zinc-600 dark:text-zinc-300 font-mono text-[10px]"
              data-testid="timer-step-badge"
            >
              Adım: {currentStep}
            </span>
          )}

          <span
            className={`px-2 py-0.5 rounded font-mono text-[10px] font-medium border ${
              status === 'RUNNING'
                ? 'bg-teal-500/15 text-teal-600 dark:text-teal-300 border-teal-500/25'
                : status === 'COMPLETED'
                ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/25'
                : status === 'STOPPED'
                ? 'bg-zinc-200/70 dark:bg-zinc-800/70 text-zinc-500 border-border/80'
                : status === 'ERROR'
                ? 'bg-destructive/15 text-destructive border-destructive/30'
                : 'bg-zinc-200/70 dark:bg-zinc-800/70 text-zinc-500 border-border/80'
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

      {/* Hata Bildirimi */}
      {status === 'ERROR' && errorMessage && (
        <div
          className="mt-1.5 px-2 py-1 rounded bg-destructive/10 border border-destructive/30 text-destructive text-[11px] font-mono"
          data-testid="timer-error-message"
        >
          Hata: {errorMessage}
        </div>
      )}
    </div>
  )
}
