/**
 * Hustler Desktop — Süre Paneli & SLA Durum Yönetimi (K-707)
 *
 * MİMARİ KURAL: OLAY TABANLI ZAMANLAYICI (EVENT-DRIVEN TIMER)
 * Frontend'de asla lokal setInterval veya spekülatif sayaç KULLANILMAZ.
 * Zamanlayıcı durumu sadece Tauri IPC ('hustler:timer') üzerinden gelen
 * start, tick, stop ve error olaylarıyla güncellenir.
 *
 * MİMARİ KURAL: 15 DAKİKA (900 SN) SLA HEDEFİ
 * - ON_TRACK: 0 - 719 sn (%0 - %79)
 * - WARNING: 720 - 900 sn (%80 - %100)
 * - BREACHED: > 900 sn (> 15 dk)
 */

import { create } from 'zustand'
import { listen } from '@tauri-apps/api/event'

export type TimerStatus = 'IDLE' | 'RUNNING' | 'COMPLETED' | 'STOPPED' | 'ERROR'

export type SlaStatus = 'ON_TRACK' | 'WARNING' | 'BREACHED'

export interface TimerEventPayload {
  type: 'timer_start' | 'timer_tick' | 'timer_stop' | 'timer_error'
  sessionId: string
  elapsedSeconds?: number
  targetDurationSeconds?: number
  step?: string
  error?: string
  status?: 'completed' | 'cancelled'
  timestamp?: number
}

export interface TimerStateData {
  sessionId: string | null
  status: TimerStatus
  elapsedSeconds: number
  targetDurationSeconds: number
  remainingSeconds: number
  slaStatus: SlaStatus
  currentStep: string | null
  errorMessage: string | null
  startedAt: number | null
  stoppedAt: number | null
}

export interface TimerStore extends TimerStateData {
  dispatchTimerEvent: (event: TimerEventPayload) => void
  subscribeToTimerBridge: () => Promise<() => void>
  resetTimer: () => void
}

export const SLA_TARGET_SECONDS = 15 * 60 // 900 saniye (15 dakika)
export const SLA_WARNING_RATIO = 0.8 // %80 eşiği (720 saniye)

/**
 * Geçen süreye göre SLA durumunu belirler.
 */
export function calculateSlaStatus(
  elapsedSeconds: number,
  targetDurationSeconds: number = SLA_TARGET_SECONDS
): SlaStatus {
  if (elapsedSeconds > targetDurationSeconds) {
    return 'BREACHED'
  }
  if (elapsedSeconds >= targetDurationSeconds * SLA_WARNING_RATIO) {
    return 'WARNING'
  }
  return 'ON_TRACK'
}

/**
 * Başlangıç boş zamanlayıcı durumunu üretir.
 */
export function createInitialTimerState(): TimerStateData {
  return {
    sessionId: null,
    status: 'IDLE',
    elapsedSeconds: 0,
    targetDurationSeconds: SLA_TARGET_SECONDS,
    remainingSeconds: SLA_TARGET_SECONDS,
    slaStatus: 'ON_TRACK',
    currentStep: null,
    errorMessage: null,
    startedAt: null,
    stoppedAt: null,
  }
}

/**
 * Saf İndirgeyici (Reducer): Gelen olaya göre durumu günceller.
 * Frontend'de setInterval çalıştırılmaz; durum yalnızca bu fonksiyon üzerinden evrilir.
 */
export function reduceTimerEvent(state: TimerStateData, event: TimerEventPayload): TimerStateData {
  switch (event.type) {
    case 'timer_start': {
      const target = event.targetDurationSeconds ?? SLA_TARGET_SECONDS
      return {
        ...state,
        sessionId: event.sessionId,
        status: 'RUNNING',
        elapsedSeconds: 0,
        targetDurationSeconds: target,
        remainingSeconds: target,
        slaStatus: 'ON_TRACK',
        currentStep: event.step ?? 'TOPIC',
        errorMessage: null,
        startedAt: event.timestamp ?? Date.now(),
        stoppedAt: null,
      }
    }

    case 'timer_tick': {
      if (state.status !== 'RUNNING') return state
      if (state.sessionId && event.sessionId !== state.sessionId) return state

      const elapsed = event.elapsedSeconds !== undefined ? event.elapsedSeconds : state.elapsedSeconds + 1
      const remaining = Math.max(0, state.targetDurationSeconds - elapsed)
      const sla = calculateSlaStatus(elapsed, state.targetDurationSeconds)

      return {
        ...state,
        elapsedSeconds: elapsed,
        remainingSeconds: remaining,
        slaStatus: sla,
        currentStep: event.step ?? state.currentStep,
      }
    }

    case 'timer_stop': {
      if (state.sessionId && event.sessionId !== state.sessionId) return state

      const elapsed = event.elapsedSeconds !== undefined ? event.elapsedSeconds : state.elapsedSeconds
      const isCancelled = event.status === 'cancelled'

      return {
        ...state,
        status: isCancelled ? 'STOPPED' : 'COMPLETED',
        elapsedSeconds: elapsed,
        remainingSeconds: Math.max(0, state.targetDurationSeconds - elapsed),
        slaStatus: calculateSlaStatus(elapsed, state.targetDurationSeconds),
        stoppedAt: event.timestamp ?? Date.now(),
      }
    }

    case 'timer_error': {
      if (state.sessionId && event.sessionId !== state.sessionId) return state

      return {
        ...state,
        status: 'ERROR',
        errorMessage: event.error ?? 'Zamanlayıcı sürecinde hata oluştu',
      }
    }

    default:
      return state
  }
}

/**
 * Zustand Zamanlayıcı Deposu (Timer Store)
 */
export const useTimerStore = create<TimerStore>((set, get) => ({
  ...createInitialTimerState(),

  dispatchTimerEvent: (event: TimerEventPayload) => {
    set((state) => reduceTimerEvent(state, event))
  },

  subscribeToTimerBridge: async (): Promise<() => void> => {
    try {
      const unlisten = await listen<TimerEventPayload>('hustler:timer', (evt) => {
        get().dispatchTimerEvent(evt.payload)
      })
      return typeof unlisten === 'function' ? unlisten : () => {}
    } catch {
      // JSDOM veya test ortamı desteği
      return () => {}
    }
  },

  resetTimer: () => {
    set(createInitialTimerState())
  },
}))

/**
 * Süreyi (saniye) MM:SS biçiminde formatlar.
 */
export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}
