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
  const toasts = useFlowStore((s) => s.toasts)

  const isDegraded = toasts.some((t) => t.code === 'DISCOVERY_DEGRADED')

  const handleSearchAndAdvance = async () => {
    if (!topic || topic.trim().length < 3 || isLoading) return
    await fetchIdeasForTopic()
    try {
      nextStep()
    } catch {
      // Beklenen hata store'a düşer
    }
  }

  const trendingTopics = [
    'Yapay Zeka ile Para Kazanma Sırları',
    'Piramitler ve Bilinmeyen Odalar',
    'Kuantum Fiziği ve Zaman Algısı',
    'Tarihin En Zengin 5 Hükümdarı',
  ]

  return (
    <div className="space-y-lg max-w-2xl mx-auto py-md animate-in fade-in duration-200" data-testid="screen-topic">
      {/* Degraded Mod Kehribar Bilgi Bandı */}
      {isDegraded && (
        <div
          className="p-sm rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs flex items-center gap-sm animate-pulse"
          data-testid="degraded-mode-banner"
        >
          <span className="text-base">⚠️</span>
          <div className="flex-1">
            <span className="font-semibold">Kırılmaz Keşif Hattı (Degraded Mod): </span>
            <span>YouTube çıkarıcısı geçici olarak yanıt vermedi; yerel önbellek ve doğrulanmış viral şablonlar devrede.</span>
          </div>
        </div>
      )}

      {/* Başlık & Açıklama */}
      <div className="border-b border-border/80 pb-md space-y-xs">
        <div className="flex items-center gap-xs">
          <span className="text-primary font-bold text-xs uppercase tracking-wider">Adım 1 / 6</span>
          <span className="text-text-muted">•</span>
          <span className="text-text-muted text-xs">Keşif ve Niş Analizi</span>
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-text-primary">
          Hangi Konuda Viral Shorts Üretmek İstiyorsunuz?
        </h2>
        <p className="text-sm text-text-secondary leading-relaxed">
          Hedef kitlenizin dikkatini çekecek anahtar konuyu girin. Sistem, YouTube trendleri ve viralite metriklerini tarayarak en yüksek skorlu 20 video fikrini listeler.
        </p>
      </div>

      <div className="space-y-md">
        <div>
          <label htmlFor="topic-input" className="block text-xs font-semibold text-text-primary uppercase tracking-wider mb-xs">
            Konu veya Niş Başlığı
          </label>
          <div className="relative">
            <input
              id="topic-input"
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && topic.trim().length >= 3 && !isLoading) {
                  e.preventDefault()
                  handleSearchAndAdvance()
                }
              }}
              placeholder="Örn: Yapay Zeka ile Para Kazanma Sırları (Enter ile ara)"
              className="w-full px-md py-3 rounded-xl border border-border bg-surface text-text-primary placeholder:text-text-muted text-sm shadow-inner transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary pr-24"
              data-testid="topic-input"
              autoFocus
            />
            <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-xs">
              <kbd className="hidden sm:inline-block px-1.5 py-0.5 rounded bg-surface-hover text-text-muted text-[10px] font-mono border border-border">
                ↵ Enter
              </kbd>
            </div>
          </div>
        </div>

        {/* Trend Önerileri */}
        <div className="space-y-xs">
          <span className="text-[11px] font-medium text-text-muted">Önerilen Viral Konular:</span>
          <div className="flex flex-wrap gap-xs">
            {trendingTopics.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTopic(t)}
                className="px-2.5 py-1 rounded-lg text-xs bg-surface-hover/70 hover:bg-surface-hover text-text-secondary hover:text-text-primary border border-border/60 transition-colors cursor-pointer"
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {errorMessage && (
          <div className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm" data-testid="topic-error">
            {errorMessage}
          </div>
        )}

        {/* Yükleme Durumu & Buton */}
        <div className="pt-sm flex items-center justify-between">
          <span className="text-xs text-text-muted">
            {isLoading ? 'YouTube verileri taranıyor...' : 'Arama yapmak için en az 3 karakter girin.'}
          </span>
          <Button
            variant="primary"
            onClick={handleSearchAndAdvance}
            isLoading={isLoading}
            disabled={!topic || topic.trim().length < 3}
            data-testid="topic-submit-btn"
          >
            Fikirleri Ara & Top 20'ye Geç →
          </Button>
        </div>
      </div>
    </div>
  )
}
