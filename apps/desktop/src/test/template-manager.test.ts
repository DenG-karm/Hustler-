/**
 * K-706: Şablon Yöneticisi — Zod Şema Doğrulaması, Idempotent Klonlama ve Tauri Native I/O Testleri
 *
 * MİMARİ KURALLAR:
 * 1. Katı Şema Doğrulaması (Zod): İçe aktarılan veya işlenen her veri Zod ile denetlenir.
 *    Eksik anahtar, geçersiz tip veya bozuk JSON anında ZodError ile reddedilir.
 * 2. Sıfır Web I/O API: Tarayıcı dosya API'leri (<input type="file">, FileReader,
 *    showOpenFilePicker, showSaveFilePicker, URL.createObjectURL, Blob) KESİNLİKLE YASAKTIR.
 *    Tüm I/O işlemleri Tauri Rust IPC (@tauri-apps/plugin-dialog ve @tauri-apps/plugin-fs) üzerinden yürütülür.
 * 3. Idempotent Klonlama: Referans kopyası (shallow copy) yasaktır. Derin kopya (deep copy)
 *    alınarak yeni UUID üretilir, referans bağı tamamen koparılır.
 *
 * Faz 1: Salt Test Kodları (İmplementasyon taslakları Faz 2'de src/lib/templates.ts'e taşınacaktır)
 */

import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { z, ZodError } from 'zod'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { TemplateManager } from '../components/templates/TemplateManager'
import { useTemplateStore } from '../store/templateStore'
import { useFlowStore } from '../store/flowStore'

// ---------------------------------------------------------------------------
// @tauri-apps/api/core Module-Level Mock (Vitest worker timeout koruması)
// ---------------------------------------------------------------------------
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
}))

import { invoke } from '@tauri-apps/api/core'
import {
  type Template,
  validateTemplate,
  cloneTemplate,
  exportTemplateToFile,
  importTemplateFromFile,
} from '../lib/templates'

// ---------------------------------------------------------------------------
// Test Veri Fixture'ı — Geçerli Referans Şablon
// ---------------------------------------------------------------------------

const VALID_TEMPLATE_FIXTURE: Template = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  name: 'Viral Shorts Kurgusu',
  category: 'tech',
  description: '9:16 dikey formatta hızlı tempolu teknoloji shorts şablonu.',
  version: 1,
  aspectRatio: '9:16',
  fps: 30,
  subtitleStyle: {
    font_name: 'Arial',
    font_size: 90,
    primary_color: '&H00FFFFFF&',
    highlight_color: '&H0000FFFF&',
    alignment: 5,
    margin_v: 50,
  },
  audioSettings: {
    voiceId: 'tr-TR-Standard-A',
    speed: 1.1,
    volume: 0.9,
  },
  slots: [
    { slotId: 'slot_hook', name: 'Giriş Kancası', type: 'video', required: true },
    { slotId: 'slot_broll_1', name: 'B-Roll 1', type: 'image', required: true },
    { slotId: 'slot_bgm', name: 'Arka Plan Müziği', type: 'audio', required: false },
  ],
  tags: ['shorts', 'tech', 'viral'],
  createdAt: 1710000000000,
  updatedAt: 1710000000000,
}

// ---------------------------------------------------------------------------
// SUITE 1: Zod Katı Şema Doğrulaması (Schema Validation & Rejection)
// ---------------------------------------------------------------------------
describe('K-706: Zod Katı Şema Doğrulaması (Schema Validation)', () => {
  it('eksiksiz ve geçerli şablon nesnesini hatasız doğrulamalı ve döndürmeli', () => {
    const validated = validateTemplate(VALID_TEMPLATE_FIXTURE)
    expect(validated).toEqual(VALID_TEMPLATE_FIXTURE)
    expect(validated.id).toBe('550e8400-e29b-41d4-a716-446655440000')
    expect(validated.category).toBe('tech')
  })

  it('geçerli JSON dizesi verildiğinde ayrıştırıp başarıyla doğrulamalı', () => {
    const jsonString = JSON.stringify(VALID_TEMPLATE_FIXTURE)
    const validated = validateTemplate(jsonString)
    expect(validated.name).toBe('Viral Shorts Kurgusu')
    expect(validated.slots).toHaveLength(3)
  })

  it('bozuk veya sentaks hatası içeren JSON dizesinde ZodError fırlatmalı', () => {
    const corruptedJson = '{ id: "123", name: "Bozuk JSON", '
    expect(() => validateTemplate(corruptedJson)).toThrow(ZodError)
  })

  it('zorunlu anahtarlardan biri eksik olduğunda ZodError fırlatmalı', () => {
    const { name, ...missingName } = VALID_TEMPLATE_FIXTURE
    expect(() => validateTemplate(missingName)).toThrow(ZodError)

    const { subtitleStyle, ...missingSubtitles } = VALID_TEMPLATE_FIXTURE
    expect(() => validateTemplate(missingSubtitles)).toThrow(ZodError)

    const { slots, ...missingSlots } = VALID_TEMPLATE_FIXTURE
    expect(() => validateTemplate(missingSlots)).toThrow(ZodError)
  })

  it('geçersiz UUID formatında id verildiğinde ZodError fırlatmalı', () => {
    const invalidIdTemplate = {
      ...VALID_TEMPLATE_FIXTURE,
      id: 'invalid-non-uuid-string-1234',
    }
    expect(() => validateTemplate(invalidIdTemplate)).toThrow(ZodError)
  })

  it('tanımsız / izin verilmeyen kategori verildiğinde reddetmeli', () => {
    const invalidCategoryTemplate = {
      ...VALID_TEMPLATE_FIXTURE,
      category: 'crypto_scam_category',
    }
    expect(() => validateTemplate(invalidCategoryTemplate)).toThrow(ZodError)
  })

  it('ASS renk formatına (&HBBGGRR&) uymayan renk kodu verildiğinde reddetmeli', () => {
    const invalidColorTemplate = {
      ...VALID_TEMPLATE_FIXTURE,
      subtitleStyle: {
        ...VALID_TEMPLATE_FIXTURE.subtitleStyle,
        primary_color: '#FFFFFF', // Geçersiz hex formatı (ASS &HBBGGRR& olmalıdır)
      },
    }
    expect(() => validateTemplate(invalidColorTemplate)).toThrow(ZodError)
  })

  it('slot listesi boş olduğunda (slots: []) kuralı ihlal edip ZodError fırlatmalı', () => {
    const emptySlotsTemplate = {
      ...VALID_TEMPLATE_FIXTURE,
      slots: [],
    }
    expect(() => validateTemplate(emptySlotsTemplate)).toThrow(ZodError)
  })

  it('geçersiz en-boy oranı (aspectRatio) verildiğinde reddetmeli', () => {
    const invalidRatioTemplate = {
      ...VALID_TEMPLATE_FIXTURE,
      aspectRatio: '4:3', // İzin verilenler: '9:16', '16:9', '1:1'
    }
    expect(() => validateTemplate(invalidRatioTemplate)).toThrow(ZodError)
  })

  it('negatif veya aralık dışı FPS değeri verildiğinde reddetmeli', () => {
    const invalidFpsTemplate = {
      ...VALID_TEMPLATE_FIXTURE,
      fps: -5,
    }
    expect(() => validateTemplate(invalidFpsTemplate)).toThrow(ZodError)
  })
})

// ---------------------------------------------------------------------------
// SUITE 2: Idempotent Klonlama (Deep Copy & UUID Generation)
// ---------------------------------------------------------------------------
describe('K-706: Idempotent Klonlama (Deep Copy & UUID)', () => {
  it('klonlanan şablon yeni ve geçerli bir UUID almalı, orijinal id korunmalı', () => {
    const clone = cloneTemplate(VALID_TEMPLATE_FIXTURE)
    expect(clone.id).not.toBe(VALID_TEMPLATE_FIXTURE.id)
    // UUID formatı doğrulaması
    expect(z.string().uuid().safeParse(clone.id).success).toBe(true)
    expect(VALID_TEMPLATE_FIXTURE.id).toBe('550e8400-e29b-41d4-a716-446655440000')
  })

  it('klonlanan nesne orijinal ile nesne referansı paylaşmamalı (Derin Kopya Garantisi)', () => {
    const clone = cloneTemplate(VALID_TEMPLATE_FIXTURE)

    // Kök nesne referansı
    expect(clone).not.toBe(VALID_TEMPLATE_FIXTURE)

    // İç içe nesne referansları (shallow copy trap testi)
    expect(clone.subtitleStyle).not.toBe(VALID_TEMPLATE_FIXTURE.subtitleStyle)
    expect(clone.audioSettings).not.toBe(VALID_TEMPLATE_FIXTURE.audioSettings)
    expect(clone.slots).not.toBe(VALID_TEMPLATE_FIXTURE.slots)
    expect(clone.tags).not.toBe(VALID_TEMPLATE_FIXTURE.tags)
  })

  it('klonlanan nesnenin slotları veya stilleri değiştirildiğinde orijinal kesinlikle etkilenmemeli', () => {
    const clone = cloneTemplate(VALID_TEMPLATE_FIXTURE)

    // Klonu mutasyona uğrat
    clone.slots[0].name = 'Tamamen Değiştirilmiş Kanca'
    clone.subtitleStyle.font_size = 150
    clone.tags.push('yeni-etiket')

    // Orijinal nesne saf kalmalı
    expect(VALID_TEMPLATE_FIXTURE.slots[0].name).toBe('Giriş Kancası')
    expect(VALID_TEMPLATE_FIXTURE.subtitleStyle.font_size).toBe(90)
    expect(VALID_TEMPLATE_FIXTURE.tags).not.toContain('yeni-etiket')
  })

  it('özel isim verilmezse varsayılan "(Kopya)" ekini almalı, verilirse özel ismi kullanmalı', () => {
    const defaultClone = cloneTemplate(VALID_TEMPLATE_FIXTURE)
    expect(defaultClone.name).toBe('Viral Shorts Kurgusu (Kopya)')

    const customNamedClone = cloneTemplate(VALID_TEMPLATE_FIXTURE, 'Benim Özel Şablonum')
    expect(customNamedClone.name).toBe('Benim Özel Şablonum')
  })

  it('klonlanan şablon Zod şema doğrulamasından eksiksiz geçmeli', () => {
    const clone = cloneTemplate(VALID_TEMPLATE_FIXTURE)
    expect(() => validateTemplate(clone)).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// SUITE 3: Tauri Native I/O (plugin-dialog & plugin-fs Mock Entegrasyonu)
// ---------------------------------------------------------------------------
describe('K-706: Tauri Native I/O (plugin-dialog ve plugin-fs)', () => {
  const mockInvoke = invoke as ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('exportTemplateToFile: Tauri dialog save ve fs write_text_file invoke komutlarını sırayla çağırmalı', async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === 'plugin:dialog|save') {
        return 'C:\\Users\\Hustler\\templates\\viral_template.json'
      }
      if (cmd === 'plugin:fs|write_text_file') {
        return undefined
      }
      return undefined
    })

    const result = await exportTemplateToFile(VALID_TEMPLATE_FIXTURE)

    expect(result.success).toBe(true)
    expect(result.filePath).toBe('C:\\Users\\Hustler\\templates\\viral_template.json')

    // Dialog çağrısı denetimi
    expect(mockInvoke).toHaveBeenCalledWith('plugin:dialog|save', expect.objectContaining({
      filters: [{ name: 'Hustler Şablonu', extensions: ['json'] }],
    }))

    // Fs yazma çağrısı denetimi
    expect(mockInvoke).toHaveBeenCalledWith('plugin:fs|write_text_file', {
      path: 'C:\\Users\\Hustler\\templates\\viral_template.json',
      contents: expect.stringContaining('"name": "Viral Shorts Kurgusu"'),
    })
  })

  it('exportTemplateToFile: kullanıcı dialogu iptal ederse diske yazma yapılmamalı ve success: false dönmeli', async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === 'plugin:dialog|save') {
        return null // Kullanıcı iptal etti
      }
      return undefined
    })

    const result = await exportTemplateToFile(VALID_TEMPLATE_FIXTURE)

    expect(result.success).toBe(false)
    expect(result.filePath).toBeNull()
    expect(mockInvoke).not.toHaveBeenCalledWith('plugin:fs|write_text_file', expect.anything())
  })

  it('importTemplateFromFile: Tauri dialog open ve fs read_text_file invoke komutlarını çağırıp şablonu doğrulamalı', async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === 'plugin:dialog|open') {
        return 'C:\\Users\\Hustler\\templates\\import_me.json'
      }
      if (cmd === 'plugin:fs|read_text_file') {
        return JSON.stringify(VALID_TEMPLATE_FIXTURE)
      }
      return undefined
    })

    const imported = await importTemplateFromFile()

    expect(mockInvoke).toHaveBeenCalledWith('plugin:dialog|open', expect.objectContaining({
      multiple: false,
      directory: false,
    }))
    expect(mockInvoke).toHaveBeenCalledWith('plugin:fs|read_text_file', {
      path: 'C:\\Users\\Hustler\\templates\\import_me.json',
    })
    expect(imported.name).toBe('Viral Shorts Kurgusu')
    expect(imported.id).toBe(VALID_TEMPLATE_FIXTURE.id)
  })

  it('importTemplateFromFile: diskteki dosya bozuk veya şema dışı ise okuma sonrası ZodError fırlatmalı', async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === 'plugin:dialog|open') {
        return 'C:\\Users\\Hustler\\templates\\corrupted.json'
      }
      if (cmd === 'plugin:fs|read_text_file') {
        return JSON.stringify({ name: 'Eksik Şablon', missingAllRequiredFields: true })
      }
      return undefined
    })

    await expect(importTemplateFromFile()).rejects.toThrow(ZodError)
  })

  it('importTemplateFromFile: kullanıcı dosya seçimini iptal ederse hata fırlatmalı', async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === 'plugin:dialog|open') {
        return null
      }
      return undefined
    })

    await expect(importTemplateFromFile()).rejects.toThrow(/iptal edildi/)
  })
})

// ---------------------------------------------------------------------------
// SUITE 4: Sıfır Web I/O API Tuzak Testleri (Zero Web I/O Policy Traps)
// ---------------------------------------------------------------------------
describe('K-706: Sıfır Web I/O API Tuzak Testleri (Zero Web I/O Traps)', () => {
  const mockInvoke = invoke as ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === 'plugin:dialog|save') return 'C:\\fake\\path.json'
      if (cmd === 'plugin:dialog|open') return 'C:\\fake\\path.json'
      if (cmd === 'plugin:fs|read_text_file') return JSON.stringify(VALID_TEMPLATE_FIXTURE)
      if (cmd === 'plugin:fs|write_text_file') return undefined
      return undefined
    })
  })

  it('içe veya dışa aktarım sırasında FileReader kesinlikle örneklendirilmemelidir (FileReader Trap)', async () => {
    const fileReaderSpy = vi.fn().mockImplementation(() => {
      throw new Error('[GÜVENLİK İHLALİ] Tarayıcı FileReader API kullanımı yasaktır!')
    })

    vi.stubGlobal('FileReader', fileReaderSpy)

    await exportTemplateToFile(VALID_TEMPLATE_FIXTURE, 'C:\\test\\out.json')
    await importTemplateFromFile('C:\\test\\in.json')

    expect(fileReaderSpy).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('içe aktarım sırasında <input type="file"> oluşturulmamalıdır (DOM File Picker Trap)', async () => {
    const originalCreateElement = document.createElement.bind(document)
    const createElementSpy = vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
      if (tagName.toLowerCase() === 'input') {
        throw new Error('[GÜVENLİK İHLALİ] Web <input type="file"> kullanımı yasaktır!')
      }
      return originalCreateElement(tagName)
    })

    await importTemplateFromFile('C:\\test\\in.json')

    expect(createElementSpy).not.toHaveBeenCalledWith('input')
    createElementSpy.mockRestore()
  })

  it('dışa aktarım sırasında <a> etiketi veya URL.createObjectURL ile indirme yapılmamalıdır (Download Anchor Trap)', async () => {
    const createObjectURLSpy = vi.fn().mockImplementation(() => {
      throw new Error('[GÜVENLİK İHLALİ] URL.createObjectURL kullanımı yasaktır!')
    })
    vi.stubGlobal('URL', { ...URL, createObjectURL: createObjectURLSpy })

    await exportTemplateToFile(VALID_TEMPLATE_FIXTURE, 'C:\\test\\out.json')

    expect(createObjectURLSpy).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('tarayıcının showOpenFilePicker ve showSaveFilePicker API\'leri çağrılmamalıdır (Window File Picker Trap)', async () => {
    const showOpenFilePickerSpy = vi.fn()
    const showSaveFilePickerSpy = vi.fn()

    Object.defineProperty(window, 'showOpenFilePicker', { value: showOpenFilePickerSpy, configurable: true })
    Object.defineProperty(window, 'showSaveFilePicker', { value: showSaveFilePickerSpy, configurable: true })

    await exportTemplateToFile(VALID_TEMPLATE_FIXTURE, 'C:\\test\\out.json')
    await importTemplateFromFile('C:\\test\\in.json')

    expect(showOpenFilePickerSpy).not.toHaveBeenCalled()
    expect(showSaveFilePickerSpy).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// SUITE 5: UI Entegrasyonu — TemplateManager Bileşeni ve Eylem Testleri
// ---------------------------------------------------------------------------
describe('K-706: UI Entegrasyonu — TemplateManager Bileşeni', () => {
  const mockInvoke = invoke as ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    useTemplateStore.getState().resetTemplates()
    useFlowStore.setState({ toasts: [] })
  })

  it('başlangıç şablonlarını ve kategori sekmelerini başarıyla listelemeli', () => {
    render(React.createElement(TemplateManager))

    expect(screen.getByTestId('template-manager-root')).toBeInTheDocument()
    expect(screen.getByText('Şablon Yöneticisi (K-706)')).toBeInTheDocument()
    expect(screen.getByText('Viral Tech Shorts')).toBeInTheDocument()
    expect(screen.getByText('Finans ve Para İpuçları')).toBeInTheDocument()
    expect(screen.getByText('Tarih ve Gizem Hikayeleri')).toBeInTheDocument()
  })

  it('kategori sekmesine tıklandığında listeyi doğru filtrelemeli', () => {
    render(React.createElement(TemplateManager))

    const financeTab = screen.getByTestId('template-cat-filter-finance')
    fireEvent.click(financeTab)

    expect(screen.getByText('Finans ve Para İpuçları')).toBeInTheDocument()
    expect(screen.queryByText('Viral Tech Shorts')).not.toBeInTheDocument()
    expect(screen.queryByText('Tarih ve Gizem Hikayeleri')).not.toBeInTheDocument()
  })

  it('UI üzerindeki Klonla butonuna tıklandığında yeni bir kopya üretmeli ve Toast eklemeli', async () => {
    render(React.createElement(TemplateManager))

    const cloneBtn = screen.getByTestId('template-clone-btn-550e8400-e29b-41d4-a716-446655440001')
    fireEvent.click(cloneBtn)

    // Yeni kopya listede görünmeli
    await waitFor(() => {
      expect(screen.getByText('Viral Tech Shorts (Kopya)')).toBeInTheDocument()
    })

    // Toast listesinde başarı bildirimi olmalı
    const toasts = useFlowStore.getState().toasts
    expect(toasts.some((t) => t.code === 'TEMPLATE_CLONED')).toBe(true)
  })

  it('UI üzerindeki Dışa Aktar butonuna tıklandığında Tauri dialog ve fs invoke çağrılmalı', async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === 'plugin:dialog|save') return 'C:\\exported_template.json'
      if (cmd === 'plugin:fs|write_text_file') return undefined
      return undefined
    })

    render(React.createElement(TemplateManager))

    const exportBtn = screen.getByTestId('template-export-btn-550e8400-e29b-41d4-a716-446655440001')
    fireEvent.click(exportBtn)

    await waitFor(() => {
      expect(mockInvoke).toHaveBeenCalledWith('plugin:dialog|save', expect.anything())
      expect(mockInvoke).toHaveBeenCalledWith('plugin:fs|write_text_file', expect.objectContaining({
        path: 'C:\\exported_template.json',
      }))
    })

    const toasts = useFlowStore.getState().toasts
    expect(toasts.some((t) => t.code === 'TEMPLATE_EXPORTED')).toBe(true)
  })

  it('UI üzerindeki İçe Aktar butonuna tıklandığında dosya okunup listeye eklenmeli', async () => {
    const newTemplateToImport = {
      ...VALID_TEMPLATE_FIXTURE,
      id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a99',
      name: 'Yepyeni İçe Aktarılan Şablon',
    }

    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === 'plugin:dialog|open') return 'C:\\imported_template.json'
      if (cmd === 'plugin:fs|read_text_file') return JSON.stringify(newTemplateToImport)
      return undefined
    })

    render(React.createElement(TemplateManager))

    const importBtn = screen.getByTestId('template-import-btn')
    fireEvent.click(importBtn)

    await waitFor(() => {
      expect(screen.getByText('Yepyeni İçe Aktarılan Şablon')).toBeInTheDocument()
    })

    const toasts = useFlowStore.getState().toasts
    expect(toasts.some((t) => t.code === 'TEMPLATE_IMPORTED')).toBe(true)
  })

  it('İçe aktarılan dosya bozuk veya geçersiz olduğunda hata banner\'ı gösterilmeli, app çökmemeli', async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === 'plugin:dialog|open') return 'C:\\bad.json'
      if (cmd === 'plugin:fs|read_text_file') return '{ "bad": "data", "corrupted": true }'
      return undefined
    })

    render(React.createElement(TemplateManager))

    const importBtn = screen.getByTestId('template-import-btn')
    fireEvent.click(importBtn)

    await waitFor(() => {
      expect(screen.getByTestId('template-error-banner')).toBeInTheDocument()
    })

    const toasts = useFlowStore.getState().toasts
    expect(toasts.some((t) => t.code === 'TEMPLATE_VALIDATION_ERROR')).toBe(true)
  })
})

