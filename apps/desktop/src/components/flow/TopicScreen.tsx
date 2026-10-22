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
  const isReady = Boolean(topic && topic.trim().length >= 3)

  const handleSearchAndAdvance = async () => {
    if (!isReady || isLoading) return
    await fetchIdeasForTopic()
    try {
      nextStep()
    } catch {
      // Beklenen hata store'a düşer
    }
  }

  const presetMatrix = [
    { category: 'TARİH & ARKEOLOJİ', label: 'Piramitler ve Bilinmeyen Odalar' },
    { category: 'BİLİM & FİZİK', label: 'Kuantum Fiziği ve Zaman Algısı' },
    { category: 'EKONOMİ & GÜÇ', label: 'Tarihin En Zengin 5 Hükümdarı' },
    { category: 'TEKNOLOJİ & SİSTEM', label: 'Yapay Zeka ile Para Kazanma Sırları' },
    { category: 'MÜHENDİSLİK', label: 'Roma Betonu Neden 2000 Yıldır Çökmüyor?' },
    { category: 'ASTROFİZİK', label: 'Kara Delik Olay Ufku ve Zaman Genişlemesi' },
  ]

  return (
    <div className="space-y-md max-w-4xl mx-auto py-xs animate-in fade-in duration-200" data-testid="screen-topic">
      {/* Degraded Mod Bilgi Bandı */}
      {isDegraded && (
        <div
          className="p-sm rounded-lg bg-warning/10 border border-warning/35 text-warning text-xs flex items-center gap-sm animate-pulse font-mono"
          data-testid="degraded-mode-banner"
        >
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
          <div className="flex-1">
            <span className="font-bold">KIRILMAZ KEŞİF HATTI (DEGRADED MOD): </span>
            <span>YouTube çıkarıcısı geçici olarak yanıt vermedi; yerel önbellek ve doğrulanmış viral şablonlar devrede.</span>
          </div>
        </div>
      )}

      {/* Ana Komut Konsolu Modülü */}
      <div className="rounded-lg border border-border/80 bg-surface studio-panel overflow-hidden">
        {/* Modül Üst Telemetri Şeridi */}
        <div className="px-5 py-2.5 bg-zinc-100/60 dark:bg-zinc-900/60 border-b border-border/80 flex flex-wrap items-center justify-between gap-xs font-mono text-[11px]">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-teal-400" />
            <span className="font-medium text-teal-600 dark:text-teal-400 tracking-wide uppercase">STAGE 01 // DISCOVERY ENGINE</span>
            <span className="text-zinc-700">|</span>
            <span className="text-zinc-500">NİŞ & VİRALİTE TARAYICI</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-zinc-200/70 dark:bg-zinc-800/70 text-zinc-600 dark:text-zinc-400">
              HEDEF: TOP 20 ADAY
            </span>
            <span
              className={`px-2 py-0.5 rounded border font-medium ${
                isReady
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                  : 'bg-zinc-200/70 dark:bg-zinc-800/70 text-zinc-500 border-border/80'
              }`}
            >
              {isReady ? 'SİNYAL HAZIR' : 'GİRİŞ BEKLENİYOR'}
            </span>
          </div>
        </div>

        {/* Modül Gövdesi */}
        <div className="p-5 space-y-5">
          {/* Başlık & Açıklama */}
          <div className="space-y-1">
            <h2 className="text-lg sm:text-xl font-semibold text-zinc-900 dark:text-zinc-100 leading-tight">
              Hangi Konuda 9:16 Dikey Video Üretilecek?
            </h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed max-w-2xl">
              Üretim hattını başlatacak anahtar konuyu veya niş başlığını girin. Motor, kanca (hook) gücünü ve etkileşim potansiyelini hesaplayarak en yüksek skorlu 20 video adayını hazırlar.
            </p>
          </div>

          {/* Gömülü Komut Terminali (Recessed Command Input) */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label
                htmlFor="topic-input"
                className="block text-[11px] font-mono font-medium text-zinc-500 dark:text-zinc-400 uppercase"
              >
                KONU VEYA NİŞ PARAMETRESİ
              </label>
              <span className="text-[11px] font-mono text-zinc-500">
                {topic.trim().length} KARAKTER (MİN: 3)
              </span>
            </div>

            <div className="relative">
              <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-teal-500 dark:text-teal-400 font-mono font-medium text-sm select-none">
                &gt;_
              </div>
              <input
                id="topic-input"
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && isReady && !isLoading) {
                    e.preventDefault()
                    handleSearchAndAdvance()
                  }
                }}
                placeholder="Örn: Piramitler ve Bilinmeyen Odalar (Enter ile taramayı başlat)"
                className="w-full pl-10 pr-24 py-3 rounded-md border border-border/80 bg-zinc-100/70 dark:bg-zinc-900/80 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-500 text-sm font-medium transition-colors duration-150 outline-none ring-0 focus:outline-none focus:ring-0 focus:border-teal-400/60"
                data-testid="topic-input"
                autoFocus
              />
              <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-xs">
                <kbd className="hidden sm:inline-block px-2 py-0.5 rounded bg-zinc-200/70 dark:bg-zinc-800/80 text-zinc-500 dark:text-zinc-400 text-[10px] font-mono border border-border/80">
                  ↵ ENTER
                </kbd>
              </div>
            </div>
          </div>

          {/* Kategorize Ön-Ayar Matrisi (Preset Matrix — Sidebar Aktif/Pasif Kontratı) */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono uppercase text-zinc-500 font-medium">
                HIZLI KANAL & KONU ÖN-AYARLARI (TEK TIKLA YÜKLE)
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
              {presetMatrix.map((item) => {
                const isSelectedPreset = topic === item.label
                return (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => setTopic(item.label)}
                    className={`group relative p-2.5 rounded-md border text-left transition-colors cursor-pointer flex flex-col justify-between gap-1 outline-none ring-0 focus:outline-none focus:ring-0 ${
                      isSelectedPreset
                        ? 'bg-zinc-200/80 dark:bg-zinc-800/80 border-border text-zinc-900 dark:text-zinc-100 font-medium'
                        : 'bg-zinc-100/50 dark:bg-zinc-900/40 hover:bg-zinc-200/50 dark:hover:bg-zinc-800/40 border-border/70 text-zinc-500 dark:text-zinc-400'
                    }`}
                  >
                    {isSelectedPreset && (
                      <span
                        className="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-r bg-teal-400"
                        aria-hidden="true"
                      />
                    )}
                    <span className="text-[9px] font-mono font-medium uppercase text-teal-600 dark:text-teal-400">
                      {item.category}
                    </span>
                    <span className="text-xs font-medium text-zinc-900 dark:text-zinc-100 group-hover:text-teal-500 dark:group-hover:text-teal-400 transition-colors line-clamp-1">
                      {item.label}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>

          {errorMessage && (
            <div
              className="p-sm rounded-md bg-destructive/10 border border-destructive/30 text-destructive text-xs font-mono"
              data-testid="topic-error"
            >
              {errorMessage}
            </div>
          )}

          {/* Alt Eylem & Telemetri Çubuğu */}
          <div className="pt-3 border-t border-border/80 flex flex-col sm:flex-row sm:items-center justify-between gap-sm">
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-500 dark:text-zinc-400">
              <span className={`w-2 h-2 rounded-full ${isLoading ? 'bg-teal-400 animate-ping' : isReady ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
              <span>
                {isLoading
                  ? 'Keşif motoru adayları skorluyor...'
                  : isReady
                  ? 'Parametre doğrulandı. Keşif başlatılabilir.'
                  : 'Arama yapmak için en az 3 karakter girin.'}
              </span>
            </div>
            <Button
              variant="primary"
              onClick={handleSearchAndAdvance}
              isLoading={isLoading}
              disabled={!isReady}
              data-testid="topic-submit-btn"
            >
              Fikirleri Ara & Top 20&apos;ye Geç →
            </Button>
          </div>
        </div>
      </div>

      {/* Alt Hat Özeti (Pipeline Signal Flow) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[10px]">
        {[
          { step: '01', title: 'KEŞİF & SKOR', desc: 'Top 20 Viral Aday' },
          { step: '02', title: '3 PERDE SENARYO', desc: 'İddia Doğrulama Kilidi' },
          { step: '03', title: '24kHz TTS SES', desc: 'SHA-256 AudioCache' },
          { step: '04', title: '9:16 MASTER MP4', desc: 'FFmpeg 30fps Render' },
        ].map((info) => (
          <div
            key={info.step}
            className="px-3 py-2 rounded-md border border-border/80 bg-surface flex items-center gap-2.5"
          >
            <span className="text-teal-500 dark:text-teal-400 font-medium text-xs">{info.step}</span>
            <div className="min-w-0">
              <div className="font-medium text-zinc-900 dark:text-zinc-100 truncate">{info.title}</div>
              <div className="text-zinc-500 truncate">{info.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

