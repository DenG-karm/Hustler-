/**
 * Hustler Desktop — K-802 State Rehydration ve Çökme Kurtarma Test Paketi
 *
 * MİMARİ KURAL: ZERO-NETWORK & CRASH RESILIENCE
 * Uygulama veya sidecar çöktüğünde / yeniden başlatıldığında, store sıfırlanmış olsa bile
 * rehydrateFromBackend() çağrısı ile son kararlı adıma (checkpoint) kadar olan tüm
 * durum (konu, fikirler, senaryo, ses, slotlar, önizleme) birebir ayağa kaldırılır.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useFlowStore } from '../store/flowStore'
import { setIpcClient, resetIpcClient, type FlowIpcClient } from '../lib/ipc'

describe('K-802 State Rehydration & Crash Recovery', () => {
  beforeEach(() => {
    useFlowStore.getState().resetFlow()
    resetIpcClient()
  })

  it('Uygulama yeniden başlatıldığında (store sıfırlandığında) rehydrateFromBackend ile yarım kalan projenin tüm adımları eksiksiz geri yüklenmelidir', async () => {
    // Başlangıçta store'un tamamen boş olduğunu doğrula
    const initial = useFlowStore.getState()
    expect(initial.currentStep).toBe('TOPIC')
    expect(initial.topic).toBe('')
    expect(initial.script).toBeNull()
    expect(initial.audio).toBeNull()

    const mockSessionPayload = {
      topic: 'Kuantum Fiziği ve Süperiletkenlik',
      ideas: [
        { id: 'idea_1', title: 'Süperiletkenlerin Gizemi', hook: 'Direnç sıfırlandığında ne olur?', score: 95 },
      ],
      selectedIdea: { id: 'idea_1', title: 'Süperiletkenlerin Gizemi', hook: 'Direnç sıfırlandığında ne olur?', score: 95 },
      script: {
        id: 'scr_rehydrate_777',
        title: 'Süperiletkenlerin Gizemi',
        hook: 'Direnç sıfırlandığında ne olur?',
        fullText: 'Oda sıcaklığında süperiletkenlik fizik dünyasını baştan aşağı değiştirecek devrimdir.',
        scenes: [
          { order: 1, narration: 'Kanca sahnesi', visualPrompt: 'Levitating magnet prompt' },
        ],
        claims: [
          { id: 'clm_1', text: 'Meissner etkisi manyetik alanı dışlar', verified: true },
        ],
        isApproved: true,
      },
      audio: {
        scriptId: 'scr_rehydrate_777',
        voiceId: 'tr-TR-Standard-A',
        audioPath: 'assets/audio/scr_rehydrate_777.mp3',
        durationSeconds: 32.5,
        isGenerated: true,
      },
      assets: {
        slots: [
          { slotId: 'slot_intro_video', name: 'Giriş Kancası', type: 'video', required: true, assignedPath: 'assets/intro.mp4' },
          { slotId: 'slot_body_img1', name: 'Gövde Görsel 1', type: 'image', required: true, assignedPath: 'assets/body1.png' },
          { slotId: 'slot_body_img2', name: 'Gövde Görsel 2', type: 'image', required: true, assignedPath: 'assets/body2.png' },
          { slotId: 'slot_bg_audio', name: 'Müzik', type: 'audio', required: false, assignedPath: null },
        ],
        allSlotsFilled: true,
      },
      preview: {
        previewUrl: 'assets/previews/scr_rehydrate_777.mp4',
        fps: 30,
        resolution: '540x960',
        isVerified: true,
      },
      render: {
        jobId: 'job_interrupted_888',
        profile: 'DRAFT',
        status: 'RENDERING',
        progress: 45,
        outputPath: null,
        error: null,
      },
    }

    const mockIpc: FlowIpcClient = {
      runDiscovery: vi.fn(),
      generateScript: vi.fn(),
      saveScript: vi.fn(),
      generateAudio: vi.fn(),
      prepareAssets: vi.fn(),
      generatePreview: vi.fn(),
      triggerRender: vi.fn(),
      getJobStatus: vi.fn(),
      cancelJob: vi.fn(),
      getActiveSession: vi.fn().mockResolvedValue({
        status: 200,
        body: {
          session: {
            id: 'session_active_123',
            topic: 'Kuantum Fiziği ve Süperiletkenlik',
            current_step: 'RENDER',
            checkpoint_step: 'PREVIEW',
            status: 'RECOVERED',
            state_payload: mockSessionPayload,
            created_at: '2026-10-14T10:00:00Z',
            updated_at: '2026-10-14T10:05:00Z',
          },
        },
      }),
      saveActiveSession: vi.fn().mockResolvedValue({ status: 200, body: { status: 'SAVED' } }),
      proxyRequest: vi.fn(),
    }

    setIpcClient(mockIpc)

    // Rehydration'ı tetikle
    const success = await useFlowStore.getState().rehydrateFromBackend()
    expect(success).toBe(true)

    // Durumun eksiksiz geri yüklendiğini doğrula
    const state = useFlowStore.getState()

    // 1. Kararlı checkpoint adımına geri dönülmeli (PREVIEW)
    expect(state.currentStep).toBe('PREVIEW')

    // 2. Konu ve Fikirler
    expect(state.topic).toBe('Kuantum Fiziği ve Süperiletkenlik')
    expect(state.ideas).toHaveLength(1)
    expect(state.selectedIdea?.id).toBe('idea_1')

    // 3. Senaryo verisi
    expect(state.script).not.toBeNull()
    expect(state.script?.id).toBe('scr_rehydrate_777')
    expect(state.script?.isApproved).toBe(true)
    expect(state.script?.scenes).toHaveLength(1)
    expect(state.script?.claims[0].verified).toBe(true)

    // 4. Ses verisi
    expect(state.audio).not.toBeNull()
    expect(state.audio?.voiceId).toBe('tr-TR-Standard-A')
    expect(state.audio?.durationSeconds).toBe(32.5)

    // 5. Görsel Slotları
    expect(state.assets.slots).toHaveLength(4)
    expect(state.assets.slots[0].assignedPath).toBe('assets/intro.mp4')

    // 6. Önizleme
    expect(state.preview.previewUrl).toBe('assets/previews/scr_rehydrate_777.mp4')
    expect(state.preview.isVerified).toBe(true)

    // 7. Kesintiye uğrayan render durumu temizlenmeli
    expect(state.render.status).toBe('CANCELLED')
    expect(state.render.error).toContain('kesintiye uğradı')

    // 8. Kullanıcıya bildirim toast'ı düşmeli
    expect(state.toasts.some((t) => t.title.includes('Kurtarıldı'))).toBe(true)
  })

  it('Aktif oturum bulunmadığında rehydrateFromBackend false dönmeli ve temiz state korunmalıdır', async () => {
    const mockIpc: FlowIpcClient = {
      runDiscovery: vi.fn(),
      generateScript: vi.fn(),
      saveScript: vi.fn(),
      generateAudio: vi.fn(),
      prepareAssets: vi.fn(),
      generatePreview: vi.fn(),
      triggerRender: vi.fn(),
      getJobStatus: vi.fn(),
      cancelJob: vi.fn(),
      getActiveSession: vi.fn().mockResolvedValue({
        status: 200,
        body: { session: null },
      }),
      saveActiveSession: vi.fn(),
      proxyRequest: vi.fn(),
    }

    setIpcClient(mockIpc)

    const success = await useFlowStore.getState().rehydrateFromBackend()
    expect(success).toBe(false)
    expect(useFlowStore.getState().currentStep).toBe('TOPIC')
  })

  it('persistSessionToBackend çağrıldığında store içeriği Rust IPC flow_save_active_session komutuna iletilmelidir', async () => {
    const saveSpy = vi.fn().mockResolvedValue({ status: 200, body: { status: 'SAVED' } })
    const mockIpc: FlowIpcClient = {
      runDiscovery: vi.fn(),
      generateScript: vi.fn(),
      saveScript: vi.fn(),
      generateAudio: vi.fn(),
      prepareAssets: vi.fn(),
      generatePreview: vi.fn(),
      triggerRender: vi.fn(),
      getJobStatus: vi.fn(),
      cancelJob: vi.fn(),
      getActiveSession: vi.fn().mockResolvedValue({ status: 200, body: { session: null } }),
      saveActiveSession: saveSpy,
      proxyRequest: vi.fn(),
    }

    setIpcClient(mockIpc)

    useFlowStore.getState().setTopic('Biyoteknoloji Devrimi')
    await useFlowStore.getState().persistSessionToBackend()

    expect(saveSpy).toHaveBeenCalledTimes(1)
    const callArg = saveSpy.mock.calls[0][0]
    expect(callArg.topic).toBe('Biyoteknoloji Devrimi')
    expect(callArg.current_step).toBe('TOPIC')
  })
})
