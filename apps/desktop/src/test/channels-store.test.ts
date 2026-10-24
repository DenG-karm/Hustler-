import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useFlowStore } from '../store/flowStore'
import { setIpcClient, type FlowIpcClient, type ChannelItem } from '../lib/ipc'
import type { DiscoveryItem } from '../store/flowTypes'
import { deriveGlobalViralPrototypes } from '../components/channels/globalPrototypes'

describe('Zustand Channel Slice ve Akış Köprüsü Testleri', () => {
  const mockChannels: ChannelItem[] = [
    {
      id: 'chn_101',
      name: 'Yapay Zeka & Gelecek',
      channel_url: 'https://youtube.com/@ai_future',
      description: 'Yapay zeka modelleri ve otomasyon',
      created_at: 1710000000,
      metrics: { total_scripts: 3, total_research: 8, avg_viral_score: 87.5 },
    },
  ]

  let mockClient: FlowIpcClient

  beforeEach(() => {
    useFlowStore.getState().resetFlow()
    useFlowStore.setState({ channels: [], activeChannelId: null, activeView: 'channels' })

    mockClient = {
      runDiscovery: vi.fn().mockResolvedValue({ status: 200, body: { results: [] } }),
      generateScript: vi.fn().mockResolvedValue({
        status: 200,
        body: {
          script_id: 'scr_from_channel_1',
          title: 'Yapay Zeka ile 10x Üretkenlik',
          hook: 'Günde 4 saat kazandıran yöntemler!',
          full_text: 'Yapay zeka ile 10x üretkenlik rehberi...',
          scenes: [],
          claims: [],
          is_approved: false,
        },
      }),
      saveScript: vi.fn(),
      generateAudio: vi.fn(),
      prepareAssets: vi.fn(),
      generatePreview: vi.fn(),
      triggerRender: vi.fn(),
      getJobStatus: vi.fn(),
      cancelJob: vi.fn(),
      getActiveSession: vi.fn().mockResolvedValue({ status: 200, body: null }),
      saveActiveSession: vi.fn().mockResolvedValue({ status: 200, body: null }),
      listChannels: vi.fn().mockResolvedValue({ status: 200, body: mockChannels }),
      createChannel: vi.fn().mockImplementation(async (payload) => ({
        status: 201,
        body: {
          id: 'chn_new_202',
          ...payload,
          created_at: 1710000500,
          metrics: { total_scripts: 0, total_research: 0, avg_viral_score: 0 },
        },
      })),
      deleteChannel: vi.fn().mockResolvedValue({
        status: 200,
        body: { status: 'deleted', channel_id: 'chn_101' },
      }),
      proxyRequest: vi.fn().mockResolvedValue({ status: 200, body: {} }),
    }

    setIpcClient(mockClient)
  })

  it('loadChannels kanalları store durumuna yüklemelidir', async () => {
    await useFlowStore.getState().loadChannels()
    const state = useFlowStore.getState()
    expect(state.channels).toHaveLength(1)
    expect(state.channels[0].id).toBe('chn_101')
    expect(state.channels[0].name).toBe('Yapay Zeka & Gelecek')
    expect(mockClient.listChannels).toHaveBeenCalledTimes(1)
  })

  it('createChannel yeni kanal eklemeli ve listeyi güncellemelidir', async () => {
    const created = await useFlowStore.getState().createChannel({
      name: 'Veri Bilimi',
      channel_url: 'https://youtube.com/@data',
      description: 'Veri analitiği',
    })

    expect(created).not.toBeNull()
    expect(created?.id).toBe('chn_new_202')
    const state = useFlowStore.getState()
    expect(state.channels.some((c) => c.id === 'chn_new_202')).toBe(true)
  })

  it('deleteChannel kanalı listeden çıkarmalıdır', async () => {
    useFlowStore.setState({ channels: mockChannels, activeChannelId: 'chn_101' })
    await useFlowStore.getState().deleteChannel('chn_101')

    const state = useFlowStore.getState()
    expect(state.channels).toHaveLength(0)
    expect(state.activeChannelId).toBeNull()
  })

  it('selectChannel aktif kanal kimliğini ayarlamalıdır', () => {
    useFlowStore.getState().selectChannel('chn_101')
    expect(useFlowStore.getState().activeChannelId).toBe('chn_101')

    useFlowStore.getState().selectChannel(null)
    expect(useFlowStore.getState().activeChannelId).toBeNull()
  })

  it('selectIdeaFromChannelAndStartFlow seçilen fikri store\'a kilitler, SCRIPT adımına geçer ve stüdyoya yönlendirir', async () => {
    const idea: DiscoveryItem = {
      video_id: 'vid_ai_001',
      title: 'Yapay Zeka ile 10x Üretkenlik',
      hook: 'Günde 4 saat kazandıran yöntemler!',
      score: 92.4,
      view_count: 350000,
    }

    useFlowStore.getState().selectIdeaFromChannelAndStartFlow('chn_101', idea)

    const state = useFlowStore.getState()
    // 1. Kanal ve fikir kilitlendi
    expect(state.activeChannelId).toBe('chn_101')
    expect(state.flowChannelId).toBe('chn_101')
    expect(state.selectedIdea?.id).toBe('vid_ai_001')
    expect(state.selectedIdea?.title).toBe(idea.title)

    // 2. Aktif üretim adımı SCRIPT yapıldı
    expect(state.currentStep).toBe('SCRIPT')

    // 3. Ana navigasyon Kanallar\'dan Akış Stüdyosu\'na (pipeline) geçirildi
    expect(state.activeView).toBe('pipeline')

    // 4. generateScriptForIdea tetiklendi ve channel_id ile çağrıldı
    expect(mockClient.generateScript).toHaveBeenCalledWith(
      'vid_ai_001',
      idea.title,
      idea.title,
      'chn_101'
    )
  })

  it('fetchChannelLiveStats /api/v1 prefixi ile çağrılmalı ve canlı abone verisini store\'a yazmalıdır', async () => {
    mockClient.proxyRequest = vi.fn().mockResolvedValue({
      status: 200,
      body: {
        live_data: {
          channel_id: 'chn_101',
          channel_name: 'Yapay Zeka & Gelecek',
          subscribers: 522000000,
          subscribers_formatted: '522.00M',
          avatar_url: 'https://yt3.googleusercontent.com/avatar.jpg',
          videos: [],
          shorts: [],
          total_fetched_videos: 0,
          total_fetched_shorts: 0,
          avg_views_sample: 0,
          avg_views_formatted: '0',
          is_live: true,
          fetched_at: Date.now(),
        },
      },
    })

    const stats = await useFlowStore.getState().fetchChannelLiveStats('chn_101')

    expect(mockClient.proxyRequest).toHaveBeenCalledWith(
      'GET',
      '/api/v1/channels/chn_101/live-stats'
    )
    expect(stats?.subscribers_formatted).toBe('522.00M')
    expect(useFlowStore.getState().channelLiveStats['chn_101']?.subscribers_formatted).toBe('522.00M')
  })

  it('deriveGlobalViralPrototypes sahte şablon döndürmemeli, yalnızca gerçek YouTube verilerini dönüştürmelidir', () => {
    // Canlı veri ve arama yokken boş dizi dönmeli (sahte kart olmamalı)
    const empty = deriveGlobalViralPrototypes('Test Kanal', 'Bilim', 'https://youtube.com/@test', [], null)
    expect(empty).toEqual([])

    // Gerçek canlı veriler verildiğinde yalnızca onları dönüştürmeli
    const realProtos = deriveGlobalViralPrototypes('Test Kanal', 'Bilim', 'https://youtube.com/@test', [], {
      channel_id: 'chn_101',
      channel_name: 'Test Kanal',
      channel_url: 'https://youtube.com/@test',
      avatar_url: null,
      description: 'Bilim',
      subscribers: 1000,
      subscribers_formatted: '1.0K',
      videos: [
        { id: 'v_real_1', type: 'video', title: 'Gerçek Kanal Videosu', url: 'https://www.youtube.com/watch?v=v_real_1', view_count: 45000, duration: 300 },
      ],
      shorts: [],
      niche_benchmarks: [
        { video_id: 'bm_real_1', title: 'Gerçek Niş Videosu', view_count: 120000, duration: 40, duration_text: '0:40', format: 'short', channel_name: 'Rakip Kanal', score: 88 },
      ],
      total_fetched_videos: 1,
      total_fetched_shorts: 0,
      avg_views_sample: 45000,
      avg_views_formatted: '45.0K',
      is_live: true,
      fetched_at: Date.now(),
    })

    expect(realProtos).toHaveLength(2)
    expect(realProtos[0].id).toBe('bm_real_1')
    expect(realProtos[0].globalViewsFormatted).toBe('120.0K İzlenme')
    expect(realProtos[1].id).toBe('v_real_1')
    expect(realProtos[1].globalViewsFormatted).toBe('45.0K İzlenme')
  })
})
