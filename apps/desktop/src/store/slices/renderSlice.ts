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

const handleSliceError = (set: Parameters<StateCreator<FlowState, [], [], RenderSlice>>[0], source: unknown) => {
  const err = parseProblemDetails(source)
  if (err.mode === 'modal') set({ activeModalError: err, isLoading: false, errorMessage: err.message })
  else set((s) => ({ toasts: [...s.toasts, err], isLoading: false, errorMessage: err.message }))
}

export const createRenderSlice: StateCreator<FlowState, [], [], RenderSlice> = (set, get) => ({
  assets: createInitialAssetsData(),
  preview: createInitialPreviewData(),
  render: createInitialRenderData(),

  assignAssetSlot: (slotId: string, path: string) => {
    set((state) => {
      const updatedSlots = state.assets.slots.map((s) => (s.slotId === slotId ? { ...s, assignedPath: path } : s))
      return {
        assets: { slots: updatedSlots, allSlotsFilled: updatedSlots.filter((s) => s.required).every((s) => s.assignedPath !== null) },
        errorMessage: null,
      }
    })
  },

  setPreviewVerified: (verified: boolean) => {
    set((state) => ({ preview: { ...state.preview, isVerified: verified }, errorMessage: null }))
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
      const resp = await getIpcClient().cancelJob(render.jobId)
      if (resp.status >= 400) handleSliceError(set, resp)
      else set((state) => ({ render: { ...state.render, status: 'CANCELLED' }, isLoading: false }))
    } catch (err: unknown) {
      handleSliceError(set, err)
    }
  },

  loadAssetsForScript: async () => {
    const { script } = get()
    if (!script) return
    set({ isLoading: true, errorMessage: null })
    try {
      const resp = await getIpcClient().prepareAssets(script.id)
      if (resp.status >= 400) {
        handleSliceError(set, resp)
        return
      }
      const rawSlots = (resp.body.slots ?? createInitialAssetsData().slots) as Array<{
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
      set({ assets: { slots, allSlotsFilled: slots.filter((s) => s.required).every((s) => s.assignedPath !== null) }, isLoading: false })
    } catch (err: unknown) {
      handleSliceError(set, err)
    }
  },

  buildPreviewForScript: async () => {
    const { script } = get()
    if (!script) return
    set({ isLoading: true, errorMessage: null })
    try {
      const resp = await getIpcClient().generatePreview(script.id)
      if (resp.status >= 400) {
        handleSliceError(set, resp)
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
      handleSliceError(set, err)
    }
  },

  dispatchRenderJob: async (profile: 'DRAFT' | 'FINAL' = 'DRAFT') => {
    const { script } = get()
    if (!script) return
    set({ isLoading: true, errorMessage: null })
    try {
      const resp = await getIpcClient().triggerRender(profile, script.id)
      if (resp.status >= 400) {
        handleSliceError(set, resp)
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
      handleSliceError(set, err)
    }
  },

  pollJobStatus: async () => {
    const { render } = get()
    if (!render.jobId) return
    try {
      const resp = await getIpcClient().getJobStatus(render.jobId)
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
      set({ errorMessage: parseProblemDetails(err).message })
    }
  },
})
