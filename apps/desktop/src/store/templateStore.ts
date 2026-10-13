/**
 * Hustler Desktop — Şablon Durum Yönetimi (K-706)
 *
 * Şablon listesi, kategori filtreleme ve klonlama işlemlerini yönetir.
 * Başlangıç verisi olarak src/lib/templates.ts içerisindeki INITIAL_TEMPLATES kullanılır.
 */

import { create } from 'zustand'
import {
  type Template,
  type TemplateCategory,
  INITIAL_TEMPLATES,
  cloneTemplate,
} from '../lib/templates'

export interface TemplateState {
  templates: Template[]
  selectedCategory: TemplateCategory | 'all'
  selectedTemplateId: string | null
  setSelectedCategory: (cat: TemplateCategory | 'all') => void
  selectTemplate: (id: string | null) => void
  addTemplate: (template: Template) => void
  removeTemplate: (id: string) => void
  cloneTemplateItem: (id: string, customName?: string) => Template | null
  resetTemplates: () => void
}

export const useTemplateStore = create<TemplateState>((set, get) => ({
  templates: [...INITIAL_TEMPLATES],
  selectedCategory: 'all',
  selectedTemplateId: null,

  setSelectedCategory: (selectedCategory) => set({ selectedCategory }),
  selectTemplate: (selectedTemplateId) => set({ selectedTemplateId }),

  addTemplate: (template) =>
    set((state) => ({
      templates: [template, ...state.templates.filter((t) => t.id !== template.id)],
    })),

  removeTemplate: (id) =>
    set((state) => ({
      templates: state.templates.filter((t) => t.id !== id),
      selectedTemplateId: state.selectedTemplateId === id ? null : state.selectedTemplateId,
    })),

  cloneTemplateItem: (id, customName) => {
    const { templates } = get()
    const target = templates.find((t) => t.id === id)
    if (!target) return null
    const cloned = cloneTemplate(target, customName)
    set((state) => ({ templates: [cloned, ...state.templates] }))
    return cloned
  },

  resetTemplates: () =>
    set({
      templates: [...INITIAL_TEMPLATES],
      selectedCategory: 'all',
      selectedTemplateId: null,
    }),
}))
