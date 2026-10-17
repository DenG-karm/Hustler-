import React from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'

export const AssetsScreen: React.FC = () => {
  const assets = useFlowStore((s) => s.assets)
  const assignAssetSlot = useFlowStore((s) => s.assignAssetSlot)
  const buildPreviewForScript = useFlowStore((s) => s.buildPreviewForScript)
  const nextStep = useFlowStore((s) => s.nextStep)
  const prevStep = useFlowStore((s) => s.prevStep)
  const isLoading = useFlowStore((s) => s.isLoading)
  const errorMessage = useFlowStore((s) => s.errorMessage)

  const handleAdvance = async () => {
    const requiredMissing = assets.slots.filter((s) => s.required && !s.assignedPath)
    if (requiredMissing.length > 0) return

    await buildPreviewForScript()
    try {
      nextStep()
    } catch {
      // Store hatası
    }
  }

  const slotTypeIcons: Record<string, string> = {
    video: '🎬',
    image: '🖼️',
    audio: '🎵',
    subtitle: '📝',
  }

  const requiredSlots = assets.slots.filter((s) => s.required)
  const filledRequiredSlots = requiredSlots.filter((s) => !!s.assignedPath)
  const allRequiredFilled = requiredSlots.length > 0 && filledRequiredSlots.length === requiredSlots.length

  return (
    <div className="space-y-lg max-w-4xl mx-auto py-sm animate-in fade-in duration-200" data-testid="screen-assets">
      {/* Üst Başlık & Durum Rozeti */}
      <div className="border-b border-border/80 pb-md flex flex-col sm:flex-row sm:items-center justify-between gap-sm">
        <div>
          <div className="flex items-center gap-xs">
            <span className="text-primary font-bold text-xs uppercase tracking-wider">Adım 4 / 6</span>
            <span className="text-text-muted">•</span>
            <span className="text-text-muted text-xs">Varlık & Slot Eşleme</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-text-primary">
            Medya Slotları ve Görsel Doğrulama
          </h2>
          <p className="text-sm text-text-secondary">
            Her sahne için zorunlu video, görsel ve arka plan müzik slotlarını eşleyin.
          </p>
        </div>

        <div className="flex items-center gap-sm shrink-0">
          <span
            className={`text-xs px-3 py-1 rounded-full font-semibold border ${
              assets.allSlotsFilled || allRequiredFilled
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
            }`}
            data-testid="assets-status-badge"
          >
            {assets.allSlotsFilled || allRequiredFilled ? 'Tüm Slotlar Hazır ✓' : 'Eksik Slot Var'}
          </span>
        </div>
      </div>

      {errorMessage && (
        <div className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm" data-testid="assets-error">
          {errorMessage}
        </div>
      )}

      {/* İlerleme Özeti */}
      <div className="p-md rounded-2xl border border-border bg-surface/60 flex items-center justify-between text-xs">
        <span className="text-text-secondary font-medium">
          Zorunlu Slot Durumu: <strong className="text-text-primary">{filledRequiredSlots.length} / {requiredSlots.length}</strong> Atandı
        </span>
        <div className="w-48 bg-surface-hover h-2 rounded-full overflow-hidden border border-border/60">
          <div
            className="h-full bg-emerald-500 transition-all duration-300"
            style={{ width: `${(filledRequiredSlots.length / Math.max(1, requiredSlots.length)) * 100}%` }}
          />
        </div>
      </div>

      {/* Slot Listesi Kartları */}
      <div className="space-y-sm">
        {assets.slots.map((slot) => {
          const isAssigned = !!slot.assignedPath
          const icon = slotTypeIcons[slot.type] || '📁'

          return (
            <div
              key={slot.slotId}
              className={`p-md rounded-2xl border transition-all duration-200 flex flex-col sm:flex-row sm:items-center justify-between gap-md ${
                isAssigned
                  ? 'border-border/80 bg-surface hover:bg-surface-hover/30'
                  : 'border-amber-500/30 bg-amber-500/5'
              }`}
              data-testid={`slot-${slot.slotId}`}
            >
              <div className="flex items-start gap-md">
                <div className="w-10 h-10 rounded-xl bg-surface-hover border border-border flex items-center justify-center text-lg shrink-0">
                  {icon}
                </div>

                <div className="space-y-xs">
                  <div className="flex items-center gap-xs flex-wrap">
                    <span className="text-sm font-bold text-text-primary">{slot.name}</span>

                    {/* Tip Rozeti */}
                    <span className="text-[10px] px-1.5 py-0.5 rounded font-mono uppercase bg-surface-hover text-text-muted border border-border/60">
                      {slot.type}
                    </span>

                    {/* Zorunlu / Opsiyonel Rozeti */}
                    {slot.required ? (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 font-bold border border-rose-500/20">
                        Zorunlu
                      </span>
                    ) : (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-hover text-text-muted border border-border/40">
                        Opsiyonel
                      </span>
                    )}

                    {/* Dolu / Eksik Rozeti */}
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                        isAssigned
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                      }`}
                    >
                      {isAssigned ? 'Dolu ✓' : 'Eksik ⚠️'}
                    </span>
                  </div>

                  <p className="text-xs text-text-muted font-mono truncate max-w-md">
                    {slot.assignedPath ? slot.assignedPath : 'Henüz medya dosyası bağlanmadı'}
                  </p>
                </div>
              </div>

              {/* Aksiyon Butonu */}
              <div className="shrink-0 flex items-center gap-sm">
                {!isAssigned ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => assignAssetSlot(slot.slotId, `assets/${slot.type}/${slot.slotId}.mp4`)}
                    data-testid={`assign-btn-${slot.slotId}`}
                  >
                    Dosya Ata
                  </Button>
                ) : (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => assignAssetSlot(slot.slotId, `assets/${slot.type}/${slot.slotId}_yenilendi.mp4`)}
                    className="text-xs text-text-muted hover:text-text-primary"
                  >
                    Değiştir
                  </Button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Alt Aksiyon Çubuğu */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-sm pt-md border-t border-border/80">
        <Button variant="ghost" onClick={prevStep} data-testid="assets-back-btn">
          ← Sese Dön
        </Button>

        <div className="flex items-center gap-md">
          {!allRequiredFilled && (
            <span className="text-xs text-amber-400 font-medium hidden sm:inline">
              ⚠️ Önizlemeye geçmek için tüm zorunlu slotların doldurulması gerekir.
            </span>
          )}
          <Button
            variant="primary"
            onClick={handleAdvance}
            isLoading={isLoading}
            disabled={!assets.allSlotsFilled && !allRequiredFilled}
            data-testid="assets-submit-btn"
          >
            Önizlemeye Geç & İlerle →
          </Button>
        </div>
      </div>
    </div>
  )
}
