import React, { useState, useMemo } from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'

const CARD_CLS =
  'p-6 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs'

function getSlotIcon(type: string) {
  switch (type) {
    case 'video':
      return (
        <svg className="w-4 h-4 text-indigo-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <rect x="2.5" y="4.5" width="14" height="15" rx="2" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 9.5l5-3v11l-5-3" />
        </svg>
      )
    case 'image':
      return (
        <svg className="w-4 h-4 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <rect x="3" y="3" width="18" height="18" rx="2.5" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 15l-5-5L5 21" />
        </svg>
      )
    case 'audio':
      return (
        <svg className="w-4 h-4 text-amber-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 18V5l12-2v13" />
          <circle cx="6" cy="18" r="3" />
          <circle cx="18" cy="16" r="3" />
        </svg>
      )
    default:
      return (
        <svg className="w-4 h-4 text-zinc-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 7h16M4 12h16M4 17h10" />
        </svg>
      )
  }
}

type FilterTab = 'all' | 'required' | 'missing' | 'filled'

export const AssetsScreen: React.FC = () => {
  const assets = useFlowStore((s) => s.assets)
  const script = useFlowStore((s) => s.script)
  const assignAssetSlot = useFlowStore((s) => s.assignAssetSlot)
  const buildPreviewForScript = useFlowStore((s) => s.buildPreviewForScript)
  const loadAssetsForScript = useFlowStore((s) => s.loadAssetsForScript)
  const nextStep = useFlowStore((s) => s.nextStep)
  const prevStep = useFlowStore((s) => s.prevStep)
  const isLoading = useFlowStore((s) => s.isLoading)
  const errorMessage = useFlowStore((s) => s.errorMessage)

  const [activeTab, setActiveTab] = useState<FilterTab>('all')

  const requiredSlots = useMemo(() => assets.slots.filter((s) => s.required), [assets.slots])
  const filledRequiredSlots = useMemo(() => requiredSlots.filter((s) => !!s.assignedPath), [requiredSlots])
  const filledAllSlots = useMemo(() => assets.slots.filter((s) => !!s.assignedPath), [assets.slots])
  const missingSlots = useMemo(() => assets.slots.filter((s) => !s.assignedPath), [assets.slots])
  const allRequiredFilled = requiredSlots.length > 0 && filledRequiredSlots.length === requiredSlots.length

  const videoCount = useMemo(() => assets.slots.filter((s) => s.type === 'video').length, [assets.slots])
  const imageCount = useMemo(() => assets.slots.filter((s) => s.type === 'image').length, [assets.slots])

  const completionPercent = requiredSlots.length > 0
    ? Math.round((filledRequiredSlots.length / requiredSlots.length) * 100)
    : 100

  const handleAdvance = async () => {
    const requiredMissing = assets.slots.filter((s) => s.required && !s.assignedPath)
    if (requiredMissing.length > 0) return

    await buildPreviewForScript()
    try {
      nextStep()
    } catch {
      useFlowStore.setState({ currentStep: 'PREVIEW', errorMessage: null })
    }
  }

  const handleAutoPatchMissing = () => {
    for (const slot of assets.slots) {
      if (!slot.assignedPath) {
        const ext = slot.type === 'image' ? 'png' : slot.type === 'audio' ? 'wav' : 'mp4'
        assignAssetSlot(slot.slotId, `assets/${slot.type}/${slot.slotId}.${ext}`)
      }
    }
  }

  const filteredSlots = useMemo(() => {
    switch (activeTab) {
      case 'required':
        return assets.slots.filter((s) => s.required)
      case 'missing':
        return assets.slots.filter((s) => !s.assignedPath)
      case 'filled':
        return assets.slots.filter((s) => !!s.assignedPath)
      default:
        return assets.slots
    }
  }, [assets.slots, activeTab])

  // Boş slot listesi durumu (Henüz slot yüklenmediyse)
  if (!assets.slots || assets.slots.length === 0) {
    return (
      <div className="space-y-6 max-w-4xl mx-auto py-2 animate-in fade-in duration-200" data-testid="screen-assets">
        <div className={`${CARD_CLS} text-center py-16`}>
          <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-indigo-50 dark:bg-indigo-950/50 border border-indigo-100 dark:border-indigo-900/50 flex items-center justify-center text-indigo-500">
            <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 mb-1">
            Slot Havuzu Henüz Hazırlanmadı
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-md mx-auto mb-6">
            Senaryo sahnelerine ait medya slotlarını oluşturmak ve şablonla eşleştirmek için hazırlık motorunu çalıştırın.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button variant="ghost" onClick={prevStep} data-testid="assets-back-btn">
              ← Sese Dön
            </Button>
            <Button
              variant="primary"
              onClick={() => loadAssetsForScript()}
              isLoading={isLoading}
            >
              Slotları Senaryodan Oluştur
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto py-2 animate-in fade-in duration-200" data-testid="screen-assets">
      {/* 1. Üst Başlık & Eylem Paneli */}
      <div className={CARD_CLS}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[11px] font-mono font-medium tracking-wider uppercase text-emerald-600 dark:text-emerald-400">
                AŞAMA 04 // GÖRSEL VE MEDYA SLOTLARI
              </span>
            </div>
            <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight">
              Medya Slotları ve Görsel Doğrulama
            </h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              Her sahneye ait görsel/video materyallerini bağlayın veya şablon üzerinden otomatik eşleyin.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            {!allRequiredFilled && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleAutoPatchMissing}
                className="text-xs font-medium cursor-pointer"
              >
                Eksik Slotları Otomatik Eşle
              </Button>
            )}
            <span
              className={`text-xs px-3.5 py-1.5 rounded-full font-mono font-medium border inline-flex items-center gap-1.5 ${
                assets.allSlotsFilled || allRequiredFilled
                  ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/60'
                  : 'bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800/60'
              }`}
              data-testid="assets-status-badge"
            >
              <span className={`w-1.5 h-1.5 rounded-full ${assets.allSlotsFilled || allRequiredFilled ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`} />
              {assets.allSlotsFilled || allRequiredFilled ? 'Tüm Slotlar Hazır ✓' : 'Eksik Slot Var'}
            </span>
          </div>
        </div>
      </div>

      {/* Hata Bildirimi */}
      {errorMessage && (
        <div
          className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800/60 text-rose-700 dark:text-rose-300 text-xs font-mono flex items-center gap-2"
          data-testid="assets-error"
        >
          <svg className="w-4 h-4 shrink-0 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>{errorMessage}</span>
        </div>
      )}

      {/* 2. Telemetri ve Eşleşme Metrikleri */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/70 backdrop-blur-md">
          <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-1">
            Zorunlu Eşleşme
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-bold text-zinc-900 dark:text-zinc-100 font-mono">
              {filledRequiredSlots.length} / {requiredSlots.length}
            </span>
            <span className="text-xs text-zinc-500 font-mono">Slot ({completionPercent}%)</span>
          </div>
          <div className="w-full bg-zinc-100 dark:bg-zinc-800 h-1.5 rounded-full overflow-hidden mt-2.5">
            <div
              className={`h-full transition-all duration-300 ${completionPercent === 100 ? 'bg-emerald-500' : 'bg-amber-500'}`}
              style={{ width: `${completionPercent}%` }}
            />
          </div>
        </div>

        <div className="p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/70 backdrop-blur-md">
          <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-1">
            Slot Dağılımı
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-bold text-zinc-900 dark:text-zinc-100 font-mono">
              {assets.slots.length} Toplam
            </span>
            <span className="text-xs text-zinc-500 font-mono">({videoCount} Video · {imageCount} Resim)</span>
          </div>
          <div className="text-[11px] text-zinc-400 font-mono mt-2 truncate">
            {filledAllSlots.length} atanmış · {missingSlots.length} eksik
          </div>
        </div>

        <div className="p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/70 backdrop-blur-md">
          <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-1">
            Kurgu Formatı &amp; SafeZone
          </div>
          <div className="text-xl font-bold text-zinc-900 dark:text-zinc-100 font-mono">
            9:16 Shorts
          </div>
          <div className="text-[11px] text-zinc-400 font-mono mt-2">
            1080×1920 · AST Filtergraph
          </div>
        </div>
      </div>

      {/* 3. Filtreleme Sekmeleri */}
      <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 pb-2">
        <div className="flex items-center gap-1.5">
          {(
            [
              { key: 'all', label: `Tümü (${assets.slots.length})` },
              { key: 'required', label: `Zorunlu (${requiredSlots.length})` },
              { key: 'missing', label: `Eksik (${missingSlots.length})` },
              { key: 'filled', label: `Atanmış (${filledAllSlots.length})` },
            ] as const
          ).map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors ${
                activeTab === tab.key
                  ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900'
                  : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <span className="text-[11px] font-mono text-zinc-400 hidden sm:inline">
          {filteredSlots.length} slot gösteriliyor
        </span>
      </div>

      {/* 4. Slot Listesi */}
      <div className="space-y-3">
        {filteredSlots.map((slot, index) => {
          const isAssigned = !!slot.assignedPath
          // Senaryo sahnesi ile eşleştir (varsa)
          const matchingScene = script?.scenes?.find(
            (sc) => sc.order === index + 1 || slot.slotId.includes(String(sc.order))
          )

          return (
            <div
              key={slot.slotId}
              className={`p-4 rounded-xl border transition-all duration-150 flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                isAssigned
                  ? 'border-zinc-200/90 dark:border-zinc-800/90 bg-white/80 dark:bg-zinc-900/80 shadow-2xs'
                  : 'border-amber-200 dark:border-amber-900/50 bg-amber-50/30 dark:bg-amber-950/15'
              }`}
              data-testid={`slot-${slot.slotId}`}
            >
              <div className="flex items-start gap-3.5 min-w-0 flex-1">
                {/* Sol Kanal / Tip İkonu */}
                <div className="w-10 h-10 rounded-xl bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700/60 flex flex-col items-center justify-center shrink-0">
                  {getSlotIcon(slot.type)}
                  <span className="text-[8px] font-mono text-zinc-500 font-semibold mt-0.5">
                    CH0{index + 1}
                  </span>
                </div>

                {/* Slot Detayları & Sahne Eşlemesi */}
                <div className="space-y-1.5 min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight">
                      {slot.name || `Slot ${index + 1}`}
                    </span>

                    {/* Tip Rozeti */}
                    <span className="text-[10px] px-2 py-0.5 rounded-md font-mono uppercase bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700 font-medium">
                      {slot.type}
                    </span>

                    {/* Zorunluluk */}
                    {slot.required ? (
                      <span className="text-[10px] px-2 py-0.5 rounded-md bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-800/60 font-mono font-medium">
                        Zorunlu
                      </span>
                    ) : (
                      <span className="text-[10px] px-2 py-0.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-500 font-mono">
                        Opsiyonel
                      </span>
                    )}

                    {/* Durum Rozeti */}
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-md font-mono font-medium border ${
                        isAssigned
                          ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/60'
                          : 'bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800/60'
                      }`}
                    >
                      {isAssigned ? 'Eşlendi ✓' : 'Eksik'}
                    </span>
                  </div>

                  {/* Sahne Görsel İpucu ve Anlatımı */}
                  {matchingScene && (
                    <div className="text-[11px] text-zinc-600 dark:text-zinc-400 bg-zinc-50/80 dark:bg-zinc-850/60 rounded-lg p-2 border border-zinc-100 dark:border-zinc-800/80 space-y-0.5">
                      {matchingScene.visualPrompt && (
                        <p className="line-clamp-1">
                          <strong className="text-zinc-700 dark:text-zinc-300">Görsel İpucu:</strong> {matchingScene.visualPrompt}
                        </p>
                      )}
                      {matchingScene.narration && (
                        <p className="text-zinc-500 italic line-clamp-1">
                          &ldquo;{matchingScene.narration}&rdquo;
                        </p>
                      )}
                    </div>
                  )}

                  {/* Dosya Yolu Gösterimi */}
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-50 dark:bg-zinc-850 border border-zinc-200/70 dark:border-zinc-800 max-w-full">
                    <svg className="w-3 h-3 text-zinc-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <p className="text-[11px] text-zinc-600 dark:text-zinc-300 font-mono truncate max-w-md">
                      {slot.assignedPath ? slot.assignedPath : 'Henüz medya dosyası bağlanmadı'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Aksiyon Butonu */}
              <div className="shrink-0 flex items-center gap-2 self-end md:self-center">
                {!isAssigned ? (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => assignAssetSlot(slot.slotId, `assets/${slot.type}/${slot.slotId}.mp4`)}
                    data-testid={`assign-btn-${slot.slotId}`}
                  >
                    Dosya Ata
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => assignAssetSlot(slot.slotId, `assets/${slot.type}/${slot.slotId}_yenilendi.mp4`)}
                    className="text-xs font-mono text-zinc-600 dark:text-zinc-300 hover:text-indigo-600 dark:hover:text-indigo-400"
                  >
                    Değiştir
                  </Button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* 5. Alt Aksiyon Çubuğu */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-4 border-t border-zinc-200 dark:border-zinc-800">
        <Button variant="ghost" onClick={prevStep} data-testid="assets-back-btn">
          ← Sese Dön
        </Button>

        <div className="flex items-center gap-4">
          {!allRequiredFilled && (
            <span className="text-xs font-mono text-amber-600 dark:text-amber-400 font-medium hidden sm:inline">
              Önizlemeye geçmek için tüm zorunlu slotların doldurulması gerekir.
            </span>
          )}
          <Button
            variant="primary"
            onClick={handleAdvance}
            isLoading={isLoading}
            disabled={!assets.allSlotsFilled && !allRequiredFilled}
            data-testid="assets-submit-btn"
          >
            Önizlemeye Geç &amp; İlerle →
          </Button>
        </div>
      </div>
    </div>
  )
}
