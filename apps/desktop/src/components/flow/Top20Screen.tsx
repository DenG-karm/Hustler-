import React from 'react'
import { useFlowStore } from '../../store/flowStore'
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
    <div className="space-y-lg max-w-4xl mx-auto" data-testid="screen-top20">
      <div className="border-b border-border pb-md flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">2. Top 20 Viral Video Fikirleri</h2>
          <p className="text-sm text-text-secondary">
            En yüksek viral skora sahip fikirlerden birini seçin. Seçtiğiniz fikir için 3 perdeli senaryo üretilecektir.
          </p>
        </div>
        <span className="text-xs px-sm py-xs rounded bg-surface-hover text-text-muted border border-border">
          {ideas.length} Aday
        </span>
      </div>

      {errorMessage && (
        <div className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm" data-testid="top20-error">
          {errorMessage}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-md max-h-[460px] overflow-y-auto pr-xs">
        {ideas.map((idea) => {
          const isSelected = selectedIdea?.id === idea.id
          return (
            <div
              key={idea.id}
              onClick={() => selectIdea(idea)}
              className={`p-md rounded-xl border transition-all cursor-pointer ${
                isSelected
                  ? 'border-accent bg-accent/5 ring-2 ring-accent/30'
                  : 'border-border bg-surface hover:border-border-focus'
              }`}
              data-testid={`idea-card-${idea.id}`}
            >
              <div className="flex items-center justify-between mb-xs">
                <span className="text-xs font-semibold px-xs py-0.5 rounded bg-surface-hover text-accent">
                  Skor: {idea.score}/100
                </span>
                {isSelected && <span className="text-xs font-bold text-accent">Seçildi ✓</span>}
              </div>
              <h3 className="font-semibold text-text-primary text-sm line-clamp-2 mb-xs">{idea.title}</h3>
              <p className="text-xs text-text-secondary line-clamp-2 italic">"{idea.hook}"</p>
            </div>
          )
        })}
      </div>

      <div className="flex items-center justify-between pt-md border-t border-border">
        <Button variant="ghost" onClick={prevStep} data-testid="top20-back-btn">
          ← Konuya Dön
        </Button>
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
  )
}
