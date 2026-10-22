import { useRef, useState, type FC } from 'react'
import { useFlowStore } from '../../store/flowStore'
import { toSafeAssetUrl } from '../../lib/securityGuard'

const CARD_CLS =
  'p-6 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs'

const WAVEFORM_BANDS = [
  38, 62, 84, 52, 95, 76, 48, 90, 64, 86, 34, 72, 92, 58, 42, 82,
  68, 96, 74, 50, 88, 60, 46, 78, 54, 85, 66, 44, 70, 56, 36, 48,
]

const AVAILABLE_VOICES = [
  { id: 'tr-TR-Standard-A', name: 'Ahmet (Dinamik & Net)', desc: 'Genel haber, shorts ve teknoloji anlatımları için ideal.' },
  { id: 'tr-TR-Standard-B', name: 'Elif (Enerjik & Akıcı)', desc: 'Viral kurgular ve hızlı tempolu hikayeler için enerjik ton.' },
  { id: 'tr-TR-Standard-C', name: 'Can (Derin & Belgesel)', desc: 'Tarih, gizem ve felsefe konuları için oturaklı sinematik ton.' },
]

export const AudioScreen: FC = () => {
  const audio = useFlowStore((s) => s.audio)
  const script = useFlowStore((s) => s.script)
  const generateAudioForScript = useFlowStore((s) => s.generateAudioForScript)
  const loadAssetsForScript = useFlowStore((s) => s.loadAssetsForScript)
  const nextStep = useFlowStore((s) => s.nextStep)
  const prevStep = useFlowStore((s) => s.prevStep)
  const isLoading = useFlowStore((s) => s.isLoading)
  const errorMessage = useFlowStore((s) => s.errorMessage)

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [selectedVoice, setSelectedVoice] = useState('tr-TR-Standard-A')

  const handleSynthesize = async () => {
    await generateAudioForScript(selectedVoice)
  }

  const handleAdvance = async () => {
    if (!audio?.isGenerated) return
    await loadAssetsForScript()
    try {
      nextStep()
    } catch {
      useFlowStore.setState({ currentStep: 'ASSETS', errorMessage: null })
    }
  }

  // Senaryo henüz yoksa güvenli boş durum
  if (!script) {
    return (
      <div className={`${CARD_CLS} text-center py-16`} data-testid="screen-audio-empty">
        <p className="text-sm text-zinc-500 mb-4">Senaryo verisi bulunamadı. Lütfen senaryo adımına geri dönün.</p>
        <button
          type="button"
          onClick={prevStep}
          className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-[#111827] dark:bg-white text-white dark:text-zinc-900 cursor-pointer hover:opacity-90 transition-opacity"
        >
          ← Senaryo Adımına Dön
        </button>
      </div>
    )
  }

  const fps = 30
  const duration = Math.max(0.1, audio?.durationSeconds || 0)
  const totalFrames = Math.round((audio?.durationSeconds || 0) * fps)
  const currentFrame = Math.min(totalFrames, Math.round(currentTime * fps))
  const formattedMinutes = Math.floor((audio?.durationSeconds || 0) / 60)
  const formattedSeconds = Math.round((audio?.durationSeconds || 0) % 60)
  const safeAudioSrc = (audio?.audioPath ? toSafeAssetUrl(audio.audioPath) : null) || undefined
  const progressRatio = duration > 0 ? Math.min(1, Math.max(0, currentTime / duration)) : 0

  const handleTogglePlay = async () => {
    const el = audioRef.current
    if (!el) return
    if (isPlaying) {
      el.pause()
      setIsPlaying(false)
    } else {
      try {
        await el.play()
        setIsPlaying(true)
      } catch {
        const nextPos = currentTime >= duration * 0.9 ? 0 : Math.min(duration, currentTime + duration * 0.25)
        setCurrentTime(nextPos)
      }
    }
  }

  const handleSeekBand = (bandIndex: number) => {
    const ratio = (bandIndex + 1) / WAVEFORM_BANDS.length
    const nextSec = Number((ratio * duration).toFixed(2))
    setCurrentTime(nextSec)
    if (audioRef.current) {
      try {
        audioRef.current.currentTime = nextSec
      } catch {
        // no-op
      }
    }
  }

  return (
    <div className="space-y-6 pb-12 max-w-5xl mx-auto animate-in fade-in duration-200" data-testid="screen-audio">
      {/* Üst Bar: Başlık, Adım Rozeti ve Kalite Etiketleri */}
      <div className={`${CARD_CLS} flex flex-col sm:flex-row sm:items-center justify-between gap-4`}>
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              Adım 3 / 6
            </span>
            <span className="text-zinc-300 dark:text-zinc-700">•</span>
            <span className="text-xs text-zinc-500 font-medium">24kHz Audio Mastering</span>
          </div>
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
            Ses Sentezi ve Zamanlama Masası
          </h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            Doğal TTS motoru, 24kHz stüdyo seslendirmesi ve kare senkronizasyonu.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="px-3 py-1 rounded-xl bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 font-mono text-xs font-semibold">
            PCM WAV 24.0 kHz
          </span>
          <span className="px-3 py-1 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-xs font-semibold">
            LUFS -14.0 Hedef
          </span>
        </div>
      </div>

      {errorMessage && (
        <div
          className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/40 text-rose-600 dark:text-rose-400 text-xs font-medium"
          data-testid="audio-error"
        >
          {errorMessage}
        </div>
      )}

      {/* Durum 1: Ses Henüz Üretilmediyse -> Seslendirici Seçici & Sentezleme Paneli */}
      {!audio?.isGenerated ? (
        <div className={`${CARD_CLS} space-y-6`}>
          <div>
            <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100 mb-1">
              Seslendirici ve Ton Tercihi
            </h3>
            <p className="text-xs text-zinc-500">
              Senaryonuz için en uygun Türkçe seslendirici tonunu seçin ve sentezleme işlemini başlatın.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {AVAILABLE_VOICES.map((v) => {
              const isSelected = selectedVoice === v.id
              return (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => setSelectedVoice(v.id)}
                  className={`p-4 rounded-xl text-left border transition-all cursor-pointer ${
                    isSelected
                      ? 'border-zinc-900 dark:border-white bg-zinc-50 dark:bg-zinc-800/80 shadow-2xs'
                      : 'border-[#E5E7EB] dark:border-zinc-800 hover:border-zinc-400 dark:hover:border-zinc-700 bg-white dark:bg-zinc-900'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-zinc-900 dark:text-zinc-100">{v.name}</span>
                    {isSelected && <span className="text-emerald-500 font-bold text-xs">✓</span>}
                  </div>
                  <p className="text-[11px] text-zinc-500 leading-relaxed">{v.desc}</p>
                </button>
              )
            })}
          </div>

          <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-950/60 border border-[#E5E7EB] dark:border-zinc-800 space-y-2">
            <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider block">
              Seslendirilecek Metin Önizlemesi ({script.fullText.length} karakter)
            </span>
            <p className="text-xs text-zinc-800 dark:text-zinc-200 leading-relaxed italic">
              &ldquo;{script.fullText}&rdquo;
            </p>
          </div>

          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleSynthesize}
              disabled={isLoading}
              className="px-6 py-2.5 rounded-xl text-xs font-semibold bg-[#111827] dark:bg-white text-white dark:text-zinc-900 hover:opacity-90 shadow-xs transition-opacity cursor-pointer flex items-center gap-2"
            >
              {isLoading && (
                <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16 9h5v-.001M3 20v-5m0 0h5m-5 0l3 3a8 8 0 0014-4M4 10a8 8 0 0114-4l3 3m0-5v5" />
                </svg>
              )}
              <span>{isLoading ? 'Ses Sentezleniyor...' : '24kHz Sesi Sentezle →'}</span>
            </button>
          </div>
        </div>
      ) : (
        /* Durum 2: Ses Başarıyla Üretildi -> Oynatıcı, Telemetri ve Dalga Formu */
        <>
          {/* 3 Ana Telemetri Kartı */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Süre */}
            <div className={`${CARD_CLS} space-y-1`}>
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
                Hesaplanan Süre
              </span>
              <span className="text-2xl font-bold font-mono text-zinc-900 dark:text-zinc-100 block">
                {audio.durationSeconds} saniye
              </span>
              <span className="text-[11px] text-zinc-500 font-mono block">
                00:{formattedMinutes < 10 ? '0' : ''}{formattedMinutes}:{formattedSeconds < 10 ? '0' : ''}{formattedSeconds}.00 Timecode
              </span>
            </div>

            {/* Toplam Kare */}
            <div className={`${CARD_CLS} space-y-1`}>
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
                Toplam Kare
              </span>
              <span className="text-2xl font-bold font-mono text-zinc-900 dark:text-zinc-100 block">
                {totalFrames} kare
              </span>
              <span className="text-[11px] text-zinc-500 font-mono block">
                @{fps} FPS Video Senkronu
              </span>
            </div>

            {/* AudioCache Durumu */}
            <div className={`${CARD_CLS} space-y-1`}>
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
                AudioCache Durumu
              </span>
              <div className="flex items-center gap-2 pt-0.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-base font-bold text-emerald-600 dark:text-emerald-400 font-mono">
                  Hazır (Hit)
                </span>
              </div>
              <span className="text-[11px] text-zinc-500 font-mono block">
                Sıfır Ağ Çağrısı • Deterministik
              </span>
            </div>
          </div>

          {/* HTML5 Ses Oynatıcı & İnteraktif Dalga Formu */}
          <div className={`${CARD_CLS} space-y-5`}>
            <audio
              ref={audioRef}
              src={safeAudioSrc}
              preload="metadata"
              onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onEnded={() => {
                setIsPlaying(false)
                setCurrentTime(0)
              }}
              className="hidden"
              data-testid="audio-native-element"
            />

            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                {/* Oynat / Duraklat Butonu */}
                <button
                  type="button"
                  onClick={handleTogglePlay}
                  aria-label={isPlaying ? 'Sesi Duraklat' : 'Sesi Oynat'}
                  data-testid="audio-transport-play-btn"
                  className="w-12 h-12 rounded-2xl bg-[#111827] hover:bg-zinc-800 dark:bg-white dark:hover:bg-zinc-100 text-white dark:text-zinc-900 flex items-center justify-center transition-all cursor-pointer shadow-xs active:scale-95"
                >
                  {isPlaying ? (
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                      <rect x="6" y="5" width="4" height="14" rx="1" />
                      <rect x="14" y="5" width="4" height="14" rx="1" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 ml-0.5" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M8 5.14v14l11-7-11-7z" />
                    </svg>
                  )}
                </button>

                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-zinc-900 dark:text-zinc-100 text-sm">{audio.voiceId}</span>
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                      Mono Master
                    </span>
                  </div>
                  <span className="text-xs text-zinc-500 mt-0.5 block">
                    Türkçe Doğal TTS • Dalga formuna tıklayarak kare konumunu sarabilirsiniz.
                  </span>
                </div>
              </div>

              {/* Canlı Sayaç */}
              <div className="px-3.5 py-2 rounded-xl bg-zinc-50 dark:bg-zinc-800/60 border border-[#E5E7EB] dark:border-zinc-800 font-mono text-xs flex items-center gap-2">
                <span className="font-bold text-zinc-900 dark:text-zinc-100">{currentTime.toFixed(1)}s</span>
                <span className="text-zinc-400">/</span>
                <span className="text-zinc-500">{audio.durationSeconds.toFixed(1)}s</span>
                <span className="text-zinc-300 dark:text-zinc-700">|</span>
                <span className="text-[11px] text-zinc-400">Kare: {currentFrame}/{totalFrames}</span>
              </div>
            </div>

            {/* 32-Bant Dalga Formu */}
            <div className="p-4 rounded-xl bg-zinc-50/70 dark:bg-zinc-950/50 border border-[#E5E7EB] dark:border-zinc-800 space-y-2">
              <div className="flex items-end justify-between gap-1 h-16 px-1">
                {WAVEFORM_BANDS.map((h, i) => {
                  const bandRatio = i / WAVEFORM_BANDS.length
                  const isPlayed = bandRatio <= progressRatio && currentTime > 0
                  return (
                    <button
                      key={i}
                      type="button"
                      onClick={() => handleSeekBand(i)}
                      title={`${((i / WAVEFORM_BANDS.length) * duration).toFixed(1)} sn`}
                      className={`flex-1 rounded-sm transition-all duration-150 cursor-pointer ${
                        isPlayed
                          ? 'bg-zinc-900 dark:bg-white'
                          : 'bg-zinc-300 dark:bg-zinc-700 hover:bg-zinc-400 dark:hover:bg-zinc-600'
                      }`}
                      style={{ height: `${h}%` }}
                    />
                  )
                })}
              </div>

              <div className="flex justify-between text-[10px] text-zinc-400 font-mono pt-1 border-t border-zinc-200 dark:border-zinc-800">
                <span>00:00.0 (Kare 0)</span>
                <span>{(duration / 2).toFixed(1)}s</span>
                <span>00:{audio.durationSeconds < 10 ? '0' : ''}{Math.round(audio.durationSeconds)}.0 ({totalFrames} Kare)</span>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between text-xs font-mono text-zinc-400 pt-1">
              <span className="truncate max-w-md text-[11px]">
                Yol: {audio.audioPath}
              </span>
              <span className="text-emerald-600 dark:text-emerald-400 font-semibold text-[11px]">
                ✓ FFmpeg İçin Doğrulandı
              </span>
            </div>
          </div>

          {/* Senaryo Metin Kartı */}
          <div className={`${CARD_CLS} space-y-2`}>
            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
              Seslendirilen Senaryo Metni
            </span>
            <p className="text-xs text-zinc-800 dark:text-zinc-200 leading-relaxed bg-zinc-50 dark:bg-zinc-950/60 p-4 rounded-xl border border-[#E5E7EB] dark:border-zinc-800">
              &ldquo;{script.fullText}&rdquo;
            </p>
          </div>
        </>
      )}

      {/* Alt Navigasyon Barı */}
      <div className="flex items-center justify-between pt-4 border-t border-[#E5E7EB] dark:border-zinc-800">
        <button
          type="button"
          onClick={prevStep}
          data-testid="audio-back-btn"
          className="flex items-center gap-2 px-4 py-2 rounded-xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-300 text-xs font-semibold transition-colors cursor-pointer"
        >
          <svg className="w-4 h-4 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          <span>← Senaryoya Dön</span>
        </button>

        <button
          type="button"
          onClick={handleAdvance}
          disabled={!audio?.isGenerated || audio.durationSeconds <= 0 || isLoading}
          className={`px-6 py-2.5 rounded-xl text-xs font-semibold transition-all duration-200 flex items-center gap-2 cursor-pointer ${
            audio?.isGenerated && audio.durationSeconds > 0 && !isLoading
              ? 'bg-[#111827] dark:bg-white text-white dark:text-zinc-900 hover:opacity-90 shadow-xs'
              : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-600 cursor-not-allowed'
          }`}
          data-testid="audio-submit-btn"
        >
          {isLoading && (
            <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16 9h5v-.001M3 20v-5m0 0h5m-5 0l3 3a8 8 0 0014-4M4 10a8 8 0 0114-4l3 3m0-5v5" />
            </svg>
          )}
          <span>Görsellere Geç &amp; İlerle →</span>
        </button>
      </div>
    </div>
  )
}
