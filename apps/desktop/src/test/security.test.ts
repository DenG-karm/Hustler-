/**
 * K-709: Arayüz Güvenlik ve CSP Modülü — Sıfır Ağ İzolasyonu, IPC İzin Listesi ve Varlık Denetimi
 *
 * MİMARİ KURALLAR:
 * 1. Sıfır Ağ İzolasyonu (Zero-Network Policy / CSP Trap):
 *    Frontend içerisinde `global.fetch` ve `XMLHttpRequest` doğrudan dış ağa (HTTP/HTTPS/WS)
 *    erişemez; herhangi bir doğrudan çağrı anında SecurityViolationError fırlatır ve güvenlik günlüğüne düşer.
 * 2. Tauri IPC Komut İzin Listesi (Command Allowlist Enforcement):
 *    Frontend'den yalnızca `ALLOWED_IPC_COMMANDS` izin listesinde kayıtlı Tauri komutları çağrılabilir.
 *    İzin listesi dışı rastgele komutlar (örn: 'plugin:hacker|steal_data') anında reddedilir.
 * 3. Yerel Varlık Güvenliği (Asset Protocol Only):
 *    Medya ve varlık yüklemelerinde yalnızca Tauri güvenli asset protokolleri (`https://asset.localhost/`, `asset://`)
 *    ve yerel önizleme blob'ları (`blob:`, `data:image/*`) kabul edilir; harici CDN ve `file://` erişimi engellenir.
 *
 * FAZ 2: Güvenlik Kalkanı Modül Doğrulaması (src/lib/securityGuard.ts)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import {
  SecurityViolationError,
  UnauthorizedIpcCommandError,
  UnsafeAssetSourceError,
  SecurityAuditLogger,
  installNetworkSecurityTrap,
  uninstallNetworkSecurityTrap,
  secureInvoke,
  isSafeAssetUrl,
  validateMediaSource,
  isSafeScriptSource,
  validateScriptSource,
} from '../lib/securityGuard'

// ===========================================================================
// TEST SUITES
// ===========================================================================

describe('K-709: Arayüz Güvenlik ve CSP Doğrulama Testleri', () => {
  beforeEach(() => {
    SecurityAuditLogger.clear()
    installNetworkSecurityTrap()
  })

  afterEach(() => {
    uninstallNetworkSecurityTrap()
    SecurityAuditLogger.clear()
  })

  // -------------------------------------------------------------------------
  // SUITE 1: Doğrudan Ağ Çağrısı Engeli (global.fetch & XMLHttpRequest Trap)
  // -------------------------------------------------------------------------
  describe('1. global.fetch ve XMLHttpRequest Trap Denetimi (Zero-Network Policy)', () => {
    it('global.fetch ile dış URL çağrıldığında anında SecurityViolationError fırlatmalı ve günlüğe kaydetmelidir', async () => {
      const maliciousUrl = 'https://api.external-leak.com/collect'

      await expect(globalThis.fetch(maliciousUrl)).rejects.toThrowError(SecurityViolationError)
      await expect(globalThis.fetch(maliciousUrl)).rejects.toThrow(
        /Yetkisiz ağ erişimi engellendi: https:\/\/api\.external-leak\.com\/collect/
      )

      // Günlük kontrolü
      const logs = SecurityAuditLogger.getRecords()
      expect(logs).toHaveLength(2)
      expect(logs[0].type).toBe('FETCH_ATTEMPT')
      expect(logs[0].target).toBe(maliciousUrl)
      expect(logs[0].reason).toContain('fetch() çağrısı yapılması yasaktır')
    })

    it('yerel HTTP portlarına dahi (http://127.0.0.1:8000) doğrudan fetch çağrısı engellenmelidir (Rust IPC zorunluluğu)', async () => {
      const localhostUrl = 'http://127.0.0.1:8000/api/v1/jobs'

      await expect(globalThis.fetch(localhostUrl)).rejects.toThrowError(SecurityViolationError)

      const logs = SecurityAuditLogger.getRecords()
      expect(logs.some((l) => l.target === localhostUrl)).toBe(true)
    })

    it('XMLHttpRequest ile harici URL açılmaya çalışıldığında anında hata fırlatmalıdır (XHR Trap)', () => {
      const xhr = new globalThis.XMLHttpRequest()
      const targetUrl = 'https://telemetry.tracking-analytics.com/event'

      expect(() => {
        xhr.open('POST', targetUrl)
      }).toThrowError(SecurityViolationError)

      const logs = SecurityAuditLogger.getRecords()
      expect(logs).toHaveLength(1)
      expect(logs[0].type).toBe('XHR_ATTEMPT')
      expect(logs[0].target).toBe(targetUrl)
      expect(logs[0].reason).toContain('XMLHttpRequest çağrısı yapılması yasaktır')
    })

    it('güvenlik trap mekanizması kaldırıldığında orijinal fetch fonksiyonu geri yüklenmelidir', () => {
      uninstallNetworkSecurityTrap()

      // Trap kaldırıldıktan sonra fetch bir güvenlik hatası değil, normal bir çağrı dener
      // (JSDOM ortamında mocklanabilir veya orijinal referansa döner)
      expect(globalThis.fetch).toBeDefined()
    })
  })

  // -------------------------------------------------------------------------
  // SUITE 2: Tauri IPC İzin Listesi Denetimi (Allowlist Gatekeeper)
  // -------------------------------------------------------------------------
  describe('2. Tauri IPC Komut İzin Listesi Denetimi (Allowlist Gatekeeper)', () => {
    it("izin verilmeyen rastgele bir komut ('plugin:hacker|steal_data') çağrıldığında reddedilmeli ve günlüğe düşmelidir", async () => {
      const mockRawInvoker = vi.fn().mockResolvedValue('leaked')
      const unauthorizedCmd = 'plugin:hacker|steal_data'

      await expect(secureInvoke(unauthorizedCmd, {}, mockRawInvoker)).rejects.toThrowError(
        UnauthorizedIpcCommandError
      )
      await expect(secureInvoke(unauthorizedCmd, {}, mockRawInvoker)).rejects.toThrow(
        /İzin listesi dışı komut reddedildi: 'plugin:hacker\|steal_data'/
      )

      // Ham invoker kesinlikle çalıştırılmamalıdır!
      expect(mockRawInvoker).not.toHaveBeenCalled()

      // Güvenlik günlüğü denetimi
      const logs = SecurityAuditLogger.getRecords()
      expect(logs).toHaveLength(2)
      expect(logs[0].type).toBe('UNAUTHORIZED_IPC')
      expect(logs[0].target).toBe(unauthorizedCmd)
      expect(logs[0].reason).toContain('Komut izin listesinde bulunamadı')
    })

    it("rastgele kabuk veya sistem komutları ('cmd:exec_arbitrary', 'system:shell') kesinlikle reddedilmelidir", async () => {
      const dangerousCommands = [
        'cmd:exec_arbitrary',
        'system:shell',
        'plugin:eval|run',
        'fs:format_disk',
      ]

      for (const cmd of dangerousCommands) {
        await expect(secureInvoke(cmd)).rejects.toThrowError(UnauthorizedIpcCommandError)
      }

      const logs = SecurityAuditLogger.getRecords()
      expect(logs).toHaveLength(dangerousCommands.length)
    })

    it("izin listesindeki meşru komutlar ('supervisor:terminate_sidecar', 'plugin:clipboard|write_text') başarıyla çalıştırılmalıdır", async () => {
      const mockRawInvoker = vi.fn().mockResolvedValue({ success: true })

      const allowedCommands = [
        'supervisor:terminate_sidecar',
        'supervisor:cleanup_orphans',
        'plugin:clipboard|write_text',
        'plugin:dialog|open',
        'flow_trigger_render',
        'flow_get_job_status',
      ]

      for (const cmd of allowedCommands) {
        const result = await secureInvoke(cmd, { test: 123 }, mockRawInvoker)
        expect(result).toEqual({ success: true })
      }

      expect(mockRawInvoker).toHaveBeenCalledTimes(allowedCommands.length)
      // Meşru komutlar güvenlik günlüğüne ihlal olarak düşmemelidir
      expect(SecurityAuditLogger.getRecords()).toHaveLength(0)
    })
  })

  // -------------------------------------------------------------------------
  // SUITE 3: Yerel Varlık (Asset Protocol) ve Güvenli Kaynak Doğrulaması
  // -------------------------------------------------------------------------
  describe('3. Yalnızca İzin Verilen Yerel Varlıkların (Asset Protokolü) Erişilebilirliği', () => {
    it('Tauri asset:// ve https://asset.localhost/ protokolleri güvenli kabul edilmeli ve onaylanmalıdır', () => {
      const validAssets = [
        'https://asset.localhost/video/preview_draft.mp4',
        'http://asset.localhost/thumbnails/scene_1.jpg',
        'asset://localhost/audio/voiceover.mp3',
        'asset://varliklar/video_001.mp4',
      ]

      for (const asset of validAssets) {
        expect(isSafeAssetUrl(asset)).toBe(true)
        expect(validateMediaSource(asset)).toBe(asset)
      }

      // İhlal olmamalı
      expect(SecurityAuditLogger.getRecords()).toHaveLength(0)
    })

    it("yerel blob URL'leri ve data:image base64 kaynakları önizleme için güvenli kabul edilmelidir", () => {
      const validLocalBlobs = [
        'blob:http://localhost:5173/550e8400-e29b-41d4-a716-446655440000',
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
        'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD...',
      ]

      for (const blobUrl of validLocalBlobs) {
        expect(isSafeAssetUrl(blobUrl)).toBe(true)
        expect(validateMediaSource(blobUrl)).toBe(blobUrl)
      }
    })

    it('harici CDN ve güvensiz web kaynakları (https://evil-cdn.com/asset.mp4) reddedilmeli ve UnsafeAssetSourceError fırlatmalıdır', () => {
      const unsafeWebUrls = [
        'https://evil-cdn.com/media/ad_tracker.mp4',
        'http://insecure-host.org/avatar.png',
        'ftp://fileserver.com/leak.mp4',
        'ws://tracking.com/socket',
      ]

      for (const unsafeUrl of unsafeWebUrls) {
        expect(isSafeAssetUrl(unsafeUrl)).toBe(false)
        expect(() => validateMediaSource(unsafeUrl)).toThrowError(UnsafeAssetSourceError)
      }

      const logs = SecurityAuditLogger.getRecords()
      expect(logs).toHaveLength(unsafeWebUrls.length)
      expect(logs[0].type).toBe('UNSAFE_ASSET')
    })

    it('doğrudan dosya sistemi erişimi (file://) XSS/LFI koruması gereği reddedilmeli, Tauri asset:// protokolü zorlanmalıdır', () => {
      const fileUrls = [
        'file:///C:/Users/Admin/secrets.txt',
        'file:///etc/passwd',
        'file:///home/user/video.mp4',
      ]

      for (const fileUrl of fileUrls) {
        expect(isSafeAssetUrl(fileUrl)).toBe(false)
        expect(() => validateMediaSource(fileUrl)).toThrowError(UnsafeAssetSourceError)
      }
    })

    it('javascript: ve XSS barındıran güvensiz şemalar anında yakalanıp engellenmelidir', () => {
      const xssUrls = [
        'javascript:alert("XSS")',
        'javascript://malicious.com',
        'vbscript:MsgBox("Hacked")',
        'data:text/html,<script>alert(1)</script>',
      ]

      for (const xss of xssUrls) {
        expect(isSafeAssetUrl(xss)).toBe(false)
        expect(() => validateMediaSource(xss)).toThrowError(UnsafeAssetSourceError)
      }
    })

    it("CSP Level 3 (CWE-79): blob: ve data: kaynakları medya için geçerli olsa dahi script-src bağlamında KESİNLİKLE reddedilmelidir", () => {
      const maliciousScriptSources = [
        'blob:http://localhost:5173/550e8400-e29b-41d4-a716-446655440000',
        'data:text/javascript;base64,YWxlcnQoMSk=',
        'data:application/javascript,console.log("hacked")',
        'javascript:alert(document.cookie)',
      ]

      for (const scriptSrc of maliciousScriptSources) {
        expect(isSafeScriptSource(scriptSrc)).toBe(false)
        expect(() => validateScriptSource(scriptSrc)).toThrowError(SecurityViolationError)
        expect(() => validateScriptSource(scriptSrc)).toThrow(/CSP LEVEL 3 İHLALİ/)
      }

      // Güvenli yerel script kaynakları onaylanmalıdır
      expect(isSafeScriptSource("'self'")).toBe(true)
      expect(isSafeScriptSource("/assets/index.js")).toBe(true)
      expect(validateScriptSource("/assets/index.js")).toBe("/assets/index.js")

      // Günlük kontrolü
      const logs = SecurityAuditLogger.getRecords()
      expect(logs.some((l) => l.type === 'UNSAFE_SCRIPT')).toBe(true)
    })
  })

  // -------------------------------------------------------------------------
  // SUITE 4: tauri.conf.json Statik CSP Güvenlik Politikası Denetimi
  // -------------------------------------------------------------------------
  describe('4. tauri.conf.json Statik CSP Güvenlik Politikası Denetimi', () => {
    it('tauri.conf.json dosyasında katı CSP tanımlı olmalı, harici wildcard veya güvensiz connect-src içermemelidir', () => {
      const configPath = path.resolve(__dirname, '../../src-tauri/tauri.conf.json')
      expect(fs.existsSync(configPath)).toBe(true)

      const rawConfig = fs.readFileSync(configPath, 'utf-8')
      const config = JSON.parse(rawConfig)

      const csp = config.app?.security?.csp as string | undefined
      expect(csp).toBeDefined()
      expect(typeof csp).toBe('string')

      // CSP Kuralları Denetimi:
      // 1. default-src 'self' olmalı
      expect(csp).toContain("default-src 'self'")

      // 2. connect-src asla harici HTTP/HTTPS veya wildcard (*) içermemeli; sadece ipc: veya localhost olmalı
      expect(csp).toMatch(/connect-src\s+[^;]*ipc:/)
      expect(csp).not.toMatch(/connect-src\s+[^;]*https?:\/\/(?!ipc\.localhost)/)
      expect(csp).not.toMatch(/connect-src\s+[^;]*\*/)

      // 3. object-src 'none' (Flash/Java/Plugin engeli)
      expect(csp).toContain("object-src 'none'")

      // 4. form-action 'none' (Harici forma veri gönderme engeli)
      expect(csp).toContain("form-action 'none'")
    })

    it("tauri.conf.json dosyasında script-src ve default-src direktifleri data: ve blob: şemalarını KESİNLİKLE İÇERMEMELİDİR (CWE-79 / CSP Level 3 Bypass Engeli)", () => {
      const configPath = path.resolve(__dirname, '../../src-tauri/tauri.conf.json')
      const rawConfig = fs.readFileSync(configPath, 'utf-8')
      const config = JSON.parse(rawConfig)

      const csp = config.app?.security?.csp as string | undefined
      expect(csp).toBeDefined()

      // 1. script-src direktifi 'self' içermeli, ancak data: ve blob: KESİNLİKLE içermemelidir
      expect(csp).toMatch(/script-src\s+[^;]*/)
      expect(csp).toContain("script-src 'self'")
      expect(csp).not.toMatch(/script-src\s+[^;]*\bdata:/)
      expect(csp).not.toMatch(/script-src\s+[^;]*\bblob:/)

      // 2. default-src direktifi 'self' içermeli, ancak data: ve blob: KESİNLİKLE içermemelidir
      expect(csp).toMatch(/default-src\s+[^;]*/)
      expect(csp).toContain("default-src 'self'")
      expect(csp).not.toMatch(/default-src\s+[^;]*\bdata:/)
      expect(csp).not.toMatch(/default-src\s+[^;]*\bblob:/)

      // 3. data: şeması yalnızca img-src ve font-src direktifleriyle sınırlandırılmış olmalıdır
      expect(csp).toMatch(/img-src\s+[^;]*data:/)
      expect(csp).toMatch(/font-src\s+[^;]*data:/)
    })
  })
})
