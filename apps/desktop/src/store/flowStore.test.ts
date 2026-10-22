import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useFlowStore, InvalidStateTransitionError } from './flowStore'
import { setIpcClient, resetIpcClient, type FlowIpcClient } from '../lib/ipc'

describe('K-702: Akış Ekranları Katı Durum Makinesi (flowStore)', () => {
  beforeEach(() => {
    useFlowStore.getState().resetFlow()
    resetIpcClient()
  })

  describe('Durum Makinesi Geçiş Kısıtlamaları (Strict FSM)', () => {
    it('başlangıçta TOPIC adımında olmalıdır', () => {
      const state = useFlowStore.getState()
      expect(state.currentStep).toBe('TOPIC')
      expect(state.canProceed()).toBe(false)
    })

    it('boş veya 3 karakterden kısa konuda nextStep() InvalidStateTransitionError fırlatmalıdır', () => {
      const store = useFlowStore.getState()
      store.setTopic('ab')

      expect(() => {
        store.nextStep()
      }).toThrowError(InvalidStateTransitionError)

      expect(useFlowStore.getState().currentStep).toBe('TOPIC')
    })

    it('geçerli konuda nextStep() TOPIC -> TOP20 geçişi yapmalıdır', () => {
      const store = useFlowStore.getState()
      store.setTopic('Yapay Zeka Tarihi')

      expect(store.canProceed()).toBe(true)
      store.nextStep()

      expect(useFlowStore.getState().currentStep).toBe('TOP20')
    })

    it('TOP20 adımında fikir seçilmeden SCRIPT adımına geçiş reddedilmelidir', () => {
      const store = useFlowStore.getState()
      store.setTopic('Yapay Zeka')
      store.nextStep() // TOP20'ye geçti

      expect(() => {
        useFlowStore.getState().nextStep()
      }).toThrowError(InvalidStateTransitionError)

      expect(useFlowStore.getState().currentStep).toBe('TOP20')
    })

    it('fikir seçildikten sonra TOP20 -> SCRIPT geçişi yapılabilmelidir', () => {
      const store = useFlowStore.getState()
      store.setTopic('Yapay Zeka')
      store.nextStep()

      store.selectIdea({
        id: 'idea_1',
        title: 'Yapay Zekanın Geleceği',
        hook: 'Bunu biliyor muydunuz?',
        score: 95,
      })

      expect(useFlowStore.getState().canProceed()).toBe(true)
      useFlowStore.getState().nextStep()

      expect(useFlowStore.getState().currentStep).toBe('SCRIPT')
    })

    it('SCRIPT adımında senaryo onaylanmadan AUDIO adımına geçiş reddedilmelidir', () => {
      const store = useFlowStore.getState()
      store.setTopic('Yapay Zeka')
      store.nextStep()
      store.selectIdea({ id: 'idea_1', title: 'Fikir', hook: 'Kanca', score: 90 })
      store.nextStep()

      // Senaryo var ama isApproved = false
      store.setScript({
        id: 'scr_1',
        title: 'Başlık',
        hook: 'Kanca',
        fullText: 'Bu yeterince uzun bir senaryo metnidir en az yirmi karakter.',
        scenes: [],
        isApproved: false,
      })

      expect(() => {
        useFlowStore.getState().nextStep()
      }).toThrowError(InvalidStateTransitionError)

      expect(useFlowStore.getState().currentStep).toBe('SCRIPT')
    })

    it('senaryo onaylandığında SCRIPT -> AUDIO geçişi yapılabilmelidir', () => {
      const store = useFlowStore.getState()
      store.setTopic('Yapay Zeka')
      store.nextStep()
      store.selectIdea({ id: 'idea_1', title: 'Fikir', hook: 'Kanca', score: 90 })
      store.nextStep()

      store.setScript({
        id: 'scr_1',
        title: 'Başlık',
        hook: 'Kanca',
        fullText: 'Bu yeterince uzun bir senaryo metnidir en az yirmi karakter.',
        scenes: [],
        isApproved: false,
      })

      store.approveScript()
      expect(useFlowStore.getState().canProceed()).toBe(true)
      useFlowStore.getState().nextStep()

      expect(useFlowStore.getState().currentStep).toBe('AUDIO')
    })

    it('AUDIO adımında ses üretilmeden veya süresi 0 iken ASSETS adımına geçiş engellenmelidir', () => {
      const store = useFlowStore.getState()
      store.setTopic('Yapay Zeka')
      store.nextStep()
      store.selectIdea({ id: 'idea_1', title: 'Fikir', hook: 'Kanca', score: 90 })
      store.nextStep()
      store.setScript({
        id: 'scr_1',
        title: 'Başlık',
        hook: 'Kanca',
        fullText: 'Uzun senaryo metni yirmi karakterden fazla.',
        scenes: [],
        isApproved: true,
      })
      store.nextStep() // AUDIO adımında

      expect(() => {
        useFlowStore.getState().nextStep()
      }).toThrowError(InvalidStateTransitionError)

      expect(useFlowStore.getState().currentStep).toBe('AUDIO')
    })

    it('ASSETS adımında zorunlu slotlar dolmadan PREVIEW adımına geçiş engellenmelidir', () => {
      const store = useFlowStore.getState()
      store.setTopic('Yapay Zeka')
      store.nextStep()
      store.selectIdea({ id: 'idea_1', title: 'Fikir', hook: 'Kanca', score: 90 })
      store.nextStep()
      store.setScript({
        id: 'scr_1',
        title: 'Başlık',
        hook: 'Kanca',
        fullText: 'Uzun senaryo metni yirmi karakterden fazla.',
        scenes: [],
        isApproved: true,
      })
      store.nextStep()
      store.setAudio({
        scriptId: 'scr_1',
        voiceId: 'tr-TR',
        audioPath: 'assets/audio/test.mp3',
        durationSeconds: 25,
        isGenerated: true,
      })
      store.nextStep() // ASSETS adımında

      // Varsayılan slotlar henüz atanmadı (assignedPath null)
      expect(() => {
        useFlowStore.getState().nextStep()
      }).toThrowError(InvalidStateTransitionError)

      expect(useFlowStore.getState().currentStep).toBe('ASSETS')
    })

    it('PREVIEW adımında doğrulama yapılmadan RENDER adımına geçiş engellenmelidir', () => {
      const store = useFlowStore.getState()
      store.setTopic('Yapay Zeka')
      store.nextStep()
      store.selectIdea({ id: 'idea_1', title: 'Fikir', hook: 'Kanca', score: 90 })
      store.nextStep()
      store.setScript({
        id: 'scr_1',
        title: 'Başlık',
        hook: 'Kanca',
        fullText: 'Uzun senaryo metni yirmi karakterden fazla.',
        scenes: [],
        isApproved: true,
      })
      store.nextStep()
      store.setAudio({
        scriptId: 'scr_1',
        voiceId: 'tr-TR',
        audioPath: 'assets/audio/test.mp3',
        durationSeconds: 25,
        isGenerated: true,
      })
      store.nextStep()

      // Tüm zorunlu slotları doldur
      store.assignAssetSlot('slot_intro_video', 'intro.mp4')
      store.assignAssetSlot('slot_body_img1', 'img1.png')
      store.assignAssetSlot('slot_body_img2', 'img2.png')
      store.nextStep() // PREVIEW adımında

      expect(useFlowStore.getState().currentStep).toBe('PREVIEW')

      // Önizleme doğrulanmadı (isVerified = false)
      expect(() => {
        useFlowStore.getState().nextStep()
      }).toThrowError(InvalidStateTransitionError)
    })
  })

  describe('Adım Atlama ve Bypass Koruması (Anti-Bypass)', () => {
    it('TOPIC adımındayken doğrudan goToStep(RENDER) çağrıldığında ara adımlar eksik olduğu için reddedilmelidir', () => {
      const store = useFlowStore.getState()
      store.setTopic('Büyük Konu')

      expect(() => {
        store.goToStep('RENDER')
      }).toThrowError(InvalidStateTransitionError)

      expect(useFlowStore.getState().currentStep).toBe('TOPIC')
    })

    it('TOPIC adımındayken doğrudan goToStep(AUDIO) çağrıldığında TOP20 eksik olduğu için reddedilmelidir', () => {
      const store = useFlowStore.getState()
      store.setTopic('Büyük Konu')

      expect(() => {
        store.goToStep('AUDIO')
      }).toThrowError(InvalidStateTransitionError)

      expect(useFlowStore.getState().currentStep).toBe('TOPIC')
    })

    it('Geriye gitmeye (prevStep veya goToStep) her zaman izin verilmelidir', () => {
      const store = useFlowStore.getState()
      store.setTopic('Büyük Konu')
      store.nextStep() // TOP20'de

      store.prevStep()
      expect(useFlowStore.getState().currentStep).toBe('TOPIC')

      store.nextStep() // Tekrar TOP20'ye geç
      store.goToStep('TOPIC') // Geriye gitme
      expect(useFlowStore.getState().currentStep).toBe('TOPIC')
    })
  })

  describe('IPC Mocklama ve Tam Akış Doğrulaması', () => {
    it('IPC çağrılarıyla baştan sona (TOPIC -> RENDER) tam akış başarıyla tamamlanmalıdır', async () => {
      const mockIpc: FlowIpcClient = {
        runDiscovery: vi.fn().mockResolvedValue({
          status: 200,
          body: [
            { video_id: 'v1', title: 'Viral Video 1', hook: 'Kanca 1', score: 98 },
            { video_id: 'v2', title: 'Viral Video 2', hook: 'Kanca 2', score: 85 },
          ],
        }),
        generateScript: vi.fn().mockResolvedValue({
          status: 200,
          body: {
            script_id: 'scr_mock_1',
            title: 'Mock Senaryo',
            hook: 'Şok Kanca!',
            full_text: 'Bu tam teşekküllü test senaryosu yirmi karakterden uzundur.',
            scenes: [{ order: 1, narration: 'Giriş', visual_prompt: 'Görsel 1' }],
          },
        }),
        generateAudio: vi.fn().mockResolvedValue({
          status: 200,
          body: {
            audio_path: 'assets/audio/mock.mp3',
            duration_seconds: 28.5,
          },
        }),
        prepareAssets: vi.fn().mockResolvedValue({
          status: 200,
          body: {
            slots: [
              { slot_id: 'slot_intro_video', name: 'Giriş', type: 'video', required: true, assigned_path: 'intro.mp4' },
              { slot_id: 'slot_body_img1', name: 'Görsel 1', type: 'image', required: true, assigned_path: 'img1.png' },
              { slot_id: 'slot_body_img2', name: 'Görsel 2', type: 'image', required: true, assigned_path: 'img2.png' },
            ],
          },
        }),
        generatePreview: vi.fn().mockResolvedValue({
          status: 200,
          body: {
            preview_url: 'assets/previews/preview.mp4',
            fps: 30,
            resolution: '540x960',
          },
        }),
        triggerRender: vi.fn().mockResolvedValue({
          status: 200,
          body: {
            job_id: 'job_render_123',
            profile: 'DRAFT',
            output_path: 'renders/output.mp4',
          },
        }),
        getJobStatus: vi.fn().mockResolvedValue({
          status: 200,
          body: {
            job_id: 'job_render_123',
            status: 'COMPLETED',
            progress: 100,
            output_path: 'renders/output.mp4',
          },
        }),
        cancelJob: vi.fn().mockResolvedValue({
          status: 200,
          body: {
            job_id: 'job_render_123',
            status: 'CANCELLED',
          },
        }),
        saveScript: vi.fn().mockResolvedValue({
          status: 200,
          body: {
            status: 'SAVED',
            script_id: 'scr_mock_1',
            is_idempotent: true,
          },
        }),
        getActiveSession: vi.fn().mockResolvedValue({ status: 200, body: { session: null } }),
        saveActiveSession: vi.fn().mockResolvedValue({ status: 200, body: { status: 'SAVED' } }),
        proxyRequest: vi.fn(),
      }

      setIpcClient(mockIpc)

      const store = useFlowStore.getState()

      // 1. TOPIC
      store.setTopic('Finansal Özgürlük')
      await store.fetchIdeasForTopic()
      expect(mockIpc.runDiscovery).toHaveBeenCalledWith('Finansal Özgürlük', null)
      expect(useFlowStore.getState().ideas).toHaveLength(2)
      store.nextStep()
      expect(useFlowStore.getState().currentStep).toBe('TOP20')

      // 2. TOP20
      const selected = useFlowStore.getState().ideas[0]
      store.selectIdea(selected)
      await store.generateScriptForIdea()
      expect(mockIpc.generateScript).toHaveBeenCalledWith('v1', 'Finansal Özgürlük', 'Viral Video 1', null)
      store.nextStep()
      expect(useFlowStore.getState().currentStep).toBe('SCRIPT')

      // 3. SCRIPT
      expect(useFlowStore.getState().script?.title).toBe('Mock Senaryo')
      // İddialar doğrulanmadan approveScript() bloke edilmelidir
      expect(() => {
        store.approveScript()
      }).toThrowError(InvalidStateTransitionError)

      // Tüm iddiaları doğrula
      const currentClaims = useFlowStore.getState().script?.claims || []
      for (const c of currentClaims) {
        store.setClaimVerified(c.id, true)
      }
      store.approveScript()
      await store.generateAudioForScript()
      expect(mockIpc.generateAudio).toHaveBeenCalled()
      store.nextStep()
      expect(useFlowStore.getState().currentStep).toBe('AUDIO')

      // 4. AUDIO
      expect(useFlowStore.getState().audio?.durationSeconds).toBe(28.5)
      await store.loadAssetsForScript()
      expect(mockIpc.prepareAssets).toHaveBeenCalled()
      store.nextStep()
      expect(useFlowStore.getState().currentStep).toBe('ASSETS')

      // 5. ASSETS
      expect(useFlowStore.getState().assets.allSlotsFilled).toBe(true)
      await store.buildPreviewForScript()
      expect(mockIpc.generatePreview).toHaveBeenCalled()
      store.nextStep()
      expect(useFlowStore.getState().currentStep).toBe('PREVIEW')

      // 6. PREVIEW
      store.setPreviewVerified(true)
      store.nextStep()
      expect(useFlowStore.getState().currentStep).toBe('RENDER')

      // 7. RENDER
      await store.dispatchRenderJob('DRAFT')
      expect(mockIpc.triggerRender).toHaveBeenCalledWith('DRAFT', 'scr_mock_1')
      expect(useFlowStore.getState().render.jobId).toBe('job_render_123')

      await store.pollJobStatus()
      expect(mockIpc.getJobStatus).toHaveBeenCalledWith('job_render_123')
      expect(useFlowStore.getState().render.status).toBe('COMPLETED')
      expect(useFlowStore.getState().render.progress).toBe(100)
    })
  })

  describe('K-704: Katı Durum Kilidi (Strict State Lock) ve İddia Onay Mekanizması', () => {
    beforeEach(() => {
      const store = useFlowStore.getState()
      store.setTopic('Kuantum Hesaplama')
      store.nextStep()
      store.selectIdea({ id: 'q_1', title: 'Kuantum Devrimi', hook: 'Şok Gerçek', score: 98 })
      store.nextStep()
      store.setScript({
        id: 'scr_k704',
        title: 'Kuantum Devrimi',
        hook: 'Şok Gerçek',
        fullText: 'Kuantum bilgisayarlar geleceğin şifreleme sistemlerini tamamen değiştirecek güçtedir.',
        scenes: [{ order: 1, narration: 'Giriş', visualPrompt: 'Quantum scene' }],
        claims: [
          { id: 'c1', text: 'Kuantum üstünlüğü 2019 yılında kanıtlanmıştır.', verified: false },
          { id: 'c2', text: 'RSA şifreleme kuantum işlemcilerle kırılabilir.', verified: false },
          { id: 'c3', text: 'Qubitler süperpozisyon durumunda çalışır.', verified: false },
        ],
        isApproved: false,
      })
    })

    it('onaylanmamış iddialar varken approveScript() InvalidStateTransitionError fırlatmalı ve onaylamamalıdır', () => {
      const store = useFlowStore.getState()

      expect(() => {
        store.approveScript()
      }).toThrowError(InvalidStateTransitionError)

      expect(useFlowStore.getState().script?.isApproved).toBe(false)
      expect(useFlowStore.getState().canProceed()).toBe(false)
    })

    it('onaylanmamış iddialar varken nextStep() geçişi engellemeli ve InvalidStateTransitionError fırlatmalıdır', () => {
      const store = useFlowStore.getState()

      expect(() => {
        store.nextStep()
      }).toThrowError(InvalidStateTransitionError)

      expect(useFlowStore.getState().currentStep).toBe('SCRIPT')
    })

    it('onaylanmamış iddialar varken goToStep(AUDIO) bypass denemesi reddedilmelidir', () => {
      const store = useFlowStore.getState()

      expect(() => {
        store.goToStep('AUDIO')
      }).toThrowError(InvalidStateTransitionError)

      expect(useFlowStore.getState().currentStep).toBe('SCRIPT')
    })

    it('kısmi onayda (3 iddiadan 2si onaylı) kilit kalkmamalı ve hata fırlatmalıdır', () => {
      const store = useFlowStore.getState()
      store.toggleClaim('c1')
      store.setClaimVerified('c2', true)

      // c3 hala verified: false
      expect(useFlowStore.getState().canProceed()).toBe(false)

      expect(() => {
        store.approveScript()
      }).toThrowError(InvalidStateTransitionError)

      expect(() => {
        store.nextStep()
      }).toThrowError(InvalidStateTransitionError)
    })

    it('tüm iddialar onaylandığında approveScript() başarılı olmalı ve AUDIO adımına geçilebilmelidir', () => {
      const store = useFlowStore.getState()
      store.toggleClaim('c1')
      store.toggleClaim('c2')
      store.toggleClaim('c3')

      // 3 iddia da onaylandı
      expect(useFlowStore.getState().script?.claims.every((c) => c.verified)).toBe(true)

      // approveScript çağrılabilir
      store.approveScript()
      expect(useFlowStore.getState().script?.isApproved).toBe(true)
      expect(store.canProceed()).toBe(true)

      // AUDIO adımına geç
      store.nextStep()
      expect(useFlowStore.getState().currentStep).toBe('AUDIO')
    })

    it('senaryo metni veya başlığı düzenlendiğinde onay durumu otomatik olarak sıfırlanmalıdır (isApproved = false)', () => {
      const store = useFlowStore.getState()
      store.setClaimVerified('c1', true)
      store.setClaimVerified('c2', true)
      store.setClaimVerified('c3', true)
      store.approveScript()
      expect(useFlowStore.getState().script?.isApproved).toBe(true)

      // Metin düzenleniyor
      store.setScript({ fullText: 'Yeni düzenlenmiş senaryo metni yeterince uzundur ve revize edilmiştir.' })

      // isApproved derhal false olmalıdır
      expect(useFlowStore.getState().script?.isApproved).toBe(false)
      expect(useFlowStore.getState().canProceed()).toBe(false)

      // Yeniden onaylama yapılmadan ilerlenemez
      expect(() => {
        store.nextStep()
      }).toThrowError(InvalidStateTransitionError)
    })

    it('onaylı durumdayken herhangi bir iddianın tiki kaldırıldığında onay durumu sıfırlanmalıdır', () => {
      const store = useFlowStore.getState()
      store.setClaimVerified('c1', true)
      store.setClaimVerified('c2', true)
      store.setClaimVerified('c3', true)
      store.approveScript()
      expect(useFlowStore.getState().script?.isApproved).toBe(true)

      // c1 onayını geri al
      store.toggleClaim('c1')

      expect(useFlowStore.getState().script?.isApproved).toBe(false)
      expect(useFlowStore.getState().canProceed()).toBe(false)

      expect(() => {
        store.nextStep()
      }).toThrowError(InvalidStateTransitionError)
    })

    it('saveScriptContent() IPC saveScript metodunu doğru parametrelerle çağırmalıdır', async () => {
      const mockSave = vi.fn().mockResolvedValue({
        status: 200,
        body: { status: 'SAVED', script_id: 'scr_k704', is_idempotent: true },
      })
      const mockIpc: FlowIpcClient = {
        saveScript: mockSave,
      } as any
      setIpcClient(mockIpc)

      const store = useFlowStore.getState()
      await store.saveScriptContent('Yeni Başlık', 'Yeni İçerik Metni en az yirmi karakter uzunluğunda olmalıdır.')

      expect(mockSave).toHaveBeenCalledWith(
        'scr_k704',
        'Yeni Başlık',
        'Yeni İçerik Metni en az yirmi karakter uzunluğunda olmalıdır.',
        expect.any(Array),
        expect.any(Array),
        false
      )
      expect(useFlowStore.getState().script?.saveStatus).toBe('SAVED')
      expect(useFlowStore.getState().script?.lastSavedAt).toBeDefined()
    })

    it('K-806: runDiscovery backend degraded: true döndüğünde toast eklemeli ve akışı kesmemelidir', async () => {
      const mockIpc: FlowIpcClient = {
        runDiscovery: vi.fn().mockResolvedValue({
          status: 200,
          body: {
            degraded: true,
            warning: 'yt-dlp çıkarıcısı yanıt vermiyor; yerel kurtarma modu aktif.',
            results: [
              { video_id: 'fallback_1', title: 'Kurtarılan Fikir 1', hook: 'Kanca 1', score: 95 },
            ],
          },
        }),
      } as any
      setIpcClient(mockIpc)

      const store = useFlowStore.getState()
      store.resetFlow()
      store.setTopic('Yapay Zeka')

      await store.runDiscovery()

      // 1. Toast eklenmiş olmalı
      const toasts = useFlowStore.getState().toasts
      expect(toasts.length).toBeGreaterThan(0)
      expect(toasts[0].message).toContain('yt-dlp çıkarıcısı yanıt vermiyor')
      expect(toasts[0].code).toBe('DISCOVERY_DEGRADED')

      // 2. Fikir listesi doldurulmuş olmalı
      const ideas = useFlowStore.getState().ideas
      expect(ideas.length).toBeGreaterThan(0)
      expect(ideas[0].id).toBe('fallback_1')

      // 3. Fikir seçilip SCRIPT adımına kesintisiz geçilebilmeli
      store.selectIdea(ideas[0])
      expect(useFlowStore.getState().canProceed()).toBe(true)
      store.nextStep()
      expect(useFlowStore.getState().currentStep).toBe('TOP20')
    })
  })
})

