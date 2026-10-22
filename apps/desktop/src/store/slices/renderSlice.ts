/**
 * Hustler Desktop — Varlık/Slot Atama, Önizleme, Render ve İptal Dilimi (Render Slice)
 */

import type { StateCreator } from 'zustand'
import {
  type FlowState,
  type AssetsData,
  type PreviewData,
  type RenderData,
  type AssetSlot,
  createInitialAssetsData,
  createInitialPreviewData,
  createInitialRenderData,
} from '../flowTypes'
import { getIpcClient } from '../../lib/ipc'
import { parseProblemDetails } from '../../lib/problemDetails'

export interface RenderSlice {
  assets: AssetsData
  preview: PreviewData
  render: RenderData

  assignAssetSlot: (slotId: string, path: string) => void
  setPreviewVerified: (verified: boolean) => void
  setRenderProgress: (progress: number, status?: RenderData['status'], outputPath?: string, error?: string) => void
  cancelRenderJob: () => Promise<void>
  loadAssetsForScript: () => Promise<void>
  buildPreviewForScript: () => Promise<void>
  dispatchRenderJob: (profile?: 'DRAFT' | 'FINAL') => Promise<void>
  pollJobStatus: () => Promise<void>
}

export const createRenderSlice: StateCreator<
  FlowState,
  [],
  [],
  RenderSlice
> = (set, get) => ({
  assets: createInitialAssetsData(),
  preview: createInitialPreviewData(),
  render: createInitialRenderData(),

  assignAssetSlot: (slotId: string, path: string) => {
    set((state) => {
      const updatedSlots = state.assets.slots.map((s) =>
        s.slotId === slotId ? { ...s, assignedPath: path } : s
      )
      const allRequiredFilled = updatedSlots
        .filter((s) => s.required)
        .every((s) => s.assignedPath !== null)

      return {
        assets: {
          slots: updatedSlots,
          allSlotsFilled: allRequiredFilled,
        },
        errorMessage: null,
      }
    })
  },

  setPreviewVerified: (verified: boolean) => {
    set((state) => ({
      preview: { ...state.preview, isVerified: verified },
      errorMessage: null,
    }))
  },

  setRenderProgress: (progress: number, status?: RenderData['status'], outputPath?: string, error?: string) => {
    set((state) => ({
      render: {
        ...state.render,
        progress,
        status: status ?? state.render.status,
        outputPath: outputPath ?? state.render.outputPath,
        error: error ?? state.render.error,
      },
    }))
  },

  cancelRenderJob: async () => {
    const { render } = get()
    if (!render.jobId) return

    set({ isLoading: true })
    try {
      const client = getIpcClient()
      const resp = await client.cancelJob(render.jobId)
      if (resp.status >= 400) {
        const uiError = parseProblemDetails(resp)
        if (uiError.mode === 'modal') {
          set({ activeModalError: uiError, isLoading: false })
        } else {
          set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false }))
        }
      } else {
        set((state) => ({
          render: {
            ...state.render,
            status: 'CANCELLED',
          },
          isLoading: false,
        }))
      }
    } catch (err: unknown) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false }))
      }
    }
  },

  loadAssetsForScript: async () => {
    const { script } = get()
    if (!script) return

    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.prepareAssets(script.id)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err })
        else set((s) => ({ toasts: [...s.toasts, err] }))
        set({ errorMessage: err.message, isLoading: false })
        return
      }

      const data = resp.body
      const rawSlots = (data.slots ?? createInitialAssetsData().slots) as Array<{
        slot_id?: string
        slotId?: string
        name?: string
        type?: 'video' | 'image' | 'audio'
        required?: boolean
        assigned_path?: string | null
        assignedPath?: string | null
      }>

      const slots: AssetSlot[] = rawSlots.map((s) => ({
        slotId: s.slot_id ?? s.slotId ?? '',
        name: s.name ?? '',
        type: s.type ?? 'image',
        required: typeof s.required === 'boolean' ? s.required : true,
        assignedPath: s.assigned_path ?? s.assignedPath ?? null,
      }))

      const allFilled = slots.filter((s) => s.required).every((s) => s.assignedPath !== null)

      set({
        assets: { slots, allSlotsFilled: allFilled },
        isLoading: false,
      })
    } catch (err: unknown) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
      }
    }
  },

  buildPreviewForScript: async () => {
    const { script } = get()
    if (!script) return

    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.generatePreview(script.id)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err })
        else set((s) => ({ toasts: [...s.toasts, err] }))
        set({ errorMessage: err.message, isLoading: false })
        return
      }

      const data = resp.body
      set({
        preview: {
          previewUrl: data.preview_url ?? `assets/previews/${script.id}.mp4`,
          fps: data.fps ?? 30,
          resolution: data.resolution ?? '540x960',
          isVerified: false,
        },
        isLoading: false,
      })
    } catch (err: unknown) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
      }
    }
  },

  dispatchRenderJob: async (profile: 'DRAFT' | 'FINAL' = 'DRAFT') => {
    const { script } = get()
    if (!script) return

    set({ isLoading: true, errorMessage: null })
    try {
      const client = getIpcClient()
      const resp = await client.triggerRender(profile, script.id)
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        if (err.mode === 'modal') set({ activeModalError: err })
        else set((s) => ({ toasts: [...s.toasts, err] }))
        set({ errorMessage: err.message, isLoading: false })
        return
      }

      const data = resp.body
      set({
        render: {
          jobId: data.job_id ?? `job_${Date.now()}`,
          profile,
          status: 'RENDERING',
          progress: 5,
          outputPath: data.output_path ?? null,
          error: null,
        },
        isLoading: false,
      })
    } catch (err: unknown) {
      const uiError = parseProblemDetails(err)
      if (uiError.mode === 'modal') {
        set({ activeModalError: uiError, isLoading: false, errorMessage: uiError.message })
      } else {
        set((s) => ({ toasts: [...s.toasts, uiError], isLoading: false, errorMessage: uiError.message }))
      }
    }
  },

  pollJobStatus: async () => {
    // K-703: SSE Event Stream önceliklidir; bu metot manuel sorgu/fallback içindir.
    const { render } = get()
    if (!render.jobId) return

    try {
      const client = getIpcClient()
      const resp = await client.getJobStatus(render.jobId)
      const data = resp.body

      set((state) => ({
        render: {
          ...state.render,
          status: data.status ?? state.render.status,
          progress: data.progress ?? state.render.progress,
          outputPath: data.output_path ?? state.render.outputPath,
          error: data.error_message ?? state.render.error,
        },
      }))
    } catch (err: unknown) {
      const uiError = parseProblemDetails(err)
      set({ errorMessage: uiError.message })
    }
  },
})
