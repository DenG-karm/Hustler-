/**
 * Hustler Desktop — Şablon Yöneticisi Çekirdek Modülü (K-706)
 *
 * MİMARİ KURALLAR:
 * 1. Katı Şema Doğrulaması (Zod): İçe aktarılan veya işlenen her veri Zod ile denetlenir.
 *    Eksik anahtar, geçersiz tip veya bozuk JSON anında ZodError ile reddedilir.
 * 2. Sıfır Web I/O API: Tarayıcı dosya API'leri (<input type="file">, FileReader,
 *    showOpenFilePicker, showSaveFilePicker, URL.createObjectURL, Blob) KESİNLİKLE YASAKTIR.
 *    Tüm I/O işlemleri Tauri Rust IPC (@tauri-apps/plugin-dialog ve @tauri-apps/plugin-fs) üzerinden yürütülür.
 * 3. Idempotent Klonlama: Referans kopyası (shallow copy) yasaktır. Derin kopya (deep copy)
 *    alınarak yeni UUID üretilir, referans bağı tamamen koparılır.
 */

import { invoke } from '@tauri-apps/api/core'
import { z, ZodError } from 'zod'

// ---------------------------------------------------------------------------
// Şablon Zod Şema Tanımları
// ---------------------------------------------------------------------------

export const SubtitleStyleSchema = z.object({
  font_name: z.string().min(1, 'Font adı boş olamaz'),
  font_size: z.number().int().positive('Font boyutu pozitif tam sayı olmalıdır'),
  primary_color: z.string().regex(/^&H[0-9A-Fa-f]{8}&$/, 'ASS renk formatı &HBBGGRR& olmalıdır'),
  highlight_color: z.string().regex(/^&H[0-9A-Fa-f]{8}&$/, 'ASS vurgu rengi &HBBGGRR& olmalıdır'),
  alignment: z.number().int().min(1).max(9, 'Hizalama 1-9 arasında olmalıdır'),
  margin_v: z.number().int().nonnegative('Kenar boşluğu negatif olamaz'),
})

export const AudioSettingsSchema = z.object({
  voiceId: z.string().min(1, 'Ses kimliği boş olamaz'),
  speed: z.number().min(0.5).max(2.0, 'Ses hızı 0.5 ile 2.0 arasında olmalıdır'),
  volume: z.number().min(0).max(1.0, 'Ses düzeyi 0.0 ile 1.0 arasında olmalıdır'),
})

export const VisualSlotSchema = z.object({
  slotId: z.string().min(1, 'Slot ID boş olamaz'),
  name: z.string().min(1, 'Slot adı boş olamaz'),
  type: z.enum(['video', 'image', 'audio']),
  required: z.boolean(),
})

export const TemplateCategoryEnum = z.enum([
  'gaming',
  'education',
  'finance',
  'tech',
  'story',
  'general',
])

export const TemplateSchema = z.object({
  id: z.string().uuid('Geçerli bir UUID formatı gereklidir'),
  name: z.string().min(1, 'Şablon adı boş olamaz'),
  category: TemplateCategoryEnum,
  description: z.string().default(''),
  version: z.number().int().positive().default(1),
  aspectRatio: z.enum(['9:16', '16:9', '1:1']),
  fps: z.number().int().min(15).max(120),
  subtitleStyle: SubtitleStyleSchema,
  audioSettings: AudioSettingsSchema,
  slots: z.array(VisualSlotSchema).min(1, 'En az bir slot tanımlanmalıdır'),
  tags: z.array(z.string()).default([]),
  createdAt: z.number().positive(),
  updatedAt: z.number().positive(),
})

export type Template = z.infer<typeof TemplateSchema>
export type TemplateCategory = z.infer<typeof TemplateCategoryEnum>

// ---------------------------------------------------------------------------
// Çekirdek Mantık Fonksiyonları
// ---------------------------------------------------------------------------

/**
 * Verilen bilinmeyen veriyi katı Zod şeması ile denetler.
 * Bozuk JSON veya kural ihlalinde ZodError fırlatır.
 */
export function validateTemplate(data: unknown): Template {
  if (typeof data === 'string') {
    let parsedJson: unknown
    try {
      parsedJson = JSON.parse(data)
    } catch {
      throw new ZodError([
        {
          code: z.ZodIssueCode.custom,
          path: [],
          message: 'Bozuk JSON biçimi: Şablon ayrıştırılamadı',
        },
      ])
    }
    return TemplateSchema.parse(parsedJson)
  }
  return TemplateSchema.parse(data)
}

/**
 * Şablonu derin kopya (deep copy) ile referans bağı kalmayacak şekilde klonlar.
 * Yeni geçerli bir UUID oluşturur.
 */
export function cloneTemplate(template: Template, customName?: string): Template {
  // structuredClone ile derin kopya garanti edilir (shallow copy yasak)
  const deepCopied = structuredClone(template)
  const now = Date.now()

  const cloned: Template = {
    ...deepCopied,
    id: crypto.randomUUID(), // Yeni benzersiz UUID
    name: customName ?? `${template.name} (Kopya)`,
    createdAt: now,
    updatedAt: now,
  }

  return TemplateSchema.parse(cloned)
}

/**
 * Şablonu Tauri Rust IPC üzerinden yerel diske dışa aktarır.
 * Web API (a.download, Blob, showSaveFilePicker) KESİNLİKLE KULLANILMAZ.
 */
export async function exportTemplateToFile(
  template: Template,
  targetPathOverride?: string
): Promise<{ success: boolean; filePath: string | null }> {
  // Önce şablon doğrulanır
  const valid = validateTemplate(template)

  // Hedef dosya yolu: ya doğrudan verilir ya da Tauri native save dialog ile kullanıcıdan alınır
  let targetPath = targetPathOverride
  if (!targetPath) {
    const dialogResult = await invoke<string | null>('plugin:dialog|save', {
      filters: [{ name: 'Hustler Şablonu', extensions: ['json'] }],
      defaultPath: `${valid.name.toLowerCase().replace(/[^a-z0-9]/g, '_')}_template.json`,
    })

    if (!dialogResult) {
      return { success: false, filePath: null }
    }
    targetPath = dialogResult
  }

  // Tauri Rust fs eklentisiyle diske yazılır
  const content = JSON.stringify(valid, null, 2)
  await invoke('plugin:fs|write_text_file', {
    path: targetPath,
    contents: content,
  })

  return { success: true, filePath: targetPath }
}

/**
 * Tauri Rust IPC üzerinden yerel diskten şablon dosyasını okur ve Zod ile doğrular.
 * Web API (<input type="file">, FileReader, showOpenFilePicker) KESİNLİKLE KULLANILMAZ.
 */
export async function importTemplateFromFile(sourcePathOverride?: string): Promise<Template> {
  let sourcePath = sourcePathOverride
  if (!sourcePath) {
    const dialogResult = await invoke<string | null>('plugin:dialog|open', {
      multiple: false,
      directory: false,
      filters: [{ name: 'Hustler Şablonu', extensions: ['json'] }],
    })

    if (!dialogResult) {
      throw new Error('Dosya seçimi kullanıcı tarafından iptal edildi')
    }
    sourcePath = dialogResult
  }

  // Tauri Rust fs eklentisiyle diskten okunur
  const fileContent = await invoke<string>('plugin:fs|read_text_file', {
    path: sourcePath,
  })

  // Zod ile katı doğrulama (bozuk veri varsa ZodError fırlatır)
  return validateTemplate(fileContent)
}

// ---------------------------------------------------------------------------
// Varsayılan Başlangıç Şablonları (Default Seed Templates)
// ---------------------------------------------------------------------------

export const INITIAL_TEMPLATES: Template[] = [
  {
    id: '550e8400-e29b-41d4-a716-446655440001',
    name: 'Viral Tech Shorts',
    category: 'tech',
    description: 'Yapay zeka ve teknoloji haberleri için dinamik dikey format.',
    version: 1,
    aspectRatio: '9:16',
    fps: 30,
    subtitleStyle: {
      font_name: 'Arial Black',
      font_size: 96,
      primary_color: '&H00FFFFFF&',
      highlight_color: '&H0000FFFF&',
      alignment: 5,
      margin_v: 60,
    },
    audioSettings: {
      voiceId: 'tr-TR-Standard-A',
      speed: 1.15,
      volume: 1.0,
    },
    slots: [
      { slotId: 'slot_intro', name: 'Kanca Sahne', type: 'video', required: true },
      { slotId: 'slot_demo', name: 'Ürün Demosu', type: 'video', required: true },
      { slotId: 'slot_cta', name: 'Kapanış ve Takip', type: 'image', required: true },
    ],
    tags: ['tech', 'ai', 'shorts'],
    createdAt: 1710000000000,
    updatedAt: 1710000000000,
  },
  {
    id: '550e8400-e29b-41d4-a716-446655440002',
    name: 'Finans ve Para İpuçları',
    category: 'finance',
    description: 'Borsa, kripto ve kişisel finans rehberleri için profesyonel stil.',
    version: 1,
    aspectRatio: '9:16',
    fps: 30,
    subtitleStyle: {
      font_name: 'Montserrat',
      font_size: 88,
      primary_color: '&H00FFFFFF&',
      highlight_color: '&H0000FF00&',
      alignment: 5,
      margin_v: 50,
    },
    audioSettings: {
      voiceId: 'tr-TR-Standard-B',
      speed: 1.05,
      volume: 0.95,
    },
    slots: [
      { slotId: 'slot_chart', name: 'Grafik ve Veri', type: 'image', required: true },
      { slotId: 'slot_speaker', name: 'Konuşmacı Kesiti', type: 'video', required: true },
    ],
    tags: ['finance', 'crypto', 'money'],
    createdAt: 1710000100000,
    updatedAt: 1710000100000,
  },
  {
    id: '550e8400-e29b-41d4-a716-446655440003',
    name: 'Tarih ve Gizem Hikayeleri',
    category: 'story',
    description: 'Karanlık atmosferli gizem ve tarih anlatıları için sinematik şablon.',
    version: 1,
    aspectRatio: '9:16',
    fps: 24,
    subtitleStyle: {
      font_name: 'Cinzel',
      font_size: 80,
      primary_color: '&H00EEEEEE&',
      highlight_color: '&H0055FFFF&',
      alignment: 2,
      margin_v: 70,
    },
    audioSettings: {
      voiceId: 'tr-TR-Standard-C',
      speed: 0.95,
      volume: 0.9,
    },
    slots: [
      { slotId: 'slot_cinematic_1', name: 'Sinematik Sahne 1', type: 'video', required: true },
      { slotId: 'slot_cinematic_2', name: 'Sinematik Sahne 2', type: 'video', required: true },
      { slotId: 'slot_bgm', name: 'Gerilim Müziği', type: 'audio', required: false },
    ],
    tags: ['history', 'mystery', 'cinematic'],
    createdAt: 1710000200000,
    updatedAt: 1710000200000,
  },
]
