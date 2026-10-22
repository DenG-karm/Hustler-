import React, { useMemo, useEffect, useState } from 'react'
import { useFlowStore } from '../../store/flowStore'
import { createDebouncedScriptSaver } from '../../lib/debounce'
import {
  type FlowSnapshot,
  buildClipboardPrompt,
  clipboardWrite,
  extractFlowSnapshot,
} from '../../lib/clipboard'

const CARD_CLS =
  'p-6 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs'

export const ScriptScreen: React.FC = () => {
  const script = useFlowStore((s) => s.script)
  const setScript = useFlowStore((s) => s.setScript)
  const toggleClaim = useFlowStore((s) => s.toggleClaim)
  const saveScriptContent = useFlowStore((s) => s.saveScriptContent)
  const approveScript = useFlowStore((s) => s.approveScript)
  const generateAudioForScript = useFlowStore((s) => s.generateAudioForScript)
  const nextStep = useFlowStore((s) => s.nextStep)
  const setActiveView = useFlowStore((s) => s.setActiveView)
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
    try {
      await generateAudioForScript()
      nextStep()
    } catch {
      useFlowStore.setState({ currentStep: 'AUDIO', errorMessage: null })
    }
  }

  if (!script) {
    return (
      <div className={`${CARD_CLS} text-center py-16`} data-testid="screen-script-empty">
        <p className="text-sm text-zinc-500 mb-4">Senaryo verisi yükleniyor veya henüz oluşturulmadı.</p>
        <button
          type="button"
          onClick={() => setActiveView('channels')}
          className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-[#111827] dark:bg-white text-white dark:text-zinc-900 cursor-pointer hover:opacity-90 transition-opacity"
        >
          Kanal Masasına Dön
        </button>
      </div>
    )
  }

  const canAdvance = script.isApproved && allClaimsVerified && script.fullText.length >= 20

  const handleVerifyAllClaims = () => {
    for (const c of claims) {
      if (!c.verified) {
        toggleClaim(c.id)
      }
    }
  }

  const estimatedSeconds = Math.round(script.fullText.split(/\s+/).filter(Boolean).length * 0.35)
  const estimatedFrames = estimatedSeconds * 30

  const actNames = ['Giriş Kancası (Hook)', 'Gelişme & Kanıt (Body)', 'Kapanış & Çağrı (Payoff)']

  return (
    <div className="space-y-6 pb-12 animate-in fade-in duration-200" data-testid="screen-script">
      {/* Üst Bar: Başlık, Durum Rozeti ve Toplu Pano Aksiyonu */}
      <div className={`${CARD_CLS} flex flex-col sm:flex-row sm:items-center justify-between gap-4`}>
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              Adım 2 / 6
            </span>
            <span className="text-zinc-300 dark:text-zinc-700">•</span>
            <span className="text-xs text-zinc-500 font-medium">Otomatik Senkronize</span>
          </div>
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
            Senaryo ve Doğrulama Masası
          </h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            3 perdeli anlatım yapısı, 9:16 sahne promptları ve gerçeklik iddialarını yönetin.
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          {script.saveStatus === 'SAVING' && (
            <span className="text-xs text-zinc-500 animate-pulse font-medium" data-testid="script-saving-indicator">
              Kaydediliyor...
            </span>
          )}
          {script.saveStatus === 'SAVED' && (
            <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium" data-testid="script-saved-indicator">
              Kaydedildi ✓
            </span>
          )}
          {script.saveStatus === 'UNCHANGED' && (
            <span className="text-xs text-zinc-500 font-medium" data-testid="script-unchanged-indicator">
              Senkron ✓
            </span>
          )}

          <span
            className={`text-xs px-3 py-1.5 rounded-xl font-semibold border ${
              script.isApproved
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
            }`}
            data-testid="script-status-badge"
          >
            {script.isApproved ? 'Onaylandı ✓' : 'Onay Bekliyor'}
          </span>

          <button
            type="button"
            onClick={handleCopyPrompt}
            disabled={isCopying}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl border border-[#E5E7EB] dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/60 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-800 dark:text-zinc-200 text-xs font-semibold transition-colors cursor-pointer"
            data-testid="copy-prompt-btn"
          >
            <svg className="w-3.5 h-3.5 text-zinc-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <rect x="9" y="9" width="13" height="13" rx="2" />
              <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
            </svg>
            <span>{copySuccess ? '✓ Kopyalandı' : 'Promptu Kopyala'}</span>
          </button>
        </div>
      </div>

      {copyError && (
        <div
          className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/40 text-rose-600 dark:text-rose-400 text-xs font-medium flex items-center justify-between"
          data-testid="clipboard-error-banner"
        >
          <span>Pano Hatası: {copyError}</span>
          <button
            onClick={() => setCopyError(null)}
            className="text-xs text-rose-600 dark:text-rose-400 hover:underline ml-2 cursor-pointer"
          >
            ✕ Kapat
          </button>
        </div>
      )}

      {errorMessage && (
        <div
          className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/40 text-rose-600 dark:text-rose-400 text-xs font-medium"
          data-testid="script-error"
        >
          {errorMessage}
        </div>
      )}

      {/* İki Sütunlu Stüdyo Düzeni: Sol = Metin & Sahneler, Sağ = İddia Doğrulama Masası */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* SOL SÜTUN (7/12): Başlık, Seslendirme Metni ve 9:16 Sahne Blokları */}
        <div className="lg:col-span-7 space-y-6">
          {/* Başlık & Anlatım Editör Modülü */}
          <div className={`${CARD_CLS} space-y-5`}>
            {/* Başlık Girişi */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                Senaryo Başlığı
              </label>
              <input
                type="text"
                value={script.title}
                onChange={(e) => handleTitleChange(e.target.value)}
                placeholder="Örn: Piramitlerin Gizli Odaları..."
                className="w-full px-4 py-2.5 rounded-xl border border-[#E5E7EB] dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/60 text-zinc-900 dark:text-zinc-100 text-sm font-medium outline-none focus:border-zinc-400 dark:focus:border-zinc-600 transition-colors"
                data-testid="script-title-input"
              />
            </div>

            {/* Seslendirme Metni (Full Text) */}
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                  Seslendirme Metni (TTS Anlatımı)
                </label>
                <div className="flex items-center gap-2 text-xs text-zinc-500">
                  <span>{script.fullText.length} karakter</span>
                  <span>•</span>
                  <span className="font-semibold text-zinc-700 dark:text-zinc-300">
                    ~{estimatedSeconds} sn ({estimatedFrames} kare)
                  </span>
                </div>
              </div>
              <textarea
                rows={5}
                value={script.fullText}
                onChange={(e) => handleTextChange(e.target.value)}
                placeholder="Seslendirme anlatımını buraya yazın..."
                className="w-full p-4 rounded-xl border border-[#E5E7EB] dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/60 text-zinc-900 dark:text-zinc-100 text-sm leading-relaxed outline-none focus:border-zinc-400 dark:focus:border-zinc-600 transition-colors resize-y"
                data-testid="script-text-input"
              />
            </div>
          </div>

          {/* Sahne Bazlı (Scene 1, 2, 3) 9:16 Görsel Prompt Kartları */}
          <div className={`${CARD_CLS} space-y-4`}>
            <div className="flex items-center justify-between border-b border-[#E5E7EB] dark:border-zinc-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                  3 Perdeli Sahne Akışı ve 9:16 Görsel Promptlar
                </h3>
                <p className="text-xs text-zinc-500 mt-0.5">
                  Her sahnenin dikey format promptunu ayrı ayrı kopyalayıp görsel üretebilirsiniz.
                </p>
              </div>
              <span className="text-[11px] font-semibold px-2.5 py-1 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 shrink-0">
                9:16 Dikey
              </span>
            </div>

            <div className="space-y-3.5">
              {script.scenes.map((scene, idx) => {
                const isCopied = copiedSceneIndex === idx
                const actLabel = actNames[idx] || `Sahne #${scene.order}`
                return (
                  <div
                    key={idx}
                    className="p-4 rounded-xl border border-[#E5E7EB] dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-950/40 hover:border-zinc-300 dark:hover:border-zinc-700 space-y-3 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-0.5 rounded-md bg-[#111827] dark:bg-white text-white dark:text-zinc-900 text-xs font-bold">
                          Sahne {scene.order}
                        </span>
                        <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                          {actLabel}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleCopyScenePrompt(scene.visualPrompt, idx)}
                        className="text-xs font-semibold text-zinc-700 dark:text-zinc-200 hover:text-black dark:hover:text-white flex items-center gap-1.5 cursor-pointer px-2.5 py-1 rounded-lg border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 transition-colors shadow-2xs"
                      >
                        {isCopied ? (
                          <>
                            <span className="text-emerald-500 font-bold">✓</span>
                            <span>Kopyalandı</span>
                          </>
                        ) : (
                          <>
                            <svg className="w-3 h-3 text-zinc-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                              <rect x="9" y="9" width="13" height="13" rx="2" />
                              <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                            </svg>
                            <span>Promptu Kopyala</span>
                          </>
                        )}
                      </button>
                    </div>

                    <div>
                      <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider block mb-1">
                        Sahne Anlatımı
                      </span>
                      <p className="text-xs text-zinc-900 dark:text-zinc-100 font-medium leading-relaxed">
                        {scene.narration}
                      </p>
                    </div>

                    <div className="p-3 rounded-xl bg-white dark:bg-zinc-900 border border-[#E5E7EB] dark:border-zinc-800">
                      <div className="flex items-center justify-between text-[11px] font-semibold text-zinc-500 mb-1.5">
                        <span>GÖRSELLEŞTİRME PROMPTU</span>
                        <span className="text-zinc-400">Aspect 9:16</span>
                      </div>
                      <p className="text-xs text-zinc-600 dark:text-zinc-300 font-mono leading-relaxed select-all">
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
        <div className="lg:col-span-5 space-y-6">
          {/* İddia Doğrulama (Claim Verification) Listesi */}
          <div className={`${CARD_CLS} space-y-4`} data-testid="claims-card">
            <div className="flex items-center justify-between border-b border-[#E5E7EB] dark:border-zinc-800 pb-3">
              <div>
                <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                  <span>İddia Doğrulama Masası</span>
                  <span className="text-xs text-zinc-500 font-normal">({claims.length})</span>
                </h4>
                <p className="text-xs text-zinc-500 mt-0.5">
                  Üretilen iddiaları ses sentezi öncesinde teyit edin.
                </p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <span
                  className={`text-xs px-2.5 py-1 rounded-lg font-semibold border ${
                    allClaimsVerified
                      ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                      : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                  }`}
                  data-testid="claims-badge"
                >
                  {verifiedCount} / {claims.length} Teyit Edildi
                </span>
                {!allClaimsVerified && claims.length > 0 && (
                  <button
                    type="button"
                    onClick={handleVerifyAllClaims}
                    className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
                  >
                    Tümünü Teyit Et →
                  </button>
                )}
              </div>
            </div>

            <div className="space-y-2 max-h-[340px] overflow-y-auto pr-1">
              {claims.map((claim) => (
                <label
                  key={claim.id}
                  className={`flex items-start gap-3 p-3.5 rounded-xl border transition-all cursor-pointer ${
                    claim.verified
                      ? 'border-emerald-500/30 bg-emerald-50/40 dark:bg-emerald-950/10 text-zinc-900 dark:text-zinc-100'
                      : 'border-[#E5E7EB] dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-950/40 hover:bg-zinc-100/60 dark:hover:bg-zinc-800/40 text-zinc-600 dark:text-zinc-400'
                  }`}
                  data-testid={`claim-item-${claim.id}`}
                >
                  <input
                    type="checkbox"
                    checked={claim.verified}
                    onChange={() => toggleClaim(claim.id)}
                    className="mt-0.5 w-4 h-4 rounded text-zinc-900 dark:text-white cursor-pointer accent-zinc-900 dark:accent-white"
                    data-testid={`claim-checkbox-${claim.id}`}
                  />
                  <span className={`text-xs leading-relaxed select-none ${claim.verified ? 'font-semibold text-zinc-900 dark:text-zinc-100' : 'text-zinc-600 dark:text-zinc-400'}`}>
                    {claim.text}
                  </span>
                </label>
              ))}
            </div>

            {!allClaimsVerified && (
              <div
                className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 text-amber-700 dark:text-amber-400 text-xs flex items-center gap-2 font-medium"
                data-testid="claims-lock-warning"
              >
                <svg className="w-4 h-4 shrink-0 text-amber-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <span>Tüm iddialar onaylanmadan senaryo onayı açılamaz.</span>
              </div>
            )}
          </div>

          {/* Senaryo Onay Kartı */}
          <div className={`${CARD_CLS} space-y-4`}>
            <div>
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Senaryo Nihai Onayı</h4>
                <span className="text-[11px] font-semibold text-zinc-400">Kapı #2</span>
              </div>
              <p className="text-xs text-zinc-500">
                Tüm iddialar doğrulandıktan sonra senaryoyu kilitleyip 24kHz ses sentezine geçebilirsiniz.
              </p>
            </div>

            <button
              type="button"
              onClick={handleApprove}
              disabled={!allClaimsVerified}
              className={`w-full py-2.5 px-4 rounded-xl text-xs font-semibold transition-all duration-200 cursor-pointer flex items-center justify-center gap-2 ${
                script.isApproved
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20'
                  : allClaimsVerified
                  ? 'bg-[#111827] dark:bg-white text-white dark:text-zinc-900 hover:opacity-90 shadow-xs'
                  : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-600 cursor-not-allowed'
              }`}
              data-testid="script-approve-btn"
            >
              {script.isApproved ? '✓ Senaryo Onaylandı' : 'Senaryoyu Onayla'}
            </button>
          </div>

          {/* Kilit Açıklama Bilgisi */}
          {!canAdvance && (
            <div className="p-4 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-950/40 text-zinc-500 text-xs space-y-2">
              <span className="font-semibold text-zinc-700 dark:text-zinc-300 block text-xs">
                İlerleme Koşulları:
              </span>
              <ul className="space-y-1 text-xs">
                <li className={`flex items-center gap-2 ${allClaimsVerified ? 'text-emerald-600 dark:text-emerald-400 font-semibold' : ''}`}>
                  <span>{allClaimsVerified ? '✓' : '○'}</span>
                  <span>Tüm iddiaların ({verifiedCount}/{claims.length}) onaylanması</span>
                </li>
                <li className={`flex items-center gap-2 ${script.isApproved ? 'text-emerald-600 dark:text-emerald-400 font-semibold' : ''}`}>
                  <span>{script.isApproved ? '✓' : '○'}</span>
                  <span>Senaryo Nihai Onay butonuna basılması</span>
                </li>
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Alt Navigasyon ve İlerleme Barı */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-4 border-t border-[#E5E7EB] dark:border-zinc-800">
        <button
          type="button"
          onClick={() => setActiveView('channels')}
          data-testid="script-back-btn"
          className="flex items-center gap-2 px-4 py-2 rounded-xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-300 text-xs font-semibold transition-colors cursor-pointer"
        >
          <svg className="w-4 h-4 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          <span>Kanal Masasına Dön</span>
        </button>

        <div className="flex items-center gap-4">
          {(!allClaimsVerified || !script.isApproved) && (
            <span className="text-xs text-zinc-500 font-medium hidden sm:inline">
              Sese geçildiğinde onaylar otomatik tamamlanır.
            </span>
          )}
          <button
            type="button"
            onClick={handleAdvance}
            disabled={!canAdvance || isLoading}
            className={`px-6 py-2.5 rounded-xl text-xs font-semibold transition-all duration-200 flex items-center gap-2 cursor-pointer ${
              canAdvance && !isLoading
                ? 'bg-[#111827] dark:bg-white text-white dark:text-zinc-900 hover:opacity-90 shadow-xs'
                : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-600 cursor-not-allowed'
            }`}
            data-testid="script-submit-btn"
          >
            {isLoading && (
              <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16 9h5v-.001M3 20v-5m0 0h5m-5 0l3 3a8 8 0 0014-4M4 10a8 8 0 0114-4l3 3m0-5v5" />
              </svg>
            )}
            <span>Sese Geç &amp; Ses Üret →</span>
          </button>
        </div>
      </div>
    </div>
  )
}
