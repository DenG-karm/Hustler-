import React from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'

export const ScriptScreen: React.FC = () => {
  const script = useFlowStore((s) => s.script)
  const setScript = useFlowStore((s) => s.setScript)
  const approveScript = useFlowStore((s) => s.approveScript)
  const generateAudioForScript = useFlowStore((s) => s.generateAudioForScript)
  const nextStep = useFlowStore((s) => s.nextStep)
  const prevStep = useFlowStore((s) => s.prevStep)
  const isLoading = useFlowStore((s) => s.isLoading)
  const errorMessage = useFlowStore((s) => s.errorMessage)

  const handleAdvance = async () => {
    if (!script?.isApproved) return
    await generateAudioForScript()
    try {
      nextStep()
    } catch {
      // Store hatası
    }
  }

  if (!script) {
    return (
      <div className="p-xl text-center text-text-muted" data-testid="screen-script-empty">
        Senaryo yükleniyor veya bulunamadı. Lütfen bir önceki adıma dönün.
      </div>
    )
  }

  return (
    <div className="space-y-lg max-w-3xl mx-auto" data-testid="screen-script">
      <div className="border-b border-border pb-md flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">3. Senaryo İnceleme & Onay</h2>
          <p className="text-sm text-text-secondary">
            Ses sentezi ve görselleştirmeye geçmeden önce senaryoyu inceleyin ve onaylayın.
          </p>
        </div>
        <span
          className={`text-xs px-sm py-xs rounded font-semibold ${
            script.isApproved
              ? 'bg-success/15 text-success border border-success/30'
              : 'bg-warning/15 text-warning border border-warning/30'
          }`}
          data-testid="script-status-badge"
        >
          {script.isApproved ? 'Onaylandı ✓' : 'Onay Bekliyor'}
        </span>
      </div>

      {errorMessage && (
        <div className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm" data-testid="script-error">
          {errorMessage}
        </div>
      )}

      <div className="space-y-md">
        <div>
          <label className="block text-xs font-semibold text-text-secondary mb-xs">Senaryo Başlığı</label>
          <input
            type="text"
            value={script.title}
            onChange={(e) => setScript({ title: e.target.value })}
            className="w-full px-md py-sm rounded-lg border border-border bg-surface text-text-primary text-sm font-medium"
            data-testid="script-title-input"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-text-secondary mb-xs">Seslendirme Metni</label>
          <textarea
            rows={4}
            value={script.fullText}
            onChange={(e) => setScript({ fullText: e.target.value })}
            className="w-full px-md py-sm rounded-lg border border-border bg-surface text-text-primary text-sm"
            data-testid="script-text-input"
          />
        </div>

        <div className="space-y-xs">
          <label className="block text-xs font-semibold text-text-secondary">Sahneler ({script.scenes.length})</label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-sm">
            {script.scenes.map((scene, i) => (
              <div key={i} className="p-sm rounded-lg border border-border bg-surface text-xs space-y-xs">
                <span className="font-bold text-accent">Sahne #{scene.order}</span>
                <p className="text-text-primary line-clamp-2">{scene.narration}</p>
                <p className="text-text-muted italic line-clamp-2">{scene.visualPrompt}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="p-md rounded-xl border border-border bg-surface flex items-center justify-between">
          <div>
            <h4 className="text-sm font-semibold text-text-primary">Senaryo Onayı</h4>
            <p className="text-xs text-text-secondary">Bir sonraki adıma (Ses) geçebilmek için senaryo onaylanmalıdır.</p>
          </div>
          <Button
            variant={script.isApproved ? 'outline' : 'primary'}
            size="sm"
            onClick={approveScript}
            data-testid="script-approve-btn"
          >
            {script.isApproved ? 'Onaylandı ✓' : 'Senaryoyu Onayla'}
          </Button>
        </div>
      </div>

      <div className="flex items-center justify-between pt-md border-t border-border">
        <Button variant="ghost" onClick={prevStep} data-testid="script-back-btn">
          ← Fikirlere Dön
        </Button>
        <Button
          variant="primary"
          onClick={handleAdvance}
          isLoading={isLoading}
          disabled={!script.isApproved || script.fullText.length < 20}
          data-testid="script-submit-btn"
        >
          Ses Üret & İlerle →
        </Button>
      </div>
    </div>
  )
}
