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

  // İçe Aktarma Tetikleyicisi (Tauri Native Dialog & Fs)
  const handleImport = async () => {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const imported = await importTemplateFromFile()
      addTemplate(imported)
      addToast({
        title: 'Şablon İçe Aktarıldı',
        message: `"${imported.name}" şablonu şema doğrulamasından başarıyla geçti ve eklendi.`,
        code: 'TEMPLATE_IMPORTED',
        status: 200,
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err || 'İçe aktarma hatası')
      // Kullanıcı iptali sessizce geçilebilir, diğer hatalar Toast ve arayüzde gösterilir
      if (!msg.includes('iptal edildi')) {
        setErrorMessage(msg)
        addToast({
          title: 'Şablon Doğrulama Hatası',
          message: msg,
          code: 'TEMPLATE_VALIDATION_ERROR',
          status: 400,
        })
      }
    } finally {
      setIsLoading(false)
    }
  }

  // Dışa Aktarma Tetikleyicisi (Tauri Native Dialog & Fs)
  const handleExport = async (template: Template) => {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const result = await exportTemplateToFile(template)
      if (result.success && result.filePath) {
        addToast({
          title: 'Şablon Dışa Aktarıldı',
          message: `"${template.name}" dosyası kaydedildi: ${result.filePath}`,
          code: 'TEMPLATE_EXPORTED',
          status: 200,
        })
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err || 'Dışa aktarma hatası')
      setErrorMessage(msg)
      addToast({
        title: 'Dışa Aktarma Hatası',
        message: msg,
        code: 'TEMPLATE_EXPORT_ERROR',
        status: 500,
      })
    } finally {
      setIsLoading(false)
    }
  }

  // Klonlama Tetikleyicisi (Idempotent Deep Copy & UUID)
  const handleClone = (id: string) => {
    try {
      const cloned = cloneTemplateItem(id)
      if (cloned) {
        addToast({
          title: 'Şablon Klonlandı',
          message: `"${cloned.name}" başarıyla oluşturuldu (Yeni ID: ${cloned.id.substring(0, 8)}...).`,
          code: 'TEMPLATE_CLONED',
          status: 200,
        })
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err || 'Klonlama hatası')
      setErrorMessage(msg)
      addToast({
        title: 'Klonlama Hatası',
        message: msg,
        code: 'TEMPLATE_CLONE_ERROR',
        status: 500,
      })
    }
  }

  // Silme Tetikleyicisi
  const handleDelete = (template: Template) => {
    removeTemplate(template.id)
    addToast({
      title: 'Şablon Silindi',
      message: `"${template.name}" listeden kaldırıldı.`,
      code: 'TEMPLATE_DELETED',
      status: 200,
    })
  }

  return (
    <div className="p-lg space-y-lg max-w-6xl mx-auto" data-testid="template-manager-root">
      {/* Üst Başlık ve Eylem Çubuğu */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-md border-b border-border pb-md">
        <div>
          <h2 className="text-xl font-bold text-text-primary tracking-tight">
            Şablon Yöneticisi (K-706)
          </h2>
          <p className="text-sm text-text-secondary">
            Kategori filtreleme, idempotent klonlama ve Tauri Native IPC dosya içe/dışa aktarımı.
          </p>
        </div>

        <div className="flex items-center gap-sm">
          <Button
            variant="primary"
            size="sm"
            onClick={handleImport}
            isLoading={isLoading}
            data-testid="template-import-btn"
          >
            📥 Şablon İçe Aktar
          </Button>
        </div>
      </div>

      {/* Hata Bildirim Çubuğu */}
      {errorMessage && (
        <div
          className="p-md rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-sm flex items-center justify-between"
          data-testid="template-error-banner"
          role="alert"
        >
          <div className="space-y-0.5">
            <span className="font-semibold">İşlem Başarısız:</span>
            <p className="text-xs text-destructive/90">{errorMessage}</p>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-xs text-destructive hover:underline px-2 py-1"
            aria-label="Hatayı Gizle"
          >
            ✕ Kapat
          </button>
        </div>
      )}

      {/* Kategori Filtre Butonları */}
      <div className="flex flex-wrap items-center gap-xs" data-testid="template-category-tabs">
        {CATEGORIES.map((cat) => {
          const count =
            cat.id === 'all'
              ? templates.length
              : templates.filter((t) => t.category === cat.id).length

          return (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-md py-xs rounded-lg text-xs font-medium transition-colors flex items-center gap-xs border ${
                selectedCategory === cat.id
                  ? 'bg-accent text-accent-contrast border-accent shadow-sm'
                  : 'bg-surface hover:bg-surface-hover text-text-secondary border-border'
              }`}
              data-testid={`template-cat-filter-${cat.id}`}
            >
              <span>{cat.label}</span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                  selectedCategory === cat.id
                    ? 'bg-white/20 text-white'
                    : 'bg-surface-hover text-text-muted'
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
          className="p-xl text-center border border-dashed border-border rounded-2xl bg-surface/30 text-text-muted space-y-sm"
          data-testid="template-empty-state"
        >
          <p className="text-sm">Bu kategoride henüz şablon bulunmuyor.</p>
          <Button variant="outline" size="sm" onClick={handleImport}>
            Bir Şablon İçe Aktarın
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-md">
          {filteredTemplates.map((template) => (
            <div
              key={template.id}
              className="p-md rounded-xl border border-border bg-surface hover:border-border-hover transition-all shadow-sm flex flex-col justify-between space-y-md"
              data-testid={`template-card-${template.id}`}
            >
              <div className="space-y-sm">
                {/* Kart Başlığı ve Rozetler */}
                <div className="flex items-start justify-between gap-sm">
                  <div>
                    <h3 className="text-sm font-bold text-text-primary leading-tight">
                      {template.name}
                    </h3>
                    <span className="text-[10px] text-text-muted font-mono uppercase">
                      ID: {template.id.substring(0, 8)}...
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] px-sm py-0.5 rounded font-semibold bg-accent/10 text-accent border border-accent/20">
                      {template.aspectRatio}
                    </span>
                    <span className="text-[10px] px-sm py-0.5 rounded font-mono bg-surface-hover text-text-secondary border border-border">
                      {template.fps}fps
                    </span>
                  </div>
                </div>

                {/* Açıklama */}
                <p className="text-xs text-text-secondary line-clamp-2 leading-relaxed">
                  {template.description || 'Açıklama belirtilmemiş.'}
                </p>

                {/* Detay Bilgileri */}
                <div className="p-xs rounded-lg bg-surface-hover/50 text-[11px] space-y-1 text-text-muted border border-border-subtle">
                  <div className="flex justify-between">
                    <span>Font:</span>
                    <span className="font-medium text-text-secondary">
                      {template.subtitleStyle.font_name} ({template.subtitleStyle.font_size}px)
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Ses Kimliği:</span>
                    <span className="font-medium text-text-secondary">
                      {template.audioSettings.voiceId} (x{template.audioSettings.speed})
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Görsel Slotlar:</span>
                    <span className="font-medium text-text-secondary">
                      {template.slots.length} adet ({template.slots.map((s) => s.name).join(', ')})
                    </span>
                  </div>
                </div>
              </div>

              {/* Kart Alt Eylemleri */}
              <div className="flex items-center justify-between pt-sm border-t border-border gap-xs">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleClone(template.id)}
                  data-testid={`template-clone-btn-${template.id}`}
                >
                  📋 Klonla
                </Button>

                <div className="flex items-center gap-xs">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleExport(template)}
                    data-testid={`template-export-btn-${template.id}`}
                  >
                    📤 Dışa Aktar
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
