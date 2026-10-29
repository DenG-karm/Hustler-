/**
 * Hustler Desktop — Keşif ve Fikir Durum Dilimi (Discovery Slice)
 */

import type { StateCreator } from 'zustand'
import type { FlowState, VideoIdea, DiscoveryItem } from '../flowTypes'
import { getIpcClient } from '../../lib/ipc'
import { parseProblemDetails } from '../../lib/problemDetails'

export interface DiscoverySlice {
  topic: string
  ideas: VideoIdea[]
  selectedIdea: VideoIdea | null

  setTopic: (topic: string) => void
  selectIdea: (idea: VideoIdea) => void
  runDiscovery: (topicOverride?: string) => Promise<void>
  fetchIdeasForTopic: () => Promise<void>
}

export const createDiscoverySlice: StateCreator<FlowState, [], [], DiscoverySlice> = (set, get) => ({
  topic: '',
  ideas: [],
  selectedIdea: null,

  setTopic: (topic: string) => set({ topic, errorMessage: null }),
  selectIdea: (idea: VideoIdea) => set({ selectedIdea: idea, errorMessage: null }),
  runDiscovery: async (topicOverride?: string) => {
    if (topicOverride) set({ topic: topicOverride })
    return get().fetchIdeasForTopic()
  },

  fetchIdeasForTopic: async () => {
    const { topic, activeChannelId, flowChannelId } = get()
    if (!topic || topic.trim().length < 3) {
      set({ errorMessage: 'Geçersiz konu başlığı.' })
      return
    }
    set({ isLoading: true, errorMessage: null })
    try {
      const resp = await getIpcClient().runDiscovery(topic, flowChannelId ?? activeChannelId)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err, errorMessage: err.message, isLoading: false })
        else set((s) => ({ toasts: [...s.toasts, err], errorMessage: err.message, isLoading: false }))
        return
      }
      if (resp.body?.degraded || resp.body?.warning) {
        get().addToast({
          title: 'Çıkarıcı Uyarısı (Degraded Mod)',
          message: typeof resp.body?.warning === 'string' ? resp.body.warning : 'Yerel kurtarma modu aktif.',
          code: 'DISCOVERY_DEGRADED',
        })
      }
      const rawItems: DiscoveryItem[] = Array.isArray(resp.body?.results) ? resp.body.results : (Array.isArray(resp.body) ? resp.body : [])
      const ideas: VideoIdea[] = rawItems.map((item: DiscoveryItem, idx: number) => ({
        id: item.video_id ?? item.id ?? `idea_${idx + 1}`,
        title: item.title ?? `Fikir #${idx + 1}: ${topic}`,
        hook: item.hook ?? item.description ?? `Dikkat çeken kanca #${idx + 1}`,
        score: typeof item.score === 'number' ? item.score : 85 - idx * 2,
        viewCount: item.view_count ?? 150000,
      }))
      set({
        ideas: ideas.length ? ideas : Array.from({ length: 5 }, (_, i) => ({
          id: `idea_det_${i + 1}`,
          title: `${topic} Hakkında ${i + 1}. Viral Gerçek`,
          hook: `Bunu biliyor muydunuz? ${topic} ile ilgili sır!`,
          score: 95 - i * 5,
          viewCount: 250000 - i * 30000,
        })),
        isLoading: false,
      })
    } catch (err: unknown) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      else set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
    }
  },
})
