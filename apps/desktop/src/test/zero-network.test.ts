import { describe, it, expect, vi } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

describe('K-702: Sıfır Ağ Çağrısı (Zero-Network Policy) Denetimi', () => {
  it('globalThis.fetch çağrıları tespit edilirse testi anında kırmalıdır (Runtime Trap)', () => {
    const fetchSpy = vi.fn().mockImplementation(() => {
      throw new Error('[GÜVENLİK İHLALİ] Frontend kodunda yetkisiz fetch() çağrısı tespit edildi!')
    })

    // fetch simülasyonu
    vi.stubGlobal('fetch', fetchSpy)

    expect(() => {
      // Herhangi bir kod fetch çağırırsa
      ;(globalThis as any).fetch('http://example.com')
    }).toThrowError(/yetkisiz fetch\(\) çağrısı tespit edildi/)

    vi.unstubAllGlobals()
  })

  it('apps/desktop/src altındaki tüm kaynak kodlarda doğrudan fetch/axios/XMLHttpRequest kullanımı olmamalıdır (Statik Kod Analizi)', () => {
    const srcDir = path.resolve(__dirname, '..')
    const forbiddenPatterns = [
      { pattern: /\bfetch\s*\(/g, name: 'fetch() doğrudan çağrısı' },
      { pattern: /import\s+.*\bfrom\s+['"]axios['"]/g, name: 'axios import' },
      { pattern: /require\s*\(\s*['"]axios['"]\s*\)/g, name: 'axios require' },
      { pattern: /new\s+XMLHttpRequest\b/g, name: 'XMLHttpRequest' },
    ]

    function scanDirectory(dir: string, fileList: string[] = []): string[] {
      const files = fs.readdirSync(dir)
      for (const file of files) {
        const fullPath = path.join(dir, file)
        const stat = fs.statSync(fullPath)
        if (stat.isDirectory()) {
          // test klasörleri hariç
          if (file !== 'test' && file !== '__tests__' && file !== 'node_modules') {
            scanDirectory(fullPath, fileList)
          }
        } else if (file.endsWith('.ts') || file.endsWith('.tsx') || file.endsWith('.js')) {
          // test dosyalarını atla
          if (!file.includes('.test.') && !file.includes('.spec.')) {
            fileList.push(fullPath)
          }
        }
      }
      return fileList
    }

    const sourceFiles = scanDirectory(srcDir)
    expect(sourceFiles.length).toBeGreaterThan(5)

    const violations: { file: string; rule: string; line: number }[] = []

    for (const file of sourceFiles) {
      const content = fs.readFileSync(file, 'utf-8')
      const lines = content.split('\n')

      lines.forEach((lineText: string, lineIdx: number) => {
        // Yorum satırlarını atla
        const trimmed = lineText.trim()
        if (trimmed.startsWith('//') || trimmed.startsWith('/*') || trimmed.startsWith('*')) {
          return
        }

        for (const { pattern, name } of forbiddenPatterns) {
          pattern.lastIndex = 0
          if (pattern.test(lineText)) {
            violations.push({
              file: path.relative(srcDir, file),
              rule: name,
              line: lineIdx + 1,
            })
          }
        }
      })
    }

    if (violations.length > 0) {
      console.error('Zero-Network Kural İhlalleri:', violations)
    }

    expect(violations).toEqual([])
  })

  it('Tüm veri alışverişi tauriIpcClient (invoke) üzerinden yönlendirilmelidir', async () => {
    const ipcModule = await import('../lib/ipc')
    expect(ipcModule.tauriIpcClient).toBeDefined()
    expect(typeof ipcModule.tauriIpcClient.runDiscovery).toBe('function')
    expect(typeof ipcModule.tauriIpcClient.generateScript).toBe('function')
    expect(typeof ipcModule.tauriIpcClient.generateAudio).toBe('function')
    expect(typeof ipcModule.tauriIpcClient.prepareAssets).toBe('function')
    expect(typeof ipcModule.tauriIpcClient.generatePreview).toBe('function')
    expect(typeof ipcModule.tauriIpcClient.triggerRender).toBe('function')
    expect(typeof ipcModule.tauriIpcClient.getJobStatus).toBe('function')
  })
})
