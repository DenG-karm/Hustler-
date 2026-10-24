/**
 * Hustler Desktop — Arayüz Güvenlik Kalkanı ve CSP Modülü (K-709)
 *
 * MİMARİ KURALLAR:
 * 1. SIFIR AĞ İZOLASYONU (Zero-Network Policy / CSP Network Trap):
 *    Frontend içerisinde `global.fetch` ve `XMLHttpRequest` doğrudan dış ağa (HTTP/HTTPS/WS)
 *    erişemez; herhangi bir doğrudan çağrı anında SecurityViolationError fırlatır ve güvenlik günlüğüne düşer.
 * 2. TAURI IPC KOMUT İZİN LİSTESİ (Command Allowlist Enforcement):
 *    Frontend'den yalnızca `ALLOWED_IPC_COMMANDS` izin listesinde kayıtlı Tauri komutları çağrılabilir.
 *    İzin listesi dışı rastgele komutlar (örn: 'plugin:hacker|steal_data') anında reddedilir.
 * 3. YEREL VARLIK VE CSP LEVEL 3 GÜVENCESİ (CWE-79 Korunumu):
 *    Medya ve varlık yüklemelerinde yalnızca Tauri güvenli asset protokolleri (`https://asset.localhost/`, `asset://`)
 *    ve yerel önizleme blob'ları (`blob:`, `data:image/*`) kabul edilir; harici CDN ve `file://` erişimi engellenir.
 *    script-src ve default-src bağlamında `data:` ve `blob:` şemaları KESİNLİKLE yasaktır.
 */

import { invoke, convertFileSrc } from '@tauri-apps/api/core'

// ---------------------------------------------------------------------------
// GÜVENLİK HATALARI VE GÜNLÜK MODELLERİ
// ---------------------------------------------------------------------------

export class SecurityViolationError extends Error {
  readonly violationType: 'FETCH' | 'XHR' | 'CSP' | 'ASSET'
  readonly targetUrl: string

  constructor(violationType: 'FETCH' | 'XHR' | 'CSP' | 'ASSET', targetUrl: string, message?: string) {
    super(message ?? `[CSP / ZERO-NETWORK GÜVENLİK İHLALİ] Yetkisiz ağ erişimi engellendi: ${targetUrl}`)
    this.name = 'SecurityViolationError'
    this.violationType = violationType
    this.targetUrl = targetUrl
  }
}

export class UnauthorizedIpcCommandError extends Error {
  readonly command: string

  constructor(command: string) {
    super(`[TAURI IPC GÜVENLİK İHLALİ] İzin listesi dışı komut reddedildi: '${command}'`)
    this.name = 'UnauthorizedIpcCommandError'
    this.command = command
  }
}

export class UnsafeAssetSourceError extends Error {
  readonly assetUrl: string

  constructor(assetUrl: string, reason: string) {
    super(`[GÜVENLİKSİZ VARLIK KAYNAĞI] '${assetUrl}' kaynağı reddedildi: ${reason}`)
    this.name = 'UnsafeAssetSourceError'
    this.assetUrl = assetUrl
  }
}

export interface SecurityAuditRecord {
  id: string
  timestamp: number
  type: 'FETCH_ATTEMPT' | 'XHR_ATTEMPT' | 'UNAUTHORIZED_IPC' | 'UNSAFE_ASSET' | 'UNSAFE_SCRIPT'
  target: string
  reason: string
}

export class SecurityAuditLogger {
  private static records: SecurityAuditRecord[] = []

  public static log(record: Omit<SecurityAuditRecord, 'id' | 'timestamp'>): SecurityAuditRecord {
    const entry: SecurityAuditRecord = {
      id: `sec_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      timestamp: Date.now(),
      ...record,
    }
    this.records.push(entry)
    return entry
  }

  public static getRecords(): SecurityAuditRecord[] {
    return [...this.records]
  }

  public static clear(): void {
    this.records = []
  }
}

// ---------------------------------------------------------------------------
// AĞ TRAP MEKANİZMASI (global.fetch & XMLHttpRequest Interceptor)
// ---------------------------------------------------------------------------

let originalFetch: typeof globalThis.fetch | undefined
let originalXhrOpen: ((method: string, url: string | URL, ...args: unknown[]) => void) | undefined

export function installNetworkSecurityTrap(): void {
  // 1. fetch Trap
  if (!originalFetch && typeof globalThis.fetch !== 'undefined') {
    originalFetch = globalThis.fetch
  }

  if (typeof globalThis.fetch !== 'undefined') {
    globalThis.fetch = ((input: RequestInfo | URL, _init?: RequestInit): Promise<Response> => {
      const targetUrl =
        typeof input === 'string'
          ? input
          : input instanceof URL
          ? input.toString()
          : (input as Request).url

      // Tauri'nin dahili IPC köprüsü (http://ipc.localhost veya ipc://) harici ağ değildir
      if (targetUrl.startsWith('http://ipc.localhost') || targetUrl.startsWith('ipc://')) {
        if (originalFetch) {
          return originalFetch(input, _init)
        }
      }

      const trappedApi = 'fetch'
      SecurityAuditLogger.log({
        type: 'FETCH_ATTEMPT',
        target: targetUrl,
        reason: `Frontend kodunda doğrudan ${trappedApi}() çağrısı yapılması yasaktır`,
      })

      const error = new SecurityViolationError('FETCH', targetUrl)
      return Promise.reject(error)
    }) as typeof globalThis.fetch
  }

  // 2. XMLHttpRequest Trap
  if (typeof globalThis.XMLHttpRequest !== 'undefined') {
    const xhrProto = globalThis.XMLHttpRequest.prototype as {
      open: (method: string, url: string | URL, ...args: unknown[]) => void
    }
    if (!originalXhrOpen) {
      originalXhrOpen = xhrProto.open
    }

    xhrProto.open = function (this: XMLHttpRequest, _method: string, url: string | URL, ..._rest: unknown[]) {
      const targetUrl = String(url)

      SecurityAuditLogger.log({
        type: 'XHR_ATTEMPT',
        target: targetUrl,
        reason: 'Frontend kodunda doğrudan XMLHttpRequest çağrısı yapılması yasaktır',
      })

      throw new SecurityViolationError('XHR', targetUrl)
    }
  }
}

export function uninstallNetworkSecurityTrap(): void {
  if (originalFetch && typeof globalThis.fetch !== 'undefined') {
    globalThis.fetch = originalFetch
    originalFetch = undefined
  }

  if (typeof globalThis.XMLHttpRequest !== 'undefined' && originalXhrOpen) {
    const xhrProto = globalThis.XMLHttpRequest.prototype as {
      open: (method: string, url: string | URL, ...args: unknown[]) => void
    }
    xhrProto.open = originalXhrOpen
    originalXhrOpen = undefined
  }
}

// ---------------------------------------------------------------------------
// TAURI IPC KOMUT İZİN LİSTESİ (Command Allowlist Enforcement)
// ---------------------------------------------------------------------------

export const ALLOWED_IPC_COMMANDS: ReadonlySet<string> = new Set([
  'proxy_request',
  'flow_discovery_run',
  'flow_generate_script',
  'flow_save_script',
  'flow_generate_audio',
  'flow_prepare_assets',
  'flow_generate_preview',
  'flow_trigger_render',
  'flow_get_job_status',
  'flow_cancel_job',
  'flow_get_active_session',
  'flow_save_active_session',
  'diagnostics_export_bundle',
  'supervisor:terminate_sidecar',
  'supervisor:cleanup_orphans',
  'plugin:clipboard|write_text',
  'plugin:dialog|open',
  'plugin:dialog|save',
  'plugin:fs|read_text_file',
  'plugin:fs|write_text_file',
])

export function isIpcCommandAllowed(command: string): boolean {
  return ALLOWED_IPC_COMMANDS.has(command)
}

export const ALLOWED_PROXY_ROUTE_PREFIXES: readonly string[] = [
  '/health',
  '/api/v1/discovery',
  '/api/v1/script',
  '/api/v1/audio',
  '/api/v1/render',
  '/api/v1/pipeline',
  '/api/v1/assistant',
  '/api/v1/jobs',
  '/api/v1/channels',
  '/api/v1/diagnostics',
  '/api/v1/session',
  '/api/v1/system',
] as const

export const ALLOWED_PROXY_PREFIXES = ALLOWED_PROXY_ROUTE_PREFIXES

export function isProxyRouteAllowed(route: string): boolean {
  if (!route || typeof route !== 'string') return false
  const cleanRoute = route.trim().split('?')[0]
  return ALLOWED_PROXY_ROUTE_PREFIXES.some(
    (prefix) => cleanRoute === prefix || cleanRoute.startsWith(prefix + '/')
  )
}

export function validateProxyRoute(route: string): string {
  if (!isProxyRouteAllowed(route)) {
    SecurityAuditLogger.log({
      type: 'UNAUTHORIZED_IPC',
      target: route,
      reason: `Yetkisiz API proxy rotası: ${route}`,
    })
    throw new SecurityViolationError(
      'CSP',
      route,
      `[PROXY GÜVENLİK İHLALİ] İzin listesi dışı API rotasına proxy isteği reddedildi: ${route}`
    )
  }
  return route
}

/**
 * Güvenli Tauri invoke sarmalayıcısı:
 * İzin listesi dışındaki herhangi bir komut çağrıldığında anında reddeder ve günlüğe kaydeder.
 */
export async function secureInvoke<T>(
  command: string,
  args?: Record<string, unknown>,
  rawInvoker?: (cmd: string, a?: Record<string, unknown>) => Promise<T>
): Promise<T> {
  if (!isIpcCommandAllowed(command)) {
    SecurityAuditLogger.log({
      type: 'UNAUTHORIZED_IPC',
      target: command,
      reason: `Komut izin listesinde bulunamadı: ${command}`,
    })
    const err = new UnauthorizedIpcCommandError(command)
    return Promise.reject(err)
  }

  if (rawInvoker) {
    return args !== undefined ? rawInvoker(command, args) : rawInvoker(command)
  }

  return args !== undefined ? invoke<T>(command, args) : invoke<T>(command)
}

// ---------------------------------------------------------------------------
// GÜVENLİ YEREL VARLIK (ASSET PROTOCOL) DOĞRULAYICISI
// ---------------------------------------------------------------------------

/**
 * Bir URL'in yalnızca Tauri güvenli yerel asset protokolüne ait olup olmadığını denetler.
 * Harici http/https, file:// veya javascript: şemaları kesinlikle reddedilir.
 */
export function isSafeAssetUrl(url: string): boolean {
  if (!url || typeof url !== 'string') return false

  const trimmed = url.trim()

  // 1. XSS ve zararlı betik şemaları
  if (/^(javascript|vbscript|data:text\/html):/i.test(trimmed)) {
    return false
  }

  // 2. Doğrudan dosya sistemi erişimi (file://) Webview'de yasaktır; asset:// zorunludur
  if (/^file:\/\//i.test(trimmed)) {
    return false
  }

  // 3. Harici ağ şemaları (http://, https://, ws://, wss://, ftp://)
  // Tauri asset.localhost istisnası haricinde tüm web URL'leri yasaktır.
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed.startsWith('https://asset.localhost/') || trimmed.startsWith('http://asset.localhost/')
  }

  // 4. İzin verilen güvenli protokoller:
  // - asset://localhost/... veya asset://... (Tauri özel varlık protokolü)
  // - blob:... (Yerel bellek önizleme kaynakları)
  // - data:image/... (Güvenli inline görseller)
  if (trimmed.startsWith('asset://')) {
    return true
  }
  if (trimmed.startsWith('blob:')) {
    return true
  }
  if (trimmed.startsWith('data:image/') && !trimmed.includes('<script')) {
    return true
  }

  return false
}

/**
 * Medya bileşenine atanacak varlık URL'ini denetler ve güvensiz ise hata fırlatır.
 */
export function validateMediaSource(src: string): string {
  if (!isSafeAssetUrl(src)) {
    SecurityAuditLogger.log({
      type: 'UNSAFE_ASSET',
      target: src,
      reason: 'Harici ağ URL veya güvensiz şema tespiti',
    })
    throw new UnsafeAssetSourceError(src, 'Yalnızca Tauri asset:// veya yerel blob kaynakları kullanılabilir')
  }
  return src
}

/**
 * Yerel disk dosya yolunu (C:\... veya renders/...) Tauri WebView2 içinde oynatılabilecek
 * güvenli https://asset.localhost/... protokolüne dönüştürür ve doğrular.
 */
export function toSafeAssetUrl(filePath: string): string {
  if (!filePath || typeof filePath !== 'string') return ''
  const trimmed = filePath.trim()
  if (isSafeAssetUrl(trimmed)) {
    return validateMediaSource(trimmed)
  }

  // Harici ağ veya yasaklı şemalar (http://, https://, file://, javascript:, vb.) doğrudan validateMediaSource ile reddedilir
  if (/^(https?:\/\/|file:\/\/|javascript:|vbscript:|data:|ws:\/\/|wss:\/\/|ftp:\/\/)/i.test(trimmed)) {
    return validateMediaSource(trimmed)
  }

  // Tauri çalışma zamanı convertFileSrc desteği (@tauri-apps/api/core)
  try {
    if (typeof window !== 'undefined' && (window as unknown as { __TAURI_INTERNALS__?: { convertFileSrc?: unknown } }).__TAURI_INTERNALS__?.convertFileSrc) {
      const converted = convertFileSrc(trimmed, 'asset')
      return validateMediaSource(converted)
    }
  } catch {
    // Test veya tarayıcı fallback
  }

  // Windows sürücü harfi (C:\ veya C:/) veya göreli yolu https://asset.localhost/ protokolüne dönüştür
  const normalized = trimmed.replace(/\\/g, '/')
  const cleanPath = normalized.startsWith('/') ? normalized.slice(1) : normalized
  const assetUrl = `https://asset.localhost/${cleanPath}`
  return validateMediaSource(assetUrl)
}

/**
 * CSP Level 3 & CWE-79 Koruma Denetleyicisi:
 * script-src bağlamında data: ve blob: şemaları KESİNLİKLE YASAKTIR.
 * data: ve blob: şemaları img-src veya media-src için yerel önizlemelerde kullanılabilse de,
 * script-src içerisinde izin verilmesi saldırganların rastgele dinamik betik yürütmesine (CSP Bypass) yol açar.
 */
export function isSafeScriptSource(src: string): boolean {
  if (!src || typeof src !== 'string') return false
  const trimmed = src.trim().toLowerCase()

  // CWE-79 / CSP Level 3: data: ve blob: script şemaları kesinlikle reddedilir
  if (trimmed.startsWith('data:') || trimmed.startsWith('blob:')) {
    return false
  }

  // javascript: ve inline XSS vektörleri
  if (trimmed.startsWith('javascript:') || trimmed.startsWith('vbscript:')) {
    return false
  }

  // Harici ağ scriptleri yasaktır
  if (/^https?:\/\//i.test(trimmed)) {
    return false
  }

  // Yalnızca 'self' veya paket içi yerel script yolları geçerlidir
  if (trimmed === "'self'" || trimmed.startsWith('/') || trimmed.startsWith('./')) {
    return true
  }

  return false
}

export function validateScriptSource(src: string): string {
  if (!isSafeScriptSource(src)) {
    SecurityAuditLogger.log({
      type: 'UNSAFE_SCRIPT',
      target: src,
      reason: 'CWE-79 / CSP Level 3: script-src içerisinde data: veya blob: kullanımı yasaktır',
    })
    throw new SecurityViolationError(
      'CSP',
      src,
      `[CSP LEVEL 3 İHLALİ (CWE-79)] script-src bağlamında data: ve blob: kullanımı yasaktır: ${src}`
    )
  }
  return src
}
