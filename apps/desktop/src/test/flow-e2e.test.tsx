import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { App } from '../App'
import { ThemeProvider } from '../theme/ThemeContext'
import { useFlowStore } from '../store/flowStore'
import { setIpcClient, resetIpcClient, type FlowIpcClient } from '../lib/ipc'

describe('K-702: Akış Ekranları Uçtan Uca (E2E) Testi', () => {
  let mockIpc: FlowIpcClient
  let fetchSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    useFlowStore.getState().resetFlow()
    resetIpcClient()

    // Sıfır Ağ Güvencesi: Eğer UI fetch çağırırsa test çöksün
    fetchSpy = vi.fn().mockImplementation(() => {
      throw new Error('[Sıfır Ağ İhlali] UI fetch() çağırdı!')
    })
    vi.stubGlobal('fetch', fetchSpy)

    mockIpc = {
      runDiscovery: vi.fn().mockResolvedValue({
        status: 200,
        body: [
          { video_id: 'vid_101', title: 'Piramitlerin Gizli Odaları', hook: 'Kimsenin bilmediği gizli koridor!', score: 96 },
          { video_id: 'vid_102', title: 'Tutankhamun Laneti Gerçek mi?', hook: 'Arkeologların şok raporu', score: 88 },
        ],
      }),
      generateScript: vi.fn().mockResolvedValue({
        status: 200,
        body: {
          script_id: 'scr_e2e_456',
          title: 'Piramitlerin Gizli Odaları',
          hook: 'Kimsenin bilmediği gizli koridor!',
          full_text: 'Piramitlerin içinde keşfedilen yeni kozmik ışın tüneli bilim dünyasını şaşkına çevirdi.',
          scenes: [
            { order: 1, narration: 'Giriş kancası', visual_prompt: 'Pyramids cinematic 9:16' },
            { order: 2, narration: 'Gövde detayı', visual_prompt: 'Muon cosmic detector 3D' },
            { order: 3, narration: 'Kapanış', visual_prompt: 'Call to action animation' },
          ],
        },
      }),
      generateAudio: vi.fn().mockResolvedValue({
        status: 200,
        body: {
          script_id: 'scr_e2e_456',
          voice_id: 'tr-TR-Standard-A',
          audio_path: 'assets/audio/scr_e2e_456.mp3',
          duration_seconds: 24.0,
          is_generated: true,
        },
      }),
      prepareAssets: vi.fn().mockResolvedValue({
        status: 200,
        body: {
          script_id: 'scr_e2e_456',
          slots: [
            { slot_id: 'slot_intro_video', name: 'Giriş Kancası (Video)', type: 'video', required: true, assigned_path: 'intro.mp4' },
            { slot_id: 'slot_body_img1', name: 'Gövde Sahne 1 (Görsel)', type: 'image', required: true, assigned_path: 'body1.png' },
            { slot_id: 'slot_body_img2', name: 'Gövde Sahne 2 (Görsel)', type: 'image', required: true, assigned_path: 'body2.png' },
          ],
        },
      }),
      generatePreview: vi.fn().mockResolvedValue({
        status: 200,
        body: {
          script_id: 'scr_e2e_456',
          preview_url: 'assets/previews/scr_e2e_456.mp4',
          fps: 30,
          resolution: '540x960',
          is_verified: true,
        },
      }),
      triggerRender: vi.fn().mockResolvedValue({
        status: 200,
        body: {
          job_id: 'rnd_e2e_789',
          profile: 'DRAFT',
          status: 'RENDERING',
          progress: 10,
          output_path: 'renders/rnd_e2e_789_draft.mp4',
        },
      }),
      getJobStatus: vi.fn().mockResolvedValue({
        status: 200,
        body: {
          job_id: 'rnd_e2e_789',
          status: 'COMPLETED',
          progress: 100,
          output_path: 'renders/rnd_e2e_789_draft.mp4',
        },
      }),
      cancelJob: vi.fn().mockResolvedValue({
        status: 200,
        body: {
          job_id: 'rnd_e2e_789',
          status: 'CANCELLED',
        },
      }),
      saveScript: vi.fn().mockResolvedValue({
        status: 200,
        body: {
          status: 'SAVED',
          script_id: 'scr_e2e_456',
          is_idempotent: true,
        },
      }),
      getActiveSession: vi.fn().mockResolvedValue({ status: 200, body: { session: null } }),
      saveActiveSession: vi.fn().mockResolvedValue({ status: 200, body: { status: 'SAVED' } }),
      proxyRequest: vi.fn(),
    }

    setIpcClient(mockIpc)
  })

  it('Ana akışı (Kanal Fikir Seçimi → Senaryo → Ses → Görseller → Önizleme → Render) kilitlenmeden tamamlamalıdır', async () => {
    // Faz 2 Kanal-Merkezli Mimari: Senaryo adımından itibaren tam akış
    useFlowStore.setState({
      activeView: 'pipeline',
      currentStep: 'SCRIPT',
      script: {
        id: 'scr_e2e_456',
        title: 'Piramitlerin Gizli Odaları',
        hook: 'Piramitler ve Gizemler',
        fullText: 'Piramitlerin altında bilinmeyen gizli odalar var. Arkeologlar yeni keşiflerle tarihi yeniden yazıyor.',
        scenes: [
          {
            order: 1,
            visualPrompt: 'Büyük piramitin altındaki tüneller',
            narration: 'Piramitlerin altında bilinmeyen gizli odalar var.',
          },
          {
            order: 2,
            visualPrompt: 'Antik hiyeroglifler ve sırlar',
            narration: 'Arkeologlar yeni keşiflerle tarihi yeniden yazıyor.',
          },
        ],
        claims: [
          {
            id: 'claim_1',
            text: 'Piramitlerin altında yeni odalar bulundu',
            verified: false,
          },
        ],
        isApproved: false,
      },
    })

    render(
      <ThemeProvider>
        <App />
      </ThemeProvider>
    )

    // -------------------------------------------------------------
    // ADIM 3: SENARYO ONAYI
    // -------------------------------------------------------------
    await waitFor(() => {
      expect(screen.getByTestId('flow-stepper')).toBeInTheDocument()
      expect(screen.getByTestId('screen-script')).toBeInTheDocument()
    })

    const scriptSubmitBtn = screen.getByTestId('script-submit-btn')
    // Onaylanmadan ilerleme butonu kilitli olmalıdır!
    expect(scriptSubmitBtn).toBeDisabled()
    expect(screen.getByTestId('script-status-badge')).toHaveTextContent('Onay Bekliyor')

    const approveBtn = screen.getByTestId('script-approve-btn')
    // İddialar doğrulanmadan Onayla butonu kilitli olmalıdır (UI seviyesinde katı kilit)
    expect(approveBtn).toBeDisabled()

    // Tüm iddia checkbox'larını işaretle
    const claimCheckboxes = screen.getAllByRole('checkbox')
    expect(claimCheckboxes.length).toBeGreaterThan(0)
    for (const cb of claimCheckboxes) {
      fireEvent.click(cb)
    }

    // Artık onay butonu aktif olmalıdır
    expect(approveBtn).toBeEnabled()
    fireEvent.click(approveBtn)

    expect(screen.getByTestId('script-status-badge')).toHaveTextContent('Onaylandı ✓')
    expect(scriptSubmitBtn).toBeEnabled()

    fireEvent.click(scriptSubmitBtn)

    await waitFor(() => {
      expect(mockIpc.generateAudio).toHaveBeenCalled()
    })

    // -------------------------------------------------------------
    // ADIM 4: SES SENTEZİ
    // -------------------------------------------------------------
    await waitFor(() => {
      expect(screen.getByTestId('screen-audio')).toBeInTheDocument()
    })

    expect(screen.getByText('24 saniye')).toBeInTheDocument()
    const audioSubmitBtn = screen.getByTestId('audio-submit-btn')
    expect(audioSubmitBtn).toBeEnabled()

    fireEvent.click(audioSubmitBtn)

    await waitFor(() => {
      expect(mockIpc.prepareAssets).toHaveBeenCalled()
    })

    // -------------------------------------------------------------
    // ADIM 5: GÖRSELLER & MEDYA SLOTLARI
    // -------------------------------------------------------------
    await waitFor(() => {
      expect(screen.getByTestId('screen-assets')).toBeInTheDocument()
    })

    expect(screen.getByTestId('assets-status-badge')).toHaveTextContent('Tüm Slotlar Hazır ✓')
    const assetsSubmitBtn = screen.getByTestId('assets-submit-btn')
    expect(assetsSubmitBtn).toBeEnabled()

    fireEvent.click(assetsSubmitBtn)

    await waitFor(() => {
      expect(mockIpc.generatePreview).toHaveBeenCalled()
    })

    // -------------------------------------------------------------
    // ADIM 6: TASLAK ÖNİZLEME
    // -------------------------------------------------------------
    await waitFor(() => {
      expect(screen.getByTestId('screen-preview')).toBeInTheDocument()
    })

    const previewSubmitBtn = screen.getByTestId('preview-submit-btn')
    // Doğrulanmadan ilerleme kilitli olmalı
    expect(previewSubmitBtn).toBeDisabled()

    const verifyBtn = screen.getByTestId('preview-verify-btn')
    fireEvent.click(verifyBtn)

    expect(screen.getByTestId('preview-status-badge')).toHaveTextContent('Doğrulandı ✓')
    expect(previewSubmitBtn).toBeEnabled()

    fireEvent.click(previewSubmitBtn)

    // -------------------------------------------------------------
    // ADIM 7: RENDER VE NİHAİ VİDEO MOTORU
    // -------------------------------------------------------------
    await waitFor(() => {
      expect(screen.getByTestId('screen-render')).toBeInTheDocument()
    })

    const renderStartBtn = screen.getByTestId('render-start-btn')
    expect(renderStartBtn).toBeInTheDocument()

    // Render başlat
    fireEvent.click(renderStartBtn)

    await waitFor(() => {
      expect(mockIpc.triggerRender).toHaveBeenCalledWith('DRAFT', 'scr_e2e_456')
    })

    await waitFor(() => {
      expect(screen.getByTestId('render-progress-card')).toBeInTheDocument()
      expect(screen.getByText(/İş ID:\s*rnd_e2e_789/)).toBeInTheDocument()
    })

    // Tamamlanma simülasyonu
    useFlowStore.getState().setRenderProgress(100, 'COMPLETED', 'renders/rnd_e2e_789_draft.mp4')

    await waitFor(() => {
      expect(screen.getByTestId('render-status-badge')).toHaveTextContent('COMPLETED')
      expect(screen.getByText('renders/rnd_e2e_789_draft.mp4')).toBeInTheDocument()
      expect(screen.getByTestId('render-reset-btn')).toBeInTheDocument()
    })

    // SIFIR AĞ GÜVENCESİ KONTROLÜ
    expect(fetchSpy).not.toHaveBeenCalled()
  })
})
