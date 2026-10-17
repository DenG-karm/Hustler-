import React from 'react'
import { useFlowStore, type VideoIdea } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'

export const Top20Screen: React.FC = () => {
  const ideas = useFlowStore((s) => s.ideas)
  const selectedIdea = useFlowStore((s) => s.selectedIdea)
  const selectIdea = useFlowStore((s) => s.selectIdea)
  const generateScriptForIdea = useFlowStore((s) => s.generateScriptForIdea)
  const nextStep = useFlowStore((s) => s.nextStep)
  const prevStep = useFlowStore((s) => s.prevStep)
  const isLoading = useFlowStore((s) => s.isLoading)
  const errorMessage = useFlowStore((s) => s.errorMessage)
  const toasts = useFlowStore((s) => s.toasts)

  const isDegraded = toasts.some((t) => t.code === 'DISCOVERY_DEGRADED')

  const handleSelectAndAdvance = async (idea: VideoIdea) => {
    selectIdea(idea)
    await generateScriptForIdea()
    try {
      nextStep()
    } catch {
      // Store hatası
    }
  }

  const handleGenerateScriptAndAdvance = async () => {
    if (!selectedIdea) return
    await generateScriptForIdea()
    try {
      nextStep()
    } catch {
      // Store hatası
    }
  }

  return (
    <div className="space-y-lg max-w-5xl mx-auto py-sm animate-in fade-in duration-200" data-testid="screen-top20">
      {/* Degraded Mod Kehribar Bilgi Bandı */}
      {isDegraded && (
        <div
          className="p-sm rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs flex items-center justify-between"
          data-testid="degraded-mode-banner-top20"
        >
          <div className="flex items-center gap-xs">
            <span className="text-base">⚠️</span>
            <span>
              <strong>Degraded Mod Aktif:</strong> Sonuçlar yerel YouTube önbelleği ve deterministik şablonlardan türetildi.
            </span>
          </div>
          <span className="text-[10px] font-mono uppercase bg-amber-500/20 px-2 py-0.5 rounded">Kurtarma Hattı</span>
        </div>
      )}

      {/* Üst Başlık & İstatistik */}
      <div className="border-b border-border/80 pb-md flex flex-col sm:flex-row sm:items-center justify-between gap-sm">
        <div>
          <div className="flex items-center gap-xs">
            <span className="text-primary font-bold text-xs uppercase tracking-wider">Adım 1 / 6 • Aday Fikirler</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-text-primary">
            Viralite Skoru En Yüksek 20 Video Fikri
          </h2>
          <p className="text-sm text-text-secondary">
            En yüksek potansiyelli fikri seçin veya tek tıkla doğrudan senaryo üretimini başlatın.
          </p>
        </div>
        <div className="flex items-center gap-xs shrink-0">
          <span className="text-xs px-2.5 py-1 rounded-full bg-primary/10 text-primary border border-primary/20 font-semibold font-mono">
            {ideas.length} Fikir Listelendi
          </span>
        </div>
      </div>

      {errorMessage && (
        <div className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm" data-testid="top20-error">
          {errorMessage}
        </div>
      )}

      {/* Kartlar Izgarası */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-md max-h-[520px] overflow-y-auto pr-xs">
        {ideas.map((idea, idx) => {
          const isSelected = selectedIdea?.id === idea.id
          const scoreFormatted = Number(idea.score).toFixed(1)

          return (
            <div
              key={idea.id}
              onClick={() => selectIdea(idea)}
              className={`group p-md rounded-2xl border transition-all duration-200 cursor-pointer flex flex-col justify-between ${
                isSelected
                  ? 'border-primary bg-primary/5 ring-2 ring-primary/40 shadow-lg shadow-primary/10'
                  : 'border-border/80 bg-surface hover:border-border hover:shadow-md hover:bg-surface-hover/50'
              }`}
              data-testid={`idea-card-${idea.id}`}
            >
              <div>
                {/* Rozetler: Sıra ve Viralite Skoru */}
                <div className="flex items-center justify-between gap-xs mb-sm">
                  <div className="flex items-center gap-xs">
                    <span className="w-5 h-5 rounded-full bg-surface-hover border border-border flex items-center justify-center text-[10px] font-mono text-text-muted">
                      #{idx + 1}
                    </span>
                    <span
                      className={`text-xs font-bold px-2 py-0.5 rounded-full border font-mono ${
                        idea.score >= 90
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : idea.score >= 80
                          ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30'
                          : 'bg-surface-hover text-text-secondary border-border'
                      }`}
                    >
                      {scoreFormatted} Puan
                    </span>
                  </div>

                  {isSelected && (
                    <span className="text-xs font-bold text-primary flex items-center gap-1">
                      <span>Seçildi</span>
                      <span>✓</span>
                    </span>
                  )}
                </div>

                {/* Başlık ve Kanca Metni */}
                <h3 className="font-semibold text-text-primary text-sm leading-snug line-clamp-2 mb-xs group-hover:text-primary transition-colors">
                  {idea.title}
                </h3>
                <p className="text-xs text-text-secondary italic line-clamp-2 bg-surface-hover/40 p-2 rounded-lg border border-border/40">
                  "{idea.hook}"
                </p>
              </div>

              {/* Alt Bilgi & Hızlı Eylem */}
              <div className="mt-md pt-sm border-t border-border/60 flex items-center justify-between">
                <span className="text-[11px] text-text-muted font-mono">
                  {idea.viewCount ? `~${(idea.viewCount / 1000).toFixed(0)}K Tahmini İzlenme` : 'Trend Adayı'}
                </span>

                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleSelectAndAdvance(idea)
                  }}
                  className="text-xs font-semibold text-primary hover:text-primary-hover hover:underline transition-colors cursor-pointer"
                >
                  Seç & Senaryoya Başla →
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Alt Navigasyon ve Ana Aksiyon */}
      <div className="flex items-center justify-between pt-md border-t border-border/80">
        <Button variant="ghost" onClick={prevStep} data-testid="top20-back-btn">
          ← Konuyu Değiştir
        </Button>
        <div className="flex items-center gap-sm">
          {!selectedIdea && (
            <span className="text-xs text-text-muted hidden sm:inline">
              Lütfen devam etmek için bir fikir kartına tıklayın.
            </span>
          )}
          <Button
            variant="primary"
            onClick={handleGenerateScriptAndAdvance}
            isLoading={isLoading}
            disabled={!selectedIdea}
            data-testid="top20-submit-btn"
          >
            Senaryo Oluştur & İlerle →
          </Button>
        </div>
      </div>
    </div>
  )
}
