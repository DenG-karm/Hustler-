/**
 * K-708: Supervisor Modülü — Yeniden Başlatma Politikası, Kapanış ve Yetim Temizliği
 *
 * MİMARİ KURALLAR:
 * 1. Pencere Kapanış Olayı (Close-Requested):
 *    Tauri pencere kapanış olayı yakalandığında alt süreçlerin (Python sidecar, FFmpeg, arka plan işçileri)
 *    asılı kalmasını (orphan process) önlemek için IPC üzerinden sonlandırma sinyalleri tetiklenir.
 * 2. Kapanış İptali (Prevent Default & isFlowBusy):
 *    Devam eden kritik bir render veya kullanıcı işlemi sırasında (useFlowStore) event.preventDefault()
 *    çağrılır, süreç sonlandırma sinyali gönderilmez, Toast ile kullanıcı uyarılır ve durum makinesi RUNNING kalır.
 * 3. Hata Yönetimi & Çökme Sıfırlama Politikası (Crash Recovery & State Reset):
 *    IPC terminate hataları yakalanır ve Toast ile bildirilir. Sidecar çöktüğünde yeniden başlatma
 *    politikası (Max Retries & Backoff) çalıştırılır, resetAfterCrash ile IDLE durumuna sıfırlanır.
 *
 * FAZ 2: Store Entegrasyonu ve Kök Bağlantı Testleri
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

// ---------------------------------------------------------------------------
// Module-level Mocks: @tauri-apps/api/core & @tauri-apps/api/window
// ---------------------------------------------------------------------------
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: vi.fn(),
}))

import { invoke } from '@tauri-apps/api/core'
import { getCurrentWindow } from '@tauri-apps/api/window'
import {
  type CloseEventContext,
  createInitialSupervisorState,
  supervisorReducer,
  useSupervisorStore,
  isFlowBusy,
} from '../store/supervisorStore'
import { useFlowStore } from '../store/flowStore'

// ===========================================================================
// TEST SUITES
// ===========================================================================

describe('K-708: Supervisor Modülü — Store Entegrasyonu, Kapanış ve Çökme Testleri', () => {
  const mockInvoke = invoke as ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    mockInvoke.mockResolvedValue(undefined)
    useSupervisorStore.getState().resetAfterCrash()
    useFlowStore.getState().resetFlow()
  })

  // -------------------------------------------------------------------------
  // SUITE 1: Tauri Pencere Kapanışında Alt Süreçleri Sonlandırma ve Yetim Temizliği
  // -------------------------------------------------------------------------
  describe('1. Pencere Kapanışında Alt Süreçleri Sonlandırma (Graceful Shutdown & Orphan Cleanup)', () => {
    it('pencere kapanışı onaylandığında supervisor:terminate_sidecar ve supervisor:cleanup_orphans IPC çağrılarını yapmalıdır', async () => {
      const store = useSupervisorStore.getState()
      store.dispatch({ type: 'STARTED', processes: ['python_sidecar', 'ffmpeg_worker'] })

      expect(useSupervisorStore.getState().status).toBe('RUNNING')
      expect(useSupervisorStore.getState().activeProcesses).toEqual(['python_sidecar', 'ffmpeg_worker'])

      const closeEvent: CloseEventContext = {
        isPrevented: false,
        preventDefault: vi.fn(),
      }

      // isBusy = false (kritik iş yok, kapanış serbest)
      const allowed = await store.handleCloseRequested(false, closeEvent)

      expect(allowed).toBe(true)
      expect(closeEvent.preventDefault).not.toHaveBeenCalled()

      // IPC sonlandırma ve yetim temizliği çağrıları
      expect(mockInvoke).toHaveBeenCalledWith('supervisor:terminate_sidecar', {
        processes: ['python_sidecar', 'ffmpeg_worker'],
      })
      expect(mockInvoke).toHaveBeenCalledWith('supervisor:cleanup_orphans')

      // Son durum: STOPPED, aktif süreçler boş, yetim temizliği tamamlandı
      const state = useSupervisorStore.getState()
      expect(state.status).toBe('STOPPED')
      expect(state.activeProcesses).toEqual([])
      expect(state.orphanCleanupDone).toBe(true)
      expect(state.isCloseRequested).toBe(true)
    })

    it('IPC sonlandırma çağrısı reddedildiğinde hata sessizce yutulmamalı, PROCESS_CRASHED ve Toast bildirimine yansımalıdır', async () => {
      mockInvoke.mockRejectedValueOnce(new Error('Rust Job Object: Süreç sonlandırılamadı (EPERM)'))

      const store = useSupervisorStore.getState()
      store.dispatch({ type: 'STARTED', processes: ['python_sidecar'] })

      const closeEvent: CloseEventContext = {
        isPrevented: false,
        preventDefault: vi.fn(),
      }

      await expect(store.handleCloseRequested(false, closeEvent)).rejects.toThrow(
        'Rust Job Object: Süreç sonlandırılamadı (EPERM)'
      )

      // Store durumu hatayı yansıtmalı
      const state = useSupervisorStore.getState()
      expect(state.lastError).toContain('Kapanış temizliği başarısız')

      // useFlowStore toasts listesinde hata toast'ı olmalı
      const toasts = useFlowStore.getState().toasts
      expect(toasts.some((t) => t.code === 'SUPERVISOR_CLEANUP_ERROR' && t.status === 500)).toBe(true)
    })
  })

  // -------------------------------------------------------------------------
  // SUITE 2: Gerçek isFlowBusy Bağlantısı ve Kapanış İptali (Prevent Default)
  // -------------------------------------------------------------------------
  describe('2. Gerçek isFlowBusy Bağlantısı ve Kapanış İptali (Prevent Default)', () => {
    it('useFlowStore içinde aktif render sürerken isFlowBusy true dönmeli, kapanış engellenmeli ve Toast gösterilmelidir', async () => {
      // FlowStore render durumuna alınıyor
      useFlowStore.setState({
        render: {
          jobId: 'job_active_render_77',
          profile: 'FINAL',
          status: 'RENDERING',
          progress: 45,
          outputPath: null,
          error: null,
        },
      })

      expect(isFlowBusy()).toBe(true)

      const store = useSupervisorStore.getState()
      store.dispatch({ type: 'STARTED', processes: ['python_sidecar', 'ffmpeg_worker'] })

      const closeEvent: CloseEventContext = {
        isPrevented: false,
        preventDefault: vi.fn(() => {
          closeEvent.isPrevented = true
        }),
      }

      const allowed = await store.handleCloseRequested(isFlowBusy(), closeEvent)

      // Kapanış engellenmeli
      expect(allowed).toBe(false)
      expect(closeEvent.preventDefault).toHaveBeenCalledTimes(1)
      expect(closeEvent.isPrevented).toBe(true)

      // Asla terminate IPC çağrısı yapılmamalıdır
      expect(mockInvoke).not.toHaveBeenCalled()

      // Durum RUNNING kalmalı
      const state = useSupervisorStore.getState()
      expect(state.status).toBe('RUNNING')
      expect(state.activeProcesses).toEqual(['python_sidecar', 'ffmpeg_worker'])
      expect(state.isClosePrevented).toBe(true)

      // Toast eklenmiş olmalı
      const toasts = useFlowStore.getState().toasts
      expect(toasts.some((t) => t.code === 'CLOSE_PREVENTED_BUSY' && t.status === 409)).toBe(true)
    })

    it('useFlowStore içinde genel yükleme (isLoading: true) sürerken isFlowBusy true dönmelidir', () => {
      useFlowStore.setState({ isLoading: true })
      expect(isFlowBusy()).toBe(true)

      useFlowStore.setState({ isLoading: false })
      expect(isFlowBusy()).toBe(false)
    })

    it('useFlowStore içinde senaryo kaydı (isSaving: true) sürerken isFlowBusy true dönmelidir', () => {
      useFlowStore.setState({
        script: {
          id: 'sc_1',
          title: 'Test',
          hook: 'Test Hook',
          fullText: 'Text',
          scenes: [],
          claims: [],
          isApproved: false,
          isSaving: true,
        },
      })
      expect(isFlowBusy()).toBe(true)
    })
  })

  // -------------------------------------------------------------------------
  // SUITE 3: Yaşam Döngüsü (initSupervisorLifecycle & onCloseRequested)
  // -------------------------------------------------------------------------
  describe('3. Yaşam Döngüsü ve Tauri getCurrentWindow().onCloseRequested Bağlantısı', () => {
    it('initSupervisorLifecycle: onCloseRequested dinleyicisini bağlamalı ve unlisten fonksiyonu dönmelidir', async () => {
      const mockUnlisten = vi.fn()
      let registeredHandler: ((evt: { preventDefault: () => void }) => Promise<void>) | null = null

      const mockWindow = {
        onCloseRequested: vi.fn().mockImplementation((handler) => {
          registeredHandler = handler
          return Promise.resolve(mockUnlisten)
        }),
      }

      const mockGetCurrentWindow = getCurrentWindow as ReturnType<typeof vi.fn>
      mockGetCurrentWindow.mockReturnValueOnce(mockWindow)

      const store = useSupervisorStore.getState()
      store.dispatch({ type: 'STARTED', processes: ['python_sidecar'] })

      const unlisten = await store.initSupervisorLifecycle()

      expect(mockWindow.onCloseRequested).toHaveBeenCalledTimes(1)
      expect(registeredHandler).not.toBeNull()

      // Simüle Tauri Close Event (Boşta iken kapanış)
      const preventDefaultSpy = vi.fn()
      if (typeof registeredHandler === 'function') {
        const handlerFn = registeredHandler as (evt: { preventDefault: () => void }) => Promise<void>
        await handlerFn({ preventDefault: preventDefaultSpy })
      }

      expect(preventDefaultSpy).not.toHaveBeenCalled()
      expect(mockInvoke).toHaveBeenCalledWith('supervisor:terminate_sidecar', {
        processes: ['python_sidecar'],
      })
      expect(useSupervisorStore.getState().status).toBe('STOPPED')

      // Unlisten temizliği
      unlisten()
      expect(mockUnlisten).toHaveBeenCalledTimes(1)
    })

    it('Tauri window bulunamadığında initSupervisorLifecycle hata vermeden boş unlisten dönmelidir', async () => {
      const mockGetCurrentWindow = getCurrentWindow as ReturnType<typeof vi.fn>
      mockGetCurrentWindow.mockReturnValueOnce(null)

      const store = useSupervisorStore.getState()
      const unlisten = await store.initSupervisorLifecycle()

      expect(typeof unlisten).toBe('function')
      expect(() => unlisten()).not.toThrow()
    })
  })

  // -------------------------------------------------------------------------
  // SUITE 4: Durum Makinesinin Çökmelerde Kendini Sıfırlaması (Crash Recovery & Reset)
  // -------------------------------------------------------------------------
  describe('4. Durum Makinesinin Çökmelerde ve Yeniden Başlatma Politikasında Sıfırlanması', () => {
    it('alt süreç çöktüğünde RECOVERING durumuna geçmeli ve retryCount artmalıdır', () => {
      let state = createInitialSupervisorState(3)
      state = supervisorReducer(state, { type: 'STARTED', processes: ['python_sidecar'] })

      expect(state.status).toBe('RUNNING')
      expect(state.retryCount).toBe(0)

      // 1. Çökme
      state = supervisorReducer(state, {
        type: 'PROCESS_CRASHED',
        processName: 'python_sidecar',
        error: 'Exit code 137 (OOM Killed)',
      })

      expect(state.status).toBe('RECOVERING')
      expect(state.retryCount).toBe(1)
      expect(state.lastError).toBe('Exit code 137 (OOM Killed)')
      expect(state.activeProcesses).not.toContain('python_sidecar')
    })

    it('kurtarma başarılı olduğunda (HEARTBEAT_OK) durum RUNNING olmalı ve retryCount sıfırlanmalıdır', () => {
      let state = createInitialSupervisorState(3)
      state = supervisorReducer(state, { type: 'STARTED', processes: ['python_sidecar'] })
      state = supervisorReducer(state, {
        type: 'PROCESS_CRASHED',
        processName: 'python_sidecar',
      })

      expect(state.status).toBe('RECOVERING')
      expect(state.retryCount).toBe(1)

      state = supervisorReducer(state, { type: 'HEARTBEAT_OK' })

      expect(state.status).toBe('RUNNING')
      expect(state.retryCount).toBe(0)
      expect(state.lastError).toBeNull()
    })

    it('maksimum yeniden başlatma sayısı (maxRetries) aşıldığında CRASHED durumuna kilitlenmelidir', () => {
      let state = createInitialSupervisorState(2)
      state = supervisorReducer(state, { type: 'STARTED', processes: ['python_sidecar'] })

      state = supervisorReducer(state, { type: 'PROCESS_CRASHED', processName: 'python_sidecar' })
      expect(state.status).toBe('RECOVERING')
      expect(state.retryCount).toBe(1)

      state = supervisorReducer(state, { type: 'PROCESS_CRASHED', processName: 'python_sidecar' })
      expect(state.status).toBe('RECOVERING')
      expect(state.retryCount).toBe(2)

      state = supervisorReducer(state, { type: 'PROCESS_CRASHED', processName: 'python_sidecar' })
      expect(state.status).toBe('CRASHED')
      expect(state.retryCount).toBe(2)
    })

    it('resetAfterCrash metodu çökmüş store durumunu temiz IDLE durumuna sıfırlamalıdır', () => {
      const store = useSupervisorStore.getState()
      store.dispatch({ type: 'STARTED', processes: ['python_sidecar'] })

      store.dispatch({ type: 'PROCESS_CRASHED', processName: 'python_sidecar', error: 'Fatal segfault' })
      store.dispatch({ type: 'PROCESS_CRASHED', processName: 'python_sidecar', error: 'Fatal segfault' })
      store.dispatch({ type: 'PROCESS_CRASHED', processName: 'python_sidecar', error: 'Fatal segfault' })
      store.dispatch({ type: 'PROCESS_CRASHED', processName: 'python_sidecar', error: 'Fatal segfault' })

      expect(useSupervisorStore.getState().status).toBe('CRASHED')
      expect(useSupervisorStore.getState().lastError).toBe('Fatal segfault')

      // Sıfırla
      useSupervisorStore.getState().resetAfterCrash()

      const resetState = useSupervisorStore.getState()
      expect(resetState.status).toBe('IDLE')
      expect(resetState.retryCount).toBe(0)
      expect(resetState.activeProcesses).toEqual([])
      expect(resetState.lastError).toBeNull()
      expect(resetState.isCloseRequested).toBe(false)
      expect(resetState.isClosePrevented).toBe(false)
      expect(resetState.orphanCleanupDone).toBe(false)
    })
  })
})
