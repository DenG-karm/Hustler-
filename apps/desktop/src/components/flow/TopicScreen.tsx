import React from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'

export const TopicScreen: React.FC = () => {
  const topic = useFlowStore((s) => s.topic)
  const setTopic = useFlowStore((s) => s.setTopic)
  const isLoading = useFlowStore((s) => s.isLoading)
  const fetchIdeasForTopic = useFlowStore((s) => s.fetchIdeasForTopic)
  const nextStep = useFlowStore((s) => s.nextStep)
  const errorMessage = useFlowStore((s) => s.errorMessage)

  const handleSearchAndAdvance = async () => {
    await fetchIdeasForTopic()
    try {
      nextStep()
    } catch {
      // Beklenen hata store'a düşer
    }
  }

  return (
    <div className="space-y-lg max-w-2xl mx-auto" data-testid="screen-topic">
      <div className="border-b border-border pb-md">
        <h2 className="text-xl font-bold text-text-primary">1. Konu ve Niş Belirleme</h2>
        <p className="text-sm text-text-secondary">
          Viral Shorts serisi oluşturmak istediğiniz ana konuyu girin. Sistem YouTube üzerinden en çok izlenen ve tutan fikirleri analiz eder.
        </p>
      </div>

      <div className="space-y-md">
        <div>
          <label htmlFor="topic-input" className="block text-sm font-medium text-text-primary mb-xs">
            Konu Başlığı
          </label>
          <input
            id="topic-input"
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Örn: Yapay Zeka ile Para Kazanma Sırları"
            className="w-full px-md py-sm rounded-lg border border-border bg-surface text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent"
            data-testid="topic-input"
          />
        </div>

        {errorMessage && (
          <div className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm" data-testid="topic-error">
            {errorMessage}
          </div>
        )}

        <div className="flex items-center gap-md pt-sm">
          <Button
            variant="primary"
            onClick={handleSearchAndAdvance}
            isLoading={isLoading}
            disabled={!topic || topic.trim().length < 3}
            data-testid="topic-submit-btn"
          >
            Fikirleri Ara & Top 20'ye Geç
          </Button>
        </div>
      </div>
    </div>
  )
}
