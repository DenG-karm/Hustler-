/**
 * Hustler Desktop — Supervisor & Süreç Yönetimi Deposu (K-708)
 *
 * MİMARİ KURALLAR:
 * 1. PENCERE KAPANIŞ VE YETİM SÜREÇ KORUMASI (Orphan Process Cleanup):
 *    Tauri penceresi kapanırken arka plandaki Python sidecar, FFmpeg ve alt işçiler
 *    asılı kalmamalıdır. IPC ('supervisor:terminate_sidecar' & 'supervisor:cleanup_orphans')
 *    ile işletim sistemi düzeyinde sonlandırılır.
 * 2. KRİTİK İŞLERDE KAPANIŞ İPTALİ (Prevent Default):
 *    Aktif bir render, dışa aktarma veya kayıt varken kapanış istenirse, pencere
 *    kapanması iptal edilir (event.preventDefault), süreçler öldürülmez ve kullanıcıya
 *    bilgilendirme Toast'ı sunulur.
 * 3. HATA YÖNETİMİ & ÇÖKME SIFIRLAMASI (Crash Recovery & Reset):
 *    IPC terminate hataları sessizce yutulmaz; Toast ve store error state'ine yansıtılır.
 *    Çöken süreç durum makinesi yeniden başlatma politikası ile kurtarılır veya sıfırlanır.
 */

import { create } from 'zustand'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { useFlowStore } from './flowStore'

// ---------------------------------------------------------------------------
// DOMAIN TİPLERİ VE SÖZLEŞMELER
// ---------------------------------------------------------------------------

export type SupervisorStatus =
  | 'IDLE'
  | 'STARTING'
  | 'RUNNING'
  | 'SHUTTING_DOWN'
  | 'STOPPED'
  | 'CRASHED'
  | 'RECOVERING'

export interface SupervisorState {
  status: SupervisorStatus
  retryCount: number
  maxRetries: number
  activeProcesses: string[]
  isCloseRequested: boolean
  isClosePrevented: boolean
  lastError: string | null
  orphanCleanupDone: boolean
}

export type SupervisorEvent =
  | { type: 'START_REQUESTED' }
  | { type: 'STARTED'; processes: string[] }
  | { type: 'HEARTBEAT_OK' }
  | { type: 'PROCESS_CRASHED'; processName: string; error?: string }
  | { type: 'RECOVERY_ATTEMPTED' }
  | { type: 'RECOVERY_SUCCEEDED' }
  | { type: 'RECOVERY_EXHAUSTED' }
  | { type: 'RESET_STATE' }
  | { type: 'CLOSE_REQUESTED' }
  | { type: 'CLOSE_PREVENTED' }
  | { type: 'CLEANUP_COMPLETED' }

export interface CloseEventContext {
  isPrevented: boolean
  preventDefault: () => void
}

export interface SupervisorStore extends SupervisorState {
  dispatch: (event: SupervisorEvent) => void
  handleCloseRequested: (isBusy: boolean, event: CloseEventContext) => Promise<boolean>
  resetAfterCrash: () => void
  initSupervisorLifecycle: () => Promise<() => void>
}

// ---------------------------------------------------------------------------
// SAF DURUM MAKİNESİ (REDUCER)
// ---------------------------------------------------------------------------

export const DEFAULT_MAX_RETRIES = 3

export function createInitialSupervisorState(maxRetries = DEFAULT_MAX_RETRIES): SupervisorState {
  return {
    status: 'IDLE',
    retryCount: 0,
    maxRetries,
    activeProcesses: [],
    isCloseRequested: false,
    isClosePrevented: false,
    lastError: null,
    orphanCleanupDone: false,
  }
}

export function supervisorReducer(
  state: SupervisorState,
  event: SupervisorEvent
): SupervisorState {
  switch (event.type) {
    case 'START_REQUESTED':
      return {
        ...state,
        status: 'STARTING',
        lastError: null,
      }

    case 'STARTED':
      return {
        ...state,
        status: 'RUNNING',
        activeProcesses: [...event.processes],
        retryCount: 0,
        lastError: null,
        orphanCleanupDone: false,
      }

    case 'HEARTBEAT_OK':
      if (state.status === 'RECOVERING') {
        return {
          ...state,
          status: 'RUNNING',
          retryCount: 0,
          lastError: null,
        }
      }
      return state

    case 'PROCESS_CRASHED': {
      const remaining = state.activeProcesses.filter((p) => p !== event.processName)
      const nextRetryCount = state.retryCount + 1
      const willRecover = nextRetryCount <= state.maxRetries

      return {
        ...state,
        status: willRecover ? 'RECOVERING' : 'CRASHED',
        retryCount: willRecover ? nextRetryCount : state.retryCount,
        activeProcesses: remaining,
        lastError: event.error ?? `${event.processName} beklenmedik şekilde sonlandı`,
      }
    }

    case 'RECOVERY_ATTEMPTED':
      return {
        ...state,
        status: 'RECOVERING',
      }

    case 'RECOVERY_SUCCEEDED':
      return {
        ...state,
        status: 'RUNNING',
        retryCount: 0,
        lastError: null,
      }

    case 'RECOVERY_EXHAUSTED':
      return {
        ...state,
        status: 'CRASHED',
        lastError: 'Maksimum yeniden başlatma sınırına ulaşıldı, kurtarma durduruldu',
      }

    case 'RESET_STATE':
      return createInitialSupervisorState(state.maxRetries)

    case 'CLOSE_REQUESTED':
      return {
        ...state,
        status: 'SHUTTING_DOWN',
        isCloseRequested: true,
        isClosePrevented: false,
      }

    case 'CLOSE_PREVENTED':
      return {
        ...state,
        status: 'RUNNING',
        isCloseRequested: false,
        isClosePrevented: true,
      }

    case 'CLEANUP_COMPLETED':
      return {
        ...state,
        status: 'STOPPED',
        activeProcesses: [],
        orphanCleanupDone: true,
      }

    default:
      return state
  }
}

// ---------------------------------------------------------------------------
// GERÇEK İŞLEM / MEŞGULİYET KONTROLÜ (isBusyCheck)
// ---------------------------------------------------------------------------

/**
 * useFlowStore üzerindeki aktif render, dosya kaydetme veya yükleme durumunu sorgular.
 */
export function isFlowBusy(): boolean {
  try {
    const flow = useFlowStore.getState()
    const isRendering =
      flow.render?.status === 'RENDERING' || flow.render?.status === 'PENDING'
    const isSaving = Boolean(flow.script?.isSaving)
    const isLoading = Boolean(flow.isLoading)

    return isRendering || isSaving || isLoading
  } catch {
    return false
  }
}

// ---------------------------------------------------------------------------
// ZUSTAND SUPERVISOR DEPOSU
// ---------------------------------------------------------------------------

export const useSupervisorStore = create<SupervisorStore>((set, get) => ({
  ...createInitialSupervisorState(),

  dispatch: (event: SupervisorEvent) => {
    set((state) => supervisorReducer(state, event))
  },

  handleCloseRequested: async (isBusy: boolean, event: CloseEventContext): Promise<boolean> => {
    const { dispatch } = get()

    if (isBusy) {
      // Kritik iş devam ediyor: Kapanışı iptal et ve kullanıcıyı uyar
      event.preventDefault()
      dispatch({ type: 'CLOSE_PREVENTED' })

      try {
        useFlowStore.getState().addToast({
          title: 'Kapanış Engellendi',
          message: 'Aktif bir render veya işlem devam ederken uygulama kapatılamaz.',
          code: 'CLOSE_PREVENTED_BUSY',
          status: 409,
        })
      } catch {
        // Test/JSDOM koruması
      }

      return false
    }

    // Kapanışa izin verildi: Nazikçe kapatma ve yetim temizliği başlat
    dispatch({ type: 'CLOSE_REQUESTED' })

    try {
      const activeProcesses = get().activeProcesses

      // 1. Alt süreçleri sonlandırma sinyalini IPC üzerinden gönder
      await invoke('supervisor:terminate_sidecar', {
        processes: activeProcesses,
      })

      // 2. Yetim kalan alt süreçleri temizle
      await invoke('supervisor:cleanup_orphans')

      dispatch({ type: 'CLEANUP_COMPLETED' })
      return true
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      dispatch({
        type: 'PROCESS_CRASHED',
        processName: 'supervisor_cleanup',
        error: `Kapanış temizliği başarısız: ${errorMsg}`,
      })

      try {
        useFlowStore.getState().addToast({
          title: 'Yetim Süreç Temizleme Hatası',
          message: `Alt süreçler kapatılırken hata oluştu: ${errorMsg}`,
          code: 'SUPERVISOR_CLEANUP_ERROR',
          status: 500,
        })
      } catch {
        // Test koruması
      }

      throw err
    }
  },

  resetAfterCrash: () => {
    get().dispatch({ type: 'RESET_STATE' })
  },

  initSupervisorLifecycle: async (): Promise<() => void> => {
    try {
      const currentWindow = getCurrentWindow()
      if (!currentWindow || typeof currentWindow.onCloseRequested !== 'function') {
        return () => {}
      }

      const unlisten = await currentWindow.onCloseRequested(
        async (tauriEvent: { preventDefault: () => void }) => {
          const isBusy = isFlowBusy()
          const ctx: CloseEventContext = {
            isPrevented: false,
            preventDefault: () => {
              ctx.isPrevented = true
              tauriEvent.preventDefault()
            },
          }
          await get().handleCloseRequested(isBusy, ctx)
        }
      )

      return unlisten
    } catch {
      // JSDOM / Test ortamı fallback
      return () => {}
    }
  },
}))
