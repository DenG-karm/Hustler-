/**
 * Hustler Desktop — İzole Tauri IPC İstemcisi (K-702 & K-805)
 *
 * MİMARİ KURAL: ZERO-NETWORK POLICY (Sıfır Ağ Çağrısı)
 * Bu dosyada ve tüm frontend kodunda `fetch`, `axios` veya doğrudan HTTP çağrısı
 * yapılması KESİNLİKLE YASAKTIR.
 *
 * Tüm veri akışı işletim sistemi güvenliği sağlayan Tauri IPC (`secureInvoke`)
 * köprüsü üzerinden Rust katmanına yönlendirilir.
 */

import { secureInvoke, validateProxyRoute } from './securityGuard'
import type {
  DiscoveryItem,
  ScriptScene,
  ScriptClaim,
  AssetSlot,
  RenderData,
  ActiveSessionPayload,
  ChannelItem,
  ChannelCreatePayload,
  ChannelDeleteResponse,
} from '../store/flowTypes'

export type { ChannelItem, ChannelCreatePayload, ChannelDeleteResponse }

export interface ProxyResponse<T = unknown> {
  status: number
  body: T
}

export interface DiscoveryResponseData {
  results: DiscoveryItem[]
  degraded?: boolean
  warning?: string | null
  fetched?: number
  discarded?: number
  inserted?: number
  max_score?: number
}

export interface ScriptGenerateResponseData {
  script_id: string
  title: string
  hook: string
  full_text: string
  scenes: ScriptScene[]
  claims: ScriptClaim[]
  is_approved?: boolean
}

export interface ScriptSaveResponseData {
  status: string
  script_id: string
  is_idempotent?: boolean
  content_hash?: string
  updated_at?: number
}

export interface AudioGenerateResponseData {
  script_id: string
  voice_id: string
  audio_path: string
  duration_seconds: number
  is_generated?: boolean
}

export interface AssetsPrepareResponseData {
  script_id: string
  slots: AssetSlot[]
  all_slots_filled: boolean
}

export interface PreviewGenerateResponseData {
  script_id: string
  preview_url: string
  fps: number
  resolution: string
  is_verified?: boolean
}

export interface RenderTriggerResponseData {
  job_id: string
  status: RenderData['status']
  progress: number
  output_path: string | null
  profile?: string
}

export interface JobStatusResponseData {
  job_id: string
  status: RenderData['status']
  progress?: number
  progress_pct?: number
  output_path?: string | null
  error_message?: string | null
  current_step?: string | null
  created_at?: number
  updated_at?: number
  message?: string
}

export interface SessionResponseData {
  session?: ActiveSessionPayload | null
  status?: string
}

export interface DiagnosticsResponseData {
  status: string
  filename: string
  bundle_path: string
  size_bytes: number
}

export interface FlowIpcClient {
  runDiscovery(topic: string, channelId?: string | null): Promise<ProxyResponse<DiscoveryResponseData>>
  generateScript(
    ideaId: string,
    topic: string,
    title: string,
    channelId?: string | null
  ): Promise<ProxyResponse<ScriptGenerateResponseData>>
  saveScript(
    scriptId: string,
    title: string,
    fullText: string,
    scenes?: ScriptScene[],
    claims?: ScriptClaim[],
    isApproved?: boolean
  ): Promise<ProxyResponse<ScriptSaveResponseData>>
  generateAudio(scriptId: string, voiceId: string, text: string): Promise<ProxyResponse<AudioGenerateResponseData>>
  prepareAssets(scriptId: string, slots?: AssetSlot[]): Promise<ProxyResponse<AssetsPrepareResponseData>>
  generatePreview(scriptId: string): Promise<ProxyResponse<PreviewGenerateResponseData>>
  triggerRender(profile: 'DRAFT' | 'FINAL', scriptId: string): Promise<ProxyResponse<RenderTriggerResponseData>>
  getJobStatus(jobId: string): Promise<ProxyResponse<JobStatusResponseData>>
  cancelJob(jobId: string): Promise<ProxyResponse<JobStatusResponseData>>
  getActiveSession(): Promise<ProxyResponse<SessionResponseData>>
  saveActiveSession(payload: ActiveSessionPayload): Promise<ProxyResponse<SessionResponseData>>
  exportDiagnostics?(format?: 'zip' | 'json'): Promise<ProxyResponse<DiagnosticsResponseData>>
  listChannels?(): Promise<ProxyResponse<ChannelItem[]>>
  createChannel?(payload: ChannelCreatePayload): Promise<ProxyResponse<ChannelItem>>
  getChannelDetail?(channelId: string): Promise<ProxyResponse<ChannelItem>>
  deleteChannel?(channelId: string): Promise<ProxyResponse<ChannelDeleteResponse>>
  proxyRequest(method: string, route: string, body?: unknown): Promise<ProxyResponse<unknown>>
}

export interface ChannelIpcClient {
  listChannels(): Promise<ProxyResponse<ChannelItem[]>>
  createChannel(payload: ChannelCreatePayload): Promise<ProxyResponse<ChannelItem>>
  getChannelDetail(channelId: string): Promise<ProxyResponse<ChannelItem>>
  deleteChannel(channelId: string): Promise<ProxyResponse<ChannelDeleteResponse>>
}

/**
 * Üretim / Yerel Çalışma Tauri IPC İstemcisi.
 * Doğrudan Tauri IPC güvenlik kalkanı (secureInvoke) üzerinden Sidecar proxy çağrısı yapar.
 * Sıfır Mock Kuralı: Tarayıcı mock işleyicileri kaldırılmış olup tüm çağrılar Tauri invoke köprüsünden geçer.
 */
export const tauriIpcClient: FlowIpcClient & ChannelIpcClient = {
  runDiscovery(topic, channelId) {
    return tauriIpcClient.proxyRequest('POST', '/api/v1/discovery/run', {
      topic,
      max_results: 20,
      score_threshold: 30.0,
      ...(channelId ? { channel_id: channelId } : {}),
    }) as Promise<ProxyResponse<DiscoveryResponseData>>
  },
  generateScript(idea_id, topic, title, channelId) {
    return tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/script', { idea_id, topic, title, ...(channelId ? { channel_id: channelId } : {}) }) as Promise<ProxyResponse<ScriptGenerateResponseData>>
  },
  saveScript(script_id, title, full_text, scenes = [], claims = [], is_approved = false) {
    return tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/script/save', { script_id, title, full_text, scenes, claims, is_approved }) as Promise<ProxyResponse<ScriptSaveResponseData>>
  },
  generateAudio(script_id, voice_id, text) {
    return tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/audio', { script_id, voice_id, text }) as Promise<ProxyResponse<AudioGenerateResponseData>>
  },
  prepareAssets(script_id, slots = []) {
    return tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/assets', { script_id, slots }) as Promise<ProxyResponse<AssetsPrepareResponseData>>
  },
  generatePreview(script_id) {
    return tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/preview', { script_id }) as Promise<ProxyResponse<PreviewGenerateResponseData>>
  },
  triggerRender(profile, script_id) {
    return tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/render', { profile, script_id }) as Promise<ProxyResponse<RenderTriggerResponseData>>
  },
  getJobStatus(jobId) {
    return tauriIpcClient.proxyRequest('GET', `/api/v1/jobs/${encodeURIComponent(jobId)}`) as Promise<ProxyResponse<JobStatusResponseData>>
  },
  cancelJob(jobId) {
    return tauriIpcClient.proxyRequest('POST', `/api/v1/jobs/${encodeURIComponent(jobId)}/cancel`) as Promise<ProxyResponse<JobStatusResponseData>>
  },
  getActiveSession() {
    return tauriIpcClient.proxyRequest('GET', '/api/v1/pipeline/session/active') as Promise<ProxyResponse<SessionResponseData>>
  },
  saveActiveSession(payload) {
    return tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/session/save', payload) as Promise<ProxyResponse<SessionResponseData>>
  },
  exportDiagnostics(format = 'json') {
    return tauriIpcClient.proxyRequest('POST', `/api/v1/diagnostics/export?format=${encodeURIComponent(format)}`) as Promise<ProxyResponse<DiagnosticsResponseData>>
  },
  listChannels() {
    return tauriIpcClient.proxyRequest('GET', '/api/v1/channels') as Promise<ProxyResponse<ChannelItem[]>>
  },
  createChannel(payload) {
    return tauriIpcClient.proxyRequest('POST', '/api/v1/channels', payload) as Promise<ProxyResponse<ChannelItem>>
  },
  getChannelDetail(channelId) {
    return tauriIpcClient.proxyRequest('GET', `/api/v1/channels/${encodeURIComponent(channelId)}`) as Promise<ProxyResponse<ChannelItem>>
  },
  deleteChannel(channelId) {
    return tauriIpcClient.proxyRequest('DELETE', `/api/v1/channels/${encodeURIComponent(channelId)}`) as Promise<ProxyResponse<ChannelDeleteResponse>>
  },
  proxyRequest(method, route, body) {
    return secureInvoke<ProxyResponse<unknown>>('proxy_request', {
      req: { method, route: validateProxyRoute(route), body: body ?? null },
    })
  },
}

let activeIpcClient: FlowIpcClient = tauriIpcClient

/**
 * Test ve mocklama için aktif IPC istemcisini değiştirir.
 */
export function setIpcClient(client: FlowIpcClient): void {
  activeIpcClient = client
}

/**
 * Aktif IPC istemcisini döndürür.
 */
export function getIpcClient(): FlowIpcClient {
  return activeIpcClient
}

/**
 * Varsayılan IPC istemcisine geri döner.
 */
export function resetIpcClient(): void {
  activeIpcClient = tauriIpcClient
}
