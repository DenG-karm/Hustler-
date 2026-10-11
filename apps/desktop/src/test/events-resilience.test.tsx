import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { App } from '../App'
import { ThemeProvider } from '../theme/ThemeContext'
import { useFlowStore } from '../store/flowStore'
import { setIpcClient, resetIpcClient, type FlowIpcClient } from '../lib/ipc'
import {
  setEventBridge,
  resetEventBridge,
  mockEventBridge,
  emitMockEvent,
  emitMockConnectionState,
} from '../lib/events'

describe('K-703: Tauri Event System, Hard-Cancel ve Yeniden Bağlanma (Resilience) Testleri', () => {
  let mockIpc: FlowIpcClient
  let cancelCalledWith: string | null = null

  beforeEach(() => {
    useFlowStore.getState().resetFlow()
    resetIpcClient()
    setEventBridge(mockEventBridge)
    cancelCalledWith = null

    mockIpc = {
      runDiscovery: vi.fn().mockResolvedValue({ status: 200, body: [] }),
      generateScript: vi.fn().mockResolvedValue({ status: 200, body: {} }),
      generateAudio: vi.fn().mockResolvedValue({ status: 200, body: {} }),
      prepareAssets: vi.fn().mockResolvedValue({ status: 200, body: {} }),
      generatePreview: vi.fn().mockResolvedValue({ status: 200, body: {} }),
      triggerRender: vi.fn().mockResolvedValue({
        status: 200,
        body: { job_id: 'job_resilience_99', profile: 'DRAFT', status: 'RENDERING', progress: 5 },
      }),
      getJobStatus: vi.fn().mockImplementation(() => {
        return Promise.resolve({ status: 200, body: {} })
      }),
      cancelJob: vi.fn().mockImplementation((jobId: string) => {
        cancelCalledWith = jobId
        return Promise.resolve({
          status: 200,
          body: { job_id: jobId, status: 'CANCELLED' },
        })
      }),
      proxyRequest: vi.fn(),
    }

    setIpcClient(mockIpc)
  })

  afterEach(() => {
    resetEventBridge()
  })

  it('1. Tauri Event System: Asenkron ilerleme SSE/Event mekanizması ile UI\'a aktarılmalı (Sıfır Polling)', async () => {
    // Render adımına başlangıçta geç
    useFlowStore.setState({
      currentStep: 'RENDER',
      render: {
        jobId: 'job_resilience_99',
        profile: 'DRAFT',
        status: 'RENDERING',
        progress: 10,
        outputPath: null,
        error: null,
      },
    })

    render(
      <ThemeProvider>
        <App />
      </ThemeProvider>
    )

    // Başlangıçta %10 görünür olmalı
    expect(screen.getByText('%10')).toBeInTheDocument()

    // FastAPI -> Rust -> Tauri Window::emit -> hustler:event (%55 İlerleme Simülasyonu)
    act(() => {
      emitMockEvent({
        type: 'job_progress',
        job_id: 'job_resilience_99',
        progress: 55,
        step: 'Encoding frame 120/240',
      })
    })

    await waitFor(() => {
      expect(screen.getByText('%55')).toBeInTheDocument()
    })

    // Event ile tamamlanma (%100 ve çıktı yolu)
    act(() => {
      emitMockEvent({
        type: 'job_completed',
        job_id: 'job_resilience_99',
        output_path: 'renders/final_output.mp4',
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('render-status-badge')).toHaveTextContent('COMPLETED')
      expect(screen.getByText('renders/final_output.mp4')).toBeInTheDocument()
      expect(screen.getByText('%100')).toBeInTheDocument()
    })

    // Polling çağrısı yapılmamış olmalı
    expect(mockIpc.getJobStatus).not.toHaveBeenCalled()
  })

  it('2. Hard-Cancel: UI üzerinden İptal butonuna basıldığında tüm hiyerarşiye iptal sinyali gönderilmeli', async () => {
    useFlowStore.setState({
      currentStep: 'RENDER',
      render: {
        jobId: 'job_cancel_test_123',
        profile: 'FINAL',
        status: 'RENDERING',
        progress: 35,
        outputPath: null,
        error: null,
      },
    })

    render(
      <ThemeProvider>
        <App />
      </ThemeProvider>
    )

    const cancelBtn = screen.getByTestId('render-cancel-btn')
    expect(cancelBtn).toBeInTheDocument()

    fireEvent.click(cancelBtn)

    await waitFor(() => {
      expect(mockIpc.cancelJob).toHaveBeenCalledWith('job_cancel_test_123')
      expect(cancelCalledWith).toBe('job_cancel_test_123')
    })

    await waitFor(() => {
      expect(screen.getByTestId('render-status-badge')).toHaveTextContent('CANCELLED')
      expect(screen.getByTestId('render-cancelled-notice')).toBeInTheDocument()
    })
  })

  it('3. Resilience (Yeniden Bağlanma): Bağlantı koptuğunda Exponential Backoff uyarısı gösterilmeli ve UI kilitlenmemeli', async () => {
    useFlowStore.setState({
      currentStep: 'RENDER',
      render: {
        jobId: 'job_resilience_99',
        profile: 'DRAFT',
        status: 'RENDERING',
        progress: 40,
        outputPath: null,
        error: null,
      },
    })

    render(
      <ThemeProvider>
        <App />
      </ThemeProvider>
    )

    // Event dinleyicilerinin bağlanmasını bekle
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    // Rust katmanından gelen "reconnecting" (backoff deneme 3) olayı
    act(() => {
      emitMockConnectionState({
        state: 'reconnecting',
        attempt: 3,
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('connection-reconnecting-banner')).toBeInTheDocument()
      expect(screen.getByText(/Yeniden Bağlanılıyor\.\.\./)).toBeInTheDocument()
      expect(screen.getByText(/\(Deneme 3\)/)).toBeInTheDocument()
      expect(screen.getByTestId('connection-status-indicator')).toHaveTextContent('Yeniden Bağlanılıyor (3)')
    })

    // Bağlantı geri geldiğinde (connected)
    act(() => {
      emitMockConnectionState({
        state: 'connected',
      })
    })

    await waitFor(() => {
      expect(screen.queryByTestId('connection-reconnecting-banner')).not.toBeInTheDocument()
      expect(screen.getByTestId('connection-status-indicator')).toHaveTextContent('Event Stream Bağlı')
    })
  })

  it('4. LLM Loop Uyarısı: Döngü uyarısı geldiğinde Toast bildirimi gösterilmeli', async () => {
    render(
      <ThemeProvider>
        <App />
      </ThemeProvider>
    )

    act(() => {
      emitMockEvent({
        type: 'llm_loop_warning',
        message: 'LLM döngü limiti uyarısı: 3. tekrarda düzeltme sağlandı.',
        iteration: 3,
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('toast-container')).toBeInTheDocument()
      expect(screen.getByText('LLM Döngü Uyarısı')).toBeInTheDocument()
      expect(screen.getByText('LLM döngü limiti uyarısı: 3. tekrarda düzeltme sağlandı.')).toBeInTheDocument()
    })
  })

  it('5. Kritik Problem Details hatası geldiğinde ErrorModal açılmalı ve ham 500 sızmamalı', async () => {
    useFlowStore.setState({
      currentStep: 'RENDER',
      render: {
        jobId: 'job_fatal_77',
        profile: 'FINAL',
        status: 'RENDERING',
        progress: 80,
        outputPath: null,
        error: null,
      },
    })

    render(
      <ThemeProvider>
        <App />
      </ThemeProvider>
    )

    // FastAPI'den gelen kritik render hatası
    act(() => {
      emitMockEvent({
        type: 'job_failed',
        job_id: 'job_fatal_77',
        error: {
          type: 'https://hustler.local/errors/encoder-fatal',
          title: 'Donanım Kodlayıcı Hatası',
          status: 500,
          detail: 'FFmpeg donanım ivmelendirici (NVENC) beklenmedik şekilde çöktü.',
          code: 'ENCODER_FATAL',
        },
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('error-modal')).toBeInTheDocument()
      expect(screen.getByTestId('error-modal-title')).toHaveTextContent('Donanım Kodlayıcı Hatası')
      expect(screen.getByTestId('error-modal-message')).toHaveTextContent(
        'FFmpeg donanım ivmelendirici (NVENC) beklenmedik şekilde çöktü.'
      )
    })

    // Modalı kapat
    const dismissBtn = screen.getByTestId('error-modal-dismiss-btn')
    fireEvent.click(dismissBtn)

    await waitFor(() => {
      expect(screen.queryByTestId('error-modal')).not.toBeInTheDocument()
    })
  })
})
