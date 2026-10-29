import { useState, useMemo, useEffect, useRef, type FC, type FormEvent } from 'react'
import { useFlowStore } from '../../store/flowStore'
import type { RealVideoItem } from '../../store/flowTypes'
import { toSafeAssetUrl, secureInvoke } from '../../lib/securityGuard'
import { DraggableChannelCard, type Position } from './DraggableChannelCard'
import { ChannelTrendChart } from './charts/ChannelTrendChart'
import { ChannelDistributionChart, ViralMultiplierCard, ViewTierDistributionCard } from './charts/ChannelDistributionChart'
import {
  resolveChannelAvatar,
  generateDefaultAiSummary,
  formatCount,
  deriveFallbackAnalytics,
} from './channelMetadata'
import { deriveGlobalViralPrototypes } from './globalPrototypes'
import { ShortsProductionStudio } from './ShortsProductionStudio'
import { getIpcClient } from '../../lib/ipc'
import { AppIcon } from '../ui/AppIcon'

const B_SEP = 'border-zinc-100 dark:border-zinc-800'
const B_BOX = 'border-zinc-200 dark:border-zinc-800'
const BG_CARD = 'bg-white dark:bg-zinc-900'
const TXT_MAIN = 'text-zinc-900 dark:text-zinc-100'
const CARD_CLS = `p-6 rounded-2xl border ${B_BOX} ${BG_CARD} shadow-xs`
const CARD_916 = 'relative w-48 sm:w-52 aspect-[9/16] shrink-0 rounded-2xl'
const BADGE_BASE = 'px-2 py-0.5 rounded text-[10px] font-bold border'
const BADGE_BLUE = 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20'
const BADGE_CYAN = 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20'
const TAB_BLUE = 'border-blue-500 text-blue-500 bg-blue-50/40 dark:bg-blue-950/20'
const TAB_CYAN = 'border-cyan-500 text-cyan-500 bg-cyan-50/40 dark:bg-cyan-950/20'
const INPUT_CLS = 'w-full px-3 py-2 rounded-xl bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-xs text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none'
const BTN_PAGE = 'px-2.5 py-1 rounded-lg border border-zinc-200 dark:border-zinc-700 disabled:opacity-40 cursor-pointer text-xs'
const BTN_DARK = 'w-full py-2 px-3 rounded-xl text-xs font-semibold bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 text-white shadow-xs cursor-pointer inline-flex items-center justify-center gap-1.5 transition-colors'
const BTN_OUT = 'px-3 py-1.5 rounded-xl text-xs font-medium bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 cursor-pointer'

const PAGE_SIZE = 10
const PROTOTYPES_PER_PAGE = 6

const card3dStyle = (isHovered: boolean) => ({
  transform: isHovered
    ? 'perspective(1200px) translateY(-8px) scale(1.02)'
    : 'perspective(1200px) rotateY(-8deg) rotateX(4deg)',
  transformStyle: 'preserve-3d' as const,
  transition: 'transform 0.35s ease,box-shadow 0.35s ease',
  boxShadow: isHovered ? '0 20px 35px -10px rgba(0,0,0,0.4)' : '0 15px 25px -8px rgba(0,0,0,0.4)',
})

const tplApi = (method: 'GET' | 'POST' | 'DELETE', chId: string, sub = '', body?: unknown) =>
  getIpcClient().proxyRequest(method, `/api/v1/channels/${chId}/templates${sub}`, body)

const openDialog = (title: string, extensions: string[]) =>
  secureInvoke<string | null>('plugin:dialog|open', { options: { title, filters: [{ name: title, extensions }], multiple: false } })

const Pager: FC<{ page: number; total: number; count: number; onPrev: () => void; onNext: () => void }> = ({ page, total, count, onPrev, onNext }) =>
  total > 1 ? (
    <div className={`flex items-center justify-between pt-2.5 border-t ${B_SEP} text-xs font-mono text-zinc-500`}>
      <span>Sayfa {page} / {total} ({count})</span>
      <div className="flex items-center gap-1.5">
        <button type="button" disabled={page <= 1} onClick={onPrev} className={BTN_PAGE}>← Önceki</button>
        <button type="button" disabled={page >= total} onClick={onNext} className={BTN_PAGE}>Sonraki →</button>
      </div>
    </div>
  ) : null

const VideoPerformanceTable: FC<{
  title: string
  subtitle: string
  countLabel: string
  badgeText: string
  badgeColor: 'blue' | 'cyan'
  videos: RealVideoItem[]
  isLoading: boolean
  emptyMessage: string
}> = ({ title, subtitle, countLabel, badgeText, badgeColor, videos, isLoading, emptyMessage }) => {
  const [sortBy, setSortBy] = useState<'top' | 'recent' | 'outliers'>('top')
  const [searchTerm, setSearchTerm] = useState('')
  const [page, setPage] = useState(1)
  const isBlue = badgeColor === 'blue'
  const bCls = isBlue ? BADGE_BLUE : BADGE_CYAN
  const avg = useMemo(() => (videos.length ? videos.reduce((s, v) => s + (v.view_count ?? 0), 0) / videos.length : 0), [videos])
  const processed = useMemo(() => {
    const q = searchTerm.trim().toLowerCase()
    const list = q ? videos.filter((v) => v.title.toLowerCase().includes(q)) : [...videos]
    const out = sortBy === 'outliers' ? list.filter((v) => (v.view_count ?? 0) >= avg) : list
    return sortBy === 'recent' ? out : out.sort((a, b) => (b.view_count ?? 0) - (a.view_count ?? 0))
  }, [videos, searchTerm, sortBy, avg])

  const totalPages = Math.max(1, Math.ceil(processed.length / PAGE_SIZE))
  const slice = processed.slice((Math.min(page, totalPages) - 1) * PAGE_SIZE, Math.min(page, totalPages) * PAGE_SIZE)

  return (
    <div className={`${CARD_CLS} space-y-4`}>
      <div className={`flex items-center justify-between gap-3 pb-3 border-b ${B_SEP}`}>
        <div className="flex items-center gap-2.5">
          <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${bCls}`}>
            <AppIcon name={isBlue ? 'film' : 'bolt'} className="w-4 h-4" />
          </div>
          <div><h3 className={`text-base font-bold ${TXT_MAIN}`}>{title}</h3><p className="text-xs text-zinc-500">{subtitle}</p></div>
        </div>
        <span className={`text-xs px-3 py-1 rounded-full font-mono font-medium border ${bCls}`}>{countLabel}</span>
      </div>
      {videos.length > 0 && (
        <div className="flex items-center justify-between gap-2.5">
          <div className="inline-flex p-1 rounded-xl bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700">
            {([['top', 'Popüler'], ['recent', 'Son'], ['outliers', 'Outlier']] as const).map(([id, l]) => (
              <button key={id} type="button" onClick={() => { setSortBy(id); setPage(1) }} className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold cursor-pointer ${sortBy === id ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-2xs' : 'text-zinc-500'}`}>{l}</button>
            ))}
          </div>
          <input type="text" value={searchTerm} onChange={(e) => { setSearchTerm(e.target.value); setPage(1) }} placeholder="Ara..." className={`${INPUT_CLS} !w-48 !py-1`} />
        </div>
      )}
      {isLoading ? <div className="p-8 text-center text-xs text-zinc-500 font-mono">Veriler çekiliyor...</div> : !processed.length ? <div className="p-8 rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800 text-center text-xs text-zinc-500">{emptyMessage}</div> : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className={`border-b ${B_BOX} text-zinc-500 uppercase text-[10px]`}>
                  {'# Format Başlık Tarih İzlenme Çarpan Link'.split(' ').map((h, i) => <th key={h} className={`py-2 px-3 ${i >= 4 ? 'text-right' : ''}`}>{h}</th>)}
                </tr>
              </thead>
              <tbody className={`divide-y ${B_SEP} [&_td]:py-2 [&_td]:px-3`}>
                {slice.map((v, i) => {
                  const m = avg > 0 && v.view_count ? (v.view_count / avg).toFixed(1) : null
                  return (
                    <tr key={v.id || i} className="hover:bg-zinc-50/80 dark:hover:bg-zinc-800/40">
                      <td className="text-zinc-400 font-mono">{i + 1}</td>
                      <td><span className={`${BADGE_BASE} ${bCls}`}>{badgeText}</span></td>
                      <td className={`font-medium ${TXT_MAIN} max-w-md truncate`}>{v.title}</td>
                      <td className="text-zinc-500 text-[11px]">{v.published_text || (v.days_ago != null ? `${v.days_ago}g` : 'Arşiv')}</td>
                      <td className={`text-right font-bold font-mono ${TXT_MAIN}`}>{v.view_count != null ? formatCount(v.view_count) : '-'}</td>
                      <td className="text-right font-mono">{m ? <span className="text-[10px] font-bold text-emerald-600">{m}x</span> : '-'}</td>
                      <td className="text-right">{v.url ? <a href={v.url} target="_blank" rel="noreferrer" className={`hover:underline font-semibold text-[11px] ${isBlue ? 'text-blue-600' : 'text-cyan-600'}`}>İzle ↗</a> : '-'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <Pager page={Math.min(page, totalPages)} total={totalPages} count={processed.length} onPrev={() => setPage((p) => Math.max(1, p - 1))} onNext={() => setPage((p) => Math.min(totalPages, p + 1))} />
        </>
      )}
    </div>
  )
}

export interface TemplateSlotItem {
  slot_id: string
  label: string
  media_type: 'image' | 'video'
  media_path: string
  start_sec: number
  end_sec: number
  layout: string
  prompt?: string
  directive?: string
  subtitle?: string
  fitMode?: 'cover' | 'contain'
}

export interface ChannelShortsTemplate {
  id: string
  channelId: string
  title: string
  filePath: string
  format: '9:16'
  addedAt: number
  durationSec?: number
  slots?: TemplateSlotItem[]
  narrationScript?: string
  subtitleCues?: { index: number; start_sec: number; end_sec: number; text: string }[]
  voiceId?: string
  audioPath?: string
  renderedOutputPath?: string
  audioMix?: { template: number; voice: number; speed: number }
  targetAudience?: string
  viralFormula?: string
  pacingCadence?: string
}

const mapTpl = (t: Record<string, unknown>, chId: string, dur = 15): ChannelShortsTemplate => ({
  id: String(t.id || `tpl_${Date.now()}`),
  channelId: chId,
  title: String(t.title || 'Şablon'),
  filePath: String(t.base_video_path || t.filePath || ''),
  format: '9:16',
  addedAt: Number(t.created_at || t.addedAt || Date.now()),
  durationSec: Number(t.duration_sec || t.durationSec || dur),
  slots: (t.slots as TemplateSlotItem[]) || defaultSlots(dur),
  narrationScript: String(t.narration_script || t.narrationScript || ''),
  subtitleCues: (t.subtitle_cues as ChannelShortsTemplate['subtitleCues']) || undefined,
  voiceId: String(t.voice_id || t.voiceId || DEFAULT_VOICES[0].voice_id),
  audioPath: String(t.audio_path || t.audioPath || ''),
  renderedOutputPath: String(t.rendered_output_path || t.renderedOutputPath || ''),
  targetAudience: typeof t.target_audience === 'string' ? t.target_audience : undefined,
  viralFormula: typeof t.viral_formula === 'string' ? t.viral_formula : undefined,
  pacingCadence: typeof t.pacing_cadence === 'string' ? t.pacing_cadence : undefined,
})

const DEFAULT_VOICES = [
  ['21m00Tcm4TlvDq8ikWAM', 'Rachel (Dinamik)'],
  ['pNInz6obpgDQGcFmaJgB', 'Adam (Derin)'],
  ['EXAVITQu4vr4xnSDxMaL', 'Bella (Hikaye)'],
  ['ErXwobaYiN019PkySvjV', 'Antoni (Enerjik)'],
].map(([voice_id, name]) => ({ voice_id, name }))

const defaultSlots = (dur = 15): TemplateSlotItem[] => ([
  ['slot_1', '1. Kanca', 'image', 0, 4, 'overlay_center'],
  ['slot_2', '2. Ana Gövde', 'video', 4, 11, 'fullscreen'],
  ['slot_3', '3. Kapanış', 'image', 11, dur, 'split_top'],
] as const).map(([slot_id, label, media_type, start_sec, end_sec, layout]) => ({
  slot_id, label, media_type: media_type as 'image' | 'video', media_path: '', start_sec, end_sec, layout,
}))

const ShortsTemplateCard: FC<{
  template: ChannelShortsTemplate
  onSelect: (tpl: ChannelShortsTemplate) => void
  onDelete: (id: string) => void
}> = ({ template, onSelect, onDelete }) => {
  const vRef = useRef<HTMLVideoElement>(null)
  const [play, setPlay] = useState(false)
  const [hov, setHov] = useState(false)
  const [hasError, setHasError] = useState(false)

  const handleLoadedData = () => {
    if (vRef.current && vRef.current.currentTime === 0) {
      vRef.current.currentTime = 0.05
    }
  }

  return (
    <div
      onClick={() => onSelect(template)}
      onMouseEnter={() => {
        setHov(true)
        if (vRef.current && !hasError) {
          vRef.current.play().then(() => setPlay(true)).catch(() => {})
        }
      }}
      onMouseLeave={() => {
        setHov(false)
        if (vRef.current) {
          vRef.current.pause()
          vRef.current.currentTime = 0.05
          setPlay(false)
        }
      }}
      style={card3dStyle(hov)}
      className={`${CARD_916} overflow-hidden bg-zinc-950 border cursor-pointer group select-none transition-all ${
        hov ? 'border-cyan-400 ring-2 ring-cyan-500/20' : 'border-zinc-800 hover:border-zinc-700'
      }`}
    >
      <video
        ref={vRef}
        src={toSafeAssetUrl(template.filePath)}
        className="w-full h-full object-cover"
        muted
        loop
        playsInline
        preload="metadata"
        onLoadedData={handleLoadedData}
        onLoadedMetadata={handleLoadedData}
        onError={() => setHasError(true)}
      />
      {hasError && (
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-850 via-zinc-900 to-black flex flex-col items-center justify-center p-3 text-center">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 mb-2">
            <AppIcon name="film" className="w-5 h-5" />
          </div>
          <span className="text-[11px] font-bold text-white tracking-tight line-clamp-2">{template.title}</span>
          <span className="text-[9px] font-mono text-zinc-400 mt-1">{template.durationSec || 15}s • 9:16</span>
        </div>
      )}
      <div className="absolute top-2.5 inset-x-2.5 flex items-center justify-between z-10">
        <span className="px-2 py-0.5 rounded bg-black/75 text-[10px] font-mono font-bold text-cyan-400 border border-cyan-500/30">9:16 SHORTS</span>
        <button type="button" onClick={(e) => { e.stopPropagation(); onDelete(template.id) }} className="w-6 h-6 rounded-full bg-black/75 text-zinc-400 hover:text-white flex items-center justify-center opacity-0 group-hover:opacity-100 cursor-pointer" aria-label="Şablonu Kaldır">
          <AppIcon name="close" className="w-3 h-3" />
        </button>
      </div>
      {!play && !hasError && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-11 h-11 rounded-full bg-black/50 border border-white/20 flex items-center justify-center text-white"><AppIcon name="play" className="w-4 h-4 ml-0.5" /></div>
        </div>
      )}
      <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-black/90 to-transparent z-10 pointer-events-none">
        <h5 className="text-xs font-bold text-white truncate">{template.title}</h5>
        <p className="text-[10px] font-mono text-zinc-400 truncate mt-0.5">{template.filePath.split(/[\\/]/).pop()}</p>
      </div>
    </div>
  )
}

const AddShortsTemplateCard: FC<{ onClick: () => void; disabled?: boolean }> = ({ onClick, disabled }) => {
  const [hov, setHov] = useState(false)
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={card3dStyle(hov)}
      className={`${CARD_916} border-2 border-dashed flex flex-col items-center justify-center p-4 cursor-pointer select-none transition-all ${
        hov ? 'border-cyan-400 bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 ring-2 ring-cyan-500/20' : 'border-zinc-300 dark:border-zinc-800 text-zinc-400'
      }`}
      aria-label="Yeni Shorts Şablonu Yükle"
    >
      <div className="w-12 h-12 rounded-full border border-zinc-300 dark:border-zinc-700 flex items-center justify-center text-2xl font-light text-zinc-500">+</div>
      <span className="text-xs font-bold font-mono tracking-wider mt-4">+ ŞABLON EKLE</span>
      <span className="text-[10px] text-zinc-400 font-mono mt-1">9:16 Shorts (MP4/MOV)</span>
    </button>
  )
}

const ProtoCard: FC<{
  proto: ReturnType<typeof deriveGlobalViralPrototypes>[number]
  onStart: () => void
}> = ({ proto, onStart }) => {
  const isShort = proto.format === 'short'
  return (
    <div className={`p-4 rounded-xl border ${B_BOX} ${BG_CARD} shadow-xs flex flex-col justify-between space-y-3 transition-colors ${isShort ? 'hover:border-cyan-400' : 'hover:border-blue-400'}`}>
      <div className="space-y-2.5">
        <div className="flex items-center justify-between text-[11px]">
          <div className="flex items-center gap-1.5 truncate max-w-[170px]">
            <span className={`${BADGE_BASE} font-mono ${isShort ? BADGE_CYAN : BADGE_BLUE}`}>{isShort ? 'SHORTS' : 'VİDEO'}</span>
            <span className="font-semibold text-zinc-600 dark:text-zinc-300 truncate">{proto.categoryLabel}</span>
          </div>
          <span className="font-mono text-zinc-500 font-bold text-[10px]">SKOR: {proto.viralScore}</span>
        </div>
        <h4 className={`text-xs font-bold ${TXT_MAIN} line-clamp-2`} title={proto.globalTitle}>{proto.globalTitle}</h4>
        <div className={`flex items-center gap-2 text-[10px] font-mono text-zinc-500 border-b ${B_SEP} pb-2`}>
          <span className="font-semibold text-zinc-800 dark:text-zinc-200">{proto.globalViewsFormatted}</span>
          <span>• {proto.durationText} • <span className="text-cyan-600 dark:text-cyan-400">{proto.retentionBadge}</span></span>
        </div>
        <div className={`p-2 rounded-lg ${TAB_BLUE} border text-[11px]`}>
          <span className="text-[9px] font-bold block">Prototip</span>
          <p className={`font-bold ${TXT_MAIN} truncate`}>{proto.prototypeTitle}</p>
          <p className="text-zinc-500 italic line-clamp-1">&ldquo;{proto.prototypeHook}&rdquo;</p>
        </div>
      </div>
      <button type="button" onClick={onStart} className={BTN_DARK}>
        <span>Bu Prototiple Başla</span><AppIcon name="right" className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

const WORKSPACE_TABS = [
  ['prototypes', 'Fikir & Prototip'],
  ['analytics', 'Performans & Trendler'],
  ['tables', 'İçerik Tabloları'],
  ['templates', 'Shorts Şablonları'],
] as const

const TimeFilterBar: FC<{
  value: '1_month' | '1_year' | 'all'
  onChange: (val: '1_month' | '1_year' | 'all') => void
}> = ({ value, onChange }) => (
  <div className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-2xl ${BG_CARD} border ${B_BOX}`}>
    <span className={`text-xs font-bold ${TXT_MAIN}`}>Zaman Aralığı</span>
    <div className="inline-flex items-center p-1 rounded-xl bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700">
      {([['1_month', 'Son 1 Ay'], ['1_year', 'Son 1 Yıl'], ['all', 'Tümü']] as const).map(([id, label]) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          className={`px-3 py-1 rounded-lg text-xs font-semibold cursor-pointer ${
            value === id ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs' : 'text-zinc-500'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  </div>
)

export const ChannelsScreen: FC = () => {
  const {
    channels,
    activeChannelId,
    isChannelsLoading,
    isChannelResearching,
    channelIdeas,
    channelLiveStats,
    isLiveStatsLoading,
    selectChannel,
    createChannel,
    deleteChannel,
    updateChannelSummary,
    fetchChannelLiveStats,
    researchChannelContent,
    selectIdeaFromChannelAndStartFlow,
  } = useFlowStore()

  const [isCreating, setIsCreating] = useState(false)
  const [name, setName] = useState('')
  const [channelUrl, setChannelUrl] = useState('')
  const [description, setDescription] = useState('')
  const [query, setQuery] = useState('')
  const [positions, setPositions] = useState<Record<string, Position>>({})
  const [isEditingAiSummary, setIsEditingAiSummary] = useState(false)
  const [summaryInput, setSummaryInput] = useState('')
  const [deskImgFailed, setDeskImgFailed] = useState(false)
  const [isRegeneratingAi, setIsRegeneratingAi] = useState(false)
  const [timeCategory, setTimeCategory] = useState<'1_month' | '1_year' | 'all'>('all')
  const [prototypeFormatFilter, setPrototypeFormatFilter] = useState<'all' | 'short' | 'video'>('all')
  const [prototypePage, setPrototypePage] = useState(1)
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<'prototypes' | 'analytics' | 'tables' | 'templates'>('prototypes')

  const TPL_KEY = 'hustler_channel_shorts_templates_v2'
  const [channelShortsTemplates, setChannelShortsTemplates] = useState<Record<string, ChannelShortsTemplate[]>>(() => {
    try {
      const raw = localStorage.getItem(TPL_KEY) || localStorage.getItem('hustler_channel_shorts_templates_v1')
      return raw ? (JSON.parse(raw) as Record<string, ChannelShortsTemplate[]>) : {}
    } catch {
      return {}
    }
  })
  const [isPickingFile, setIsPickingFile] = useState(false)
  const [selectedShortsTemplate, setSelectedShortsTemplate] = useState<ChannelShortsTemplate | null>(null)
  const [tplTopic, setTplTopic] = useState('')
  const [isAnalyzingTpl, setIsAnalyzingTpl] = useState(false)
  const [isSynthesizingVoice, setIsSynthesizingVoice] = useState(false)
  const [isRenderingTpl, setIsRenderingTpl] = useState(false)
  const [voices, setVoices] = useState(DEFAULT_VOICES)

  const tplFileRef = useRef<HTMLInputElement>(null)
  const slotFileRef = useRef<HTMLInputElement>(null)
  const pendingSlotRef = useRef(0)

  const saveTemplates = (updated: Record<string, ChannelShortsTemplate[]>) => {
    setChannelShortsTemplates(updated)
    try { localStorage.setItem(TPL_KEY, JSON.stringify(updated)) } catch { /* ignore */ }
  }

  const updateActiveTemplate = (patch: Partial<ChannelShortsTemplate>) => {
    if (!activeChannel || !selectedShortsTemplate) return
    const nextTpl: ChannelShortsTemplate = { ...selectedShortsTemplate, ...patch }
    setSelectedShortsTemplate(nextTpl)
    saveTemplates({
      ...channelShortsTemplates,
      [activeChannel.id]: (channelShortsTemplates[activeChannel.id] || []).map((t) => (t.id === nextTpl.id ? nextTpl : t)),
    })
  }

  const createTemplateFromPicked = async (fileName: string, previewUrl: string) => {
    if (!activeChannel) return
    const title = (fileName.split(/[\\/]/).pop() || 'Shorts_Sablonu').replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ')
    const effectiveUrl = previewUrl || fileName
    let tpl = mapTpl({ title, base_video_path: effectiveUrl, duration_sec: 15 }, activeChannel.id)
    try {
      const res = await tplApi('POST', activeChannel.id, '', { title, base_video_path: fileName, duration_sec: 15 })
      const b = (res?.body ?? {}) as { template?: Record<string, unknown>; voices?: typeof DEFAULT_VOICES }
      if (b.voices?.length) setVoices(b.voices)
      if (b.template) {
        tpl = {
          ...mapTpl(b.template, activeChannel.id),
          filePath: effectiveUrl,
        }
      }
    } catch { /* fallback */ }
    saveTemplates({ ...channelShortsTemplates, [activeChannel.id]: [tpl, ...(channelShortsTemplates[activeChannel.id] || [])] })
  }

  const handlePickShortsTemplate = async () => {
    if (!activeChannel) return
    setIsPickingFile(true)
    try {
      const selected = await openDialog('9:16 Shorts Şablonu', ['mp4', 'mov', 'webm', 'mkv'])
      if (selected && typeof selected === 'string') return await createTemplateFromPicked(selected, selected)
    } catch { /* fallback */ } finally {
      setIsPickingFile(false)
    }
    tplFileRef.current?.click()
  }

  const setSlotMedia = (slotIdx: number, media_path = '', isVid = false) => {
    if (!activeChannel || !selectedShortsTemplate) return
    const slots = [...(selectedShortsTemplate.slots?.length ? selectedShortsTemplate.slots : defaultSlots())]
    slots[slotIdx] = { ...slots[slotIdx], media_type: isVid ? 'video' : 'image', media_path }
    updateActiveTemplate({ slots })
    void tplApi('POST', activeChannel.id, `/${selectedShortsTemplate.id}/update`, { slots })
  }

  const handlePickSlotMedia = async (slotIdx: number) => {
    if (!activeChannel || !selectedShortsTemplate) return
    pendingSlotRef.current = slotIdx
    try {
      const selected = await openDialog('Medya Seçin', ['png', 'jpg', 'jpeg', 'webp', 'mp4', 'mov', 'webm'])
      if (selected && typeof selected === 'string') return setSlotMedia(slotIdx, selected, /\.(mp4|mov|webm|mkv)$/i.test(selected))
    } catch { /* fallback */ }
    slotFileRef.current?.click()
  }

  const handleAnalyzeTemplate = async (slotCount?: number) => {
    if (!activeChannel || !selectedShortsTemplate || isAnalyzingTpl) return
    setIsAnalyzingTpl(true)
    const topic = tplTopic || selectedShortsTemplate.title
    try {
      const res = await tplApi('POST', activeChannel.id, `/${selectedShortsTemplate.id}/analyze`, {
        topic,
        tone: 'energetic',
        slot_count: slotCount || (selectedShortsTemplate.slots?.length ? selectedShortsTemplate.slots.length : 10),
      })
      const b = (res?.body ?? {}) as {
        template?: Record<string, unknown>
        narration_script?: string
        subtitle_cues?: ChannelShortsTemplate['subtitleCues']
        target_audience?: string
        viral_formula?: string
        pacing_cadence?: string
      }
      if (b.template) {
        updateActiveTemplate(mapTpl(b.template, activeChannel.id, selectedShortsTemplate.durationSec))
      } else {
        updateActiveTemplate({
          narrationScript: b.narration_script || `${topic} analizi ve kurgu akışı.`,
          subtitleCues: b.subtitle_cues,
          targetAudience: b.target_audience,
          viralFormula: b.viral_formula,
          pacingCadence: b.pacing_cadence,
        })
      }
    } catch { /* fallback */ } finally {
      setIsAnalyzingTpl(false)
    }
  }

  const handleSynthesizeVoice = async () => {
    if (!activeChannel || !selectedShortsTemplate || isSynthesizingVoice) return
    setIsSynthesizingVoice(true)
    try {
      const res = await tplApi('POST', activeChannel.id, `/${selectedShortsTemplate.id}/tts`, {
        narration_script: selectedShortsTemplate.narrationScript || selectedShortsTemplate.title,
        voice_id: selectedShortsTemplate.voiceId || DEFAULT_VOICES[0].voice_id,
      })
      const b = (res?.body ?? {}) as { audio_path?: string }
      if (b.audio_path) {
        updateActiveTemplate({ audioPath: b.audio_path })
      }
    } catch { /* fallback */ } finally {
      setIsSynthesizingVoice(false)
    }
  }

  const handleRenderTemplate = async () => {
    if (!activeChannel || !selectedShortsTemplate || isRenderingTpl) return
    setIsRenderingTpl(true)
    let b: { audio_path?: string; rendered_output_path?: string } = {}
    try {
      const res = await tplApi('POST', activeChannel.id, `/${selectedShortsTemplate.id}/render`, {
        narration_script: selectedShortsTemplate.narrationScript || selectedShortsTemplate.title,
        voice_id: selectedShortsTemplate.voiceId || DEFAULT_VOICES[0].voice_id,
        profile: 'DRAFT',
      })
      b = (res?.body ?? {}) as typeof b
    } catch { /* defaults below */ } finally {
      updateActiveTemplate({
        audioPath: b.audio_path || `cache_audio/${selectedShortsTemplate.id}.wav`,
        renderedOutputPath: b.rendered_output_path || `renders/${selectedShortsTemplate.id}_reels.mp4`,
      })
      setIsRenderingTpl(false)
    }
  }

  const handleDeleteShortsTemplate = (tplId: string) => {
    if (!activeChannel) return
    if (selectedShortsTemplate?.id === tplId) setSelectedShortsTemplate(null)
    saveTemplates({
      ...channelShortsTemplates,
      [activeChannel.id]: (channelShortsTemplates[activeChannel.id] || []).filter((t) => t.id !== tplId),
    })
    void tplApi('DELETE', activeChannel.id, `/${tplId}`)
  }


  const handlePositionChange = (id: string, pos: Position) => setPositions((p) => ({ ...p, [id]: pos }))

  const activeChannel = channels.find((c) => c.id === activeChannelId) ?? null
  const liveStats = activeChannel ? channelLiveStats[activeChannel.id] : null

  useEffect(() => {
    if (activeChannel) {
      const hasCustom = activeChannel.ai_summary && !activeChannel.ai_summary.includes('İçerik analizi bekleniyor')
      setSummaryInput(
        hasCustom
          ? activeChannel.ai_summary || ''
          : generateDefaultAiSummary(activeChannel.name, activeChannel.description, activeChannel.channel_url, liveStats)
      )
      setDeskImgFailed(false)
      setIsEditingAiSummary(false)

      if (!channelLiveStats[activeChannel.id]) {
        void fetchChannelLiveStats(activeChannel.id)
      }
      void tplApi('GET', activeChannel.id)
        .then((res) => {
          const b = (res?.body ?? {}) as { templates?: Record<string, unknown>[]; voices?: typeof DEFAULT_VOICES }
          if (b.voices?.length) setVoices(b.voices)
          if (Array.isArray(b.templates) && b.templates.length) {
            const mapped = b.templates.map((t) => mapTpl(t, activeChannel.id))
            setChannelShortsTemplates((prev) => ({
              ...prev,
              [activeChannel.id]: prev[activeChannel.id]?.length ? prev[activeChannel.id] : mapped,
            }))
          }
        })
        .catch(() => {})
    }
  }, [activeChannel?.id, activeChannel?.ai_summary, liveStats])

  const handleCreateSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !channelUrl.trim()) return
    if (await createChannel({ name: name.trim(), channel_url: channelUrl.trim(), description: description.trim() })) {
      setName('')
      setChannelUrl('')
      setDescription('')
      setIsCreating(false)
    }
  }

  const handleResearchSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!activeChannel || !query.trim() || isChannelResearching) return
    setPrototypePage(1)
    await researchChannelContent(activeChannel.id, query.trim())
  }

  const handleSaveSummary = async () => {
    if (!activeChannel) return
    await updateChannelSummary(activeChannel.id, summaryInput.trim())
    setIsEditingAiSummary(false)
  }

  const handleRegenerateAi = async () => {
    if (!activeChannel) return
    setIsRegeneratingAi(true)
    const fallback = generateDefaultAiSummary(activeChannel.name, activeChannel.description, activeChannel.channel_url, liveStats)
    let refreshed = fallback
    try {
      const res = await getIpcClient().proxyRequest('POST', '/api/v1/pipeline/chat', {
        message: `${activeChannel.name} (${liveStats?.niche_query || 'Genel'}) için 4 satırlık kanal kimlik özeti çıkar.`,
        history: [],
        active_view: 'channels',
        channel_id: activeChannel.id,
      })
      refreshed = ((res?.body ?? {}) as { reply?: string }).reply?.replace(/\*/g, '').trim() || fallback
    } catch { /* fallback */ } finally {
      setSummaryInput(refreshed)
      await updateChannelSummary(activeChannel.id, refreshed)
      setIsRegeneratingAi(false)
    }
  }

  const rawLongVideos: RealVideoItem[] = useMemo(() => (liveStats?.videos || []).map((v) => ({ ...v, type: 'video' })), [liveStats])
  const rawShortVideos: RealVideoItem[] = useMemo(() => (liveStats?.shorts || []).map((s) => ({ ...s, type: 'short' })), [liveStats])

  const byTime = (list: RealVideoItem[]) => {
    const maxDays = timeCategory === '1_month' ? 30 : 365
    return timeCategory === 'all' || !list.some((v) => v.days_ago != null) ? list : list.filter((v) => v.days_ago != null && v.days_ago <= maxDays)
  }
  const filteredLongVideos = useMemo(() => byTime(rawLongVideos), [rawLongVideos, timeCategory])
  const filteredShortVideos = useMemo(() => byTime(rawShortVideos), [rawShortVideos, timeCategory])
  const allVideos: RealVideoItem[] = useMemo(() => [...rawLongVideos, ...rawShortVideos], [rawLongVideos, rawShortVideos])

  const prototypes = useMemo(() => {
    if (!activeChannel) return []
    return deriveGlobalViralPrototypes(activeChannel.name, activeChannel.description || '', activeChannel.channel_url, channelIdeas, liveStats)
  }, [activeChannel?.name, activeChannel?.description, activeChannel?.channel_url, channelIdeas, liveStats])

  const filteredPrototypes = useMemo(() => {
    if (prototypeFormatFilter === 'all') return prototypes
    return prototypes.filter((p) => p.format === prototypeFormatFilter)
  }, [prototypes, prototypeFormatFilter])

  const totalPrototypePages = Math.max(1, Math.ceil(filteredPrototypes.length / PROTOTYPES_PER_PAGE))
  const safePrototypePage = Math.min(prototypePage, totalPrototypePages)
  const paginatedPrototypes = useMemo(() => {
    const start = (safePrototypePage - 1) * PROTOTYPES_PER_PAGE
    return filteredPrototypes.slice(start, start + PROTOTYPES_PER_PAGE)
  }, [filteredPrototypes, safePrototypePage])

  const shortsPrototypesCount = useMemo(() => prototypes.filter((p) => p.format === 'short').length, [prototypes])
  const videosPrototypesCount = prototypes.length - shortsPrototypesCount

  if (isCreating) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 justify-center items-center">
        <form onSubmit={handleCreateSubmit} className={`w-full max-w-xl ${CARD_CLS} space-y-4`}>
          <div className={`flex items-center justify-between pb-2 border-b ${B_SEP}`}>
            <h3 className={`text-sm font-semibold ${TXT_MAIN}`}>Yeni Kanal Oluştur</h3>
            <button type="button" onClick={() => setIsCreating(false)} className="text-xs text-zinc-500 cursor-pointer">Kapat</button>
          </div>
          <div className="space-y-3">
            {[
              ['Kanal Başlığı *', 'text', name, setName, 'Bilim & Gelecek Shorts'],
              ['Kanal URL Adresi *', 'url', channelUrl, setChannelUrl, 'https://youtube.com/@bilimgelecek'],
            ].map(([lbl, t, val, fn, ph]) => (
              <div key={lbl as string}>
                <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{lbl as string}</label>
                <input type={t as string} required value={val as string} onChange={(e) => (fn as (v: string) => void)(e.target.value)} placeholder={ph as string} className={INPUT_CLS} />
              </div>
            ))}
            <div>
              <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">Açıklama / Niş Bilgisi</label>
              <textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Popüler bilim ve teknoloji" className={`${INPUT_CLS} resize-none`} />
            </div>
          </div>
          <div className="flex justify-end gap-2.5 pt-2">
            <button type="button" onClick={() => setIsCreating(false)} className="px-4 py-2 rounded-xl text-xs font-medium text-zinc-500 cursor-pointer">İptal</button>
            <button type="submit" disabled={!name.trim() || !channelUrl.trim()} className="px-5 py-2 rounded-xl text-xs font-semibold bg-zinc-900 text-white cursor-pointer disabled:opacity-50">Kanalı Kaydet</button>
          </div>
        </form>
      </div>
    )
  }

  if (activeChannel) {
    const avatarData = resolveChannelAvatar(activeChannel.channel_url, activeChannel.name)
    const effectiveAvatarUrl = liveStats?.avatar_url || activeChannel.avatar_url || avatarData.avatarUrl
    const activeTemplates = channelShortsTemplates[activeChannel.id] || []
    const totalVideosCount = filteredLongVideos.length
    const totalShortsCount = filteredShortVideos.length
    const totalContent = totalVideosCount + totalShortsCount
    const videoRatio = totalContent > 0 ? Math.round((totalVideosCount / totalContent) * 100) : 50
    const shortsRatio = totalContent > 0 ? 100 - videoRatio : 50

    const effectiveAnalytics =
      timeCategory === 'all' && liveStats?.analytics && liveStats.analytics.has_data
        ? liveStats.analytics
        : deriveFallbackAnalytics(filteredLongVideos, filteredShortVideos)

    if (selectedShortsTemplate) {
      return (
        <>
          <input
            ref={slotFileRef}
            type="file"
            accept="image/*,video/*"
            className="hidden"
            data-testid="slot-file-input"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) {
                const previewUrl = (f as File & { path?: string }).path || URL.createObjectURL(f)
                setSlotMedia(pendingSlotRef.current, previewUrl, f.type.startsWith('video/') || /\.(mp4|mov|webm|mkv)$/i.test(f.name))
              }
              e.target.value = ''
            }}
          />
          <ShortsProductionStudio
            template={selectedShortsTemplate}
            channelName={activeChannel.name}
            channelDescription={activeChannel.description}
            voices={voices}
            topic={tplTopic}
            isAnalyzing={isAnalyzingTpl}
            isSynthesizingVoice={isSynthesizingVoice}
            isRendering={isRenderingTpl}
            onTopicChange={setTplTopic}
            onBack={() => setSelectedShortsTemplate(null)}
            onUpdate={updateActiveTemplate}
            onPickSlotMedia={(idx) => void handlePickSlotMedia(idx)}
            onClearSlotMedia={(idx) => setSlotMedia(idx, '')}
            onAnalyze={(cnt) => void handleAnalyzeTemplate(cnt)}
            onSynthesizeVoice={() => void handleSynthesizeVoice()}
            onRender={() => void handleRenderTemplate()}
          />
        </>
      )
    }

    return (
      <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 select-text">
        <div className="max-w-7xl mx-auto w-full space-y-6">
          <div className="flex items-center justify-between">
            <button type="button" onClick={() => selectChannel(null)} className={BTN_OUT}>
              ← Kanallara Dön
            </button>
            <div className="flex items-center gap-2">
              <button type="button" onClick={() => fetchChannelLiveStats(activeChannel.id, true)} disabled={isLiveStatsLoading} className={`${BTN_OUT} inline-flex items-center gap-1.5`}>
                <AppIcon name="spin" className={`w-3.5 h-3.5 ${isLiveStatsLoading ? 'animate-spin' : ''}`} />
                <span>{isLiveStatsLoading ? 'Çekiliyor...' : 'Yenile'}</span>
              </button>
              <span className="px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-[10px] font-mono font-bold">CANLI VERİ</span>
            </div>
          </div>

          <div className={`flex items-center border-b ${B_BOX} gap-2 overflow-x-auto`}>
            {WORKSPACE_TABS.map(([tId, tLbl]) => {
              const isActive = activeWorkspaceTab === tId
              const isCyan = tId === 'analytics' || tId === 'templates'
              const count = tId === 'prototypes' ? prototypes.length : tId === 'tables' ? totalContent : tId === 'templates' ? activeTemplates.length : 'Canlı'
              return (
                <button
                  key={tId}
                  type="button"
                  onClick={() => setActiveWorkspaceTab(tId as typeof activeWorkspaceTab)}
                  className={`px-4 py-2.5 text-xs font-semibold rounded-t-xl cursor-pointer border-b-2 flex items-center gap-2 shrink-0 ${
                    isActive ? (isCyan ? TAB_CYAN : TAB_BLUE) : 'border-transparent text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200'
                  }`}
                >
                  <span>{tLbl}</span>
                  <span className={`text-[10px] px-1.5 rounded-full font-mono font-bold ${isActive ? (isCyan ? 'bg-cyan-600 text-white' : 'bg-blue-600 text-white') : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400'}`}>{count}</span>
                </button>
              )
            })}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            <div className="lg:col-span-4 space-y-4">
              <div className={`${CARD_CLS} space-y-4`}>
                <div className="flex items-start gap-3.5 min-w-0">
                  <div className="relative w-16 h-16 sm:w-20 sm:h-20 rounded-2xl overflow-hidden border-2 border-white dark:border-zinc-800 shadow-md ring-2 ring-zinc-200/80 dark:ring-zinc-700 bg-zinc-100 dark:bg-zinc-800 shrink-0 flex items-center justify-center">
                    {!deskImgFailed ? (
                      <img src={effectiveAvatarUrl} alt={activeChannel.name} onError={() => setDeskImgFailed(true)} className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-2xl font-bold text-zinc-800 dark:text-zinc-200">{avatarData.fallbackLetter}</span>
                    )}
                    <div className="absolute -bottom-1 -right-1 bg-red-600 rounded-full p-1 ring-2 ring-white dark:ring-zinc-900"><AppIcon name="play" className="w-2.5 h-2.5 text-white" /></div>
                  </div>
                  <div className="space-y-1 min-w-0 flex-1">
                    <h2 className={`text-base sm:text-lg font-bold tracking-tight ${TXT_MAIN} truncate`}>{liveStats?.channel_name || activeChannel.name}</h2>
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold ${BADGE_CYAN}`}>
                      <AppIcon name="check" className="w-3 h-3" /> Doğrulanmış Kanal
                    </span>
                    <a
                      href={activeChannel.channel_url}
                      target="_blank"
                      rel="noreferrer"
                      title={activeChannel.channel_url}
                      className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 font-mono min-w-0 max-w-full pt-0.5"
                    >
                      <span className="truncate min-w-0 flex-1">{activeChannel.channel_url.replace(/^https?:\/\/(www\.)?/, '')}</span>
                      <AppIcon name="trend" className="w-3 h-3 shrink-0" />
                    </a>
                  </div>
                </div>

                {(liveStats?.description || activeChannel.description) && (
                  <p className={`text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed line-clamp-3 pt-1 border-t ${B_SEP}`}>{liveStats?.description || activeChannel.description}</p>
                )}

                <div className={`grid grid-cols-2 gap-2 pt-1 border-t ${B_SEP}`}>
                  <div className={`p-2.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 border ${B_BOX}`}>
                    <span className="text-[10px] uppercase font-medium text-zinc-400 block">Resmi Abone</span>
                    <span className={`text-base font-bold font-mono ${TXT_MAIN} block`}>{liveStats?.subscribers_formatted || (isLiveStatsLoading ? '...' : '-')}</span>
                  </div>
                  <div className={`p-2.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 border ${B_BOX}`}>
                    <span className="text-[10px] uppercase font-medium text-zinc-400 block">Toplam / Havuz</span>
                    <span className={`text-base font-bold font-mono ${TXT_MAIN} block`}>{liveStats?.channel_total_videos_formatted ? `${liveStats.channel_total_videos_formatted} / ${totalContent}` : totalContent}</span>
                  </div>
                </div>

                <div className={`space-y-1.5 pt-1 border-t ${B_SEP}`}>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-zinc-500 font-medium">Format Dengesi</span>
                    <span className="font-mono text-zinc-700 dark:text-zinc-300">%{videoRatio} / %{shortsRatio}</span>
                  </div>
                  <div className="w-full h-2 rounded-full overflow-hidden bg-zinc-200 dark:bg-zinc-700 flex">
                    <div style={{ width: `${videoRatio}%` }} className="bg-blue-600" />
                    <div style={{ width: `${shortsRatio}%` }} className="bg-cyan-500" />
                  </div>
                </div>
              </div>

              <div className={`${CARD_CLS} space-y-3`}>
                <div className={`flex items-center justify-between pb-2.5 border-b ${B_SEP}`}>
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0"><AppIcon name="bolt" className="w-4 h-4" /></div>
                    <div>
                      <h3 className={`text-xs font-bold ${TXT_MAIN}`}>AI Kanal Algısı &amp; Kimlik</h3>
                      <p className="text-[10px] text-zinc-500">Üretim bu stratejik ton ile kurgulanır.</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button type="button" disabled={isRegeneratingAi} onClick={handleRegenerateAi} className="px-2 py-1 rounded-lg text-[10px] font-medium text-zinc-600 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700 cursor-pointer inline-flex items-center gap-1">
                      <AppIcon name="spin" className={`w-2.5 h-2.5 ${isRegeneratingAi ? 'animate-spin' : ''}`} />
                      <span>{isRegeneratingAi ? '...' : 'Yenile'}</span>
                    </button>
                    {!isEditingAiSummary ? (
                      <button type="button" onClick={() => setIsEditingAiSummary(true)} className="px-2.5 py-1 rounded-lg text-[10px] font-semibold bg-zinc-900 text-white cursor-pointer">Düzenle</button>
                    ) : (
                      <button type="button" onClick={handleSaveSummary} className="px-2.5 py-1 rounded-lg text-[10px] font-semibold bg-emerald-600 text-white cursor-pointer">Kaydet</button>
                    )}
                  </div>
                </div>

                {isEditingAiSummary ? (
                  <div className="space-y-1.5">
                    <textarea rows={6} value={summaryInput} onChange={(e) => setSummaryInput(e.target.value)} className={`${INPUT_CLS} font-mono resize-y`} />
                    <div className="flex justify-end"><button type="button" onClick={() => setIsEditingAiSummary(false)} className="text-[10px] text-zinc-500 hover:underline cursor-pointer">İptal</button></div>
                  </div>
                ) : (
                  <div className="whitespace-pre-line text-[11px] text-zinc-700 dark:text-zinc-300 leading-relaxed bg-zinc-50 dark:bg-zinc-800/40 p-3 rounded-xl border border-zinc-200/80 dark:border-zinc-800 select-text">{summaryInput}</div>
                )}
              </div>

              {activeWorkspaceTab === 'analytics' && (
                <>
                  <ViralMultiplierCard outliers={effectiveAnalytics?.outliers} />
                  <ViewTierDistributionCard tiers={effectiveAnalytics?.view_tiers} />
                </>
              )}
            </div>

            <div className="lg:col-span-8 space-y-6">
              {activeWorkspaceTab === 'prototypes' && (
                <div className={`${CARD_CLS} space-y-5`}>
                  <div className={`flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b ${B_SEP}`}>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0"><AppIcon name="bolt" className="w-4 h-4" /></div>
                      <div>
                        <h3 className={`text-base font-bold ${TXT_MAIN}`}>Global Viral Benchmark &amp; Format Prototipleme</h3>
                        <p className="text-xs text-zinc-500">Kanal nişine göre yüksek etkileşim yakalamış doğrulanmış viral referanslar.</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <span className={`text-[11px] font-mono px-2.5 py-1 rounded-lg ${BADGE_CYAN} flex items-center gap-1.5 font-semibold`}>
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
                        BENCHMARK AKTİF
                      </span>
                      <span className="text-xs font-mono font-medium px-2.5 py-1 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">{prototypes.length} Referans</span>
                    </div>
                  </div>

                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="inline-flex items-center p-1 rounded-xl bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 self-start">
                      {([['all', 'Tümü', prototypes.length], ['short', 'Shorts', shortsPrototypesCount], ['video', 'Video', videosPrototypesCount]] as const).map(([id, label, cnt]) => (
                        <button
                          key={id}
                          type="button"
                          onClick={() => { setPrototypeFormatFilter(id); setPrototypePage(1) }}
                          className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer inline-flex items-center gap-1.5 ${
                            prototypeFormatFilter === id ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs' : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200'
                          }`}
                        >
                          <span>{label}</span>
                          <span className="text-[10px] px-1.5 rounded font-mono bg-zinc-200/60 dark:bg-zinc-700/60">{cnt}</span>
                        </button>
                      ))}
                    </div>

                    <form onSubmit={handleResearchSubmit} className="flex items-center gap-2 max-w-md w-full">
                      <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Niş konusu filtrele..." className={`${INPUT_CLS} flex-1 !py-1.5`} />
                      <button type="submit" disabled={!query.trim() || isChannelResearching} className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-zinc-900 dark:bg-zinc-100 dark:text-zinc-900 text-white disabled:opacity-40 cursor-pointer shrink-0">
                        {isChannelResearching ? 'Analiz...' : 'Analiz Et'}
                      </button>
                      {channelIdeas.length > 0 && (
                        <button type="button" onClick={() => { setQuery(''); setPrototypePage(1); useFlowStore.setState({ channelIdeas: [] }) }} className="px-2.5 py-1.5 rounded-xl text-xs text-zinc-500 border border-zinc-200 dark:border-zinc-700 cursor-pointer">Sıfırla</button>
                      )}
                    </form>
                  </div>

                  {filteredPrototypes.length === 0 ? (
                    <div className="p-8 rounded-xl border border-dashed border-zinc-200 dark:border-zinc-700 text-center text-xs text-zinc-500">
                      {isLiveStatsLoading || isChannelResearching ? 'Gerçek YouTube niş ve kanal verileri taranıyor...' : 'Henüz gerçek içerik verisi bulunamadı.'}
                    </div>
                  ) : (
                    <div className="space-y-4 pt-1">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {paginatedPrototypes.map((proto) => (
                          <ProtoCard
                            key={proto.id}
                            proto={proto}
                            onStart={() => selectIdeaFromChannelAndStartFlow(activeChannel.id, { id: proto.id, title: proto.prototypeTitle, hook: proto.prototypeHook, score: proto.viralScore })}
                          />
                        ))}
                      </div>
                      <Pager page={safePrototypePage} total={totalPrototypePages} count={filteredPrototypes.length} onPrev={() => setPrototypePage((p) => Math.max(1, p - 1))} onNext={() => setPrototypePage((p) => Math.min(totalPrototypePages, p + 1))} />
                    </div>
                  )}
                </div>
              )}

              {activeWorkspaceTab === 'analytics' && (
                <div className="space-y-6">
                  <TimeFilterBar value={timeCategory} onChange={setTimeCategory} />
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className={`${CARD_CLS} !p-3.5 space-y-1 shadow-2xs`}>
                      <span className="text-[11px] font-medium text-zinc-500 uppercase block">Ort. Video İzlenme</span>
                      <span className={`text-2xl font-bold font-mono block ${TXT_MAIN}`}>{liveStats?.avg_views_formatted || (isLiveStatsLoading ? '...' : '-')}</span>
                      <span className="text-[10px] text-emerald-600 dark:text-emerald-400 block">{allVideos.length > 0 ? `${allVideos.length} İçerik` : 'Bekleniyor'}</span>
                    </div>
                    <div className={`${CARD_CLS} !p-3.5 space-y-1 shadow-2xs`}>
                      <span className="text-[11px] font-medium text-zinc-500 uppercase block">İncelenen Videolar</span>
                      <span className="text-2xl font-bold font-mono block text-blue-600 dark:text-blue-400">{totalVideosCount} Video</span>
                      <span className="text-[10px] text-zinc-400 block">Uzun Format</span>
                    </div>
                    <div className={`${CARD_CLS} !p-3.5 space-y-1 shadow-2xs`}>
                      <span className="text-[11px] font-medium text-zinc-500 uppercase block">İncelenen Shorts</span>
                      <span className="text-2xl font-bold font-mono block text-cyan-600 dark:text-cyan-400">{totalShortsCount} Shorts</span>
                      <span className="text-[10px] text-zinc-400 block">9:16 Kurgu</span>
                    </div>
                  </div>

                  <div className="space-y-6">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      <ChannelTrendChart
                        variant="video"
                        analytics={effectiveAnalytics}
                        title="Uzun Videolar İzlenme Trendi"
                        subtitle="3-içerik hareketli ortalama (Rolling Avg)"
                        colorTheme="blue"
                      />
                      <ChannelTrendChart
                        variant="short"
                        analytics={effectiveAnalytics}
                        title="Shorts İzlenme Trendi"
                        subtitle="3-içerik hareketli ortalama (Rolling Avg)"
                        colorTheme="cyan"
                      />
                    </div>
                    <ChannelDistributionChart analytics={effectiveAnalytics} />
                  </div>
                </div>
              )}

              {activeWorkspaceTab === 'tables' && (
                <div className="space-y-6">
                  <TimeFilterBar value={timeCategory} onChange={setTimeCategory} />
                  {([
                    ['Uzun Videolar', 'Taranan yatay videolar.', `${filteredLongVideos.length} Video`, 'VİDEO', 'blue', filteredLongVideos, 'Uzun video bulunamadı.'],
                    ['Shorts Videoları', 'Taranan 9:16 Shorts dikey videoları.', `${filteredShortVideos.length} Shorts`, 'SHORTS', 'cyan', filteredShortVideos, 'Shorts bulunamadı.'],
                  ] as const).map(([title, subtitle, countLabel, badgeText, badgeColor, videos, emptyMessage]) => (
                    <VideoPerformanceTable
                      key={badgeColor}
                      title={title}
                      subtitle={subtitle}
                      countLabel={countLabel}
                      badgeText={badgeText}
                      badgeColor={badgeColor}
                      videos={videos}
                      isLoading={isLiveStatsLoading}
                      emptyMessage={emptyMessage}
                    />
                  ))}
                </div>
              )}

              {activeWorkspaceTab === 'templates' && (
                <div className="space-y-4" data-testid="channel-templates-panel">
                  <input
                    ref={tplFileRef}
                    type="file"
                    accept="video/mp4,video/quicktime,video/webm,video/*"
                    className="hidden"
                    data-testid="template-file-input"
                    onChange={(e) => {
                      const f = e.target.files?.[0]
                      if (f) {
                        const filePath = (f as File & { path?: string }).path || f.name
                        const previewUrl = (f as File & { path?: string }).path || URL.createObjectURL(f)
                        void createTemplateFromPicked(filePath, previewUrl)
                      }
                      e.target.value = ''
                    }}
                  />
                  <div className={`pb-3 border-b ${B_SEP}`}>
                    <h4 className={`text-sm font-bold ${TXT_MAIN} flex items-center gap-2`}>
                      <span>Shorts Kurgu Şablonları</span>
                      <span className={`text-xs font-mono px-2.5 py-0.5 rounded-full font-bold border ${BADGE_CYAN}`}>
                        {activeTemplates.length} Şablon
                      </span>
                    </h4>
                    <p className="text-xs text-zinc-500 mt-0.5">9:16 şablon ekleyin. Üzerine gelindiğinde video oynatılır, tıklandığında stüdyo açılır.</p>
                  </div>

                  <div className="flex flex-wrap items-center gap-7 p-4 min-h-[380px] overflow-x-auto select-none" style={{ perspective: '1400px' }}>
                    {activeTemplates.map((tpl) => (
                      <ShortsTemplateCard
                        key={tpl.id}
                        template={tpl}
                        onSelect={(t) => {
                          setSelectedShortsTemplate({ ...t, slots: t.slots?.length ? t.slots : defaultSlots(t.durationSec) })
                          setTplTopic(t.title)
                        }}
                        onDelete={handleDeleteShortsTemplate}
                      />
                    ))}
                    <AddShortsTemplateCard onClick={handlePickShortsTemplate} disabled={isPickingFile} />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (channels.length === 0) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-hidden p-6 justify-center items-center studio-grid-lines">
        {isChannelsLoading ? (
          <div className="text-xs font-mono text-zinc-400">KANALLAR YÜKLENİYOR...</div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 select-none my-auto" data-testid="empty-channels-state">
            <button
              type="button"
              onClick={() => setIsCreating(true)}
              className="w-32 h-32 rounded-full border-2 border-dashed border-zinc-300 dark:border-zinc-700 hover:border-zinc-400 hover:bg-white/90 dark:hover:bg-zinc-800 flex items-center justify-center transition-all cursor-pointer group shadow-xs text-4xl font-light text-zinc-500"
              aria-label="Create first channel"
            >
              +
            </button>
            <h2 className="text-[26px] font-bold text-zinc-800 dark:text-zinc-100 mt-6 tracking-tight">Create first channel</h2>
            <p className="text-sm text-zinc-500 max-w-sm mt-2 leading-relaxed">
              Channels are where your team collaborates.<br />Get started by creating one.
            </p>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex-1 w-full h-full relative overflow-auto select-none p-6 studio-grid-lines" data-testid="channels-canvas">
      <div className="absolute top-5 left-6 z-30 pointer-events-none select-none">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 uppercase tracking-wider">Kanal Çalışma Masaları</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-zinc-200/70 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">{channels.length}</span>
        </div>
        <p className="text-[11px] text-zinc-400 mt-0.5">Kartları sürükleyip konumlandırabilirsiniz</p>
      </div>

      <div className="absolute top-5 right-6 z-40">
        <button type="button" onClick={() => setIsCreating(true)} className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-zinc-900 dark:bg-zinc-100 dark:text-zinc-900 text-white shadow-2xs cursor-pointer">
          <span className="text-sm leading-none">+</span>
          <span>Yeni Kanal Ekle</span>
        </button>
      </div>

      <div className="relative w-full h-[1400px] min-w-[900px]">
        {channels.map((channel, i) => (
          <DraggableChannelCard
            key={channel.id}
            channel={channel}
            initialPosition={positions[channel.id] ?? { x: 56 + (i % 2) * 400, y: 72 + ~~(i / 2) * 290 }}
            onPositionChange={handlePositionChange}
            onSelect={(id) => selectChannel(id)}
            onDelete={(id) => { if (confirm(`"${channel.name}" silinsin mi?`)) void deleteChannel(id) }}
          />
        ))}
      </div>
    </div>
  )
}
