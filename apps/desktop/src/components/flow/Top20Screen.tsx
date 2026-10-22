import React, { useState, useMemo } from 'react'
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

  const [sortBy, setSortBy] = useState<'default' | 'score'>('default')

  const isDegraded = toasts.some((t) => t.code === 'DISCOVERY_DEGRADED')

  const displayedIdeas = useMemo(() => {
    if (sortBy === 'score') {
      return [...ideas].sort((a, b) => Number(b.score) - Number(a.score))
    }
    return ideas
  }, [ideas, sortBy])

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
    <div className="space-y-md max-w-6xl mx-auto py-xs animate-in fade-in duration-200" data-testid="screen-top20">
      {/* Degraded Mod Bilgi Bandı */}
      {isDegraded && (
        <div
          className="p-sm rounded-lg bg-warning/10 border border-warning/35 text-warning text-xs flex items-center justify-between font-mono"
          data-testid="degraded-mode-banner-top20"
        >
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
            <span>
              <strong>DEGRADED MOD AKTİF:</strong> Sonuçlar yerel YouTube önbelleği ve deterministik şablonlardan türetildi.
            </span>
          </div>
          <span className="text-[10px] font-mono uppercase bg-warning/20 px-2 py-0.5 rounded border border-warning/30">
            KURTARMA HATTI
          </span>
        </div>
      )}

      {/* Üst Başlık & Telemetri Kontrol Çubuğu */}
      <div className="p-4 rounded-lg border border-border/80 bg-surface studio-panel flex flex-col sm:flex-row sm:items-center justify-between gap-sm">
        <div>
          <div className="flex items-center gap-2 font-mono text-[10px]">
            <span className="text-teal-500 dark:text-teal-400 font-medium uppercase">STAGE 01B // CANDIDATE MATRIX</span>
            <span className="text-zinc-700">|</span>
            <span className="text-zinc-500">VİRALİTE SKOR SIRALAMASI</span>
          </div>
          <h2 className="text-base sm:text-lg font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">
            Viralite Skoru En Yüksek Video Adayları
          </h2>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Sıralama Anahtarı */}
          <div className="flex items-center gap-0.5 p-0.5 rounded-md bg-zinc-100 dark:bg-zinc-900 border border-border/80 font-mono text-[10px]">
            <button
              type="button"
              onClick={() => setSortBy('default')}
              className={`px-2 py-1 rounded transition-colors cursor-pointer outline-none ring-0 ${
                sortBy === 'default'
                  ? 'bg-zinc-200/80 dark:bg-zinc-800/80 text-teal-600 dark:text-teal-400 font-medium'
                  : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200'
              }`}
            >
              VARSAYILAN
            </button>
            <button
              type="button"
              onClick={() => setSortBy('score')}
              className={`px-2 py-1 rounded transition-colors cursor-pointer outline-none ring-0 ${
                sortBy === 'score'
                  ? 'bg-zinc-200/80 dark:bg-zinc-800/80 text-teal-600 dark:text-teal-400 font-medium'
                  : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200'
              }`}
            >
              SKOR (↓)
            </button>
          </div>

          <span className="text-xs px-2.5 py-1 rounded-md bg-teal-500/15 text-teal-600 dark:text-teal-300 font-medium font-mono">
            {ideas.length} Fikir Listelendi
          </span>
        </div>
      </div>

      {errorMessage && (
        <div className="p-sm rounded-md bg-destructive/10 border border-destructive/30 text-destructive text-xs font-mono" data-testid="top20-error">
          {errorMessage}
        </div>
      )}

      {/* Aday Kartları Izgarası */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-sm max-h-[500px] overflow-y-auto pr-1">
        {displayedIdeas.map((idea, idx) => {
          const isSelected = selectedIdea?.id === idea.id
          const numericScore = Number(idea.score)
          const scoreFormatted = numericScore.toFixed(1)
          const clampedBarWidth = Math.min(100, Math.max(10, Math.round(numericScore)))

          return (
            <div
              key={idea.id}
              onClick={() => selectIdea(idea)}
              className={`group relative p-4 rounded-lg border transition-colors duration-150 cursor-pointer flex flex-col justify-between studio-panel ${
                isSelected
                  ? 'border-border bg-zinc-200/70 dark:bg-zinc-800/80'
                  : 'border-border/80 bg-surface hover:bg-zinc-200/40 dark:hover:bg-zinc-800/40'
              }`}
              data-testid={`idea-card-${idea.id}`}
            >
              {/* Seçili Sol 2px Yumuşak Teal Çizgisi */}
              {isSelected && (
                <span className="absolute left-0 top-2 bottom-2 w-[2px] rounded-r bg-teal-400" aria-hidden="true" />
              )}

              <div className="space-y-2">
                {/* Üst Satır: Sıra, Skor Rozeti & Seçim Durumu */}
                <div className="flex items-center justify-between gap-xs">
                  <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 rounded bg-zinc-200/70 dark:bg-zinc-800/80 text-[10px] font-mono font-medium text-zinc-500 dark:text-zinc-400">
                      #{idx + 1 < 10 ? `0${idx + 1}` : idx + 1}
                    </span>
                    <span
                      className={`text-[11px] font-medium px-2 py-0.5 rounded font-mono ${
                        numericScore >= 90
                          ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                          : numericScore >= 80
                          ? 'bg-teal-500/15 text-teal-600 dark:text-teal-300'
                          : 'bg-zinc-200/70 dark:bg-zinc-800/70 text-zinc-500 dark:text-zinc-400'
                      }`}
                    >
                      {scoreFormatted} Puan
                    </span>
                  </div>

                  {isSelected && (
                    <span className="text-[11px] font-mono font-medium text-teal-600 dark:text-teal-400 flex items-center gap-1 bg-teal-500/10 px-2 py-0.5 rounded">
                      <span>Seçildi</span>
                      <span>✓</span>
                    </span>
                  )}
                </div>

                {/* Skor İlerleme Barı */}
                <div className="w-full h-1 rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${
                      numericScore >= 90 ? 'bg-emerald-400' : 'bg-teal-400'
                    }`}
                    style={{ width: `${clampedBarWidth}%` }}
                  />
                </div>

                {/* Başlık ve Kanca (Hook) Terminali */}
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm leading-snug line-clamp-2 group-hover:text-teal-500 dark:group-hover:text-teal-400 transition-colors">
                  {idea.title}
                </h3>
                <div className="p-2.5 rounded-md bg-zinc-100/80 dark:bg-zinc-900/70 border border-border/70">
                  <span className="text-[9px] font-mono uppercase text-zinc-500 block mb-0.5">
                    KANCA (HOOK // 00:00 - 00:03)
                  </span>
                  <p className="text-xs text-zinc-600 dark:text-zinc-400 line-clamp-2">
                    &ldquo;{idea.hook}&rdquo;
                  </p>
                </div>
              </div>

              {/* Alt Telemetri & Doğrudan Geçiş */}
              <div className="mt-3 pt-2 border-t border-border/70 flex items-center justify-between">
                <span className="text-[10px] text-zinc-500 font-mono">
                  {idea.viewCount ? `~${(idea.viewCount / 1000).toFixed(0)}K TAHMİNİ İZLENME` : 'TREND ADAYI // YEREL'}
                </span>

                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleSelectAndAdvance(idea)
                  }}
                  className="text-xs font-mono font-medium text-teal-600 dark:text-teal-400 hover:underline transition-colors cursor-pointer outline-none ring-0"
                >
                  Seç & Senaryoya Başla →
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Alt Navigasyon ve Ana Aksiyon */}
      <div className="flex items-center justify-between pt-sm border-t border-border/80">
        <Button variant="ghost" onClick={prevStep} data-testid="top20-back-btn">
          ← Konuyu Değiştir
        </Button>
        <div className="flex items-center gap-sm">
          {!selectedIdea && (
            <span className="text-xs font-mono text-zinc-500 hidden sm:inline">
              Devam etmek için bir aday kartı seçin.
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

