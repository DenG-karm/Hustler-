import { useEffect, useRef, useState, type FC, type PointerEvent as ReactPointerEvent, type MouseEvent as ReactMouseEvent } from 'react'
import { toSafeAssetUrl } from '../../lib/securityGuard'
import type { ChannelShortsTemplate, TemplateSlotItem } from './ChannelsScreen'
import { AppIcon } from '../ui/AppIcon'

type AudioMix = NonNullable<ChannelShortsTemplate['audioMix']>

interface ShortsProductionStudioProps {
  template: ChannelShortsTemplate
  channelName?: string
  channelDescription?: string
  voices: { voice_id: string; name: string }[]
  topic: string
  isAnalyzing: boolean
  isSynthesizingVoice?: boolean
  isRendering: boolean
  onTopicChange: (value: string) => void
  onBack: () => void
  onUpdate: (patch: Partial<ChannelShortsTemplate>) => void
  onPickSlotMedia: (slotIdx: number) => void
  onClearSlotMedia: (slotIdx: number) => void
  onAnalyze: (slotCount?: number) => void
  onSynthesizeVoice?: () => void
  onRender: () => void
}

const DEFAULT_MIX: AudioMix = { template: 80, voice: 100, speed: 1 }
const LBL = 'text-[10px] font-mono font-semibold uppercase tracking-wider text-zinc-400'
const BORDER = 'border border-zinc-200 dark:border-zinc-800'
const CARD = `p-3.5 rounded-2xl ${BORDER} bg-white dark:bg-zinc-900 shadow-xs`
const BOX = `p-2 rounded-lg ${BORDER} bg-zinc-50 dark:bg-zinc-800/40`
const INP = `w-full px-3 py-2 rounded-xl bg-white dark:bg-zinc-900 ${BORDER} text-xs text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none transition-colors`
const BTN_SEC = `px-3 py-1.5 rounded-xl text-xs font-medium ${BORDER} text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer inline-flex items-center gap-1.5 transition-colors`
const BTN_SLOT = 'w-11 h-11 rounded-xl border flex flex-col items-center justify-center relative overflow-hidden cursor-pointer shadow-xs'
const CIRC_BTN = 'rounded-full flex items-center justify-center cursor-pointer'
const BTN_PRI = 'py-2 rounded-xl text-xs font-semibold bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 disabled:opacity-50 cursor-pointer transition-opacity'
const MIX_LBL = 'block space-y-1'
const T_BLOCK = 'absolute inset-y-0.5 rounded px-2 flex items-center text-[9px] truncate border'
const fmt = (s: number) => `${~~(s / 60)}:${String(~~(s % 60)).padStart(2, '0')}`
const baseName = (p: string) => p.split(/[\\/]/).pop() || p

const MiniGrid: FC<{ cols: 2 | 3; data: readonly (readonly [string, string])[] }> = ({ cols, data }) => (
  <div className={`grid ${cols === 3 ? 'grid-cols-3' : 'grid-cols-2'} gap-2 pt-1 text-center text-[10px] font-mono`}>
    {data.map(([k, v]) => (
      <div key={k} className={BOX}><span className="text-zinc-400 block text-[8px]">{k}</span><span className="font-bold">{v}</span></div>
    ))}
  </div>
)

const SlotPreview: FC<{
  type: 'image' | 'video'
  path: string
  label: string
  fitMode?: 'cover' | 'contain'
}> = ({ type, path, label, fitMode = 'cover' }) => {
  const u = toSafeAssetUrl(path)
  if (fitMode === 'contain') {
    return (
      <div className="relative w-full h-full overflow-hidden bg-black flex items-center justify-center">
        {type === 'video' ? (
          <video src={u} className="absolute inset-0 w-full h-full object-cover blur-2xl opacity-40 scale-125" autoPlay muted loop playsInline />
        ) : (
          <img src={u} alt="" className="absolute inset-0 w-full h-full object-cover blur-2xl opacity-40 scale-125" />
        )}
        {type === 'video' ? (
          <video src={u} className="relative z-10 max-w-full max-h-full object-contain" autoPlay muted loop playsInline />
        ) : (
          <img src={u} alt={label} className="relative z-10 max-w-full max-h-full object-contain drop-shadow-2xl" />
        )}
      </div>
    )
  }
  return type === 'video' ? (
    <video src={u} className="w-full h-full object-cover" autoPlay muted loop playsInline />
  ) : (
    <img src={u} alt={label} className="w-full h-full object-cover" />
  )
}

export const ShortsProductionStudio: FC<ShortsProductionStudioProps> = ({
  template,
  channelName,
  voices,
  topic,
  isAnalyzing,
  isSynthesizingVoice,
  isRendering,
  onTopicChange,
  onBack,
  onUpdate,
  onPickSlotMedia,
  onClearSlotMedia,
  onAnalyze,
  onSynthesizeVoice,
  onRender,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const voiceRef = useRef<HTMLAudioElement>(null)
  const timelineRef = useRef<HTMLDivElement>(null)
  const [time, setTime] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isLeftPanelOpen, setIsLeftPanelOpen] = useState(true)
  const [panelWidth, setPanelWidth] = useState(380)
  const [activeLeftTab, setActiveLeftTab] = useState<'storyboard' | 'stats'>('storyboard')
  const [isMixerOpen, setIsMixerOpen] = useState(false)
  const [slotCountChoice, setSlotCountChoice] = useState(10)
  const [copiedSlotId, setCopiedSlotId] = useState<string | null>(null)
  const [videoLoadError, setVideoLoadError] = useState(false)
  const isResizingRef = useRef(false)

  const handleVideoLoadedData = () => {
    setVideoLoadError(false)
    if (videoRef.current && videoRef.current.currentTime === 0) {
      videoRef.current.currentTime = 0.05
    }
  }

  const duration = template.durationSec ?? 15
  const slots = template.slots ?? []
  const mix: AudioMix = { ...DEFAULT_MIX, ...template.audioMix }
  const activeIdx = slots.findIndex((s) => time >= s.start_sec && time < s.end_sec)
  const activeSlot = activeIdx >= 0 ? slots[activeIdx] : undefined

  // Dinamik Zaman Damgalı Değişen Altyazı Listesi
  const cues = template.subtitleCues && template.subtitleCues.length > 0
    ? template.subtitleCues
    : [
        { index: 1, start_sec: 0, end_sec: Math.min(4, duration), text: template.narrationScript?.slice(0, 50) || 'Kanca: Dikkat çekici açılış cümlesi.' },
        { index: 2, start_sec: Math.min(4, duration), end_sec: Math.min(11, duration), text: template.narrationScript?.slice(50, 120) || 'Ana Gövde: Bilgi ve görsel dinamizm sekansı.' },
        { index: 3, start_sec: Math.min(11, duration), end_sec: duration, text: template.narrationScript?.slice(120) || 'Kapanış: Etkileşim ve harekete geçirici mesaj (CTA).' },
      ]

  const activeCue = cues.find((c) => time >= c.start_sec && time < c.end_sec)
  const activeSubtitle = activeCue?.text || ''

  useEffect(() => {
    for (const el of [videoRef.current, voiceRef.current]) {
      if (!el) continue
      el.playbackRate = mix.speed
      el.volume = (el === videoRef.current ? mix.template : mix.voice) / 100
    }
  }, [mix.template, mix.voice, mix.speed, template.audioPath])

  const setMix = (patch: Partial<AudioMix>) => onUpdate({ audioMix: { ...mix, ...patch } })

  const seek = (t: number) => {
    const next = Math.min(Math.max(0, t), duration)
    if (videoRef.current) videoRef.current.currentTime = next
    if (voiceRef.current) voiceRef.current.currentTime = next
    setTime(next)
  }

  const togglePlay = () => {
    const v = videoRef.current
    if (!v) return
    if (v.paused) {
      void v.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false))
      void voiceRef.current?.play().catch(() => {})
    } else {
      v.pause()
      voiceRef.current?.pause()
      setIsPlaying(false)
    }
  }

  const onPointerSeek = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.buttons !== 1 || !timelineRef.current) return
    const r = timelineRef.current.getBoundingClientRect()
    seek(((Math.max(0, Math.min(e.clientX - r.left, r.width))) / r.width) * duration)
  }

  const handleResizeStart = (e: ReactMouseEvent) => {
    e.preventDefault()
    isResizingRef.current = true
    const startX = e.clientX
    const startW = panelWidth
    const onMouseMove = (ev: MouseEvent) => {
      if (!isResizingRef.current) return
      const next = Math.max(300, Math.min(680, startW + (ev.clientX - startX)))
      setPanelWidth(next)
    }
    const onMouseUp = () => {
      isResizingRef.current = false
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  const handleCopyPrompt = (slotId: string, promptText: string) => {
    void navigator.clipboard.writeText(promptText)
    setCopiedSlotId(slotId)
    setTimeout(() => setCopiedSlotId(null), 1600)
  }

  const updateSlot = (idx: number, patch: Partial<TemplateSlotItem>) => {
    const nextSlots = [...slots]
    nextSlots[idx] = { ...nextSlots[idx], ...patch }
    onUpdate({ slots: nextSlots })
  }

  const pct = (s: number) => `${(Math.min(s, duration) / duration) * 100}%`
  const slotW = (s: { start_sec: number; end_sec: number }) => ({ left: pct(s.start_sec), width: `calc(${pct(s.end_sec - s.start_sec)} - 2px)` })

  return (
    <div className="fixed inset-0 z-40 flex flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 select-none font-sans antialiased" data-testid="shorts-production-studio">
      {/* Header */}
      <header className={`h-14 shrink-0 flex items-center justify-between gap-4 px-5 border-b ${BORDER} bg-white/95 dark:bg-zinc-950/95 backdrop-blur-md`}>
        <div className="flex items-center gap-2">
          <button type="button" onClick={onBack} className={BTN_SEC}>
            <AppIcon name="left" className="w-3.5 h-3.5" />
            <span>Geri Dön</span>
          </button>
          {!isLeftPanelOpen && (
            <button
              type="button"
              onClick={() => setIsLeftPanelOpen(true)}
              className="p-2 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-300 cursor-pointer flex items-center justify-center shadow-2xs transition-colors"
              title="Paneli Aç"
              aria-label="Paneli Aç"
            >
              <AppIcon name="right" className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
        <div className="min-w-0 text-center">
          <span className={LBL}>Shorts Üretim Stüdyosu</span>
          <h1 className="text-sm font-semibold tracking-tight truncate max-w-xs sm:max-w-md">{template.title}</h1>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => window.dispatchEvent(new CustomEvent('hustler:toggle-ai'))} className={BTN_SEC} title="AI Chat">
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-900 dark:bg-zinc-100 animate-pulse" />
            <span>AI Chat</span>
          </button>
          <button type="button" disabled={isRendering} onClick={onRender} className={`${BTN_PRI} px-4 !py-1.5 shadow-xs`}>
            {isRendering ? 'Derleniyor...' : 'Dışa Aktar'}
          </button>
        </div>
      </header>

      <div className="flex-1 min-h-0 flex relative overflow-hidden">
        {/* SOL BÜYÜTÜLEBİLİR PANEL */}
        {isLeftPanelOpen && (
          <aside
            style={{ width: `${panelWidth}px` }}
            className={`relative shrink-0 border-r ${BORDER} p-4 overflow-y-auto space-y-4 bg-zinc-50/70 dark:bg-zinc-900/40 select-none scrollbar-thin`}
          >
            {/* Sürükleme / Boyutlandırma Tutamacı */}
            <div
              onMouseDown={handleResizeStart}
              className="absolute top-0 right-0 bottom-0 w-2 cursor-col-resize hover:bg-cyan-500/30 transition-colors z-20 flex items-center justify-center group"
              title="Genişlet / Daralt"
            >
              <span className="w-0.5 h-8 rounded-full bg-zinc-300 dark:bg-zinc-700 group-hover:bg-cyan-500 transition-colors" />
            </div>

            <div className="flex items-center gap-1.5">
              <div className={`flex-1 p-1 rounded-xl bg-zinc-200/60 dark:bg-zinc-800/60 ${BORDER} flex items-center gap-1`}>
                {(['storyboard', 'stats'] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setActiveLeftTab(t)}
                    className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-medium cursor-pointer text-center inline-flex items-center justify-center gap-1 ${
                      activeLeftTab === t ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-2xs font-semibold' : 'text-zinc-500'
                    }`}
                  >
                    {t === 'stats' && <AppIcon name="chart" className="w-3.5 h-3.5" />}
                    <span>{t === 'storyboard' ? 'Kurgu & Storyboard' : 'Şablon İstatistiği'}</span>
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => setIsLeftPanelOpen(false)}
                className="w-8 h-8 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center justify-center text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 cursor-pointer shrink-0 shadow-2xs transition-colors"
                title="Paneli Gizle"
                aria-label="Paneli Gizle"
              >
                <AppIcon name="left" className="w-3.5 h-3.5" />
              </button>
            </div>

            {activeLeftTab === 'storyboard' ? (
              <div className="space-y-4">
                {/* 1. ŞABLON MATEMATİĞİ & HEDEF KİTLE KARTI */}
                <div className={`${CARD} space-y-2.5`}>
                  <div className="flex items-center justify-between">
                    <span className={LBL}>Şablon Matematiği &amp; Kitle</span>
                    <span className="text-[10px] font-mono text-cyan-600 dark:text-cyan-400 font-bold">9:16 Dikey</span>
                  </div>
                  <MiniGrid
                    cols={3}
                    data={[
                      ['SÜRE', `${duration}s`],
                      ['SLOT', `${slots.length} Sahne`],
                      ['TEMPO', `~${(duration / Math.max(1, slots.length)).toFixed(1)}s`],
                    ]}
                  />
                  <div className="space-y-1 text-[11px] font-sans">
                    <div className={BOX}>
                      <span className="text-zinc-400 block text-[9px] font-mono uppercase">Hedef Kitle</span>
                      <span className="font-medium text-zinc-800 dark:text-zinc-200">
                        {template.targetAudience || (channelName ? `${channelName} Takipçileri & Nitelikli Shorts İzleyicisi` : 'Yüksek Bilgi Yoğunluğu Bekleyen Shorts İzleyicileri')}
                      </span>
                    </div>
                    <div className={BOX}>
                      <span className="text-zinc-400 block text-[9px] font-mono uppercase">Viral Kurgu Modeli</span>
                      <span className="font-mono text-[10px] text-zinc-700 dark:text-zinc-300">
                        {template.viralFormula || 'Kanca (Hook) → Problem → Mikro Kanıtlar → Çözüm & CTA'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 2. KONU & AI KURGU ÜRETİM GİRİŞİ */}
                <div className={`${CARD} space-y-3`}>
                  <div className="flex items-center justify-between">
                    <span className={LBL}>Viral Kurgu Konusu</span>
                    <div className="flex items-center gap-1 font-mono text-[10px]">
                      {[8, 10, 12].map((cnt) => (
                        <button
                          key={cnt}
                          type="button"
                          onClick={() => setSlotCountChoice(cnt)}
                          className={`px-1.5 py-0.5 rounded cursor-pointer ${
                            slotCountChoice === cnt ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 font-bold' : 'text-zinc-400 hover:text-zinc-600'
                          }`}
                        >
                          {cnt}S
                        </button>
                      ))}
                    </div>
                  </div>
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => onTopicChange(e.target.value)}
                    placeholder="Örn: 99%'ın Yanlış Bildiği Kritik Denklem..."
                    className={INP}
                  />
                  <button
                    type="button"
                    disabled={isAnalyzing}
                    onClick={() => onAnalyze(slotCountChoice)}
                    className={`w-full ${BTN_PRI}`}
                  >
                    {isAnalyzing ? 'Kurgu & Promptlar Çıkarılıyor...' : 'AI Kurgu, Prompt & Altyazı Oluştur'}
                  </button>
                </div>

                {/* 3. ELEVENLABS SESLENDİRME & ALTYAZI ALANI */}
                <div className={`${CARD} space-y-3`}>
                  <div className="flex items-center justify-between">
                    <span className={LBL}>ElevenLabs Seslendirme</span>
                    {template.audioPath && (
                      <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[10px] font-mono font-bold border border-emerald-500/20">
                        Ses Hazır (wav)
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-[1fr_auto] gap-2 items-center">
                    <select
                      value={template.voiceId || voices[0]?.voice_id}
                      onChange={(e) => onUpdate({ voiceId: e.target.value })}
                      className={INP}
                    >
                      {voices.map((v) => (
                        <option key={v.voice_id} value={v.voice_id}>{v.name}</option>
                      ))}
                    </select>
                    {onSynthesizeVoice && (
                      <button
                        type="button"
                        disabled={isSynthesizingVoice}
                        onClick={onSynthesizeVoice}
                        className={`${BTN_SEC} bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 border-transparent hover:opacity-90`}
                        title="ElevenLabs ile Okut"
                      >
                        {isSynthesizingVoice ? 'Okunuyor...' : 'Seslendir'}
                      </button>
                    )}
                  </div>
                  <div className="space-y-1.5">
                    <span className={LBL}>Tam Seslendirme Metni</span>
                    <textarea
                      rows={3}
                      value={template.narrationScript || ''}
                      onChange={(e) => onUpdate({ narrationScript: e.target.value })}
                      placeholder="Seslendirilecek tam senaryo metni..."
                      className={`${INP} resize-y text-xs leading-relaxed`}
                    />
                  </div>
                </div>

                {/* 4. SAHNELİK STORYBOARD: KURGU DİREKTİFLERİ & GÖRSEL PROMPTLARI LİSTESİ */}
                <div className={`${CARD} space-y-3`}>
                  <div className="flex items-center justify-between">
                    <span className={LBL}>Kurgu &amp; Görsel Direktifleri ({slots.length})</span>
                    <span className="text-[10px] font-mono text-cyan-600 dark:text-cyan-400 font-bold">Zaman Kurgusu</span>
                  </div>

                  <div className="space-y-2.5 max-h-[460px] overflow-y-auto pr-1">
                    {slots.map((slot, idx) => {
                      const isCur = activeIdx === idx
                      return (
                        <div
                          key={slot.slot_id || idx}
                          onClick={() => seek(slot.start_sec)}
                          className={`p-3 rounded-xl border transition-all cursor-pointer space-y-2 ${
                            isCur
                              ? 'border-cyan-500 bg-cyan-50/15 dark:bg-cyan-950/20 shadow-xs ring-1 ring-cyan-500/30'
                              : 'border-zinc-200 dark:border-zinc-800 bg-zinc-50/40 dark:bg-zinc-850/40 hover:border-zinc-300 dark:hover:border-zinc-700'
                          }`}
                        >
                          {/* Slot Başlık Satırı */}
                          <div className="flex items-center justify-between text-[10px] font-mono">
                            <span className={`font-bold ${isCur ? 'text-cyan-600 dark:text-cyan-400' : 'text-zinc-800 dark:text-zinc-200'}`}>
                              {slot.label}
                            </span>
                            <div className="flex items-center gap-1.5">
                              <span className="text-zinc-400 font-mono">
                                {slot.start_sec}s - {slot.end_sec}s
                              </span>
                              {isCur && (
                                <span className="px-1.5 py-0.2 rounded bg-cyan-500 text-white text-[9px] font-bold">Şimdi</span>
                              )}
                            </div>
                          </div>

                          {/* Reji Direktifi */}
                          <div className="text-[10.5px] text-zinc-600 dark:text-zinc-300 leading-relaxed bg-black/5 dark:bg-white/5 p-2 rounded-lg">
                            <strong className="text-zinc-900 dark:text-zinc-100 font-semibold block text-[9px] font-mono uppercase mb-0.5">
                              Reji Direktifi:
                            </strong>
                            {slot.directive || 'Dikey 9:16 yakın plan, dinamik yaklaşma, yüksek kontrast, hızlı kesme.'}
                          </div>

                          {/* AI Görsel Üretim Promptu (Midjourney / Flux) */}
                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-[9px] font-mono">
                              <span className="text-cyan-600 dark:text-cyan-400 font-semibold uppercase">Görsel / Video Promptu</span>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleCopyPrompt(slot.slot_id, slot.prompt || '')
                                }}
                                className="cursor-pointer text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 flex items-center gap-1 font-semibold"
                                title="Promptu Kopyala"
                              >
                                <AppIcon name={copiedSlotId === slot.slot_id ? 'check' : 'copy'} className="w-3 h-3 text-cyan-500" />
                                <span>{copiedSlotId === slot.slot_id ? 'Kopyalandı' : 'Kopyala'}</span>
                              </button>
                            </div>
                            <textarea
                              rows={2}
                              value={slot.prompt || ''}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) => updateSlot(idx, { prompt: e.target.value })}
                              placeholder="Midjourney / Flux promptu..."
                              className="w-full text-[10px] font-mono bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg p-1.5 text-zinc-800 dark:text-zinc-200 resize-none focus:outline-none"
                            />
                          </div>

                          {/* Medya Yerleştirme Durumu */}
                          <div className="flex items-center justify-between pt-1 border-t border-zinc-100 dark:border-zinc-800/80">
                            <div className="flex items-center gap-2 min-w-0">
                              {slot.media_path ? (
                                <>
                                  <div className="w-7 h-7 rounded overflow-hidden shrink-0 border border-zinc-300 dark:border-zinc-700">
                                    <SlotPreview type={slot.media_type} path={slot.media_path} label={slot.label} />
                                  </div>
                                  <span className="text-[10px] font-mono text-zinc-500 truncate max-w-[130px]">
                                    {baseName(slot.media_path)}
                                  </span>
                                </>
                              ) : (
                                <span className="text-[10px] font-mono text-amber-600 dark:text-amber-400">
                                  ● Görsel bekleniyor
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              {slot.media_path && (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    updateSlot(idx, { fitMode: slot.fitMode === 'contain' ? 'cover' : 'contain' })
                                  }}
                                  className="px-1.5 py-1 rounded-lg text-[9px] font-mono border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-300 cursor-pointer"
                                  title="En-boy oranını koru (bulanık fon) veya 9:16 ekrana tam doldur"
                                >
                                  {slot.fitMode === 'contain' ? 'Sığdır' : 'Dolgu'}
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  onPickSlotMedia(idx)
                                }}
                                className="px-2 py-1 rounded-lg text-[10px] font-medium border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer"
                              >
                                {slot.media_path ? 'Değiştir' : 'Görsel Yükle'}
                              </button>
                              {slot.media_path && (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    onClearSlotMedia(idx)
                                  }}
                                  className="w-6 h-6 rounded-lg text-zinc-400 hover:text-red-500 flex items-center justify-center cursor-pointer"
                                  title="Kaldır"
                                >
                                  <AppIcon name="close" className="w-3 h-3" />
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-4 text-xs">
                {/* 1. İzlenme Trendi Çizgi Grafiği */}
                <div className={`${CARD} space-y-3`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <span className={LBL}>İzlenme Trendi</span>
                      <h4 className="text-xs font-bold text-zinc-900 dark:text-zinc-100">Son 5 Video</h4>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">+48.5%</span>
                  </div>
                  <div className="relative pt-1">
                    <svg className="w-full h-16 overflow-visible" viewBox="0 0 240 50">
                      <polyline fill="none" stroke="currentColor" strokeWidth="2" className="text-cyan-500" points="10,40 65,28 120,32 175,12 230,15" />
                      {([[10, 40, '45K'], [65, 28, '120K'], [120, 32, '95K'], [175, 12, '210K'], [230, 15, '180K']] as const).map(([x, y, txt]) => (
                        <g key={x}>
                          <circle cx={x} cy={y} r="3" fill="currentColor" className="text-zinc-900 dark:text-zinc-100" />
                          <text x={x} y={y - 5} textAnchor="middle" className="text-[8px] font-mono font-bold fill-zinc-500">{txt}</text>
                        </g>
                      ))}
                    </svg>
                  </div>
                  <div className="flex justify-between text-[9px] font-mono text-zinc-400 border-t border-zinc-100 dark:border-zinc-800 pt-1">
                    {'V1 V2 V3 V4 V5'.split(' ').map((v) => <span key={v}>{v}</span>)}
                  </div>
                </div>

                {/* 2. Beğenme & Kalite Kıyaslaması */}
                <div className={`${CARD} space-y-3`}>
                  <span className={LBL}>Beğenme &amp; Kalite</span>
                  <div className="grid grid-cols-2 gap-2 text-center font-mono">
                    <div className={BOX}><span className="text-[9px] text-zinc-400 block">BEĞENİ</span><span className="text-sm font-bold">97.4%</span></div>
                    <div className={BOX}><span className="text-[9px] text-zinc-400 block">KALİTE</span><span className="text-sm font-bold">94 / 100</span></div>
                  </div>
                  <div className="space-y-1.5 pt-1 border-t border-zinc-100 dark:border-zinc-800">
                    {[
                      ['0-3s Kanca', 84, 'text-emerald-600 dark:text-emerald-400', 'bg-emerald-500'],
                      ['3-11s Gövde', 72, 'text-cyan-600 dark:text-cyan-400', 'bg-cyan-500'],
                      ['11-15s Kapanış', 65, 'text-blue-600 dark:text-blue-400', 'bg-blue-600'],
                    ].map(([lbl, val, cls, bg]) => (
                      <div key={lbl as string} className="space-y-0.5">
                        <div className="flex justify-between text-[10px] font-mono">
                          <span className="text-zinc-500">{lbl as string}</span>
                          <span className={`font-bold ${cls as string}`}>%{val as number}</span>
                        </div>
                        <div className="w-full h-1 rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
                          <div className={`h-full ${bg as string}`} style={{ width: `${val as number}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 3. Slot Ritim Dağılımı */}
                <div className={`${CARD} space-y-2`}>
                  <span className={LBL}>Slot Ritim Dağılımı ({slots.length})</span>
                  <div className="space-y-1">
                    {slots.map((s, idx) => (
                      <div key={s.slot_id} className={`flex items-center justify-between p-1.5 rounded-lg border ${BORDER} text-[11px]`}>
                        <span className="font-medium truncate">{idx + 1}. {s.label}</span>
                        <div className="flex items-center gap-1.5 font-mono text-[10px] shrink-0">
                          <span className="text-zinc-400">{s.start_sec}-{s.end_sec}s</span>
                          <span className={`px-1 py-0.2 rounded text-[9px] font-semibold ${s.media_path ? 'bg-emerald-500/10 text-emerald-600' : 'bg-amber-500/10 text-amber-600'}`}>
                            {s.media_path ? 'Dolu' : 'Boş'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 4. AI Şablon Değerlendirmesi */}
                <div className={`${CARD} space-y-2`}>
                  <div className="flex items-center gap-1.5">
                    <AppIcon name="spark" className="w-3.5 h-3.5" />
                    <span className={LBL}>AI Şablon Değerlendirmesi</span>
                  </div>
                  <div className="text-[11px] text-zinc-600 dark:text-zinc-400 space-y-1.5 leading-relaxed">
                    <p className={BOX}><strong className="text-zinc-900 dark:text-zinc-100 font-semibold">Güçlü:</strong> 0-3s kanca ritmi yüksek tutunma sağlıyor. Hızlı görsel geçişler CTR çarpanını destekliyor.</p>
                    <p className={BOX}><strong className="text-zinc-900 dark:text-zinc-100 font-semibold">Gelişim:</strong> 10-12s aralığında hafif tempo düşüşü mevcut. Hareketli B-roll tercih edilmeli.</p>
                  </div>
                </div>
              </div>
            )}
          </aside>
        )}

        {/* ORTA ÇALIŞMA ALANI */}
        <main className="flex-1 min-w-0 flex flex-col bg-white dark:bg-zinc-950 overflow-hidden">
          {/* Live Yüzey: Sol Dikey Slotlar + Canvas + Studio Çizgili Arka Plan */}
          <section className="flex-1 min-h-0 flex flex-col items-center justify-center p-4 bg-zinc-50/60 dark:bg-zinc-950 studio-grid-lines relative overflow-hidden">
            <div className="flex-1 min-h-0 flex items-center justify-center gap-4 max-w-full">
              {/* Dikey Medya Slotları */}
              <div className="flex flex-col gap-2 items-center justify-center py-2 shrink-0 z-10 max-h-[80vh] overflow-y-auto scrollbar-none">
                {slots.map((slot, idx) => {
                  const isActive = activeIdx === idx
                  return (
                    <div key={slot.slot_id} className="relative group flex flex-col items-center gap-0.5">
                      <button
                        type="button"
                        onClick={() => {
                          seek(slot.start_sec)
                          onPickSlotMedia(idx)
                        }}
                        className={`${BTN_SLOT} ${
                          isActive
                            ? 'ring-2 ring-zinc-900 dark:ring-white scale-105 border-zinc-900 dark:border-white shadow-md bg-black'
                            : slot.media_path
                            ? 'border-zinc-800 dark:border-zinc-300 bg-black opacity-90 hover:opacity-100'
                            : `border-dashed ${BORDER} hover:border-zinc-900 dark:hover:border-zinc-100 bg-white/90 dark:bg-zinc-900/90`
                        }`}
                        title={`Slot #${idx + 1}: ${slot.label} (${slot.start_sec}s - ${slot.end_sec}s)`}
                      >
                        {slot.media_path ? (
                          <SlotPreview type={slot.media_type} path={slot.media_path} label={slot.label} />
                        ) : (
                          <AppIcon name="plus" className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-zinc-500'} group-hover:text-zinc-900 dark:group-hover:text-zinc-100`} />
                        )}
                      </button>
                      <span className={`text-[8.5px] font-mono ${isActive ? 'text-zinc-900 dark:text-zinc-100 font-bold' : 'text-zinc-400'}`}>
                        {slot.start_sec}s
                      </span>
                      {slot.media_path && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            onClearSlotMedia(idx)
                          }}
                          className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-zinc-900 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer shadow-xs"
                          title="Görseli Kaldır"
                        >
                          <AppIcon name="close" className="w-2.5 h-2.5" />
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* 9:16 Video Canvası */}
              <div className={`relative h-full ${isMixerOpen ? 'max-h-[calc(100vh-19rem)]' : 'max-h-[calc(100vh-13rem)]'} aspect-[9/16] rounded-2xl overflow-hidden bg-black shadow-2xl ${BORDER} flex items-center justify-center transition-all duration-200`}>
                <video
                  ref={videoRef}
                  src={toSafeAssetUrl(template.filePath)}
                  className="w-full h-full object-cover"
                  playsInline
                  loop
                  onClick={togglePlay}
                  onLoadedData={handleVideoLoadedData}
                  onLoadedMetadata={handleVideoLoadedData}
                  onTimeUpdate={(e) => {
                    const t = e.currentTarget.currentTime
                    if (t >= duration) seek(0)
                    else setTime(t)
                  }}
                  onPause={() => setIsPlaying(false)}
                  onError={() => setVideoLoadError(true)}
                />
                {template.audioPath && <audio ref={voiceRef} src={toSafeAssetUrl(template.audioPath)} preload="auto" />}

                {/* Video yüklenemezse veya yerel dosya yolu doğrudan çözümlenemezse gösterilecek zengin canlı yüzey */}
                {videoLoadError && (
                  <div className="absolute inset-0 bg-gradient-to-b from-zinc-900 via-zinc-950 to-black flex flex-col items-center justify-center p-6 text-center select-none z-0">
                    <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 mb-2 shadow-lg">
                      <AppIcon name="film" className="w-6 h-6" />
                    </div>
                    <h3 className="text-sm font-bold text-white tracking-tight">{template.title}</h3>
                    <p className="text-[10px] font-mono text-zinc-400 mt-0.5 max-w-[200px] truncate">{baseName(template.filePath)}</p>
                    <span className="mt-2.5 px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 text-[10px] font-mono font-bold border border-cyan-500/20">
                      {duration}s 9:16 Shorts Şablonu
                    </span>
                    <p className="text-[10px] text-zinc-500 mt-3 max-w-[200px] leading-relaxed">
                      Şablon aktif. Aşağıdaki zaman çizelgesi ve soldaki slotlarla kurguyu canlı yönetebilirsiniz.
                    </p>
                  </div>
                )}

                {/* Eğer aktif slotta kullanıcı medyası varsa tam ekran (9:16) önizleme göster */}
                {activeSlot?.media_path && (
                  <div className="absolute inset-0 w-full h-full overflow-hidden pointer-events-none z-10">
                    <SlotPreview
                      type={activeSlot.media_type}
                      path={activeSlot.media_path}
                      label={activeSlot.label}
                      fitMode={activeSlot.fitMode || 'cover'}
                    />
                    <div className="absolute top-3 left-3 right-3 flex items-center justify-between pointer-events-auto">
                      <span className="px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-xs text-[10px] font-mono font-bold text-white border border-white/20 shadow-xs">
                        {activeSlot.label} ({activeSlot.start_sec}-{activeSlot.end_sec}s)
                      </span>
                      <button
                        type="button"
                        onClick={() => updateSlot(activeIdx, { fitMode: activeSlot.fitMode === 'contain' ? 'cover' : 'contain' })}
                        className="px-2 py-0.5 rounded-md bg-black/80 hover:bg-black text-[9px] font-mono font-semibold text-cyan-300 border border-cyan-500/30 cursor-pointer shadow-xs"
                        title="En-boy oranını koru (bulanık fon) veya 9:16 ekrana tam doldur"
                      >
                        {activeSlot.fitMode === 'contain' ? 'Sığdır (Blur)' : '9:16 Dolgu'}
                      </button>
                    </div>
                  </div>
                )}

                {/* EĞER AKTİF SLOTTA MEDYA YOKSA: CANVASA REJİ DİREKTİFİ & PROMPT KARTINI CANLI GÖSTER */}
                {activeSlot && !activeSlot.media_path && (
                  <div className="absolute inset-x-3 top-8 bottom-24 rounded-xl border border-cyan-500/30 bg-zinc-950/80 backdrop-blur-md p-3.5 flex flex-col justify-between text-left shadow-2xl pointer-events-auto">
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400 font-mono text-[9px] font-bold border border-cyan-500/30">
                          REJİ DİREKTİFİ • {activeSlot.start_sec}s - {activeSlot.end_sec}s
                        </span>
                        <span className="text-[9px] font-mono text-zinc-400 font-semibold">{activeSlot.media_type.toUpperCase()}</span>
                      </div>
                      <h4 className="text-xs font-bold text-white tracking-tight">{activeSlot.label}</h4>
                      <p className="text-[10px] text-zinc-300 leading-relaxed">
                        {activeSlot.directive || 'Dikey 9:16 yakın plan, dinamik yaklaşma, hızlı kesme.'}
                      </p>
                    </div>

                    <div className="p-2 rounded-lg bg-black/70 border border-white/10 space-y-1 my-1">
                      <div className="flex items-center justify-between text-[8px] font-mono text-cyan-300 font-bold uppercase">
                        <span>AI Görsel Promptu</span>
                        <button
                          type="button"
                          onClick={() => handleCopyPrompt(activeSlot.slot_id, activeSlot.prompt || '')}
                          className="cursor-pointer text-white hover:text-cyan-400 flex items-center gap-1"
                        >
                          <AppIcon name={copiedSlotId === activeSlot.slot_id ? 'check' : 'copy'} className="w-2.5 h-2.5 text-cyan-400" />
                          <span>{copiedSlotId === activeSlot.slot_id ? 'Kopyalandı' : 'Kopyala'}</span>
                        </button>
                      </div>
                      <p className="text-[9px] text-zinc-300 font-mono line-clamp-3 select-all leading-snug">
                        {activeSlot.prompt || 'Cinematic 9:16 vertical shot, dramatic lighting --ar 9:16'}
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => onPickSlotMedia(activeIdx)}
                      className="w-full py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black text-[10px] font-bold cursor-pointer transition-colors text-center inline-flex items-center justify-center gap-1 shadow-xs"
                    >
                      <AppIcon name="plus" className="w-3 h-3" />
                      <span>Bu Sahne İçin Görsel / Video Yükle</span>
                    </button>
                  </div>
                )}

                {/* Dinamik Değişen Video İçi Altyazı */}
                {activeSubtitle && (
                  <div className="absolute inset-x-3 bottom-5 px-3 py-2 rounded-xl bg-black/85 border border-white/10 text-center pointer-events-none transition-all duration-150 z-20">
                    <span className="text-[9px] font-mono font-bold text-cyan-400 block uppercase mb-0.5">
                      {activeCue ? `${activeCue.start_sec}s - ${activeCue.end_sec}s` : 'Altyazı'}
                    </span>
                    <p className="text-xs font-semibold tracking-tight text-white leading-snug line-clamp-3">
                      {activeSubtitle}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Kontrol Butonları */}
            <div className="flex items-center gap-4 mt-2 shrink-0">
              <button type="button" onClick={() => seek(0)} className={`w-8 h-8 text-zinc-500 hover:text-zinc-900 dark:hover:text-white ${CIRC_BTN}`} aria-label="Başa sar">
                <AppIcon name="rewind" className="w-4 h-4" />
              </button>
              <button type="button" onClick={togglePlay} className={`w-10 h-10 bg-zinc-900 hover:bg-zinc-800 text-white dark:bg-white dark:text-zinc-900 font-bold shadow-xs ${CIRC_BTN}`} aria-label={isPlaying ? 'Duraklat' : 'Oynat'}>
                <AppIcon name={isPlaying ? 'pause' : 'play'} className="w-4 h-4" />
              </button>
              <span className="text-xs font-mono font-medium text-zinc-600 dark:text-zinc-400 w-24 text-center">{fmt(time)} / {fmt(duration)}</span>
            </div>
          </section>

          {/* GENİŞLETİLMİŞ ZAMAN ÇİZELGESİ ALANI */}
          <section className={`shrink-0 border-t ${BORDER} bg-white dark:bg-zinc-950 px-6 py-2.5 space-y-2.5`}>
            {/* Üst Çubuk: Durum & Ses Ayarları Butonu */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className={LBL}>Zaman Çizelgesi &amp; Medya Kanalları</span>
                <span className="text-[10px] font-mono text-zinc-400 font-semibold">{duration}s Toplam Süre</span>
              </div>
              <button
                type="button"
                onClick={() => setIsMixerOpen(!isMixerOpen)}
                className={`${BTN_SEC} ${isMixerOpen ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900' : ''}`}
                title="Ses Mikseri Ayarları"
              >
                <AppIcon name="settings" className="w-3.5 h-3.5" />
                <span>{isMixerOpen ? 'Mikseri Kapat' : 'Ses Mikseri'}</span>
              </button>
            </div>

            {/* Zaman Çizelgesi Kanalları */}
            <div
              ref={timelineRef}
              onPointerDown={onPointerSeek}
              onPointerMove={onPointerSeek}
              className="grid grid-cols-[56px_1fr] gap-x-3 gap-y-1.5 items-center cursor-pointer select-none touch-none"
            >
              <span />
              <div className="relative h-3 select-none">
                {Array.from({ length: Math.floor(duration / 5) + 1 }, (_, i) => i * 5).map((s) => (
                  <span key={s} className="absolute top-0 text-[8px] font-mono text-zinc-400 -translate-x-1/2" style={{ left: pct(s) }}>
                    {s}s
                  </span>
                ))}
              </div>
              {(['Medya', 'Altyazı', 'Ses'] as const).map((track) => (
                <div key={track} className="contents">
                  <span className="text-[10px] font-mono font-medium text-zinc-400 text-right">{track}</span>
                  <div className={`relative h-7 rounded-lg bg-zinc-100 dark:bg-zinc-900 ${BORDER} overflow-hidden`}>
                    {track === 'Medya' ? (
                      slots.map((s, idx) => (
                        <div
                          key={s.slot_id}
                          style={slotW(s)}
                          className={`${T_BLOCK} font-mono ${
                            s.media_path
                              ? 'bg-zinc-800 text-white dark:bg-zinc-200 dark:text-zinc-900 border-zinc-700'
                              : 'bg-zinc-200/60 dark:bg-zinc-800/60 border-dashed text-zinc-500'
                          } ${idx === activeIdx ? 'ring-2 ring-zinc-900 dark:ring-white' : ''}`}
                        >
                          {s.media_path ? baseName(s.media_path) : s.label}
                        </div>
                      ))
                    ) : track === 'Altyazı' ? (
                      cues.map((c, idx) => (
                        <div
                          key={c.index || idx}
                          style={{ left: pct(c.start_sec), width: `calc(${pct(c.end_sec - c.start_sec)} - 2px)` }}
                          className={`${T_BLOCK} font-sans font-medium text-[9.5px] truncate border ${
                            activeCue?.index === c.index
                              ? 'bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 border-cyan-500/40 ring-1 ring-cyan-500'
                              : 'bg-zinc-200/90 dark:bg-zinc-800/90 text-zinc-700 dark:text-zinc-300 border-zinc-300 dark:border-zinc-700'
                          }`}
                        >
                          {c.text}
                        </div>
                      ))
                    ) : template.audioPath ? (
                      <div className="absolute inset-y-0.5 inset-x-0 rounded bg-zinc-300 dark:bg-zinc-700 border border-zinc-400" />
                    ) : (
                      <div className="absolute inset-0 flex items-center px-2 text-[9px] font-mono text-zinc-400">Ses henüz eklenmedi</div>
                    )}
                    <div className="absolute inset-y-0 w-0.5 bg-zinc-900 dark:bg-white pointer-events-none" style={{ left: pct(time) }} />
                  </div>
                </div>
              ))}
            </div>

            {/* Ses Mikseri Çekmecesi */}
            {isMixerOpen && (
              <div className={`p-3 rounded-xl ${BORDER} bg-zinc-50 dark:bg-zinc-900/60 grid grid-cols-1 md:grid-cols-4 gap-4 items-end animate-in fade-in duration-150`}>
                {([
                  ['Şablon Sesi', `%${mix.template}`, 0, 100, 1, mix.template, (v: number) => setMix({ template: v })],
                  ['Seslendirme', `%${mix.voice}`, 0, 100, 1, mix.voice, (v: number) => setMix({ voice: v })],
                  ['Oynatma Hızı', `${mix.speed.toFixed(2)}x`, 0.5, 2, 0.05, mix.speed, (v: number) => setMix({ speed: v })],
                ] as const).map(([l, v, min, max, step, val, fn]) => (
                  <label key={l} className={MIX_LBL}>
                    <div className="flex items-center justify-between"><span className={LBL}>{l}</span><span className="text-[10px] font-mono font-bold text-zinc-800 dark:text-zinc-200">{v}</span></div>
                    <input type="range" min={min} max={max} step={step} value={val} onChange={(e) => fn(Number(e.target.value))} className="w-full h-1.5 accent-zinc-900 dark:accent-zinc-100 cursor-pointer" />
                  </label>
                ))}
                <label className={MIX_LBL}>
                  <span className={LBL}>Ses Karakteri</span>
                  <select value={template.voiceId || voices[0]?.voice_id} onChange={(e) => onUpdate({ voiceId: e.target.value })} className={INP}>
                    {voices.map((v) => <option key={v.voice_id} value={v.voice_id}>{v.name}</option>)}
                  </select>
                </label>
              </div>
            )}
          </section>
        </main>
      </div>
    </div>
  )
}
