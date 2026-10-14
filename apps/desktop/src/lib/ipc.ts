/**
 * Hustler Desktop — İzole Tauri IPC İstemcisi (K-702)
 *
 * MİMARİ KURAL: ZERO-NETWORK POLICY (Sıfır Ağ Çağrısı)
 * Bu dosyada ve tüm frontend kodunda `fetch`, `axios` veya doğrudan HTTP çağrısı
 * yapılması KESİNLİKLE YASAKTIR.
 *
 * Tüm veri akışı işletim sistemi güvenliği sağlayan Tauri IPC (`invoke`)
 * köprüsü üzerinden Rust katmanına yönlendirilir.
 */

import { invoke } from '@tauri-apps/api/core'

export interface ProxyResponse<T = any> {
  status: number
  body: T
}

export interface FlowIpcClient {
  runDiscovery(topic: string): Promise<ProxyResponse>
  generateScript(ideaId: string, topic: string, title: string): Promise<ProxyResponse>
  saveScript(
    scriptId: string,
    title: string,
    fullText: string,
    scenes?: any[],
    claims?: any[],
    isApproved?: boolean
  ): Promise<ProxyResponse>
  generateAudio(scriptId: string, voiceId: string, text: string): Promise<ProxyResponse>
  prepareAssets(scriptId: string, slots?: any[]): Promise<ProxyResponse>
  generatePreview(scriptId: string): Promise<ProxyResponse>
  triggerRender(profile: 'DRAFT' | 'FINAL', scriptId: string): Promise<ProxyResponse>
  getJobStatus(jobId: string): Promise<ProxyResponse>
  cancelJob(jobId: string): Promise<ProxyResponse>
  getActiveSession(): Promise<ProxyResponse>
  saveActiveSession(payload: any): Promise<ProxyResponse>
  exportDiagnostics?(format?: 'zip' | 'json'): Promise<ProxyResponse>
  proxyRequest(method: string, route: string, body?: any): Promise<ProxyResponse>
}

/**
 * Üretim / Yerel Çalışma Tauri IPC İstemcisi.
 * Doğrudan `@tauri-apps/api/core` invoke çağrılarını kullanır.
 */
export const tauriIpcClient: FlowIpcClient = {
  async runDiscovery(topic: string): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('flow_discovery_run', { topic })
  },

  async generateScript(ideaId: string, topic: string, title: string): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('flow_generate_script', { ideaId, topic, title })
  },

  async saveScript(
    scriptId: string,
    title: string,
    fullText: string,
    scenes: any[] = [],
    claims: any[] = [],
    isApproved = false
  ): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('flow_save_script', {
      scriptId,
      title,
      fullText,
      scenes,
      claims,
      isApproved,
    })
  },

  async generateAudio(scriptId: string, voiceId: string, text: string): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('flow_generate_audio', { scriptId, voiceId, text })
  },

  async prepareAssets(scriptId: string, slots: any[] = []): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('flow_prepare_assets', { scriptId, slots })
  },

  async generatePreview(scriptId: string): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('flow_generate_preview', { scriptId })
  },

  async triggerRender(profile: 'DRAFT' | 'FINAL', scriptId: string): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('flow_trigger_render', { profile, scriptId })
  },

  async getJobStatus(jobId: string): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('flow_get_job_status', { jobId })
  },

  async cancelJob(jobId: string): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('flow_cancel_job', { jobId })
  },

  async getActiveSession(): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('flow_get_active_session')
  },

  async saveActiveSession(payload: any): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('flow_save_active_session', { payload })
  },

  async exportDiagnostics(format: 'zip' | 'json' = 'json'): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('diagnostics_export_bundle', { format })
  },

  async proxyRequest(method: string, route: string, body?: any): Promise<ProxyResponse> {
    return invoke<ProxyResponse>('proxy_request', {
      req: {
        method,
        route,
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
