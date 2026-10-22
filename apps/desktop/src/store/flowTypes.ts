/**
 * Hustler Desktop — Akış Durum Makinesi Tipleri ve Doğrulama Kuralları
 */

import type { ConnectionStatePayload } from '../lib/events'
import type { UIError } from '../lib/problemDetails'
import type { ProxyResponse } from '../lib/ipc'

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

export type AppView = 'pipeline' | 'channels' | 'library' | 'settings' | 'templates'

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

export interface DiscoveryItem {
  id?: string
  video_id?: string
  title: string
  hook?: string
  description?: string
  score?: number
  view_count?: number
  topic?: string
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
  stepName?: string | null
  encoder?: string | null
}

export interface ActiveSessionPayload {
  id?: string
  topic?: string
  current_step?: FlowStep
  checkpoint_step?: FlowStep
  status?: string
  state_payload?: {
    topic?: string
    ideas?: VideoIdea[]
    selectedIdea?: VideoIdea | null
    script?: ScriptData | null
    audio?: AudioData | null
    assets?: AssetsData
    preview?: PreviewData
    render?: RenderData
    [key: string]: unknown
  }
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
  runDiscovery: (topicOverride?: string) => Promise<void>
  fetchIdeasForTopic: () => Promise<void>
  generateScriptForIdea: () => Promise<void>
  generateAudioForScript: (voiceId?: string) => Promise<void>
  loadAssetsForScript: () => Promise<void>
  buildPreviewForScript: () => Promise<void>
  dispatchRenderJob: (profile?: 'DRAFT' | 'FINAL') => Promise<void>
  pollJobStatus: () => Promise<void>
  rehydrateFromBackend: () => Promise<boolean>
  persistSessionToBackend: () => Promise<void>

  // Kanal-Merkezli Mimari (Faz 2/2): Kanal Çalışma Alanı & Akış Köprüsü
  activeView: AppView
  channels: ChannelItem[]
  activeChannelId: string | null
  flowChannelId: string | null
  channelIdeas: VideoIdea[]
  channelResearchQuery: string
  isChannelsLoading: boolean
  isChannelResearching: boolean
  channelLiveStats: Record<string, ChannelLiveStats | null>
  isLiveStatsLoading: boolean
  setActiveView: (view: AppView) => void
  loadChannels: () => Promise<void>
  createChannel: (payload: ChannelCreatePayload) => Promise<ChannelItem | null>
  deleteChannel: (id: string) => Promise<void>
  selectChannel: (id: string | null) => void
  researchChannelContent: (channelId: string, query: string) => Promise<void>
  updateChannelSummary: (channelId: string, aiSummary: string) => Promise<void>
  fetchChannelLiveStats: (channelId: string, refresh?: boolean) => Promise<ChannelLiveStats | null>
  selectIdeaFromChannelAndStartFlow: (channelId: string, idea: DiscoveryItem | VideoIdea) => void
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

export function checkStepValidation(state: FlowState, step: FlowStep): { valid: boolean; reason?: string } {
  switch (step) {
    case 'TOPIC': {
      if (state.flowChannelId || state.activeChannelId) return { valid: true }
      if (!state.topic || state.topic.trim().length < 3) {
        return { valid: false, reason: 'Konu başlığı en az 3 karakter olmalıdır.' }
      }
      return { valid: true }
    }
    case 'TOP20': {
      if (state.flowChannelId || state.activeChannelId) return { valid: true }
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

// ---------------------------------------------------------------------------
// Kanal-Merkezli Mimari (Faz 1/2): Kanal Modelleri
// ---------------------------------------------------------------------------

export interface ChannelMetrics {
  total_scripts: number
  total_research: number
  avg_viral_score?: number
  avg_performance_score?: number
}

export interface RealVideoItem {
  id: string | null
  type: 'video' | 'short'
  title: string
  url: string | null
  view_count: number | null
  duration: number | null
  published_text?: string | null
  days_ago?: number | null
  time_period?: 'month' | 'year' | 'all_time' | null
}

export interface TrendPoint {
  index: number
  id: string | null
  title: string
  type: string
  view_count: number
  view_count_formatted: string
  rolling_avg: number
  rolling_avg_formatted: string
}

export interface PieSlice {
  type: string
  label: string
  color: string
  count: number
  total_views: number
  total_views_formatted: string
  percentage: number
}

export interface LineChartData {
  points: TrendPoint[]
  max_val: number
  min_val: number
  avg_val: number
  avg_val_formatted: string
  trend_direction: 'up' | 'down' | 'stable'
}

export interface ChannelAnalytics {
  has_data: boolean
  line_chart: LineChartData
  videos_line_chart?: LineChartData
  shorts_line_chart?: LineChartData
  pie_chart: {
    slices: PieSlice[]
    total_views: number
    total_views_formatted: string
  }
  summary: {
    median_views: number
    median_views_formatted: string
    max_views: number
    max_views_formatted: string
    min_views: number
    total_views: number
    total_views_formatted: string
    sample_count: number
  }
}

export interface ChannelLiveStats {
  channel_id: string
  channel_name: string
  channel_url: string
  avatar_url: string | null
  description: string
  subscribers: number | null
  subscribers_formatted: string | null
  videos: RealVideoItem[]
  shorts: RealVideoItem[]
  total_fetched_videos: number
  total_fetched_shorts: number
  avg_views_sample: number | null
  avg_views_formatted: string | null
  analytics?: ChannelAnalytics
  is_live: boolean
  fetched_at: number
}

export interface ChannelItem {
  id: string
  name: string
  channel_url: string
  description: string
  created_at: number
  avatar_url?: string
  ai_summary?: string
  metrics: ChannelMetrics
}

export interface ChannelCreatePayload {
  name: string
  channel_url: string
  description: string
}

export interface ChannelDeleteResponse {
  status: string
  channel_id: string
}

