/**
 * K-705: Toplu Prompt Kopyalama — Snapshot ve Tauri Pano Testi
 *
 * Mimari Kurallar:
 * 1. navigator.clipboard YASAKTIR. Kopyalama yalnızca Tauri IPC üzerinden yapılır.
 * 2. buildClipboardPrompt() saf (pure) fonksiyon; Compact Key-Value formatı snapshot ile sabitlenir.
 * 3. clipboardWrite() Tauri plugin-clipboard-manager invoke çağrısını sarmalar.
 * 4. Herhangi bir token israfı veya format değişikliği snapshot farkıyla CI'da anında yakalanır.
 *
 * JSDOM/Node uyumluluk notu:
 * @tauri-apps/api/core gerçek Tauri WebView dışında çalışmaz.
 * vi.mock() ile module-level hoist yapılarak statik import güvence altına alınır.
 * Dynamic import() kullanımı kesinlikle yasak — worker timeout'a yol açar.
 */

import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ---------------------------------------------------------------------------
// @tauri-apps/api/core → module-level mock (hoisted, dynamic import YASAK)
// ---------------------------------------------------------------------------
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn().mockResolvedValue(undefined),
}))

import { invoke } from '@tauri-apps/api/core'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import {
  type FlowSnapshot,
  buildClipboardPrompt,
  clipboardWrite,
  extractFlowSnapshot,
} from '../lib/clipboard'
import { ScriptScreen } from '../components/flow/ScriptScreen'
import { useFlowStore } from '../store/flowStore'

// ---------------------------------------------------------------------------
// Test Fixture — merkezi, tekrarı önleyen veri seti
// ---------------------------------------------------------------------------

const FIXTURE_SNAPSHOT: FlowSnapshot = {
  topic: 'Kuantum Hesaplama ve Kriptografi',
  selectedIdea: {
    id: 'vid_quantum_001',
    title: "RSA Şifreleme Çöküyor mu?",
    hook: "Kuantum bilgisayarlar RSA'yı 8 saatte kırdı!",
    score: 97,
  },
  script: {
    id: 'scr_quantum_k705',
    title: "RSA Şifreleme Çöküyor mu?",
    hook: "Kuantum bilgisayarlar RSA'yı 8 saatte kırdı!",
    fullText:
      'Kuantum hesaplama dünyası yeni bir dönüm noktasına ulaştı. ' +
      "IBM'nin 1000 qubitlik işlemcisi, 2048-bit RSA şifrelemesini teorik olarak kırabilecek kapasiteye erişti. " +
      'Bu gelişme internet güvenliğinin temelini sarsmaktadır. ' +
      'Kriptografi uzmanları post-kuantum algoritmalarına geçişi hızlandırıyor.',
    scenes: [
      {
        order: 1,
        narration: 'Kuantum bilgisayarlar artık gerçek tehdittir!',
        visualPrompt: 'Dramatic quantum computer render, neon blue, 9:16 vertical, cinematic',
      },
      {
        order: 2,
        narration: "IBM'nin 1000 qubit işlemcisi RSA şifrelemesini aşıyor.",
        visualPrompt: 'Infographic: qubit vs classical bit, dark background, vertical',
      },
      {
        order: 3,
        narration: 'Post-kuantum kriptografi çağı başlıyor. Hazır mısınız?',
        visualPrompt: 'Call to action animation, subscribe button, youtube shorts style',
      },
    ],
    claims: [
      {
        id: 'c1',
        text: "IBM'nin 1000 qubit işlemcisi 2023'te tanıtılmıştır.",
        verified: true,
      },
      {
        id: 'c2',
        text: 'RSA-2048 kırılması için henüz pratik bir kuantum bilgisayar mevcut değildir.',
        verified: true,
      },
      {
        id: 'c3',
        text: "NIST 2024'te post-kuantum şifreleme standartlarını onayladı.",
        verified: false,
      },
    ],
  },
  audioVoiceId: 'tr-TR-Standard-A',
  renderProfile: 'DRAFT',
}

// ---------------------------------------------------------------------------
// SUITE 1: Compact Key-Value Format — Snapshot Testi
// ---------------------------------------------------------------------------
describe('K-705: buildClipboardPrompt — Compact Key-Value Format Snapshot', () => {
  it('tam veri setiyle beklenen Compact Key-Value formatını üretmeli (snapshot sabitler)', () => {
    const output = buildClipboardPrompt(FIXTURE_SNAPSHOT)
    // İlk çalıştırmada .snap dosyası yazılır; sonraki çalıştırmalarda karşılaştırılır.
    // Format değişikliği = token israfı veya yapı bozulması → CI kırar.
    expect(output).toMatchSnapshot()
  })

  it('her üst-düzey satır KEY: formatında olmalı', () => {
    const output = buildClipboardPrompt(FIXTURE_SNAPSHOT)
    // Üst-düzey satırlar: KEY:VALUE veya KEY:\n formatı
    const topLines = output.split('\n').filter((l) => !l.startsWith('[') && l.trim() !== '')
    for (const line of topLines) {
      expect(line).toMatch(/^[A-Z_]+:/)
    }
  })

  it('buildClipboardPrompt senkron ve saf fonksiyondur — Promise döndürmemeli', () => {
    const result = buildClipboardPrompt(FIXTURE_SNAPSHOT)
    expect((result as unknown) instanceof Promise).toBe(false)
    expect(typeof result).toBe('string')
  })

  it('sahneler order alanına göre sıralanmış çıktı üretmeli', () => {
    const shuffledSnapshot: FlowSnapshot = {
      ...FIXTURE_SNAPSHOT,
      script: {
        ...FIXTURE_SNAPSHOT.script,
        scenes: [
          { order: 3, narration: 'Kapanış', visualPrompt: 'Closing shot' },
          { order: 1, narration: 'Açılış', visualPrompt: 'Opening shot' },
          { order: 2, narration: 'Gövde', visualPrompt: 'Main content shot' },
        ],
      },
    }

    const output = buildClipboardPrompt(shuffledSnapshot)
    const scenesBlock = output.split('SCENES:\n')[1]?.split('\nCLAIMS:')[0] ?? ''
    const scenesLines = scenesBlock.split('\n').filter(Boolean)

    expect(scenesLines[0]).toMatch(/^\[1\]/)
    expect(scenesLines[1]).toMatch(/^\[2\]/)
    expect(scenesLines[2]).toMatch(/^\[3\]/)
  })

  it('doğrulanmış iddialar [OK], doğrulanmamışlar [PENDING] öneki almalı', () => {
    const output = buildClipboardPrompt(FIXTURE_SNAPSHOT)
    const claimsBlock = output.split('CLAIMS:\n')[1]?.split('\nVOICE:')[0] ?? ''

    expect(claimsBlock).toContain("[OK] IBM'nin 1000 qubit işlemcisi")
    expect(claimsBlock).toContain('[OK] RSA-2048 kırılması')
    expect(claimsBlock).toContain("[PENDING] NIST 2024")
  })

  it('topic ve script başındaki/sonundaki boşluklar normalize edilmeli', () => {
    const whitespaceSnapshot: FlowSnapshot = {
      ...FIXTURE_SNAPSHOT,
      topic: '  Boşluklu Konu  ',
      script: {
        ...FIXTURE_SNAPSHOT.script,
        title: '  Boşluklu Başlık   ',
        fullText: '   Senaryo metninin başı ve sonu.   ',
      },
    }

    const output = buildClipboardPrompt(whitespaceSnapshot)
    expect(output).toContain('TOPIC:Boşluklu Konu')
    expect(output).toContain('SCRIPT_TITLE:Boşluklu Başlık')
    expect(output).toContain('SCRIPT_TEXT:Senaryo metninin başı ve sonu.')
    expect(output).not.toMatch(/TOPIC:\s{2,}/)
  })

  it('sahne ve iddia listesi boş olduğunda çökmemeli, boş blok üretmeli', () => {
    const emptySnapshot: FlowSnapshot = {
      ...FIXTURE_SNAPSHOT,
      script: { ...FIXTURE_SNAPSHOT.script, scenes: [], claims: [] },
    }

    expect(() => buildClipboardPrompt(emptySnapshot)).not.toThrow()
    const output = buildClipboardPrompt(emptySnapshot)
    expect(output).toContain('SCENES:\n')
    expect(output).toContain('CLAIMS:\n')
  })

  it('DRAFT ve FINAL render profilleri çıktıda doğru yansımalı', () => {
    const draftOutput = buildClipboardPrompt({ ...FIXTURE_SNAPSHOT, renderProfile: 'DRAFT' })
    const finalOutput = buildClipboardPrompt({ ...FIXTURE_SNAPSHOT, renderProfile: 'FINAL' })

    expect(draftOutput).toContain('RENDER:DRAFT')
    expect(finalOutput).toContain('RENDER:FINAL')
  })

  it('buildClipboardPrompt çağrısı navigator.clipboard\'a dokunmamalı', () => {
    const navigatorClipboardSpy = vi.fn()
    Object.defineProperty(navigator, 'clipboard', {
      get: () => ({ writeText: navigatorClipboardSpy }),
      configurable: true,
    })

    buildClipboardPrompt(FIXTURE_SNAPSHOT)

    expect(navigatorClipboardSpy).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// SUITE 2: Tauri Native Clipboard — clipboardWrite Mock Testi
// ---------------------------------------------------------------------------
describe('K-705: clipboardWrite — Tauri Native Clipboard (navigator.clipboard yasak)', () => {
  const mockInvoke = invoke as ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('clipboardWrite, Tauri invoke("plugin:clipboard|write_text") ile çağrılmalıdır', async () => {
    const testText = 'TOPIC:Test\nSCRIPT_ID:scr_001'
    await clipboardWrite(testText)

    expect(mockInvoke).toHaveBeenCalledTimes(1)
    expect(mockInvoke).toHaveBeenCalledWith('plugin:clipboard|write_text', { text: testText })
  })

  it('navigator.clipboard.writeText kesinlikle çağrılmamalıdır', async () => {
    const navigatorWriteSpy = vi.fn()
    Object.defineProperty(navigator, 'clipboard', {
      get: () => ({ writeText: navigatorWriteSpy }),
      configurable: true,
    })

    await clipboardWrite('herhangi bir metin')

    expect(navigatorWriteSpy).not.toHaveBeenCalled()
    expect(mockInvoke).toHaveBeenCalledWith('plugin:clipboard|write_text', expect.any(Object))
  })

  it('Tauri invoke başarısız olduğunda hata fırlatmalı, sessizce yutmamalıdır', async () => {
    mockInvoke.mockRejectedValueOnce(new Error('Tauri: pano erişim izni reddedildi'))

    await expect(clipboardWrite('test')).rejects.toThrow('Tauri: pano erişim izni reddedildi')
  })

  it('boş string ile çağrıldığında Tauri invoke yine de tetiklenmeli', async () => {
    await clipboardWrite('')
    expect(mockInvoke).toHaveBeenCalledWith('plugin:clipboard|write_text', { text: '' })
  })

  it('buildClipboardPrompt çıktısı clipboardWrite\'e aktarıldığında invoke doğru payload almalı', async () => {
    const promptText = buildClipboardPrompt(FIXTURE_SNAPSHOT)
    await clipboardWrite(promptText)

    const [command, args] = mockInvoke.mock.calls[0] as [string, { text: string }]
    expect(command).toBe('plugin:clipboard|write_text')
    expect(args.text).toBe(promptText)
    expect(args.text).toContain('TOPIC:Kuantum Hesaplama ve Kriptografi')
    expect(args.text).toContain('SCRIPT_ID:scr_quantum_k705')
  })
})

// ---------------------------------------------------------------------------
// SUITE 3: Sıfır Web Clipboard API — Zero Web API Policy
// ---------------------------------------------------------------------------
describe('K-705: Sıfır Web Clipboard API — Zero Web API Policy', () => {
  it('navigator.clipboard undefined olsa dahi buildClipboardPrompt çökmemeli', () => {
    const originalDescriptor = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
    Object.defineProperty(navigator, 'clipboard', {
      get: () => undefined,
      configurable: true,
    })

    expect(() => buildClipboardPrompt(FIXTURE_SNAPSHOT)).not.toThrow()

    if (originalDescriptor) {
      Object.defineProperty(navigator, 'clipboard', originalDescriptor)
    }
  })

  it('buildClipboardPrompt async değil, senkron tamamlanmalı', () => {
    const result = buildClipboardPrompt(FIXTURE_SNAPSHOT)
    expect((result as unknown) instanceof Promise).toBe(false)
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------
// SUITE 4: extractFlowSnapshot — FlowState Durumundan Eşleme Testi
// ---------------------------------------------------------------------------
describe('K-705: extractFlowSnapshot — FlowState Durumundan Eşleme', () => {
  it('boş veya eksik state ile çağrıldığında güvenli varsayılanlarla FlowSnapshot üretmeli', () => {
    const snapshot = extractFlowSnapshot({})
    expect(snapshot.topic).toBe('')
    expect(snapshot.selectedIdea.id).toBe('')
    expect(snapshot.script.id).toBe('')
    expect(snapshot.script.scenes).toEqual([])
    expect(snapshot.script.claims).toEqual([])
    expect(snapshot.audioVoiceId).toBe('tr-TR-Standard-A')
    expect(snapshot.renderProfile).toBe('DRAFT')
  })

  it('dolu store verisini tam ve doğru şekilde FlowSnapshot nesnesine eşlemeli', () => {
    const mockState = {
      topic: ' Yapay Zeka Devrimi ',
      selectedIdea: {
        id: 'idea_42',
        title: 'AGI Ne Zaman Geliyor?',
        hook: '2027 tahminleri şaşırttı!',
        score: 95,
      },
      script: {
        id: 'scr_42',
        title: 'AGI Senaryosu',
        hook: 'Kanca',
        fullText: 'Metin',
        scenes: [{ order: 1, narration: 'Giriş', visualPrompt: 'Robot görseli' }],
        claims: [{ id: 'cl_1', text: 'İddia 1', verified: true }],
        isApproved: true,
      },
      audio: {
        scriptId: 'scr_42',
        voiceId: 'tr-TR-Neural2-A',
        audioPath: '/tmp/audio.wav',
        durationSeconds: 15,
        isGenerated: true,
      },
      render: {
        jobId: 'job_1',
        profile: 'FINAL' as const,
        status: 'IDLE' as const,
        progress: 0,
        outputPath: null,
        error: null,
      },
    }

    const snapshot = extractFlowSnapshot(mockState as any)
    expect(snapshot.topic).toBe('Yapay Zeka Devrimi')
    expect(snapshot.selectedIdea.id).toBe('idea_42')
    expect(snapshot.selectedIdea.score).toBe(95)
    expect(snapshot.script.id).toBe('scr_42')
    expect(snapshot.script.scenes).toHaveLength(1)
    expect(snapshot.script.claims[0].verified).toBe(true)
    expect(snapshot.audioVoiceId).toBe('tr-TR-Neural2-A')
    expect(snapshot.renderProfile).toBe('FINAL')
  })
})

// ---------------------------------------------------------------------------
// SUITE 5: UI Entegrasyonu — ScriptScreen Üzerinden Prompt Kopyalama ve Hata Yönetimi
// ---------------------------------------------------------------------------
describe('K-705: UI Entegrasyonu — ScriptScreen Prompt Kopyalama', () => {
  const mockInvoke = invoke as ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    useFlowStore.getState().resetFlow()
    // Test senaryosu için store durumunu hazırla
    useFlowStore.setState({
      topic: 'Kuantum Hesaplama ve Kriptografi',
      selectedIdea: FIXTURE_SNAPSHOT.selectedIdea,
      script: {
        id: FIXTURE_SNAPSHOT.script.id,
        title: FIXTURE_SNAPSHOT.script.title,
        hook: FIXTURE_SNAPSHOT.script.hook,
        fullText: FIXTURE_SNAPSHOT.script.fullText,
        scenes: FIXTURE_SNAPSHOT.script.scenes,
        claims: FIXTURE_SNAPSHOT.script.claims,
        isApproved: false,
      },
      audio: {
        scriptId: FIXTURE_SNAPSHOT.script.id,
        voiceId: FIXTURE_SNAPSHOT.audioVoiceId,
        audioPath: null,
        durationSeconds: 0,
        isGenerated: false,
      },
      render: {
        jobId: null,
        profile: FIXTURE_SNAPSHOT.renderProfile,
        status: 'IDLE',
        progress: 0,
        outputPath: null,
        error: null,
      },
    })
  })

  it('ScriptScreen üzerindeki "Promptu Kopyala" butonuna tıklandığında clipboardWrite tetiklenmeli ve başarı Toast eklenmeli', async () => {
    render(React.createElement(ScriptScreen))

    const copyBtn = screen.getByTestId('copy-prompt-btn')
    expect(copyBtn).toBeInTheDocument()
    expect(copyBtn).toHaveTextContent('Promptu Kopyala')

    fireEvent.click(copyBtn)

    await waitFor(() => {
      expect(mockInvoke).toHaveBeenCalledWith(
        'plugin:clipboard|write_text',
        expect.objectContaining({ text: expect.stringContaining('TOPIC:Kuantum Hesaplama ve Kriptografi') })
      )
    })

    // Store toasts listesinde başarı toast'ı yer almalı
    const toasts = useFlowStore.getState().toasts
    expect(toasts.some((t) => t.code === 'PROMPT_COPIED' && t.status === 200)).toBe(true)

    // Buton metni başarı durumuna geçmeli
    await waitFor(() => {
      expect(copyBtn).toHaveTextContent('✓ Kopyalandı')
    })
  })

  it('Rust IPC invoke hata fırlatırsa hata sessizce yutulmamalı, UI ve Toast üzerinde gösterilmeli', async () => {
    mockInvoke.mockRejectedValueOnce(new Error('Rust IPC: Pano kilitli veya erişilemez!'))

    render(React.createElement(ScriptScreen))

    const copyBtn = screen.getByTestId('copy-prompt-btn')
    fireEvent.click(copyBtn)

    // UI'daki hata banner'ı görünür olmalı
    await waitFor(() => {
      expect(screen.getByTestId('clipboard-error-banner')).toBeInTheDocument()
    })
    expect(screen.getByTestId('clipboard-error-banner')).toHaveTextContent('Rust IPC: Pano kilitli veya erişilemez!')

    // Store toasts listesinde hata toast'ı yer almalı
    const toasts = useFlowStore.getState().toasts
    expect(toasts.some((t) => t.code === 'CLIPBOARD_ERROR' && t.status === 500)).toBe(true)
  })

  it('UI butonuna tıklama sırasında navigator.clipboard kesinlikle çağrılmamalıdır (Sıfır Web API Kuralı)', async () => {
    const navigatorWriteSpy = vi.fn()
    Object.defineProperty(navigator, 'clipboard', {
      get: () => ({ writeText: navigatorWriteSpy }),
      configurable: true,
    })

    render(React.createElement(ScriptScreen))
    const copyBtn = screen.getByTestId('copy-prompt-btn')
    fireEvent.click(copyBtn)

    await waitFor(() => {
      expect(mockInvoke).toHaveBeenCalled()
    })

    expect(navigatorWriteSpy).not.toHaveBeenCalled()
  })
})


