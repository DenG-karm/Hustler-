import React, { useMemo, useEffect, useState } from 'react'
import { useFlowStore } from '../../store/flowStore'
import { Button } from '../ui/Button/Button'
import { createDebouncedScriptSaver } from '../../lib/debounce'
import {
  type FlowSnapshot,
  buildClipboardPrompt,
  clipboardWrite,
  extractFlowSnapshot,
} from '../../lib/clipboard'

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
  const addToast = useFlowStore((s) => s.addToast)

  const [isCopying, setIsCopying] = useState(false)
  const [copySuccess, setCopySuccess] = useState(false)
  const [copyError, setCopyError] = useState<string | null>(null)
  const [copiedSceneIndex, setCopiedSceneIndex] = useState<number | null>(null)

  // K-705: Tek Tık Toplu Prompt Kopyalama (Tauri Native IPC)
  const handleCopyPrompt = async () => {
    setIsCopying(true)
    setCopyError(null)
    try {
      const currentState = useFlowStore.getState()
      const snapshot: FlowSnapshot = extractFlowSnapshot(currentState)
      const promptText = buildClipboardPrompt(snapshot)
      await clipboardWrite(promptText)

      setCopySuccess(true)
      addToast({
        title: 'Prompt Kopyalandı',
        message: 'Toplu prompt panoya başarıyla kopyalandı.',
        code: 'PROMPT_COPIED',
        status: 200,
      })
      setTimeout(() => setCopySuccess(false), 2500)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err || 'Pano kopyalama hatası')
      setCopyError(msg)
      addToast({
        title: 'Pano Hatası',
        message: msg,
        code: 'CLIPBOARD_ERROR',
        status: 500,
      })
    } finally {
      setIsCopying(false)
    }
  }

  // Sahne Bazlı 9:16 Prompt Kopyalama
  const handleCopyScenePrompt = async (prompt: string, idx: number) => {
    try {
      await clipboardWrite(prompt)
      setCopiedSceneIndex(idx)
      addToast({
        title: `Sahne #${idx + 1} Promptu Kopyalandı`,
        message: '9:16 dikey görsel prompt panoya aktarıldı.',
        code: 'SCENE_PROMPT_COPIED',
        status: 200,
      })
      setTimeout(() => setCopiedSceneIndex(null), 2000)
    } catch {
      // no-op
    }
  }

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
      void saveScriptContent()
    } catch {
      // Store zaten yönetir
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

  const canAdvance = script.isApproved && allClaimsVerified && script.fullText.length >= 20

  return (
    <div className="space-y-md max-w-6xl mx-auto py-sm animate-in fade-in duration-200" data-testid="screen-script">
      {/* Üst Bar: Başlık, Durum Rozeti ve Toplu Pano Aksiyonu */}
      <div className="border-b border-border/80 pb-sm flex flex-col sm:flex-row sm:items-center justify-between gap-sm">
        <div>
          <div className="flex items-center gap-xs">
            <span className="text-primary font-bold text-xs uppercase tracking-wider">Adım 2 / 6</span>
            <span className="text-text-muted">•</span>
            <span className="text-text-muted text-xs">Senaryo Editörü & İddia Doğrulama</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-text-primary">
            3 Perdeli Senaryo ve Doğrulama Masası
          </h2>
        </div>

        <div className="flex items-center gap-xs sm:gap-sm shrink-0">
          {script.saveStatus === 'SAVING' && (
            <span className="text-xs text-text-muted animate-pulse font-mono" data-testid="script-saving-indicator">
              Kaydediliyor...
            </span>
          )}
          {script.saveStatus === 'SAVED' && (
            <span className="text-xs text-emerald-400 font-mono" data-testid="script-saved-indicator">
              Kaydedildi ✓
            </span>
          )}
          {script.saveStatus === 'UNCHANGED' && (
            <span className="text-xs text-text-muted font-mono" data-testid="script-unchanged-indicator">
              Senkron ✓
            </span>
          )}

          <span
            className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
              script.isApproved
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
            }`}
            data-testid="script-status-badge"
          >
            {script.isApproved ? 'Onaylandı ✓' : 'Onay Bekliyor'}
          </span>

          <Button
            variant="outline"
            size="sm"
            onClick={handleCopyPrompt}
            isLoading={isCopying}
            data-testid="copy-prompt-btn"
          >
            {copySuccess ? '✓ Kopyalandı' : 'Promptu Kopyala'}
          </Button>
        </div>
      </div>

      {copyError && (
        <div
          className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm flex items-center justify-between"
          data-testid="clipboard-error-banner"
        >
          <span>Pano Hatası: {copyError}</span>
          <button
            onClick={() => setCopyError(null)}
            className="text-xs text-destructive hover:underline ml-2"
          >
            ✕
          </button>
        </div>
      )}

      {errorMessage && (
        <div
          className="p-sm rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm"
          data-testid="script-error"
        >
          {errorMessage}
        </div>
      )}

      {/* İki Sütunlu Stüdyo Düzeni: Sol = Metin & Sahneler, Sağ = İddia Doğrulama Masası */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-lg">
        {/* SOL SÜTUN (7/12): Başlık, Seslendirme Metni ve 9:16 Sahne Blokları */}
        <div className="lg:col-span-7 space-y-md">
          {/* Başlık Girişi */}
          <div className="space-y-xs">
            <label className="block text-xs font-semibold text-text-primary uppercase tracking-wider">
              Senaryo Başlığı
            </label>
            <input
              type="text"
              value={script.title}
              onChange={(e) => handleTitleChange(e.target.value)}
              className="w-full px-md py-2.5 rounded-xl border border-border bg-surface text-text-primary text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary shadow-inner"
              data-testid="script-title-input"
            />
          </div>

          {/* Seslendirme Metni (Full Text) */}
          <div className="space-y-xs">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold text-text-primary uppercase tracking-wider">
                Seslendirme Metni (TTS Anlatımı)
              </label>
              <span className="text-[11px] text-text-muted font-mono">
                {script.fullText.length} Karakter • ~{Math.round(script.fullText.split(/\s+/).length * 0.35)} sn
              </span>
            </div>
            <textarea
              rows={4}
              value={script.fullText}
              onChange={(e) => handleTextChange(e.target.value)}
              className="w-full p-md rounded-xl border border-border bg-surface text-text-primary text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary shadow-inner resize-y"
              data-testid="script-text-input"
            />
          </div>

          {/* Sahne Bazlı (Scene 1, 2, 3) 9:16 Görsel Prompt Kartları */}
          <div className="space-y-sm">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold text-text-primary uppercase tracking-wider">
                3 Perdeli Sahneler & 9:16 Görsel Promptlar ({script.scenes.length})
              </label>
              <span className="text-[11px] text-text-muted">Dikey Video 9:16 Midjourney/FLUX Uyumlu</span>
            </div>

            <div className="space-y-sm">
              {script.scenes.map((scene, idx) => {
                const isCopied = copiedSceneIndex === idx
                return (
                  <div
                    key={idx}
                    className="p-md rounded-xl border border-border/80 bg-surface/80 hover:bg-surface space-y-sm transition-all"
                  >
                    <div className="flex items-center justify-between">
                      <span className="px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs font-bold font-mono">
                        Sahne #{scene.order}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCopyScenePrompt(scene.visualPrompt, idx)}
                        className="text-[11px] font-semibold text-primary hover:text-primary-hover hover:underline transition-colors flex items-center gap-1 cursor-pointer"
                      >
                        {isCopied ? (
                          <>
                            <span className="text-emerald-400">✓</span>
                            <span>Kopyalandı</span>
                          </>
                        ) : (
                          <>
                            <span>📋</span>
                            <span>9:16 Promptu Kopyala</span>
                          </>
                        )}
                      </button>
                    </div>

                    <div>
                      <span className="text-[11px] text-text-muted font-semibold">Anlatım (Voiceover):</span>
                      <p className="text-xs text-text-primary font-medium mt-0.5">{scene.narration}</p>
                    </div>

                    <div className="p-2 rounded-lg bg-surface-hover/70 border border-border/60">
                      <div className="flex items-center justify-between text-[10px] text-text-muted uppercase font-mono mb-1">
                        <span>Görselleştirme Promptu (9:16 Aspect)</span>
                        <span className="text-primary font-semibold">--ar 9:16</span>
                      </div>
                      <p className="text-xs text-text-secondary font-mono leading-relaxed select-all">
                        {scene.visualPrompt}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* SAĞ SÜTUN (5/12): İddia Doğrulama Masası & Senaryo Onay Kartı */}
        <div className="lg:col-span-5 space-y-md">
          {/* İddia Doğrulama (Claim Verification) Listesi */}
          <div className="p-md rounded-2xl border border-border bg-surface shadow-sm space-y-sm" data-testid="claims-card">
            <div className="flex items-center justify-between border-b border-border/60 pb-sm">
              <div>
                <h4 className="text-sm font-bold text-text-primary flex items-center gap-1">
                  <span>İddia Doğrulama</span>
                  <span className="text-xs text-text-muted font-mono">({claims.length})</span>
                </h4>
                <p className="text-[11px] text-text-secondary mt-0.5">
                  Yapay zekanın ürettiği gerçeklik iddialarını teyit edin.
                </p>
              </div>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-bold font-mono border ${
                  allClaimsVerified
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                    : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                }`}
                data-testid="claims-badge"
              >
                {verifiedCount} / {claims.length} Onaylandı
              </span>
            </div>

            <div className="space-y-xs pt-xs max-h-[320px] overflow-y-auto pr-xs">
              {claims.map((claim) => (
                <label
                  key={claim.id}
                  className={`flex items-start gap-sm p-sm rounded-xl border transition-all cursor-pointer ${
                    claim.verified
                      ? 'border-emerald-500/30 bg-emerald-500/5 text-text-primary'
                      : 'border-border/80 bg-surface-hover/30 hover:bg-surface-hover text-text-secondary'
                  }`}
                  data-testid={`claim-item-${claim.id}`}
                >
                  <input
                    type="checkbox"
                    checked={claim.verified}
                    onChange={() => toggleClaim(claim.id)}
                    className="mt-0.5 rounded border-border text-primary focus:ring-primary w-4 h-4 cursor-pointer"
                    data-testid={`claim-checkbox-${claim.id}`}
                  />
                  <span className={`text-xs leading-snug select-none ${claim.verified ? 'font-medium text-text-primary' : 'text-text-muted'}`}>
                    {claim.text}
                  </span>
                </label>
              ))}
            </div>

            {!allClaimsVerified && (
              <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs flex items-center gap-1.5" data-testid="claims-lock-warning">
                <span>⚠️</span>
                <span>Tüm iddialar onaylanmadan senaryo onayı açılamaz.</span>
              </div>
            )}
          </div>

          {/* Senaryo Onay Kartı */}
          <div className="p-md rounded-2xl border border-border bg-surface/90 shadow-sm space-y-sm">
            <div>
              <h4 className="text-sm font-bold text-text-primary">Senaryo Nihai Onayı</h4>
              <p className="text-xs text-text-secondary mt-0.5">
                Tüm iddialar doğrulandıktan sonra senaryoyu kilitleyip ses sentezine geçebilirsiniz.
              </p>
            </div>

            <Button
              variant={script.isApproved ? 'outline' : 'primary'}
              size="md"
              onClick={handleApprove}
              disabled={!allClaimsVerified}
              className="w-full justify-center"
              data-testid="script-approve-btn"
            >
              {script.isApproved ? '✓ Senaryo Onaylandı' : 'Senaryoyu Onayla'}
            </Button>
          </div>

          {/* Kilit Açıklama Mikro-Kopyası */}
          {!canAdvance && (
            <div className="p-sm rounded-xl border border-border/80 bg-surface-hover/40 text-text-muted text-xs space-y-1">
              <span className="font-semibold text-text-secondary block">İlerleme Koşulları:</span>
              <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                <li className={allClaimsVerified ? 'text-emerald-400 font-medium' : ''}>
                  Tüm iddiaların ({verifiedCount}/{claims.length}) onaylanması
                </li>
                <li className={script.isApproved ? 'text-emerald-400 font-medium' : ''}>
                  Senaryo Nihai Onay butonuna basılması
                </li>
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Alt Navigasyon ve İlerleme Barı */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-sm pt-md border-t border-border/80">
        <Button variant="ghost" onClick={prevStep} data-testid="script-back-btn">
          ← Fikirlere Dön
        </Button>

        <div className="flex items-center gap-md">
          {!canAdvance && (
            <span className="text-xs text-amber-400 font-medium hidden sm:inline" title="İlerleme kilitli">
              ⚠️ Tüm iddialar onaylanmadan ses üretimine geçilemez.
            </span>
          )}
          <Button
            variant="primary"
            onClick={handleAdvance}
            isLoading={isLoading}
            disabled={!canAdvance}
            data-testid="script-submit-btn"
          >
            Sese Geç & Ses Üret →
          </Button>
        </div>
      </div>
    </div>
  )
}
