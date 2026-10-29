/**
 * Hustler Desktop — Kanal Çalışma Alanı Durum Dilimi (Channel Slice)
 * Kanal-Merkezli Mimari (Faz 2/2): Kanal CRUD, kanal içi içerik araştırması ve
 * seçilen içerikle Akış Stüdyosu → Senaryo adımına doğrudan geçiş (handoff).
 */

import type { StateCreator } from 'zustand'
import {
  createInitialAssetsData,
  createInitialPreviewData,
  createInitialRenderData,
  type AppView,
  type ChannelCreatePayload,
  type ChannelItem,
  type ChannelLiveStats,
  type DiscoveryItem,
  type FlowState,
  type VideoIdea,
} from '../flowTypes'
import { getIpcClient, type ProxyResponse } from '../../lib/ipc'
import { parseProblemDetails } from '../../lib/problemDetails'
import { generateDefaultAiSummary } from '../../components/channels/channelMetadata'

export interface ChannelSlice {
  activeView: AppView
  channels: ChannelItem[]
  activeChannelId: string | null
  /** Mevcut üretim akışının bağlı olduğu kanal (senaryo kaydına channel_id olarak iletilir). */
  flowChannelId: string | null
  channelIdeas: VideoIdea[]
  channelResearchQuery: string
  isChannelsLoading: boolean
  isChannelResearching: boolean
  channelLiveStats: Record<string, ChannelLiveStats | null>
  isLiveStatsLoading: boolean

  setActiveView: (view: AppView) => void
  loadChannels: () => Promise<void>
  createChannel: (payload: ChannelCreatePayload) => Promise<ChannelItem | null>
  deleteChannel: (id: string) => Promise<void>
  selectChannel: (id: string | null) => void
  updateChannelSummary: (channelId: string, aiSummary: string) => Promise<void>
  fetchChannelLiveStats: (channelId: string, refresh?: boolean) => Promise<ChannelLiveStats | null>
  researchChannelContent: (channelId: string, query: string) => Promise<void>
  selectIdeaFromChannelAndStartFlow: (channelId: string, idea: DiscoveryItem | VideoIdea) => void
}

type SliceSet = Parameters<StateCreator<FlowState, [], [], ChannelSlice>>[0]

/** RFC 9457 Problem Details yanıtını modal veya toast olarak yüzeye çıkarır. */
function surfaceError(set: SliceSet, source: unknown): string {
  const err = parseProblemDetails(source)
  if (err.mode === 'modal') set({ activeModalError: err })
  else set((s) => ({ toasts: [...s.toasts, err] }))
  return err.message
}

function isFailed(resp: ProxyResponse<unknown> | undefined): boolean {
  return !resp || resp.status >= 400
}

export function mapDiscoveryItemsToIdeas(items: DiscoveryItem[], topic: string): VideoIdea[] {
  return items.map((item, idx) => ({
    id: item.video_id ?? item.id ?? `idea_${idx + 1}`,
    title: item.title || `${topic} #${idx + 1}`,
    hook: item.hook ?? item.description ?? item.title ?? topic,
    score: typeof item.score === 'number' ? item.score : 85,
    viewCount: item.view_count ?? 0,
    duration: item.duration,
    durationText: item.duration_text,
    format: item.format,
    channelName: item.channel_name,
    url: item.url,
  }))
}

export const createChannelSlice: StateCreator<FlowState, [], [], ChannelSlice> = (set, get) => ({
  activeView: 'channels',
  channels: [],
  activeChannelId: null,
  flowChannelId: null,
  channelIdeas: [],
  channelResearchQuery: '',
  isChannelsLoading: false,
  isChannelResearching: false,
  channelLiveStats: {},
  isLiveStatsLoading: false,

  setActiveView: (view: AppView) => {
    set({ activeView: view })
  },

  loadChannels: async () => {
    const client = getIpcClient()
    if (!client.listChannels) return
    set({ isChannelsLoading: true })
    try {
      const resp = await client.listChannels()
      if (isFailed(resp)) {
        surfaceError(set, resp)
        set({ isChannelsLoading: false })
        return
      }
      const rawChannels = Array.isArray(resp.body) ? resp.body : []
      let savedMap: Record<string, string> = {}
      try {
        savedMap = JSON.parse(localStorage.getItem('hustler_ai_summaries_v1') || '{}') as Record<string, string>
      } catch {
        /* ignore */
      }
      const channels = rawChannels.map((ch: ChannelItem) => ({
        ...ch,
        ai_summary: ch.ai_summary || savedMap[ch.id] || generateDefaultAiSummary(ch.name, ch.description, ch.channel_url),
      }))
      const { activeChannelId } = get()
      const stillExists = activeChannelId ? channels.some((c) => c.id === activeChannelId) : true
      set({
        channels,
        isChannelsLoading: false,
        ...(stillExists ? {} : { activeChannelId: null, channelIdeas: [] }),
      })

      // Kanalların canlı YouTube abone ve üstverilerini arka planda hazırla
      channels.forEach((c) => {
        if (!get().channelLiveStats[c.id]) {
          void get().fetchChannelLiveStats(c.id)
        }
      })
    } catch (err: unknown) {
      surfaceError(set, err)
      set({ isChannelsLoading: false })
    }
  },

  createChannel: async (payload: ChannelCreatePayload) => {
    const client = getIpcClient()
    if (!client.createChannel) return null
    try {
      const resp = await client.createChannel({
        name: payload.name.trim(),
        channel_url: payload.channel_url.trim(),
        description: payload.description.trim(),
      })
      if (isFailed(resp)) {
        surfaceError(set, resp)
        return null
      }
      const rawCreated = resp.body
      const created: ChannelItem = {
        ...rawCreated,
        ai_summary: rawCreated.ai_summary || generateDefaultAiSummary(payload.name, payload.description, payload.channel_url),
      }
      set((s) => ({
        channels: [created, ...s.channels.filter((c) => c.id !== created.id)],
        activeChannelId: created.id,
      }))
      void get().fetchChannelLiveStats(created.id, true)
      get().addToast({ title: 'Kanal Oluşturuldu', message: `"${created.name}" eklendi.`, code: 'CHANNEL_CREATED' })
      return created
    } catch (err: unknown) {
      surfaceError(set, err)
      return null
    }
  },

  updateChannelSummary: async (channelId: string, aiSummary: string) => {
    set((s) => ({ channels: s.channels.map((c) => (c.id === channelId ? { ...c, ai_summary: aiSummary } : c)) }))
    try {
      const savedMap = JSON.parse(localStorage.getItem('hustler_ai_summaries_v1') || '{}') as Record<string, string>
      savedMap[channelId] = aiSummary
      localStorage.setItem('hustler_ai_summaries_v1', JSON.stringify(savedMap))
      get().addToast({ title: 'AI Algısı Güncellendi', message: 'Kanal profili kaydedildi.', code: 'CHANNEL_SUMMARY_UPDATED' })
    } catch { /* ignore */ }
  },

  deleteChannel: async (id: string) => {
    const client = getIpcClient()
    if (!client.deleteChannel) return
    try {
      const resp = await client.deleteChannel(id)
      if (isFailed(resp)) {
        surfaceError(set, resp)
        return
      }
      set((s) => ({
        channels: s.channels.filter((c) => c.id !== id),
        activeChannelId: s.activeChannelId === id ? null : s.activeChannelId,
        flowChannelId: s.flowChannelId === id ? null : s.flowChannelId,
        channelIdeas: s.activeChannelId === id ? [] : s.channelIdeas,
      }))
    } catch (err: unknown) {
      surfaceError(set, err)
    }
  },

  selectChannel: (id: string | null) => {
    const changed = get().activeChannelId !== id
    set({
      activeChannelId: id,
      ...(changed ? { channelIdeas: [], channelResearchQuery: '' } : {}),
    })
    if (id) {
      void get().fetchChannelLiveStats(id)
    }
  },

  fetchChannelLiveStats: async (channelId: string, refresh = false) => {
    const client = getIpcClient()
    if (!client.proxyRequest) return null
    set({ isLiveStatsLoading: true })
    try {
      const resp = await client.proxyRequest(
        'GET',
        `/api/v1/channels/${channelId}/live-stats${refresh ? '?refresh=true' : ''}`
      )
      if (isFailed(resp) || !resp.body) {
        set({ isLiveStatsLoading: false })
        return null
      }
      const data = resp.body as {
        live_data?: ChannelLiveStats
      }
      const liveStats = data.live_data ?? null
      if (liveStats) {
        set((s) => ({
          channelLiveStats: { ...s.channelLiveStats, [channelId]: liveStats },
          isLiveStatsLoading: false,
          channels: s.channels.map((c) =>
            c.id === channelId && liveStats.avatar_url
              ? { ...c, avatar_url: liveStats.avatar_url }
              : c
          ),
        }))
        return liveStats
      }
      set({ isLiveStatsLoading: false })
      return null
    } catch (err: unknown) {
      surfaceError(set, err)
      set({ isLiveStatsLoading: false })
      return null
    }
  },

  researchChannelContent: async (channelId: string, query: string) => {
    const topic = query.trim()
    if (topic.length < 2) {
      get().addToast({
        title: 'Geçersiz Arama',
        message: 'Araştırma konusu en az 2 karakter olmalıdır.',
        code: 'CHANNEL_RESEARCH_INVALID',
      })
      return
    }

    set({ isChannelResearching: true, channelResearchQuery: topic })
    try {
      const resp = await getIpcClient().runDiscovery(topic, channelId)
      if (isFailed(resp)) {
        surfaceError(set, resp)
        set({ isChannelResearching: false })
        return
      }
      if (resp.body?.degraded) {
        get().addToast({
          title: 'Kurtarma Modu (Degraded)',
          message: resp.body.warning ?? 'Sonuçlar yerel önbellek veya deterministik şablondan üretildi.',
          code: 'DISCOVERY_DEGRADED',
        })
      }
      const items = Array.isArray(resp.body?.results) ? resp.body.results : []
      set({ channelIdeas: mapDiscoveryItemsToIdeas(items, topic), isChannelResearching: false })
      // Gerçek araştırma metriğini yenile (SQLite COUNT)
      void get().loadChannels()
    } catch (err: unknown) {
      surfaceError(set, err)
      set({ isChannelResearching: false })
    }
  },

  selectIdeaFromChannelAndStartFlow: (channelId: string, idea: DiscoveryItem | VideoIdea) => {
    const videoIdea: VideoIdea = {
      id: ('video_id' in idea && idea.video_id) ? idea.video_id : (idea.id || `idea_${Date.now()}`),
      title: idea.title,
      hook: ('hook' in idea && idea.hook) ? idea.hook : (('description' in idea && idea.description) ? idea.description : idea.title),
      score: typeof idea.score === 'number' ? idea.score : 85,
      viewCount: ('view_count' in idea && idea.view_count) ? idea.view_count : (('viewCount' in idea && idea.viewCount) ? idea.viewCount : 150000),
    }

    const { channelIdeas, channelResearchQuery } = get()
    const topic = channelResearchQuery.trim().length >= 3 ? channelResearchQuery.trim() : videoIdea.title

    set({
      activeChannelId: channelId,
      flowChannelId: channelId,
      topic,
      ideas: channelIdeas.length > 0 ? channelIdeas : [videoIdea],
      selectedIdea: videoIdea,
      script: null,
      audio: null,
      assets: createInitialAssetsData(),
      preview: createInitialPreviewData(),
      render: createInitialRenderData(),
      currentStep: 'SCRIPT',
      activeView: 'pipeline',
      errorMessage: null,
    })

    // Seçilen içerik için senaryo üretimini başlat; ardından kanal metriklerini tazele
    void get()
      .generateScriptForIdea()
      .then(() => get().loadChannels())
  },
})
