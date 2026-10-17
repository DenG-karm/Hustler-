/**
 * Hustler Desktop — Akış Ekranları Durum Makinesi (K-702 & K-703)
 * Modüler Dilim Patterni: discoverySlice, scriptSlice, renderSlice orkestrasyonu.
 */

import { create } from 'zustand'
import {
  FLOW_STEPS,
  InvalidStateTransitionError,
  checkStepValidation,
  createInitialAssetsData,
  createInitialPreviewData,
  createInitialRenderData,
  type FlowStep,
  type FlowState,
} from './flowTypes'
import { createDiscoverySlice } from './slices/discoverySlice'
import { createScriptSlice } from './slices/scriptSlice'
import { createRenderSlice } from './slices/renderSlice'
import { getIpcClient } from '../lib/ipc'
import { getEventBridge, type HustlerEvent, type ConnectionStatePayload } from '../lib/events'
import { parseProblemDetails, type UIError } from '../lib/problemDetails'

export * from './flowTypes'

export const useFlowStore = create<FlowState>()((set, get, api) => ({
  ...createDiscoverySlice(set, get, api),
  ...createScriptSlice(set, get, api),
  ...createRenderSlice(set, get, api),

  currentStep: 'TOPIC',
  isLoading: false,
  errorMessage: null,

  connectionState: 'connecting',
  reconnectAttempt: 0,
  activeModalError: null,
  toasts: [],

  validateCurrentStep: () => checkStepValidation(get(), get().currentStep),
  isStepValid: (step: FlowStep) => checkStepValidation(get(), step),
  canProceed: () => checkStepValidation(get(), get().currentStep).valid,

  nextStep: () => {
    const { currentStep } = get()
    const currentIndex = FLOW_STEPS.indexOf(currentStep)
    if (currentIndex >= FLOW_STEPS.length - 1) return

    const validation = checkStepValidation(get(), currentStep)
    const nextStepName = FLOW_STEPS[currentIndex + 1]
    if (!validation.valid) {
      const error = new InvalidStateTransitionError(currentStep, nextStepName, validation.reason || 'Adım doğrulanamadı')
      set({ errorMessage: error.message })
      throw error
    }
    set({ currentStep: nextStepName, errorMessage: null })
  },

  prevStep: () => {
    const { currentStep } = get()
    const currentIndex = FLOW_STEPS.indexOf(currentStep)
    if (currentIndex <= 0) return
    set({ currentStep: FLOW_STEPS[currentIndex - 1], errorMessage: null })
  },

  goToStep: (targetStep: FlowStep) => {
    const { currentStep } = get()
    const currentIndex = FLOW_STEPS.indexOf(currentStep)
    const targetIndex = FLOW_STEPS.indexOf(targetStep)
    if (targetIndex === currentIndex) return
    if (targetIndex < currentIndex) {
      set({ currentStep: targetStep, errorMessage: null })
      return
    }

    for (let i = 0; i < targetIndex; i++) {
      const stepToCheck = FLOW_STEPS[i]
      const stepValidation = checkStepValidation(get(), stepToCheck)
      if (!stepValidation.valid) {
        const error = new InvalidStateTransitionError(
          currentStep,
          targetStep,
          `Önceki '${stepToCheck}' adımı tamamlanmadan '${targetStep}' adımına atlanamaz: ${stepValidation.reason}`
        )
        set({ errorMessage: error.message })
        throw error
      }
    }
    set({ currentStep: targetStep, errorMessage: null })
  },

  resetFlow: () => {
    set({
      currentStep: 'TOPIC',
      isLoading: false,
      errorMessage: null,
      connectionState: 'connecting',
      reconnectAttempt: 0,
      activeModalError: null,
      toasts: [],
      topic: '',
      ideas: [],
      selectedIdea: null,
      script: null,
      audio: null,
      assets: createInitialAssetsData(),
      preview: createInitialPreviewData(),
      render: createInitialRenderData(),
    })
  },

  addToast: (toast: Partial<UIError> & { title: string; message: string }) => {
    const timestamp = Date.now()
    const newToast: UIError = {
      id: toast.id || `toast_${timestamp}_${Math.random().toString(36).substring(2, 7)}`,
      mode: toast.mode || 'toast',
      title: toast.title,
      message: toast.message,
      code: toast.code || 'NOTIFICATION',
      status: toast.status ?? 200,
      instance: toast.instance,
      timestamp,
      actionLabel: toast.actionLabel,
      onAction: toast.onAction,
    }
    set((state) => ({ toasts: [...state.toasts, newToast] }))
  },

  dismissToast: (id: string) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
  },

  dismissModalError: () => {
    set({ activeModalError: null })
  },

  setConnectionState: (connectionState: ConnectionStatePayload['state'], reconnectAttempt = 0) => {
    set({ connectionState, reconnectAttempt })
  },

  subscribeEvents: async () => {
    const bridge = getEventBridge()

    const [unlistenEvent, unlistenConnection] = await Promise.all([
      bridge.onEvent((event: HustlerEvent) => {
        const currentState = get()
        if (event.type === 'job_progress') {
          const evt = event as any
          if (!currentState.render.jobId || currentState.render.jobId === evt.job_id) {
            set((s) => ({
              render: {
                ...s.render,
                jobId: evt.job_id,
                progress: typeof evt.progress === 'number' ? evt.progress : s.render.progress,
                status: 'RENDERING',
                stepName: evt.step ?? s.render.stepName,
                encoder: evt.encoder ?? s.render.encoder,
              },
            }))
          }
        } else if (event.type === 'job_completed') {
          const evt = event as any
          if (!currentState.render.jobId || currentState.render.jobId === evt.job_id) {
            set((s) => ({
              render: {
                ...s.render,
                progress: 100,
                status: 'COMPLETED',
                outputPath: evt.output_path ?? s.render.outputPath,
                encoder: evt.encoder ?? s.render.encoder,
              },
            }))
          }
        } else if (event.type === 'job_cancelled') {
          const evt = event as any
          if (!currentState.render.jobId || currentState.render.jobId === evt.job_id) {
            set((s) => ({ render: { ...s.render, status: 'CANCELLED' } }))
          }
        } else if (event.type === 'job_failed') {
          const evt = event as any
          const uiError = parseProblemDetails(evt.error)
          if (uiError.mode === 'modal') {
            set((s) => ({ activeModalError: uiError, render: { ...s.render, status: 'FAILED', error: uiError.message }, errorMessage: uiError.message }))
          } else {
            set((s) => ({ toasts: [...s.toasts, uiError], render: { ...s.render, status: 'FAILED', error: uiError.message }, errorMessage: uiError.message }))
          }
        } else if (event.type === 'llm_loop_warning') {
          const evt = event as any
          const warningToast: UIError = {
            id: `warn_${Date.now()}`,
            mode: 'toast',
            title: 'LLM Döngü Uyarısı',
            message: evt.message || 'LLM döngü limiti uyarısı alındı.',
            code: 'LLM_LOOP_WARNING',
            status: 200,
            timestamp: Date.now(),
          }
          set((s) => ({ toasts: [...s.toasts, warningToast] }))
        }
      }),
      bridge.onConnectionState((statePayload: ConnectionStatePayload) => {
        set({ connectionState: statePayload.state, reconnectAttempt: statePayload.attempt ?? 0 })
      }),
    ])

    // Tauri setup() aşamasında yayınlanan ilk hustler:connection_state olayı Webview yüklenmeden
    // önce kaçırılmış olabileceği için aktif /health yoklaması ile bağlantıyı doğrula.
    try {
      const client = getIpcClient()
      const healthResp = await client.proxyRequest('GET', '/health')
      if (healthResp && healthResp.status === 200 && get().connectionState === 'connecting') {
        set({ connectionState: 'connected', reconnectAttempt: 0 })
      }
    } catch {
      // Sidecar henüz hazır değilse ColdStartSplash veya SSE köprüsü durumu güncelleyecektir
    }

    return () => {
      unlistenEvent()
      unlistenConnection()
    }
  },

  rehydrateFromBackend: async () => {
    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.getActiveSession()
      if (resp.status >= 400 || !resp.body) {
        set({ isLoading: false })
        return false
      }
      if (get().connectionState === 'connecting') {
        set({ connectionState: 'connected', reconnectAttempt: 0 })
      }

      const session = resp.body.session
      if (!session) {
        set({ isLoading: false })
        return false
      }

      const payload = (session.state_payload || {}) as Record<string, any>
      const candidateStep = (session.checkpoint_step || session.current_step || 'TOPIC') as FlowStep
      const targetStep = (FLOW_STEPS as readonly string[]).includes(candidateStep) ? candidateStep : 'TOPIC'

      const wasRecovered = session.status === 'RECOVERED' || session.status === 'RUNNING' || session.status === 'RENDERING'

      let renderState = payload.render ?? createInitialRenderData()
      if (wasRecovered && (renderState.status === 'RENDERING' || renderState.status === 'PENDING')) {
        renderState = {
          ...renderState,
          status: 'CANCELLED',
          error: 'Önceki oturum kesintiye uğradı, son kararlı adıma dönüldü.',
        }
      }

      set({
        topic: session.topic || payload.topic || '',
        ideas: payload.ideas ?? [],
        selectedIdea: payload.selectedIdea ?? null,
        script: payload.script ?? null,
        audio: payload.audio ?? null,
        assets: payload.assets ?? createInitialAssetsData(),
        preview: payload.preview ?? createInitialPreviewData(),
        render: renderState,
        currentStep: targetStep,
        isLoading: false,
        errorMessage: null,
      })

      if (wasRecovered) {
        get().addToast({
          title: 'Kurtarıldı (Rehydrated)',
          message: `Kesintiye uğrayan oturum son kararlı adım olan '${targetStep}' aşamasına başarıyla geri yüklendi.`,
          mode: 'toast',
        })
      }

      return true
    } catch (err: any) {
      const uiError = parseProblemDetails(err)
      set({ isLoading: false, errorMessage: uiError.message })
      return false
    }
  },

  persistSessionToBackend: async () => {
    const s = get()
    try {
      const client = getIpcClient()
      const { topic, currentStep, ideas, selectedIdea, script, audio, assets, preview, render } = s
      await client.saveActiveSession({
        id: script?.id ? `session_${script.id}` : 'session_active',
        topic,
        current_step: currentStep,
        checkpoint_step: currentStep,
        status: 'IDLE',
        state_payload: { topic, ideas, selectedIdea, script, audio, assets, preview, render },
      })
    } catch {
      // ignore
    }
  },
}))
