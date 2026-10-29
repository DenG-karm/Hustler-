/**
 * Hustler Desktop — Şablon Yöneticisi Arayüzü (K-706)
 *
 * MİMARİ KURALLAR:
 * 1. Katı Şema Doğrulaması: İçe aktarılan her dosya Zod ile denetlenir.
 * 2. Sıfır Web I/O API: <input type="file">, FileReader, URL.createObjectURL YASAKTIR.
 *    Dosya seçim ve kayıtları doğrudan Tauri Rust IPC (@tauri-apps/plugin-dialog ve @tauri-apps/plugin-fs)
 *    kullanan exportTemplateToFile ve importTemplateFromFile üzerinden yürütülür.
 * 3. Idempotent Klonlama: cloneTemplate fonksiyonu ile derin kopya alınır ve yeni UUID atanır.
 */

import React, { useState } from 'react'
import {
  type Template,
  type TemplateCategory,
  exportTemplateToFile,
  importTemplateFromFile,
} from '../../lib/templates'
import { useTemplateStore } from '../../store/templateStore'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'

const CATEGORIES: Array<{ id: TemplateCategory | 'all'; label: string }> = [
  { id: 'all', label: 'Tümü' },
  { id: 'tech', label: 'Teknoloji' },
  { id: 'finance', label: 'Finans' },
  { id: 'story', label: 'Hikaye & Tarih' },
  { id: 'gaming', label: 'Oyun' },
  { id: 'education', label: 'Eğitim' },
  { id: 'general', label: 'Genel' },
]

export const TemplateManager: React.FC = () => {
  const templates = useTemplateStore((s) => s.templates)
  const selectedCategory = useTemplateStore((s) => s.selectedCategory)
  const setSelectedCategory = useTemplateStore((s) => s.setSelectedCategory)
  const addTemplate = useTemplateStore((s) => s.addTemplate)
  const removeTemplate = useTemplateStore((s) => s.removeTemplate)
  const cloneTemplateItem = useTemplateStore((s) => s.cloneTemplateItem)

  const addToast = useFlowStore((s) => s.addToast)

  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Kategoriye göre filtrelenmiş liste
  const filteredTemplates = templates.filter((template) => {
    if (selectedCategory === 'all') return true
    return template.category === selectedCategory
  })

  const toast = (title: string, message: string, code: string, status: number) => addToast({ title, message, code, status })
  const fail = (err: unknown, fallback: string, title: string, code: string, status: number) => {
    const msg = err instanceof Error ? err.message : String(err || fallback)
    setErrorMessage(msg)
    toast(title, msg, code, status)
  }

  // Tauri Native Dialog & Fs
  const handleImport = async () => {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const imported = await importTemplateFromFile()
      addTemplate(imported)
      toast('Şablon İçe Aktarıldı', `"${imported.name}" şablonu şema doğrulamasından başarıyla geçti ve eklendi.`, 'TEMPLATE_IMPORTED', 200)
    } catch (err: unknown) {
      // Kullanıcı iptali sessizce geçilir
      if (!(err instanceof Error && err.message.includes('iptal edildi'))) fail(err, 'İçe aktarma hatası', 'Şablon Doğrulama Hatası', 'TEMPLATE_VALIDATION_ERROR', 400)
    } finally {
      setIsLoading(false)
    }
  }

  const handleExport = async (template: Template) => {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const result = await exportTemplateToFile(template)
      if (result.success && result.filePath) toast('Şablon Dışa Aktarıldı', `"${template.name}" dosyası kaydedildi: ${result.filePath}`, 'TEMPLATE_EXPORTED', 200)
    } catch (err: unknown) {
      fail(err, 'Dışa aktarma hatası', 'Dışa Aktarma Hatası', 'TEMPLATE_EXPORT_ERROR', 500)
    } finally {
      setIsLoading(false)
    }
  }

  const handleClone = (id: string) => {
    try {
      const cloned = cloneTemplateItem(id)
      if (cloned) toast('Şablon Klonlandı', `"${cloned.name}" başarıyla oluşturuldu (Yeni ID: ${cloned.id.substring(0, 8)}...).`, 'TEMPLATE_CLONED', 200)
    } catch (err: unknown) {
      fail(err, 'Klonlama hatası', 'Klonlama Hatası', 'TEMPLATE_CLONE_ERROR', 500)
    }
  }

  const handleDelete = (template: Template) => {
    removeTemplate(template.id)
    toast('Şablon Silindi', `"${template.name}" listeden kaldırıldı.`, 'TEMPLATE_DELETED', 200)
  }

  return (
    <div className="p-6 space-y-4 max-w-6xl mx-auto" data-testid="template-manager-root">
      {/* Üst Başlık ve Eylem Çubuğu */}
      <div className="p-5 rounded-lg border border-border/80 bg-surface studio-panel flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 font-mono text-[10px]">
            <span className="text-teal-600 dark:text-teal-400 font-semibold uppercase tracking-wider">MOD // 02 • TEMPLATE VAULT</span>
            <span className="text-zinc-700">|</span>
            <span className="text-zinc-500">ZOD SCHEMA &amp; ATOMIC NATIVE I/O</span>
          </div>
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight mt-1">
            Şablon Yöneticisi (K-706)
          </h2>
          <p className="text-[12px] text-zinc-500 dark:text-zinc-400 mt-0.5">
            Kategori filtreleme, idempotent klonlama ve Tauri Native IPC dosya içe/dışa aktarımı.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="primary"
            size="sm"
            onClick={handleImport}
            isLoading={isLoading}
            data-testid="template-import-btn"
          >
            Şablon İçe Aktar
          </Button>
        </div>
      </div>

      {/* Hata Bildirim Çubuğu */}
      {errorMessage && (
        <div
          className="p-4 rounded-lg bg-destructive/10 border border-destructive/25 text-destructive text-xs font-mono flex items-center justify-between"
          data-testid="template-error-banner"
          role="alert"
        >
          <div className="space-y-0.5">
            <span className="font-semibold">İşlem Başarısız:</span>
            <p className="text-xs text-destructive/90">{errorMessage}</p>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-xs text-destructive hover:underline px-2 py-1 outline-none ring-0 focus:outline-none focus:ring-0"
            aria-label="Hatayı Gizle"
          >
            Kapat
          </button>
        </div>
      )}

      {/* Kategori Filtre Butonları (Linear / Arc Tab Strip) */}
      <div className="flex flex-wrap items-center gap-1.5" data-testid="template-category-tabs">
        {CATEGORIES.map((cat) => {
          const count =
            cat.id === 'all'
              ? templates.length
              : templates.filter((t) => t.category === cat.id).length
          const isSelected = selectedCategory === cat.id

          return (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`relative px-3 py-1.5 rounded-md text-[12px] transition-colors flex items-center gap-2 cursor-pointer outline-none ring-0 focus:outline-none focus:ring-0 ${
                isSelected
                  ? 'bg-zinc-200/80 dark:bg-zinc-800/80 text-zinc-900 dark:text-zinc-100 font-medium'
                  : 'bg-transparent text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200 hover:bg-zinc-200/40 dark:hover:bg-zinc-800/40'
              }`}
              data-testid={`template-cat-filter-${cat.id}`}
            >
              {isSelected && (
                <span
                  aria-hidden="true"
                  className="absolute left-2.5 right-2.5 bottom-0 h-[2px] rounded-full bg-teal-400"
                />
              )}
              <span>{cat.label}</span>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                  isSelected
                    ? 'bg-zinc-300/80 dark:bg-zinc-700/80 text-teal-600 dark:text-teal-400 font-medium'
                    : 'bg-zinc-100 dark:bg-zinc-900 text-zinc-500'
                }`}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>

      {/* Şablon Kartları Izgarası */}
      {filteredTemplates.length === 0 ? (
        <div
          className="p-8 text-center border border-dashed border-border/80 rounded-lg bg-surface/50 text-zinc-500 space-y-3"
          data-testid="template-empty-state"
        >
          <p className="text-[13px] font-medium">Bu kategoride henüz şablon bulunmuyor.</p>
          <Button variant="outline" size="sm" onClick={handleImport}>
            Bir Şablon İçe Aktarın
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTemplates.map((template) => (
            <div
              key={template.id}
              className="p-5 rounded-lg border border-border/80 bg-surface hover:border-zinc-600/80 transition-colors studio-panel flex flex-col justify-between space-y-4"
              data-testid={`template-card-${template.id}`}
            >
              <div className="space-y-3">
                {/* Kart Başlığı ve Rozetler */}
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-[14px] font-semibold text-zinc-900 dark:text-zinc-100 leading-tight">
                      {template.name}
                    </h3>
                    <span className="text-[10px] text-zinc-500 font-mono uppercase">
                      ID: {template.id.substring(0, 8)}...
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-zinc-200/80 dark:bg-zinc-800/80 text-teal-600 dark:text-teal-400">
                      {template.aspectRatio}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded font-mono bg-zinc-100 dark:bg-zinc-900 text-zinc-400 border border-border/70">
                      {template.fps}fps
                    </span>
                  </div>
                </div>

                {/* Açıklama */}
                <p className="text-[12px] text-zinc-500 dark:text-zinc-400 line-clamp-2 leading-relaxed">
                  {template.description || 'Açıklama belirtilmemiş.'}
                </p>

                {/* Detay Bilgileri */}
                <div className="p-3 rounded-md bg-zinc-100 dark:bg-zinc-900/90 text-[11px] font-mono space-y-1.5 text-zinc-500 border border-border/70 studio-recessed">
                  <div className="flex justify-between">
                    <span>FONT:</span>
                    <span className="font-medium text-zinc-900 dark:text-zinc-200">
                      {template.subtitleStyle.font_name} ({template.subtitleStyle.font_size}px)
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>SES KİMLİĞİ:</span>
                    <span className="font-medium text-teal-600 dark:text-teal-400">
                      {template.audioSettings.voiceId} (x{template.audioSettings.speed})
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>SLOTLAR:</span>
                    <span className="font-medium text-zinc-600 dark:text-zinc-300 truncate max-w-[160px]">
                      {template.slots.length} adet ({template.slots.map((s) => s.name).join(', ')})
                    </span>
                  </div>
                </div>
              </div>

              {/* Kart Alt Eylemleri */}
              <div className="flex items-center justify-between pt-3 border-t border-border/70 gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleClone(template.id)}
                  data-testid={`template-clone-btn-${template.id}`}
                >
                  Klonla
                </Button>

                <div className="flex items-center gap-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleExport(template)}
                    data-testid={`template-export-btn-${template.id}`}
                  >
                    Dışa Aktar
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDelete(template)}
                    data-testid={`template-delete-btn-${template.id}`}
                  >
                    Sil
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
