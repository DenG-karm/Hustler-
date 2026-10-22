import { describe, it, expect, vi, beforeEach } from 'vitest'
import { tauriIpcClient, type ChannelItem, type ChannelCreatePayload } from '../lib/ipc'
import { isProxyRouteAllowed, validateProxyRoute } from '../lib/securityGuard'

describe('Channel IPC ve Proxy İzin Listesi Testleri', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('/api/v1/channels rotaları güvenlik kalkanı izin listesinde geçerli olmalıdır', () => {
    expect(isProxyRouteAllowed('/api/v1/channels')).toBe(true)
    expect(isProxyRouteAllowed('/api/v1/channels/chn_12345')).toBe(true)
    expect(() => validateProxyRoute('/api/v1/channels')).not.toThrow()
    expect(() => validateProxyRoute('/api/v1/channels/chn_abc')).not.toThrow()
  })

  it('tauriIpcClient.listChannels çağrısı doğru rotaya GET isteği atmalıdır', async () => {
    const mockChannels: ChannelItem[] = [
      {
        id: 'chn_1',
        name: 'Tarih & Gizem',
        channel_url: 'https://youtube.com/@tarih',
        description: 'Tarih belgeselleri',
        created_at: 1710000000,
        metrics: { total_scripts: 5, total_research: 10 },
      },
    ]

    const spy = vi.spyOn(tauriIpcClient, 'proxyRequest').mockResolvedValue({
      status: 200,
      body: mockChannels,
    })

    const res = await tauriIpcClient.listChannels()
    expect(spy).toHaveBeenCalledWith('GET', '/api/v1/channels')
    expect(res.status).toBe(200)
    expect(res.body).toEqual(mockChannels)
  })

  it('tauriIpcClient.createChannel çağrısı doğru rotaya POST isteği atmalıdır', async () => {
    const payload: ChannelCreatePayload = {
      name: 'Bilim Kanalı',
      channel_url: 'https://youtube.com/@bilim',
      description: 'Uzay ve teknoloji',
    }
    const createdChannel: ChannelItem = {
      id: 'chn_created_1',
      ...payload,
      created_at: 1710000000,
      metrics: { total_scripts: 0, total_research: 0 },
    }

    const spy = vi.spyOn(tauriIpcClient, 'proxyRequest').mockResolvedValue({
      status: 201,
      body: createdChannel,
    })

    const res = await tauriIpcClient.createChannel(payload)
    expect(spy).toHaveBeenCalledWith('POST', '/api/v1/channels', payload)
    expect(res.status).toBe(201)
    expect(res.body.name).toBe('Bilim Kanalı')
  })

  it('tauriIpcClient.getChannelDetail ve deleteChannel doğru rotalara istek atmalıdır', async () => {
    const spy = vi.spyOn(tauriIpcClient, 'proxyRequest').mockImplementation(async (method, _route) => {
      if (method === 'GET') {
        return {
          status: 200,
          body: {
            id: 'chn_test_id',
            name: 'Kanal',
            channel_url: 'https://youtube.com/@test',
            description: 'Açıklama',
            created_at: 1710000000,
            metrics: { total_scripts: 0, total_research: 0 },
          },
        }
      }
      return {
        status: 200,
        body: { status: 'deleted', channel_id: 'chn_test_id' },
      }
    })

    const detailRes = await tauriIpcClient.getChannelDetail('chn_test_id')
    expect(spy).toHaveBeenCalledWith('GET', '/api/v1/channels/chn_test_id')
    expect(detailRes.body.id).toBe('chn_test_id')

    const deleteRes = await tauriIpcClient.deleteChannel('chn_test_id')
    expect(spy).toHaveBeenCalledWith('DELETE', '/api/v1/channels/chn_test_id')
    expect(deleteRes.body.status).toBe('deleted')
  })
})
