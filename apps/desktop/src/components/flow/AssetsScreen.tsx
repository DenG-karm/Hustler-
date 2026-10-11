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

  return (
    <div className="space-y-lg max-w-3xl mx-auto" data-testid="screen-assets">
      <div className="border-b border-border pb-md flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">5. Görseller & Slot Eşleme</h2>
          <p className="text-sm text-text-secondary">
            Şablondaki zorunlu medya slotlarını (video, görsel, müzik) doldurun.
          </p>
        </div>
        <span
          className={`text-xs px-sm py-xs rounded font-semibold ${
            assets.allSlotsFilled
              ? 'bg-success/15 text-success border border-success/30'
              : 'bg-warning/15 text-warning border border-warning/30'
          }`}
          data-testid="assets-status-badge"
        >
          {assets.allSlotsFilled ? 'Tüm Slotlar Hazır ✓' : 'Eksik Slot Var'}
        </span>
      </div>

      {errorMessage && (
        <div className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm" data-testid="assets-error">
          {errorMessage}
        </div>
      )}

      <div className="space-y-sm">
        {assets.slots.map((slot) => {
          const isAssigned = !!slot.assignedPath
          return (
            <div
              key={slot.slotId}
              className={`p-md rounded-xl border flex items-center justify-between transition-colors ${
                isAssigned ? 'border-border bg-surface' : 'border-warning/30 bg-warning/5'
              }`}
              data-testid={`slot-${slot.slotId}`}
            >
              <div className="space-y-xs">
                <div className="flex items-center gap-xs">
                  <span className="text-sm font-semibold text-text-primary">{slot.name}</span>
                  {slot.required ? (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-destructive/10 text-destructive font-bold">
                      Zorunlu
                    </span>
                  ) : (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-hover text-text-muted">
                      Opsiyonel
                    </span>
                  )}
                </div>
                <p className="text-xs text-text-muted font-mono">
                  {slot.assignedPath ? slot.assignedPath : 'Henüz dosya atanmadı'}
                </p>
              </div>

              <div>
                {!isAssigned ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => assignAssetSlot(slot.slotId, `assets/${slot.type}/${slot.slotId}.mp4`)}
                    data-testid={`assign-btn-${slot.slotId}`}
                  >
                    Dosya Seç / Ata
                  </Button>
                ) : (
                  <span className="text-xs text-success font-semibold">Hazır ✓</span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex items-center justify-between pt-md border-t border-border">
        <Button variant="ghost" onClick={prevStep} data-testid="assets-back-btn">
          ← Sese Dön
        </Button>
        <Button
          variant="primary"
          onClick={handleAdvance}
          isLoading={isLoading}
          disabled={!assets.allSlotsFilled}
          data-testid="assets-submit-btn"
        >
          Önizleme Oluştur & İlerle →
        </Button>
      </div>
    </div>
  )
}
