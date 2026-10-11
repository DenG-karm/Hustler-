import React, { useMemo, useEffect } from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'
import { createDebouncedScriptSaver } from '../../lib/debounce'

export const ScriptScreen: React.FC = () => {
  const script = useFlowStore((s) => s.script)
  const setScript = useFlowStore((s) => s.setScript)
  const toggleClaim = useFlowStore((s) => s.toggleClaim)
  const saveScriptContent = useFlowStore((s) => s.saveScriptContent)
  const approveScript = useFlowStore((s) => s.approveScript)
  const generateAudioForScript = useFlowStore((s) => s.generateAudioForScript)
  const nextStep = useFlowStore((s) => s.nextStep)
  const prevStep = useFlowStore((s) => s.prevStep)
  const isLoading = useFlowStore((s) => s.isLoading)
  const errorMessage = useFlowStore((s) => s.errorMessage)

  // K-704: Minimum 400ms Debounce ile IPC Trafik Yönetimi
  const debouncedSaver = useMemo(() => {
    return createDebouncedScriptSaver(
      async (title: string, fullText: string) => {
        await saveScriptContent(title, fullText)
      },
      400,
      (msg) => console.log(msg)
    )
  }, [saveScriptContent])

  useEffect(() => {
    return () => {
      debouncedSaver.cancel()
    }
  }, [debouncedSaver])

  const handleTitleChange = (newTitle: string) => {
    setScript({ title: newTitle })
    debouncedSaver(newTitle, script?.fullText ?? '')
  }

  const handleTextChange = (newText: string) => {
    setScript({ fullText: newText })
    debouncedSaver(script?.title ?? '', newText)
  }

  const claims = script?.claims ?? []
  const verifiedCount = claims.filter((c) => c.verified).length
  const allClaimsVerified = claims.length > 0 && verifiedCount === claims.length

  const handleApprove = () => {
    try {
      approveScript()
      // Onaylandığı an sunucuya da güncel durumu kaydet
      void saveScriptContent()
    } catch {
      // Store zaten hata mesajını yönetir
    }
  }

  const handleAdvance = async () => {
    if (!script?.isApproved || !allClaimsVerified) return
    await generateAudioForScript()
    try {
      nextStep()
    } catch {
      // Store kural ihlali
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
            Ses sentezi ve görselleştirmeye geçmeden önce senaryoyu düzenleyin ve güvenlik iddialarını onaylayın.
          </p>
        </div>
        <div className="flex items-center gap-xs">
          {script.saveStatus === 'SAVING' && (
            <span className="text-xs text-text-muted animate-pulse" data-testid="script-saving-indicator">
              Kaydediliyor...
            </span>
          )}
          {script.saveStatus === 'SAVED' && (
            <span className="text-xs text-success" data-testid="script-saved-indicator">
              Kaydedildi ✓
            </span>
          )}
          {script.saveStatus === 'UNCHANGED' && (
            <span className="text-xs text-text-muted" data-testid="script-unchanged-indicator">
              Senkron ✓
            </span>
          )}
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
      </div>

      {errorMessage && (
        <div
          className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm"
          data-testid="script-error"
        >
          {errorMessage}
        </div>
      )}

      <div className="space-y-md">
        <div>
          <label className="block text-xs font-semibold text-text-secondary mb-xs">Senaryo Başlığı</label>
          <input
            type="text"
            value={script.title}
            onChange={(e) => handleTitleChange(e.target.value)}
            className="w-full px-md py-sm rounded-lg border border-border bg-surface text-text-primary text-sm font-medium"
            data-testid="script-title-input"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-text-secondary mb-xs">Seslendirme Metni</label>
          <textarea
            rows={4}
            value={script.fullText}
            onChange={(e) => handleTextChange(e.target.value)}
            className="w-full px-md py-sm rounded-lg border border-border bg-surface text-text-primary text-sm"
            data-testid="script-text-input"
          />
        </div>

        {/* K-704: LLM Tarafından Üretilen İddialar (Claims) Listesi & Katı Kilit */}
        <div className="p-md rounded-xl border border-border bg-surface/50 space-y-sm" data-testid="claims-card">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-semibold text-text-primary flex items-center gap-xs">
                <span>Doğruluk ve Güvenlik İddiaları (Claims)</span>
                <span className="text-xs text-text-muted">({claims.length})</span>
              </h4>
              <p className="text-xs text-text-secondary">
                Yapay zekanın ürettiği iddiaların doğruluğunu tek tek teyit etmeden seslendirmeye geçilemez.
              </p>
            </div>
            <span
              className={`text-xs px-sm py-xs rounded font-semibold ${
                allClaimsVerified
                  ? 'bg-success/15 text-success border border-success/30'
                  : 'bg-warning/15 text-warning border border-warning/30'
              }`}
              data-testid="claims-badge"
            >
              {verifiedCount} / {claims.length} Onaylandı
            </span>
          </div>

          <div className="space-y-xs pt-xs">
            {claims.map((claim) => (
              <label
                key={claim.id}
                className="flex items-start gap-sm p-sm rounded-lg border border-border hover:bg-surface cursor-pointer transition-colors"
                data-testid={`claim-item-${claim.id}`}
              >
                <input
                  type="checkbox"
                  checked={claim.verified}
                  onChange={() => toggleClaim(claim.id)}
                  className="mt-0.5 rounded border-border text-accent focus:ring-accent"
                  data-testid={`claim-checkbox-${claim.id}`}
                />
                <span className={`text-xs ${claim.verified ? 'text-text-primary font-medium' : 'text-text-muted'}`}>
                  {claim.text}
                </span>
              </label>
            ))}
          </div>

          {!allClaimsVerified && (
            <p className="text-xs text-warning font-medium pt-xs" data-testid="claims-lock-warning">
              ⚠️ Katı Kural: Devam edebilmek için yukarıdaki tüm iddiaların onaylanması zorunludur.
            </p>
          )}
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
            <p className="text-xs text-text-secondary">
              Tüm iddialar doğrulandıktan sonra senaryo kilitlenir ve ses sentezi aşamasına açılır.
            </p>
          </div>
          <Button
            variant={script.isApproved ? 'outline' : 'primary'}
            size="sm"
            onClick={handleApprove}
            disabled={!allClaimsVerified}
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
          disabled={!script.isApproved || !allClaimsVerified || script.fullText.length < 20}
          data-testid="script-submit-btn"
        >
          Ses Üret & İlerle →
        </Button>
      </div>
    </div>
  )
}
