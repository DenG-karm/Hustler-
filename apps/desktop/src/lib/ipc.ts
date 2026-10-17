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
} from '../store/flowTypes'

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
  runDiscovery(topic: string): Promise<ProxyResponse<DiscoveryResponseData>>
  generateScript(ideaId: string, topic: string, title: string): Promise<ProxyResponse<ScriptGenerateResponseData>>
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
  proxyRequest(method: string, route: string, body?: unknown): Promise<ProxyResponse<unknown>>
}

/**
 * Üretim / Yerel Çalışma Tauri IPC İstemcisi.
 * Doğrudan Tauri IPC güvenlik kalkanı (secureInvoke) üzerinden çağrı yapar.
 */
export const tauriIpcClient: FlowIpcClient = {
  async runDiscovery(topic: string): Promise<ProxyResponse<DiscoveryResponseData>> {
    return (await tauriIpcClient.proxyRequest('POST', '/api/v1/discovery/run', {
      topic,
      max_results: 20,
      score_threshold: 30.0,
    })) as ProxyResponse<DiscoveryResponseData>
  },

  async generateScript(ideaId: string, topic: string, title: string): Promise<ProxyResponse<ScriptGenerateResponseData>> {
    return (await tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/script', {
      idea_id: ideaId,
      topic,
      title,
    })) as ProxyResponse<ScriptGenerateResponseData>
  },

  async saveScript(
    scriptId: string,
    title: string,
    fullText: string,
    scenes: ScriptScene[] = [],
    claims: ScriptClaim[] = [],
    isApproved = false
  ): Promise<ProxyResponse<ScriptSaveResponseData>> {
    return (await tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/script/save', {
      script_id: scriptId,
      title,
      full_text: fullText,
      scenes,
      claims,
      is_approved: isApproved,
    })) as ProxyResponse<ScriptSaveResponseData>
  },

  async generateAudio(scriptId: string, voiceId: string, text: string): Promise<ProxyResponse<AudioGenerateResponseData>> {
    return (await tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/audio', {
      script_id: scriptId,
      voice_id: voiceId,
      text,
    })) as ProxyResponse<AudioGenerateResponseData>
  },

  async prepareAssets(scriptId: string, slots: AssetSlot[] = []): Promise<ProxyResponse<AssetsPrepareResponseData>> {
    return (await tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/assets', {
      script_id: scriptId,
      slots,
    })) as ProxyResponse<AssetsPrepareResponseData>
  },

  async generatePreview(scriptId: string): Promise<ProxyResponse<PreviewGenerateResponseData>> {
    return (await tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/preview', {
      script_id: scriptId,
    })) as ProxyResponse<PreviewGenerateResponseData>
  },

  async triggerRender(profile: 'DRAFT' | 'FINAL', scriptId: string): Promise<ProxyResponse<RenderTriggerResponseData>> {
    return (await tauriIpcClient.proxyRequest('POST', '/api/v1/pipeline/render', {
      profile,
      script_id: scriptId,
    })) as ProxyResponse<RenderTriggerResponseData>
  },

  async getJobStatus(jobId: string): Promise<ProxyResponse<JobStatusResponseData>> {
    return (await tauriIpcClient.proxyRequest(
      'GET',
      `/api/v1/jobs/${encodeURIComponent(jobId)}`
    )) as ProxyResponse<JobStatusResponseData>
  },

  async cancelJob(jobId: string): Promise<ProxyResponse<JobStatusResponseData>> {
    return (await tauriIpcClient.proxyRequest(
      'POST',
      `/api/v1/jobs/${encodeURIComponent(jobId)}/cancel`
    )) as ProxyResponse<JobStatusResponseData>
  },

  async getActiveSession(): Promise<ProxyResponse<SessionResponseData>> {
    return (await tauriIpcClient.proxyRequest(
      'GET',
      '/api/v1/pipeline/session/active'
    )) as ProxyResponse<SessionResponseData>
  },

  async saveActiveSession(payload: ActiveSessionPayload): Promise<ProxyResponse<SessionResponseData>> {
    return (await tauriIpcClient.proxyRequest(
      'POST',
      '/api/v1/pipeline/session/save',
      payload
    )) as ProxyResponse<SessionResponseData>
  },

  async exportDiagnostics(format: 'zip' | 'json' = 'json'): Promise<ProxyResponse<DiagnosticsResponseData>> {
    return (await tauriIpcClient.proxyRequest(
      'POST',
      `/api/v1/diagnostics/export?format=${encodeURIComponent(format)}`
    )) as ProxyResponse<DiagnosticsResponseData>
  },

  async proxyRequest(method: string, route: string, body?: unknown): Promise<ProxyResponse<unknown>> {
    const validatedRoute = validateProxyRoute(route)
    return secureInvoke<ProxyResponse<unknown>>('proxy_request', {
      req: {
        method,
        route: validatedRoute,
        body: body ?? null,
      },
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
