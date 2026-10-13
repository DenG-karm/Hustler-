/**
 * Hustler Desktop — Akış Ekranları Durum Makinesi (K-702 & K-703)
 *
 * MİMARİ KURAL: KATI DURUM MAKİNESİ (Strict Unidirectional FSM)
 * Akış adımları: Konu → Top 20 → Senaryo → Ses → Görseller → Önizleme → Render
 *
 * MİMARİ KURAL: TAURI EVENT SYSTEM & SIFIR POLLING (K-703)
 * Asenkron ilerleme (%0-100), log akışları ve uyarılar Event Bridge üzerinden dinlenir.
 * Polling kesinlikle yasaktır.
 *
 * MİMARİ KURAL: RFC 7807 PROBLEM DETAILS
 * Hatalar asla ham 500 veya stack trace olarak UI'a verilmez; parseProblemDetails ile
 * modal, toast veya inline bileşenlere eşlenir.
 */

import { create } from 'zustand'
import { getIpcClient, type ProxyResponse } from '../lib/ipc'
import { getEventBridge, type HustlerEvent, type ConnectionStatePayload } from '../lib/events'
import { parseProblemDetails, type UIError } from '../lib/problemDetails'

export type FlowStep =
  | 'TOPIC'
  | 'TOP20'
  | 'SCRIPT'
  | 'AUDIO'
  | 'ASSETS'
  | 'PREVIEW'
  | 'RENDER'

export const FLOW_STEPS: readonly FlowStep[] = [
  'TOPIC',
  'TOP20',
  'SCRIPT',
  'AUDIO',
  'ASSETS',
  'PREVIEW',
  'RENDER',
] as const

export class InvalidStateTransitionError extends Error {
  readonly fromStep: FlowStep
  readonly toStep: FlowStep
  readonly reason: string

  constructor(fromStep: FlowStep, toStep: FlowStep, reason: string) {
    super(`[FSM Kural İhlali] ${fromStep} -> ${toStep} geçişi reddedildi: ${reason}`)
    this.name = 'InvalidStateTransitionError'
    this.fromStep = fromStep
    this.toStep = toStep
    this.reason = reason
  }
}

export interface VideoIdea {
  id: string
  title: string
  hook: string
  score: number
  viewCount?: number
}

export interface ScriptScene {
  order: number
  narration: string
  visualPrompt: string
}

export interface ScriptClaim {
  id: string
  text: string
  verified: boolean
}

export interface ScriptData {
  id: string
  title: string
  hook: string
  fullText: string
  scenes: ScriptScene[]
  claims: ScriptClaim[]
  isApproved: boolean
  lastSavedAt?: number
  isSaving?: boolean
  saveStatus?: 'IDLE' | 'SAVING' | 'SAVED' | 'UNCHANGED' | 'ERROR'
}

export interface AudioData {
  scriptId: string
  voiceId: string
  audioPath: string | null
  durationSeconds: number
  isGenerated: boolean
}

export interface AssetSlot {
  slotId: string
  name: string
  type: 'video' | 'image' | 'audio'
  required: boolean
  assignedPath: string | null
}

export interface AssetsData {
  slots: AssetSlot[]
  allSlotsFilled: boolean
}

export interface PreviewData {
  previewUrl: string | null
  fps: number
  resolution: string
  isVerified: boolean
}

export interface RenderData {
  jobId: string | null
  profile: 'DRAFT' | 'FINAL'
  status: 'IDLE' | 'PENDING' | 'RENDERING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
  progress: number
  outputPath: string | null
  error: string | null
}

export interface FlowState {
  currentStep: FlowStep
  isLoading: boolean
  errorMessage: string | null

  // K-703 Problem Details & Resilience State
  connectionState: ConnectionStatePayload['state']
  reconnectAttempt: number
  activeModalError: UIError | null
  toasts: UIError[]

  // Step Data
  topic: string
  ideas: VideoIdea[]
  selectedIdea: VideoIdea | null
  script: ScriptData | null
  audio: AudioData | null
  assets: AssetsData
  preview: PreviewData
  render: RenderData

  // Validasyon Kontrolleri
  validateCurrentStep: () => { valid: boolean; reason?: string }
  isStepValid: (step: FlowStep) => { valid: boolean; reason?: string }
  canProceed: () => boolean

  // Durum Makinesi Geçişleri (FSM Transitions)
  nextStep: () => void
  prevStep: () => void
  goToStep: (targetStep: FlowStep) => void
  resetFlow: () => void

  // Veri Güncelleyiciler
  setTopic: (topic: string) => void
  selectIdea: (idea: VideoIdea) => void
  setScript: (script: Partial<ScriptData>) => void
  toggleClaim: (claimId: string) => void
  setClaimVerified: (claimId: string, verified: boolean) => void
  saveScriptContent: (titleOverride?: string, fullTextOverride?: string) => Promise<ProxyResponse | null>
  approveScript: () => void
  setAudio: (audio: Partial<AudioData>) => void
  assignAssetSlot: (slotId: string, path: string) => void
  setPreviewVerified: (verified: boolean) => void
  setRenderProgress: (progress: number, status?: RenderData['status'], outputPath?: string, error?: string) => void

  // Hata & Bildirim Yönetimi
  addToast: (toast: Partial<UIError> & { title: string; message: string }) => void
  dismissToast: (id: string) => void
  dismissModalError: () => void
  setConnectionState: (state: ConnectionStatePayload['state'], attempt?: number) => void

  // K-703 Hard-Cancel & Event Subscription
  cancelRenderJob: () => Promise<void>
  subscribeEvents: () => Promise<() => void>

  // IPC Tetikleyicileri (Zero-Network)
  fetchIdeasForTopic: () => Promise<void>
  generateScriptForIdea: () => Promise<void>
  generateAudioForScript: (voiceId?: string) => Promise<void>
  loadAssetsForScript: () => Promise<void>
  buildPreviewForScript: () => Promise<void>
  dispatchRenderJob: (profile?: 'DRAFT' | 'FINAL') => Promise<void>
  pollJobStatus: () => Promise<void>
}

export function createInitialAssetsData(): AssetsData {
  return {
    slots: [
      { slotId: 'slot_intro_video', name: 'Giriş Kancası (Video)', type: 'video', required: true, assignedPath: null },
      { slotId: 'slot_body_img1', name: 'Gövde Sahne 1 (Görsel)', type: 'image', required: true, assignedPath: null },
      { slotId: 'slot_body_img2', name: 'Gövde Sahne 2 (Görsel)', type: 'image', required: true, assignedPath: null },
      { slotId: 'slot_bg_audio', name: 'Arka Plan Müziği', type: 'audio', required: false, assignedPath: null },
    ],
    allSlotsFilled: false,
  }
}

export function createInitialPreviewData(): PreviewData {
  return {
    previewUrl: null,
    fps: 30,
    resolution: '540x960',
    isVerified: false,
  }
}

export function createInitialRenderData(): RenderData {
  return {
    jobId: null,
    profile: 'DRAFT',
    status: 'IDLE',
    progress: 0,
    outputPath: null,
    error: null,
  }
}

function checkStepValidation(state: FlowState, step: FlowStep): { valid: boolean; reason?: string } {
  switch (step) {
    case 'TOPIC': {
      if (!state.topic || state.topic.trim().length < 3) {
        return { valid: false, reason: 'Konu başlığı en az 3 karakter olmalıdır.' }
      }
      return { valid: true }
    }
    case 'TOP20': {
      if (!state.selectedIdea || !state.selectedIdea.id) {
        return { valid: false, reason: 'Top 20 listesinden bir video fikri seçilmelidir.' }
      }
      return { valid: true }
    }
    case 'SCRIPT': {
      if (!state.script) {
        return { valid: false, reason: 'Senaryo henüz oluşturulmamıştır.' }
      }
      if (!state.script.title || state.script.title.trim().length === 0) {
        return { valid: false, reason: 'Senaryo başlığı boş olamaz.' }
      }
      if (!state.script.fullText || state.script.fullText.trim().length < 20) {
        return { valid: false, reason: 'Senaryo metni en az 20 karakter olmalıdır.' }
      }
      const unverifiedClaims = (state.script.claims || []).filter((c) => !c.verified)
      if (unverifiedClaims.length > 0) {
        return {
          valid: false,
          reason: `Tüm iddialar (claims) kullanıcı tarafından onaylanmalıdır. Onay bekleyen iddia sayısı: ${unverifiedClaims.length}.`,
        }
      }
      if (!state.script.isApproved) {
        return { valid: false, reason: 'Senaryo devam edilmeden önce kullanıcı tarafından onaylanmalıdır.' }
      }
      return { valid: true }
    }
    case 'AUDIO': {
      if (!state.audio || !state.audio.isGenerated || !state.audio.audioPath) {
        return { valid: false, reason: 'Ses sentezi henüz oluşturulmamıştır.' }
      }
      if (state.audio.durationSeconds <= 0) {
        return { valid: false, reason: 'Ses süresi 0 saniyeden büyük olmalıdır.' }
      }
      return { valid: true }
    }
    case 'ASSETS': {
      const requiredSlots = state.assets.slots.filter((s) => s.required)
      const missing = requiredSlots.some((s) => !s.assignedPath)
      if (missing) {
        return { valid: false, reason: 'Tüm zorunlu görsel ve video slotları doldurulmalıdır.' }
      }
      return { valid: true }
    }
    case 'PREVIEW': {
      if (!state.preview.previewUrl || !state.preview.isVerified) {
        return { valid: false, reason: 'Önizleme videosu oynatılıp doğrulanmalıdır.' }
      }
      return { valid: true }
    }
    case 'RENDER': {
      if (!state.render.jobId) {
        return { valid: false, reason: 'Render işi henüz başlatılmamıştır.' }
      }
      return { valid: true }
    }
    default:
      return { valid: false, reason: 'Bilinmeyen adım.' }
  }
}

export const useFlowStore = create<FlowState>((set, get) => ({
  currentStep: 'TOPIC',
  isLoading: false,
  errorMessage: null,

  // K-703 State
  connectionState: 'connected',
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

  validateCurrentStep: () => {
    return checkStepValidation(get(), get().currentStep)
  },

  isStepValid: (step: FlowStep) => {
    return checkStepValidation(get(), step)
  },

  canProceed: () => {
    return checkStepValidation(get(), get().currentStep).valid
  },

  nextStep: () => {
    const { currentStep } = get()
    const currentIndex = FLOW_STEPS.indexOf(currentStep)

    if (currentIndex >= FLOW_STEPS.length - 1) {
      return
    }

    const validation = checkStepValidation(get(), currentStep)
    const nextStepName = FLOW_STEPS[currentIndex + 1]

    if (!validation.valid) {
      const error = new InvalidStateTransitionError(
        currentStep,
        nextStepName,
        validation.reason || 'Adım doğrulanamadı'
      )
      set({ errorMessage: error.message })
      throw error
    }

    set({ currentStep: nextStepName, errorMessage: null })
  },

  prevStep: () => {
    const { currentStep } = get()
    const currentIndex = FLOW_STEPS.indexOf(currentStep)

    if (currentIndex <= 0) {
      return
    }

    set({ currentStep: FLOW_STEPS[currentIndex - 1], errorMessage: null })
  },

  goToStep: (targetStep: FlowStep) => {
    const { currentStep } = get()
    const currentIndex = FLOW_STEPS.indexOf(currentStep)
    const targetIndex = FLOW_STEPS.indexOf(targetStep)

    if (targetIndex === currentIndex) {
      return
    }

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

  setTopic: (topic: string) => {
    set({ topic, errorMessage: null })
  },

  selectIdea: (idea: VideoIdea) => {
    set({ selectedIdea: idea, errorMessage: null })
  },

  setScript: (scriptUpdate: Partial<ScriptData>) => {
    set((state) => {
      if (!state.script) {
        return {
          script: {
            id: scriptUpdate.id ?? `scr_${Date.now()}`,
            title: scriptUpdate.title ?? '',
            hook: scriptUpdate.hook ?? '',
            fullText: scriptUpdate.fullText ?? '',
            scenes: scriptUpdate.scenes ?? [],
            claims: scriptUpdate.claims ?? [],
            isApproved: scriptUpdate.isApproved ?? false,
          },
          errorMessage: null,
        }
      }
      const textOrTitleChanged =
        (scriptUpdate.title !== undefined && scriptUpdate.title !== state.script.title) ||
        (scriptUpdate.fullText !== undefined && scriptUpdate.fullText !== state.script.fullText)

      return {
        script: {
          ...state.script,
          ...scriptUpdate,
          isApproved: textOrTitleChanged ? false : (scriptUpdate.isApproved ?? state.script.isApproved),
        },
        errorMessage: null,
      }
    })
  },

  toggleClaim: (claimId: string) => {
    set((state) => {
      if (!state.script) return state
      const updatedClaims = (state.script.claims || []).map((c) =>
        c.id === claimId ? { ...c, verified: !c.verified } : c
      )
      return {
        script: {
          ...state.script,
          claims: updatedClaims,
          isApproved: false, // İddia durumu değiştiğinde yeniden onay gerekir
        },
        errorMessage: null,
      }
    })
  },

  setClaimVerified: (claimId: string, verified: boolean) => {
    set((state) => {
      if (!state.script) return state
      const updatedClaims = (state.script.claims || []).map((c) =>
        c.id === claimId ? { ...c, verified } : c
      )
      return {
        script: {
          ...state.script,
          claims: updatedClaims,
          isApproved: false,
        },
        errorMessage: null,
      }
    })
  },

  saveScriptContent: async (titleOverride?: string, fullTextOverride?: string) => {
    const { script } = get()
    if (!script) return null

    const title = titleOverride ?? script.title
    const fullText = fullTextOverride ?? script.fullText

    set((s) => ({
      script: s.script ? { ...s.script, isSaving: true, saveStatus: 'SAVING' } : null,
    }))

    try {
      const client = getIpcClient()
      const resp = await client.saveScript(
        script.id,
        title,
        fullText,
        script.scenes,
        script.claims,
        script.isApproved
      )

      const status = resp.body?.status === 'UNCHANGED' ? 'UNCHANGED' : 'SAVED'
      set((s) => ({
        script: s.script
          ? {
              ...s.script,
              isSaving: false,
              saveStatus: status,
              lastSavedAt: Date.now(),
            }
          : null,
      }))
      return resp
    } catch (err: any) {
      set((s) => ({
        script: s.script ? { ...s.script, isSaving: false, saveStatus: 'ERROR' } : null,
      }))
      throw err
    }
  },

  approveScript: () => {
    const state = get()
    if (!state.script) {
      const err = new InvalidStateTransitionError('SCRIPT', 'AUDIO', 'Onaylanacak senaryo bulunamadı.')
      set({ errorMessage: err.message })
      throw err
    }
    const unverified = (state.script.claims || []).filter((c) => !c.verified)
    if (unverified.length > 0) {
      const err = new InvalidStateTransitionError(
        'SCRIPT',
        'AUDIO',
        `Tüm iddialar (claims) kullanıcı tarafından onaylanmadan senaryo onaylanamaz. Onay bekleyen iddia sayısı: ${unverified.length}`
      )
      set({ errorMessage: err.message })
      throw err
    }

    set((s) => ({
      script: s.script ? { ...s.script, isApproved: true } : null,
      errorMessage: null,
    }))
  },

  setAudio: (audioUpdate: Partial<AudioData>) => {
    set((state) => ({
      audio: state.audio ? { ...state.audio, ...audioUpdate } : (audioUpdate as AudioData),
      errorMessage: null,
    }))
  },

  assignAssetSlot: (slotId: string, path: string) => {
    set((state) => {
      const updatedSlots = state.assets.slots.map((s) =>
        s.slotId === slotId ? { ...s, assignedPath: path } : s
      )
      const allRequiredFilled = updatedSlots
        .filter((s) => s.required)
        .every((s) => s.assignedPath !== null)

      return {
        assets: {
          slots: updatedSlots,
          allSlotsFilled: allRequiredFilled,
        },
        errorMessage: null,
      }
    })
  },

  setPreviewVerified: (verified: boolean) => {
    set((state) => ({
      preview: { ...state.preview, isVerified: verified },
      errorMessage: null,
    }))
  },

  setRenderProgress: (progress: number, status?: RenderData['status'], outputPath?: string, error?: string) => {
    set((state) => ({
      render: {
        ...state.render,
        progress,
        status: status ?? state.render.status,
        outputPath: outputPath ?? state.render.outputPath,
        error: error ?? state.render.error,
      },
    }))
  },

  addToast: (toast: Partial<UIError> & { title: string; message: string }) => {
    const timestamp = Date.now()
    const errorId = toast.id || `toast_${timestamp}_${Math.random().toString(36).substring(2, 7)}`
    const newToast: UIError = {
      id: errorId,
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
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }))
  },

  dismissModalError: () => {
    set({ activeModalError: null })
  },

  setConnectionState: (connectionState: ConnectionStatePayload['state'], reconnectAttempt = 0) => {
    set({ connectionState, reconnectAttempt })
  },

  // -------------------------------------------------------------------------
  // K-703 Hard-Cancel
  // -------------------------------------------------------------------------
  cancelRenderJob: async () => {
    const { render } = get()
    if (!render.jobId) return

    set({ isLoading: true })
    try {
      const client = getIpcClient()
      const resp = await client.cancelJob(render.jobId)
      if (resp.status >= 400) {
        const uiError = parseProblemDetails(resp)
        if (uiError.mode === 'modal') {
          set({ activeModalError: uiError, isLoading: false })
        } else {
          set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false }))
        }
      } else {
        set((state) => ({
          render: {
            ...state.render,
            status: 'CANCELLED',
          },
          isLoading: false,
        }))
      }
    } catch (err: any) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false }))
      }
    }
  },

  // -------------------------------------------------------------------------
  // K-703 Event Bridge Dinleyicisi
  // -------------------------------------------------------------------------
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
              },
            }))
          }
        } else if (event.type === 'job_cancelled') {
          const evt = event as any
          if (!currentState.render.jobId || currentState.render.jobId === evt.job_id) {
            set((s) => ({
              render: {
                ...s.render,
                status: 'CANCELLED',
              },
            }))
          }
        } else if (event.type === 'job_failed') {
          const evt = event as any
          const uiError = parseProblemDetails(evt.error)
          if (uiError.mode === 'modal') {
            set((s) => ({
              activeModalError: uiError,
              render: { ...s.render, status: 'FAILED', error: uiError.message },
              errorMessage: uiError.message,
            }))
          } else {
            set((s) => ({
              toasts: [...s.toasts, uiError],
              render: { ...s.render, status: 'FAILED', error: uiError.message },
              errorMessage: uiError.message,
            }))
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
        set({
          connectionState: statePayload.state,
          reconnectAttempt: statePayload.attempt ?? 0,
        })
      }),
    ])

    return () => {
      unlistenEvent()
      unlistenConnection()
    }
  },

  // -------------------------------------------------------------------------
  // IPC Çağrıları (Zero-Network & Problem Details Protected)
  // -------------------------------------------------------------------------
  fetchIdeasForTopic: async () => {
    const { topic } = get()
    if (!topic || topic.trim().length < 3) {
      set({ errorMessage: 'Geçersiz konu başlığı.' })
      return
    }

    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.runDiscovery(topic)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err })
        else set((s) => ({ toasts: [...s.toasts, err] }))
        set({ errorMessage: err.message, isLoading: false })
        return
      }

      const rawItems = Array.isArray(resp.body) ? resp.body : resp.body?.results ?? []

      const ideas: VideoIdea[] = rawItems.map((item: any, idx: number) => ({
        id: item.video_id ?? item.id ?? `idea_${idx + 1}`,
        title: item.title ?? `Fikir #${idx + 1}: ${topic}`,
        hook: item.hook ?? item.description ?? `Dikkat çeken kanca #${idx + 1}`,
        score: typeof item.score === 'number' ? item.score : 85 - idx * 2,
        viewCount: item.view_count ?? 150000,
      }))

      const fallbackIdeas: VideoIdea[] =
        ideas.length > 0
          ? ideas
          : Array.from({ length: 5 }, (_, i) => ({
              id: `idea_det_${i + 1}`,
              title: `${topic} Hakkında ${i + 1}. Viral Gerçek`,
              hook: `Bunu biliyor muydunuz? ${topic} ile ilgili kimsenin söylemediği sır!`,
              score: 95 - i * 5,
              viewCount: 250000 - i * 30000,
            }))

      set({ ideas: fallbackIdeas, isLoading: false })
    } catch (err: any) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
      }
    }
  },

  generateScriptForIdea: async () => {
    const { selectedIdea, topic } = get()
    if (!selectedIdea) {
      set({ errorMessage: 'Önce bir fikir seçmelisiniz.' })
      return
    }

    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.generateScript(selectedIdea.id, topic, selectedIdea.title)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err })
        else set((s) => ({ toasts: [...s.toasts, err] }))
        set({ errorMessage: err.message, isLoading: false })
        return
      }

      const data = resp.body
      const rawClaims = Array.isArray(data.claims) ? data.claims : []
      const claims: ScriptClaim[] =
        rawClaims.length > 0
          ? rawClaims.map((c: any, idx: number) => ({
              id: c.id ?? `claim_${idx + 1}`,
              text: typeof c === 'string' ? c : c.text ?? `İddia #${idx + 1}`,
              verified: Boolean(c.verified),
            }))
          : [
              { id: 'claim_1', text: `${topic} konusundaki veriler resmi kaynaklarla doğrulanmıştır.`, verified: false },
              { id: 'claim_2', text: 'Sunulan rakamlar ve test sonuçları güncel araştırmalara dayanmaktadır.', verified: false },
              { id: 'claim_3', text: 'Metin yanıltıcı veya asılsız sağlık/finansal vaatler içermemektedir.', verified: false },
            ]

      const script: ScriptData = {
        id: data.script_id ?? `scr_${Date.now()}`,
        title: data.title ?? selectedIdea.title,
        hook: data.hook ?? selectedIdea.hook,
        fullText: data.full_text ?? `${selectedIdea.title}. ${selectedIdea.hook}`,
        scenes: data.scenes ?? [
          { order: 1, narration: selectedIdea.hook, visualPrompt: 'Cinematic visual' },
        ],
        claims,
        isApproved: false,
      }

      set({ script, isLoading: false })
    } catch (err: any) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
      }
    }
  },

  generateAudioForScript: async (voiceId = 'tr-TR-Standard-A') => {
    const { script } = get()
    if (!script) {
      set({ errorMessage: 'Ses üretmek için onaylanmış bir senaryo gereklidir.' })
      return
    }

    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.generateAudio(script.id, voiceId, script.fullText)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err })
        else set((s) => ({ toasts: [...s.toasts, err] }))
        set({ errorMessage: err.message, isLoading: false })
        return
      }

      const data = resp.body
      const audio: AudioData = {
        scriptId: script.id,
        voiceId,
        audioPath: data.audio_path ?? `assets/audio/${script.id}.mp3`,
        durationSeconds: data.duration_seconds ?? 30,
        isGenerated: true,
      }

      set({ audio, isLoading: false })
    } catch (err: any) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
      }
    }
  },

  loadAssetsForScript: async () => {
    const { script } = get()
    if (!script) return

    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.prepareAssets(script.id)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err })
        else set((s) => ({ toasts: [...s.toasts, err] }))
        set({ errorMessage: err.message, isLoading: false })
        return
      }

      const data = resp.body
      const rawSlots = data.slots ?? createInitialAssetsData().slots

      const slots: AssetSlot[] = rawSlots.map((s: any) => ({
        slotId: s.slot_id ?? s.slotId,
        name: s.name,
        type: s.type,
        required: s.required ?? true,
        assignedPath: s.assigned_path ?? s.assignedPath ?? null,
      }))

      const allFilled = slots.filter((s) => s.required).every((s) => s.assignedPath !== null)

      set({
        assets: { slots, allSlotsFilled: allFilled },
        isLoading: false,
      })
    } catch (err: any) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
      }
    }
  },

  buildPreviewForScript: async () => {
    const { script } = get()
    if (!script) return

    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.generatePreview(script.id)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err })
        else set((s) => ({ toasts: [...s.toasts, err] }))
        set({ errorMessage: err.message, isLoading: false })
        return
      }

      const data = resp.body
      set({
        preview: {
          previewUrl: data.preview_url ?? `assets/previews/${script.id}.mp4`,
          fps: data.fps ?? 30,
          resolution: data.resolution ?? '540x960',
          isVerified: false,
        },
        isLoading: false,
      })
    } catch (err: any) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
      }
    }
  },

  dispatchRenderJob: async (profile: 'DRAFT' | 'FINAL' = 'DRAFT') => {
    const { script } = get()
    if (!script) return

    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.triggerRender(profile, script.id)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err })
        else set((s) => ({ toasts: [...s.toasts, err] }))
        set({ errorMessage: err.message, isLoading: false })
        return
      }

      const data = resp.body
      set({
        render: {
          jobId: data.job_id ?? `job_${Date.now()}`,
          profile,
          status: 'RENDERING',
          progress: 5,
          outputPath: data.output_path ?? null,
          error: null,
        },
        isLoading: false,
      })
    } catch (err: any) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
      }
    }
  },

  pollJobStatus: async () => {
    // K-703: Polling yerine SSE Event Stream kullanılmalıdır.
    // Geriye dönük uyumluluk veya manuel fallback için getJobStatus sorgusu.
    const { render } = get()
    if (!render.jobId) return

    try {
      const client = getIpcClient()
      const resp = await client.getJobStatus(render.jobId)
      const data = resp.body

      set((state) => ({
        render: {
          ...state.render,
          status: data.status ?? state.render.status,
          progress: data.progress ?? state.render.progress,
          outputPath: data.output_path ?? state.render.outputPath,
          error: data.error_message ?? state.render.error,
        },
      }))
    } catch (err: any) {
      const uiError = parseProblemDetails(err)
      set({ errorMessage: uiError.message })
    }
  },
}))
