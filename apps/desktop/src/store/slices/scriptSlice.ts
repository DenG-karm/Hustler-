/**
 * Hustler Desktop — Senaryo, İddia Doğrulama ve Ses Durum Dilimi (Script Slice)
 */

import type { StateCreator } from 'zustand'
import {
  InvalidStateTransitionError,
  type FlowState,
  type ScriptData,
  type ScriptClaim,
  type AudioData,
} from '../flowTypes'
import { getIpcClient, type ProxyResponse } from '../../lib/ipc'
import { parseProblemDetails } from '../../lib/problemDetails'

export interface ScriptSlice {
  script: ScriptData | null
  audio: AudioData | null

  setScript: (script: Partial<ScriptData>) => void
  toggleClaim: (claimId: string) => void
  setClaimVerified: (claimId: string, verified: boolean) => void
  saveScriptContent: (titleOverride?: string, fullTextOverride?: string) => Promise<ProxyResponse | null>
  approveScript: () => void
  setAudio: (audio: Partial<AudioData>) => void
  generateScriptForIdea: () => Promise<void>
  generateAudioForScript: (voiceId?: string) => Promise<void>
}

export const createScriptSlice: StateCreator<
  FlowState,
  [],
  [],
  ScriptSlice
> = (set, get) => ({
  script: null,
  audio: null,

  setScript: (scriptUpdate: Partial<ScriptData>) => {
    set((state) => {
      if (!state.script) {
        return {
          script: {
            id: scriptUpdate.id ?? `scr_${Date.now()}`,
            title: scriptUpdate.title ?? '',
            hook: scriptUpdate.hook ?? '',
            fullText: scriptUpdate.fullText ?? '',
            scenes: scriptUpdate.scenes ?? [],
            claims: scriptUpdate.claims ?? [],
            isApproved: scriptUpdate.isApproved ?? false,
          },
          errorMessage: null,
        }
      }
      const textOrTitleChanged =
        (scriptUpdate.title !== undefined && scriptUpdate.title !== state.script.title) ||
        (scriptUpdate.fullText !== undefined && scriptUpdate.fullText !== state.script.fullText)

      return {
        script: {
          ...state.script,
          ...scriptUpdate,
          isApproved: textOrTitleChanged ? false : (scriptUpdate.isApproved ?? state.script.isApproved),
        },
        errorMessage: null,
      }
    })
  },

  toggleClaim: (claimId: string) => {
    set((state) => {
      if (!state.script) return state
      const updatedClaims = (state.script.claims || []).map((c) =>
        c.id === claimId ? { ...c, verified: !c.verified } : c
      )
      return {
        script: {
          ...state.script,
          claims: updatedClaims,
          isApproved: false, // İddia durumu değiştiğinde yeniden onay gerekir
        },
        errorMessage: null,
      }
    })
  },

  setClaimVerified: (claimId: string, verified: boolean) => {
    set((state) => {
      if (!state.script) return state
      const updatedClaims = (state.script.claims || []).map((c) =>
        c.id === claimId ? { ...c, verified } : c
      )
      return {
        script: {
          ...state.script,
          claims: updatedClaims,
          isApproved: false,
        },
        errorMessage: null,
      }
    })
  },

  saveScriptContent: async (titleOverride?: string, fullTextOverride?: string) => {
    const { script } = get()
    if (!script) return null

    const title = titleOverride ?? script.title
    const fullText = fullTextOverride ?? script.fullText

    set((s) => ({
      script: s.script ? { ...s.script, isSaving: true, saveStatus: 'SAVING' } : null,
    }))

    try {
      const client = getIpcClient()
      const resp = await client.saveScript(
        script.id,
        title,
        fullText,
        script.scenes,
        script.claims,
        script.isApproved
      )

      const status = resp.body?.status === 'UNCHANGED' ? 'UNCHANGED' : 'SAVED'
      set((s) => ({
        script: s.script
          ? {
              ...s.script,
              isSaving: false,
              saveStatus: status,
              lastSavedAt: Date.now(),
            }
          : null,
      }))
      return resp
    } catch (err: unknown) {
      set((s) => ({
        script: s.script ? { ...s.script, isSaving: false, saveStatus: 'ERROR' } : null,
      }))
      throw err
    }
  },

  approveScript: () => {
    const state = get()
    if (!state.script) {
      const err = new InvalidStateTransitionError('SCRIPT', 'AUDIO', 'Onaylanacak senaryo bulunamadı.')
      set({ errorMessage: err.message })
      throw err
    }
    const unverified = (state.script.claims || []).filter((c) => !c.verified)
    if (unverified.length > 0) {
      const err = new InvalidStateTransitionError(
        'SCRIPT',
        'AUDIO',
        `Tüm iddialar (claims) kullanıcı tarafından onaylanmadan senaryo onaylanamaz. Onay bekleyen iddia sayısı: ${unverified.length}`
      )
      set({ errorMessage: err.message })
      throw err
    }

    set((s) => ({
      script: s.script ? { ...s.script, isApproved: true } : null,
      errorMessage: null,
    }))
  },

  setAudio: (audioUpdate: Partial<AudioData>) => {
    set((state) => ({
      audio: state.audio ? { ...state.audio, ...audioUpdate } : (audioUpdate as AudioData),
      errorMessage: null,
    }))
  },

  generateScriptForIdea: async () => {
    const { selectedIdea, topic, flowChannelId, activeChannelId } = get()
    if (!selectedIdea) {
      set({ errorMessage: 'Önce bir fikir seçmelisiniz.' })
      return
    }

    const currentIdea = selectedIdea
    const channelId = flowChannelId ?? activeChannelId

    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.generateScript(currentIdea.id, topic, currentIdea.title, channelId)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err })
        else set((s) => ({ toasts: [...s.toasts, err] }))
        set({ errorMessage: err.message, isLoading: false })
        return
      }

      const data = resp.body
      const rawClaims = Array.isArray(data.claims) ? data.claims : []
      const claims: ScriptClaim[] =
        rawClaims.length > 0
          ? rawClaims.map((c: ScriptClaim | { id?: string; text?: string; verified?: boolean } | string, idx: number) => ({
              id: typeof c === 'object' && c && 'id' in c && c.id ? c.id : `claim_${idx + 1}`,
              text: typeof c === 'string' ? c : (c.text ?? `İddia #${idx + 1}`),
              verified: typeof c === 'object' && c && 'verified' in c ? Boolean(c.verified) : false,
            }))
          : [
              { id: 'claim_1', text: `${topic} konusundaki veriler resmi kaynaklarla doğrulanmıştır.`, verified: false },
              { id: 'claim_2', text: 'Sunulan rakamlar ve test sonuçları güncel araştırmalara dayanmaktadır.', verified: false },
              { id: 'claim_3', text: 'Metin yanıltıcı veya asılsız sağlık/finansal vaatler içermemektedir.', verified: false },
            ]

      const script: ScriptData = {
        id: data.script_id ?? `scr_${Date.now()}`,
        title: data.title ?? currentIdea.title,
        hook: data.hook ?? currentIdea.hook,
        fullText: data.full_text ?? `${currentIdea.title}. ${currentIdea.hook}`,
        scenes: data.scenes ?? [
          { order: 1, narration: currentIdea.hook, visualPrompt: 'Cinematic visual' },
        ],
        claims,
        isApproved: false,
      }

      set({ script, isLoading: false })
    } catch (err: unknown) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
      }
    }
  },

  generateAudioForScript: async (voiceId = 'tr-TR-Standard-A') => {
    const { script } = get()
    if (!script) {
      set({ errorMessage: 'Ses üretmek için onaylanmış bir senaryo gereklidir.' })
      return
    }

    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.generateAudio(script.id, voiceId, script.fullText)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err })
        else set((s) => ({ toasts: [...s.toasts, err] }))
        set({ errorMessage: err.message, isLoading: false })
        return
      }

      const data = resp.body
      const audio: AudioData = {
        scriptId: script.id,
        voiceId,
        audioPath: data.audio_path ?? `assets/audio/${script.id}.mp3`,
        durationSeconds: data.duration_seconds ?? 30,
        isGenerated: true,
      }

      set({ audio, isLoading: false })
    } catch (err: unknown) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
      }
    }
  },
})
