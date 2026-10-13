/**
 * K-707: Süre Paneli — Zamanlayıcı Olayları, SLA Durum Makinesi ve Sıfır setInterval Testi
 *
 * MİMARİ KURALLAR:
 * 1. Olay Tabanlı Zamanlayıcı: Frontend'de kontrolsüz `setInterval` veya spekülatif sayaç YASAKTIR.
 *    Tek gerçek kaynak (Single Source of Truth) Tauri IPC üzerinden gelen (start, tick, stop, error) olaylarıdır.
 * 2. 15 Dakika SLA Hedefi (900 sn):
 *    - 0 - 719 sn (%0 - %79): 'ON_TRACK' (Normal)
 *    - 720 - 900 sn (%80 - %100): 'WARNING' (Uyarı Eşiği)
 *    - > 900 sn (> 15 dk): 'BREACHED' (SLA İhlali)
 * 3. Vitest Fake Timers: Sahte zamanlayıcılar (vi.useFakeTimers) ile zamansal sıçramalarda
 *    SLA eşiklerinin ve oturum bütünlüğünün korunduğu doğrulanır.
 *
 * Faz 1: Salt Test Kodları (İmplementasyon taslakları Faz 2'de src/lib/timer.ts ve store'a aktarılacaktır)
 */

import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

// ---------------------------------------------------------------------------
// @tauri-apps/api/event Module-Level Mock (Vitest worker timeout koruması)
// ---------------------------------------------------------------------------
vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn().mockResolvedValue(vi.fn()),
}))

import { listen } from '@tauri-apps/api/event'
import {
  type TimerEventPayload,
  calculateSlaStatus,
  createInitialTimerState,
  reduceTimerEvent,
  useTimerStore,
} from '../store/timerStore'
import { TimerPanel } from '../components/timer/TimerPanel'

/**
 * Tauri Event Bridge dinleyicisini test eden yardımcı fonksiyon
 */
export async function listenToTimerEvents(
  handler: (payload: TimerEventPayload) => void
): Promise<() => void> {
  const unlisten = await listen<TimerEventPayload>('hustler:timer', (event) => {
    handler(event.payload)
  })
  return unlisten
}

// ---------------------------------------------------------------------------
// SUITE 1: Tauri IPC Olayları ile Zamanlayıcı Durum Geçişleri (start, tick, stop, error)
// ---------------------------------------------------------------------------
describe('K-707: Tauri IPC Olayları ile Zamanlayıcı Durum Geçişleri', () => {
  it('timer_start: oturumu başlatmalı, durumu RUNNING yapmalı ve SLA durumunu ON_TRACK olarak kurmalı', () => {
    const initial = createInitialTimerState()
    const startEvent: TimerEventPayload = {
      type: 'timer_start',
      sessionId: 'sess_prod_001',
      targetDurationSeconds: 900,
      step: 'TOPIC',
      timestamp: 1710000000000,
    }

    const state = reduceTimerEvent(initial, startEvent)

    expect(state.status).toBe('RUNNING')
    expect(state.sessionId).toBe('sess_prod_001')
    expect(state.elapsedSeconds).toBe(0)
    expect(state.targetDurationSeconds).toBe(900)
    expect(state.remainingSeconds).toBe(900)
    expect(state.slaStatus).toBe('ON_TRACK')
    expect(state.currentStep).toBe('TOPIC')
    expect(state.startedAt).toBe(1710000000000)
    expect(state.stoppedAt).toBeNull()
  })

  it('timer_tick: geçen süreyi ve kalan süreyi IPC payload değerine göre hatasız güncellemeli', () => {
    let state = reduceTimerEvent(createInitialTimerState(), {
      type: 'timer_start',
      sessionId: 'sess_prod_001',
      targetDurationSeconds: 900,
      step: 'TOPIC',
    })

    // 120. saniye tick olayı
    state = reduceTimerEvent(state, {
      type: 'timer_tick',
      sessionId: 'sess_prod_001',
      elapsedSeconds: 120,
      step: 'SCRIPT',
    })

    expect(state.status).toBe('RUNNING')
    expect(state.elapsedSeconds).toBe(120)
    expect(state.remainingSeconds).toBe(780)
    expect(state.currentStep).toBe('SCRIPT')
    expect(state.slaStatus).toBe('ON_TRACK')
  })

  it('farklı bir sessionId taşıyan yetkisiz tick olaylarını yoksaymalı (Oturum Koruması)', () => {
    let state = reduceTimerEvent(createInitialTimerState(), {
      type: 'timer_start',
      sessionId: 'sess_prod_001',
      targetDurationSeconds: 900,
    })

    // Başka bir oturuma ait tick olayı
    const foreignEvent: TimerEventPayload = {
      type: 'timer_tick',
      sessionId: 'sess_attacker_999',
      elapsedSeconds: 500,
    }

    const nextState = reduceTimerEvent(state, foreignEvent)

    // Durum değişmemeli
    expect(nextState.elapsedSeconds).toBe(0)
    expect(nextState.sessionId).toBe('sess_prod_001')
  })

  it('timer_stop (completed): zamanlayıcıyı COMPLETED durumuna geçirmeli ve stoppedAt kaydetmeli', () => {
    let state = reduceTimerEvent(createInitialTimerState(), {
      type: 'timer_start',
      sessionId: 'sess_prod_001',
      targetDurationSeconds: 900,
    })

    state = reduceTimerEvent(state, {
      type: 'timer_stop',
      sessionId: 'sess_prod_001',
      status: 'completed',
      elapsedSeconds: 680,
      timestamp: 1710000680000,
    })

    expect(state.status).toBe('COMPLETED')
    expect(state.elapsedSeconds).toBe(680)
    expect(state.remainingSeconds).toBe(220)
    expect(state.stoppedAt).toBe(1710000680000)
    expect(state.slaStatus).toBe('ON_TRACK')
  })

  it('timer_stop (cancelled): iptal durumunda STOPPED statüsüne geçmeli', () => {
    let state = reduceTimerEvent(createInitialTimerState(), {
      type: 'timer_start',
      sessionId: 'sess_prod_001',
    })

    state = reduceTimerEvent(state, {
      type: 'timer_stop',
      sessionId: 'sess_prod_001',
      status: 'cancelled',
      elapsedSeconds: 45,
    })

    expect(state.status).toBe('STOPPED')
    expect(state.elapsedSeconds).toBe(45)
  })

  it('timer_error: IPC hata mesajını alıp durumu ERROR statüsüne çekmeli', () => {
    let state = reduceTimerEvent(createInitialTimerState(), {
      type: 'timer_start',
      sessionId: 'sess_prod_001',
    })

    state = reduceTimerEvent(state, {
      type: 'timer_error',
      sessionId: 'sess_prod_001',
      error: 'FFMPEG enkoder yanıt vermedi, zamanlayıcı askıya alındı',
    })

    expect(state.status).toBe('ERROR')
    expect(state.errorMessage).toBe('FFMPEG enkoder yanıt vermedi, zamanlayıcı askıya alındı')
  })

  it('listenToTimerEvents: Tauri listen("hustler:timer") komutunu çağırmalı ve unlisten fonksiyonu dönmeli', async () => {
    const unlistenMock = vi.fn()
    const mockListen = listen as ReturnType<typeof vi.fn>
    mockListen.mockResolvedValueOnce(unlistenMock)

    const handler = vi.fn()
    const unlisten = await listenToTimerEvents(handler)

    expect(mockListen).toHaveBeenCalledWith('hustler:timer', expect.any(Function))
    expect(unlisten).toBe(unlistenMock)
  })
})

// ---------------------------------------------------------------------------
// SUITE 2: Vitest Fake Timers ile 15 Dakika (900 sn) SLA Eşik Geçişleri
// ---------------------------------------------------------------------------
describe('K-707: Vitest Fake Timers ile 15 Dakika SLA Durum Makinesi', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('0 ile 719 saniye arasında (%80 altı) SLA durumu ON_TRACK kalmalıdır', () => {
    expect(calculateSlaStatus(0)).toBe('ON_TRACK')
    expect(calculateSlaStatus(300)).toBe('ON_TRACK') // 5. dakika
    expect(calculateSlaStatus(719)).toBe('ON_TRACK') // 11 dk 59 sn
  })

  it('720 ile 900 saniye arasında (%80 - %100 aralığı) SLA durumu WARNING olmalıdır', () => {
    expect(calculateSlaStatus(720)).toBe('WARNING') // Tam 12. dakika (%80)
    expect(calculateSlaStatus(850)).toBe('WARNING') // 14 dk 10 sn
    expect(calculateSlaStatus(900)).toBe('WARNING') // Tam 15. dakika (%100)
  })

  it('901 saniyeden itibaren (> 15 dakika) SLA durumu kesinlikle BREACHED olmalıdır', () => {
    expect(calculateSlaStatus(901)).toBe('BREACHED') // 15 dk 1 sn
    expect(calculateSlaStatus(1200)).toBe('BREACHED') // 20. dakika
  })

  it('vi.advanceTimersByTime ile zaman simüle edildiğinde SLA aşımı hatasız yakalanmalıdır', () => {
    let state = reduceTimerEvent(createInitialTimerState(), {
      type: 'timer_start',
      sessionId: 'sess_sla_test',
      targetDurationSeconds: 900,
    })

    // Simülasyon Adım 1: 10 dakika ilerlet (600 saniye)
    vi.advanceTimersByTime(600 * 1000)
    state = reduceTimerEvent(state, {
      type: 'timer_tick',
      sessionId: 'sess_sla_test',
      elapsedSeconds: 600,
    })
    expect(state.slaStatus).toBe('ON_TRACK')
    expect(state.remainingSeconds).toBe(300)

    // Simülasyon Adım 2: 2 dakika daha ilerlet -> Toplam 12 dakika (720 saniye - Uyarı Eşiği)
    vi.advanceTimersByTime(120 * 1000)
    state = reduceTimerEvent(state, {
      type: 'timer_tick',
      sessionId: 'sess_sla_test',
      elapsedSeconds: 720,
    })
    expect(state.slaStatus).toBe('WARNING')
    expect(state.remainingSeconds).toBe(180)

    // Simülasyon Adım 3: 3 dakika 1 saniye daha ilerlet -> Toplam 15 dakika 1 saniye (901 saniye - İhlal)
    vi.advanceTimersByTime(181 * 1000)
    state = reduceTimerEvent(state, {
      type: 'timer_tick',
      sessionId: 'sess_sla_test',
      elapsedSeconds: 901,
    })
    expect(state.slaStatus).toBe('BREACHED')
    expect(state.remainingSeconds).toBe(0) // Kalan süre sıfıra kilitlenmeli
  })
})

// ---------------------------------------------------------------------------
// SUITE 3: Sıfır setInterval / Event-Driven Güvence Testleri (Runaway Timer Trap)
// ---------------------------------------------------------------------------
describe('K-707: Sıfır setInterval ve Saf Event-Driven Güvencesi', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('zamanlayıcı olayları işlenirken frontend kodunda setInterval KESİNLİKLE çağrılmamalıdır (Runaway Trap)', () => {
    const setIntervalSpy = vi.spyOn(globalThis, 'setInterval')

    let state = createInitialTimerState()

    // Olay akışını simüle et
    state = reduceTimerEvent(state, {
      type: 'timer_start',
      sessionId: 'sess_event_pure',
      targetDurationSeconds: 900,
    })
    state = reduceTimerEvent(state, {
      type: 'timer_tick',
      sessionId: 'sess_event_pure',
      elapsedSeconds: 1,
    })
    state = reduceTimerEvent(state, {
      type: 'timer_stop',
      sessionId: 'sess_event_pure',
      status: 'completed',
    })

    // setInterval kesinlikle tetiklenmemiş olmalı
    expect(setIntervalSpy).not.toHaveBeenCalled()
    setIntervalSpy.mockRestore()
  })

  it('Tauri IPC tick olayı gelmediğinde sahte zaman aksa dahi zamanlayıcı kendi kendine ilerlememelidir (Tek Gerçek Kaynak)', () => {
    let state = reduceTimerEvent(createInitialTimerState(), {
      type: 'timer_start',
      sessionId: 'sess_strict_ipc',
      targetDurationSeconds: 900,
    })

    expect(state.elapsedSeconds).toBe(0)

    // Aradan 500 saniye sahte zaman geçsin ama IPC tick gelmesin
    vi.advanceTimersByTime(500 * 1000)

    // Durum spekülatif olarak ilerlememeli; IPC tick olmadan sayaç donuk kalmalı
    expect(state.elapsedSeconds).toBe(0)
    expect(state.slaStatus).toBe('ON_TRACK')
  })

  it('zamanlayıcı durdurulduktan sonra gelen tick olayları durumu değiştirmemelidir (Durum Kilidi)', () => {
    let state = reduceTimerEvent(createInitialTimerState(), {
      type: 'timer_start',
      sessionId: 'sess_locked',
      targetDurationSeconds: 900,
    })

    state = reduceTimerEvent(state, {
      type: 'timer_stop',
      sessionId: 'sess_locked',
      status: 'completed',
      elapsedSeconds: 400,
    })

    expect(state.status).toBe('COMPLETED')
    expect(state.elapsedSeconds).toBe(400)

    // Durduktan sonra gelen gecikmiş tick olayı
    const lateState = reduceTimerEvent(state, {
      type: 'timer_tick',
      sessionId: 'sess_locked',
      elapsedSeconds: 405,
    })

    // Durum değişmemeli
    expect(lateState.status).toBe('COMPLETED')
    expect(lateState.elapsedSeconds).toBe(400)
  })
})

// ---------------------------------------------------------------------------
// SUITE 4: TimerPanel UI Bileşeni, Renk/Stil Geri Bildirimleri & Sıfır setInterval
// ---------------------------------------------------------------------------
describe('K-707: TimerPanel UI Bileşeni ve Zustand Store Entegrasyonu', () => {
  beforeEach(() => {
    useTimerStore.getState().resetTimer()
    vi.clearAllMocks()
  })

  it('TimerPanel ilk açılışta Hazır durumunda ve ON_TRACK stilinde render edilmelidir', () => {
    const { unmount } = render(React.createElement(TimerPanel))

    expect(screen.getByTestId('timer-panel')).toBeInTheDocument()
    expect(screen.getByTestId('timer-sla-badge')).toHaveTextContent('SLA Hedefinde (15 dk)')
    expect(screen.getByTestId('timer-status-badge')).toHaveTextContent('Hazır')
    expect(screen.getByTestId('timer-elapsed-display')).toHaveTextContent('00:00')
    expect(screen.getByTestId('timer-remaining-display')).toHaveTextContent('15:00')

    unmount()
  })

  it('ON_TRACK durumunda Yeşil/Nötr renkler ve sayaçlar doğru gösterilmelidir', () => {
    useTimerStore.getState().dispatchTimerEvent({
      type: 'timer_start',
      sessionId: 'sess_ui_1',
      targetDurationSeconds: 900,
      step: 'IDEAS',
    })
    useTimerStore.getState().dispatchTimerEvent({
      type: 'timer_tick',
      sessionId: 'sess_ui_1',
      elapsedSeconds: 300,
    })

    const { unmount } = render(React.createElement(TimerPanel))

    const badge = screen.getByTestId('timer-sla-badge')
    expect(badge).toHaveTextContent('SLA Hedefinde (15 dk)')
    expect(badge.className).toContain('text-success')

    expect(screen.getByTestId('timer-elapsed-display')).toHaveTextContent('05:00')
    expect(screen.getByTestId('timer-remaining-display')).toHaveTextContent('10:00')
    expect(screen.getByTestId('timer-step-badge')).toHaveTextContent('Adım: IDEAS')

    unmount()
  })

  it('WARNING (%80 Eşik: 12. dakika) durumunda Sarı uyarı stili uygulanmalıdır', () => {
    useTimerStore.getState().dispatchTimerEvent({
      type: 'timer_start',
      sessionId: 'sess_ui_warn',
      targetDurationSeconds: 900,
    })
    useTimerStore.getState().dispatchTimerEvent({
      type: 'timer_tick',
      sessionId: 'sess_ui_warn',
      elapsedSeconds: 750, // 12 dk 30 sn
    })

    const { unmount } = render(React.createElement(TimerPanel))

    const badge = screen.getByTestId('timer-sla-badge')
    expect(badge).toHaveTextContent('Dikkat: %80 Süre Eşiği Aşıldı')
    expect(badge.className).toContain('text-warning')
    expect(screen.getByTestId('timer-elapsed-display').className).toContain('text-warning')
    expect(screen.getByTestId('timer-elapsed-display')).toHaveTextContent('12:30')

    unmount()
  })

  it('BREACHED (>15 dk) durumunda Kırmızı alarm stili ve ihlal mesajı uygulanmalıdır', () => {
    useTimerStore.getState().dispatchTimerEvent({
      type: 'timer_start',
      sessionId: 'sess_ui_breach',
      targetDurationSeconds: 900,
    })
    useTimerStore.getState().dispatchTimerEvent({
      type: 'timer_tick',
      sessionId: 'sess_ui_breach',
      elapsedSeconds: 935, // 15 dk 35 sn
    })

    const { unmount } = render(React.createElement(TimerPanel))

    const badge = screen.getByTestId('timer-sla-badge')
    expect(badge).toHaveTextContent('SLA İhlali: 15 Dakika Aşıldı!')
    expect(badge.className).toContain('text-destructive')
    expect(screen.getByTestId('timer-elapsed-display').className).toContain('text-destructive')
    expect(screen.getByTestId('timer-elapsed-display')).toHaveTextContent('15:35')
    expect(screen.getByTestId('timer-remaining-display')).toHaveTextContent('00:00')

    unmount()
  })

  it('timer_error olayında hata kutusu görünmeli ve hata metni gösterilmelidir', () => {
    useTimerStore.getState().dispatchTimerEvent({
      type: 'timer_start',
      sessionId: 'sess_ui_err',
    })
    useTimerStore.getState().dispatchTimerEvent({
      type: 'timer_error',
      sessionId: 'sess_ui_err',
      error: 'Ses sentezleme zaman aşımına uğradı',
    })

    const { unmount } = render(React.createElement(TimerPanel))

    expect(screen.getByTestId('timer-error-message')).toBeInTheDocument()
    expect(screen.getByTestId('timer-error-message')).toHaveTextContent('Ses sentezleme zaman aşımına uğradı')
    expect(screen.getByTestId('timer-status-badge')).toHaveTextContent('Hata')

    unmount()
  })

  it('TimerPanel mount edildiğinde setInterval veya setTimeout çağrılmamalıdır (Sıfır Lokal Sayaç)', () => {
    const setIntervalSpy = vi.spyOn(globalThis, 'setInterval')
    const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout')

    const { unmount } = render(React.createElement(TimerPanel))

    expect(setIntervalSpy).not.toHaveBeenCalled()
    expect(setTimeoutSpy).not.toHaveBeenCalled()

    setIntervalSpy.mockRestore()
    setTimeoutSpy.mockRestore()
    unmount()
  })

  it('TimerPanel mount edildiğinde hustler:timer Tauri kanalını dinlemeli ve unmount sırasında temizlemelidir', async () => {
    const mockUnlisten = vi.fn()
    const mockListen = listen as ReturnType<typeof vi.fn>
    mockListen.mockResolvedValueOnce(mockUnlisten)

    const { unmount } = render(React.createElement(TimerPanel))

    expect(mockListen).toHaveBeenCalledWith('hustler:timer', expect.any(Function))

    // Asenkron abonelik promise'inin store üzerinde çözülmesini bekle
    await waitFor(() => {
      expect(mockListen).toHaveBeenCalled()
    })
    await Promise.resolve()
    await Promise.resolve()

    // Unmount edildiğinde unlisten temizliği yapılmalı
    unmount()
    expect(mockUnlisten).toHaveBeenCalled()
  })
})

