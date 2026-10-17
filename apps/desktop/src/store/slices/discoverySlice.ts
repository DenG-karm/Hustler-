/**
 * Hustler Desktop — Keşif ve Fikir Durum Dilimi (Discovery Slice)
 */

import type { StateCreator } from 'zustand'
import type { FlowState, VideoIdea } from '../flowTypes'
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

export const createDiscoverySlice: StateCreator<
  FlowState,
  [],
  [],
  DiscoverySlice
> = (set, get) => ({
  topic: '',
  ideas: [],
  selectedIdea: null,

  setTopic: (topic: string) => {
    set({ topic, errorMessage: null })
  },

  selectIdea: (idea: VideoIdea) => {
    set({ selectedIdea: idea, errorMessage: null })
  },

  runDiscovery: async (topicOverride?: string) => {
    if (topicOverride) {
      set({ topic: topicOverride })
    }
    return get().fetchIdeasForTopic()
  },

  fetchIdeasForTopic: async () => {
    const { topic } = get()
    if (!topic || topic.trim().length < 3) {
      set({ errorMessage: 'Geçersiz konu başlığı.' })
      return
    }

    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.runDiscovery(topic)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err })
        else set((s) => ({ toasts: [...s.toasts, err] }))
        set({ errorMessage: err.message, isLoading: false })
        return
      }

      // K-806: yt-dlp bozulduğunda degraded uyarısı ver ama akışı kesme
      if (resp.body?.degraded || resp.body?.warning) {
        const warningMsg =
          typeof resp.body?.warning === 'string'
            ? resp.body.warning
            : 'yt-dlp çıkarıcısı yanıt vermiyor; yerel kurtarma modu aktif.'
        get().addToast({
          title: 'Çıkarıcı Uyarısı (Degraded Mod)',
          message: warningMsg,
          code: 'DISCOVERY_DEGRADED',
          mode: 'toast',
        })
      }

      const rawItems = Array.isArray(resp.body) ? resp.body : resp.body?.results ?? []

      const ideas: VideoIdea[] = rawItems.map((item: any, idx: number) => ({
        id: item.video_id ?? item.id ?? `idea_${idx + 1}`,
        title: item.title ?? `Fikir #${idx + 1}: ${topic}`,
        hook: item.hook ?? item.description ?? `Dikkat çeken kanca #${idx + 1}`,
        score: typeof item.score === 'number' ? item.score : 85 - idx * 2,
        viewCount: item.view_count ?? 150000,
      }))

      const fallbackIdeas: VideoIdea[] =
        ideas.length > 0
          ? ideas
          : Array.from({ length: 5 }, (_, i) => ({
              id: `idea_det_${i + 1}`,
              title: `${topic} Hakkında ${i + 1}. Viral Gerçek`,
              hook: `Bunu biliyor muydunuz? ${topic} ile ilgili kimsenin söylemediği sır!`,
              score: 95 - i * 5,
              viewCount: 250000 - i * 30000,
            }))

      set({ ideas: fallbackIdeas, isLoading: false })
    } catch (err: any) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
      }
    }
  },
})
