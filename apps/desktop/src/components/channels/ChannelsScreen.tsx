import { useState, useMemo, useEffect, useRef, type FC, type FormEvent } from 'react'
import { useFlowStore } from '../../store/flowStore'
import type { RealVideoItem } from '../../store/flowTypes'
import { toSafeAssetUrl, secureInvoke } from '../../lib/securityGuard'
import { DraggableChannelCard, type Position } from './DraggableChannelCard'
import { ChannelTrendChart } from './charts/ChannelTrendChart'
import { ChannelDistributionChart } from './charts/ChannelDistributionChart'
import {
  resolveChannelAvatar,
  generateDefaultAiSummary,
  formatCount,
  deriveFallbackAnalytics,
} from './channelMetadata'
import { deriveGlobalViralPrototypes } from './globalPrototypes'
import { getIpcClient } from '../../lib/ipc'

const SpinIcon = ({ className = 'w-3.5 h-3.5' }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h5M20 20v-5h-5M4 9a9 9 0 0114.6-3.6L20 7M20 15a9 9 0 01-14.6 3.6L4 17" />
  </svg>
)

const YtBadge = () => (
  <svg className="w-3.5 h-3.5 text-white" viewBox="0 0 24 24" fill="currentColor">
    <path d="M9 16V8l8 4-8 4z" />
  </svg>
)

const FilmIcon = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 10l5-3v10l-5-3M4 6h11v12H4z" />
  </svg>
)

const BoltIcon = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>
)

const TrendUpIcon = () => (
  <svg className="w-3 h-3 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 17l6-6 4 4 8-8M21 12V7h-5" />
  </svg>
)

const ArrowRightIcon = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7-7 7M21 12H3" />
  </svg>
)

const CARD_CLS = 'p-6 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs'
const card3dStyle = (isHovered: boolean) => ({
  transform: isHovered
    ? 'perspective(1200px) rotateY(0deg) rotateX(0deg) translateY(-8px) scale(1.02)'
    : 'perspective(1200px) rotateY(-8deg) rotateX(4deg) translateZ(0)',
  transformStyle: 'preserve-3d' as const,
  transition: 'transform 0.35s cubic-bezier(0.16,1,0.3,1),box-shadow 0.35s ease,border-color 0.35s ease',
  boxShadow: isHovered
    ? '0 20px 35px -10px rgba(0,0,0,0.4),0 0 0 1px rgba(255,255,255,0.12)'
    : '0 15px 25px -8px rgba(0,0,0,0.4),0 0 0 1px rgba(255,255,255,0.06)',
})

const VideoPerformanceTable: FC<{
  title: string
  subtitle: string
  countLabel: string
  badgeText: string
  badgeColor: 'blue' | 'cyan'
  videos: RealVideoItem[]
  isLoading: boolean
  emptyMessage: string
}> = ({ title, subtitle, countLabel, badgeText, badgeColor, videos, isLoading, emptyMessage }) => (
  <div className={`${CARD_CLS} space-y-4`}>
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#F3F4F6] dark:border-zinc-800">
      <div className="flex items-center gap-2.5">
        <div
          className={`w-7 h-7 rounded-lg ${
            badgeColor === 'blue'
              ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
              : 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400'
          } flex items-center justify-center`}
        >
          {badgeColor === 'blue' ? <FilmIcon /> : <BoltIcon />}
        </div>
        <div>
          <h3 className="text-base font-bold text-[#111827] dark:text-zinc-100 tracking-tight">{title}</h3>
          <p className="text-xs text-zinc-500">{subtitle}</p>
        </div>
      </div>

      <span
        className={`text-xs px-3 py-1 rounded-full font-mono font-medium ${
          badgeColor === 'blue'
            ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-800/60'
            : 'bg-cyan-50 dark:bg-cyan-950/40 text-cyan-600 dark:text-cyan-400 border-cyan-200 dark:border-cyan-800/60'
        } border self-start sm:self-auto`}
      >
        {countLabel}
      </span>
    </div>

    {isLoading ? (
      <div className="p-8 text-center space-y-2">
        <span className="inline-block w-5 h-5 border-2 border-zinc-400 border-t-zinc-900 rounded-full animate-spin" />
        <p className="text-xs text-zinc-500 font-mono">Veriler çekiliyor...</p>
      </div>
    ) : videos.length === 0 ? (
      <div className="p-8 rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800 text-center text-xs text-zinc-500">
        {emptyMessage}
      </div>
    ) : (
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-zinc-200 dark:border-zinc-800 text-zinc-500 uppercase tracking-wider text-[10px]">
              <th className="py-2.5 px-3">#</th>
              <th className="py-2.5 px-3">Format</th>
              <th className="py-2.5 px-3">Resmi Başlık</th>
              <th className="py-2.5 px-3">Yayınlanma</th>
              <th className="py-2.5 px-3 text-right">Gerçek İzlenme</th>
              <th className="py-2.5 px-3 text-right">Bağlantı</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/60 font-mono">
            {videos.map((vid, idx) => (
              <tr key={vid.id || idx} className="hover:bg-zinc-50/80 dark:hover:bg-zinc-800/40">
                <td className="py-2.5 px-3 text-zinc-400">{idx + 1}</td>
                <td className="py-2.5 px-3">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold border font-sans ${
                      badgeColor === 'blue'
                        ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20'
                        : 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20'
                    }`}
                  >
                    {badgeText}
                  </span>
                </td>
                <td className="py-2.5 px-3 font-sans font-medium text-zinc-900 dark:text-zinc-100 max-w-md truncate">
                  {vid.title}
                </td>
                <td className="py-2.5 px-3 font-sans text-zinc-500 text-[11px] whitespace-nowrap">
                  {vid.published_text || (vid.days_ago != null ? `${vid.days_ago} gün önce` : '-')}
                </td>
                <td className="py-2.5 px-3 text-right font-bold text-zinc-900 dark:text-zinc-100">
                  {vid.view_count != null ? formatCount(vid.view_count) : 'Bilinmiyor'}
                </td>
                <td className="py-2.5 px-3 text-right font-sans">
                  {vid.url ? (
                    <a
                      href={vid.url}
                      target="_blank"
                      rel="noreferrer"
                      className={`hover:underline font-semibold text-[11px] ${
                        badgeColor === 'blue'
                          ? 'text-blue-600 dark:text-blue-400'
                          : 'text-cyan-600 dark:text-cyan-400'
                      }`}
                    >
                      İzle ↗
                    </a>
                  ) : (
                    '-'
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </div>
)

export interface ChannelShortsTemplate {
  id: string
  channelId: string
  title: string
  filePath: string
  format: '9:16'
  addedAt: number
}

const ShortsTemplateCard: FC<{
  template: ChannelShortsTemplate
  onSelect: (tpl: ChannelShortsTemplate) => void
  onDelete: (id: string) => void
}> = ({ template, onSelect, onDelete }) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isHovered, setIsHovered] = useState(false)

  const handleMouseEnter = () => {
    setIsHovered(true)
    if (videoRef.current) {
      videoRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch(() => {})
    }
  }

  const handleMouseLeave = () => {
    setIsHovered(false)
    if (videoRef.current) {
      videoRef.current.pause()
      videoRef.current.currentTime = 0
      setIsPlaying(false)
    }
  }

  return (
    <div
      onClick={() => onSelect(template)}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={card3dStyle(isHovered)}
      className="relative w-48 sm:w-52 aspect-[9/16] shrink-0 rounded-2xl overflow-hidden bg-black border border-zinc-800 hover:border-zinc-500 dark:hover:border-zinc-400 cursor-pointer group select-none transition-colors"
    >
      <video
        ref={videoRef}
        src={toSafeAssetUrl(template.filePath)}
        className="w-full h-full object-cover"
        muted
        loop
        playsInline
        preload="metadata"
      />

      {/* Üst Rozet & Silme Butonu */}
      <div className="absolute top-2.5 inset-x-2.5 flex items-center justify-between z-10">
        <span className="px-2 py-0.5 rounded-md bg-black/75 backdrop-blur-xs text-[10px] font-mono font-bold text-cyan-400 border border-cyan-500/30">
          9:16 SHORTS
        </span>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onDelete(template.id)
          }}
          className="w-6 h-6 rounded-full bg-black/75 backdrop-blur-xs text-zinc-400 hover:text-white hover:bg-black border border-white/10 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
          title="Şablonu Kaldır"
          aria-label="Şablonu Kaldır"
        >
          ✕
        </button>
      </div>

      {/* Ortadaki Play Simgesi (Mouse üzerinde değilken) */}
      {!isPlaying && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-11 h-11 rounded-full bg-black/50 backdrop-blur-xs border border-white/20 flex items-center justify-center text-white/90 shadow-md text-sm">
            ▶
          </div>
        </div>
      )}

      {/* Alt Karartma ve Başlık */}
      <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-black/90 via-black/50 to-transparent z-10 pointer-events-none">
        <h5 className="text-xs font-bold text-white truncate drop-shadow-xs leading-tight">
          {template.title}
        </h5>
        <p className="text-[10px] font-mono text-zinc-400 truncate mt-0.5">
          {template.filePath.split(/[\\/]/).pop()}
        </p>
      </div>
    </div>
  )
}

const AddShortsTemplateCard: FC<{
  onClick: () => void
  disabled?: boolean
}> = ({ onClick, disabled }) => {
  const [isHovered, setIsHovered] = useState(false)

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={card3dStyle(isHovered)}
      className={`relative w-48 sm:w-52 aspect-[9/16] shrink-0 rounded-2xl border-2 border-dashed flex flex-col items-center justify-center p-4 cursor-pointer group select-none focus:outline-none transition-all ${
        isHovered
          ? 'border-zinc-400 dark:border-zinc-500 bg-zinc-100 dark:bg-zinc-800/90 text-zinc-900 dark:text-zinc-100 ring-1 ring-zinc-300 dark:ring-zinc-700'
          : 'border-zinc-300 dark:border-zinc-800 bg-zinc-100/40 dark:bg-zinc-950/40 text-zinc-400'
      }`}
      title="Yeni Shorts Şablonu Yükle"
      aria-label="Yeni Shorts Şablonu Yükle"
    >
      <div
        className={`w-13 h-13 rounded-full border flex items-center justify-center transition-all duration-300 text-2xl font-light ${
          isHovered
            ? 'bg-zinc-200 dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 border-zinc-400 dark:border-zinc-500 scale-110 shadow-md'
            : 'bg-white dark:bg-zinc-900 border-zinc-300 dark:border-zinc-700 text-zinc-600 dark:text-zinc-300 shadow-xs'
        }`}
      >
        +
      </div>
      <span
        className={`text-xs font-bold font-mono tracking-wider mt-4 transition-colors ${
          isHovered ? 'text-zinc-900 dark:text-zinc-100' : 'text-zinc-700 dark:text-zinc-300'
        }`}
      >
        + ŞABLON EKLE
      </span>
      <span className="text-[10px] text-zinc-400 dark:text-zinc-500 font-mono mt-1">
        9:16 Shorts (MP4/MOV)
      </span>
    </button>
  )
}

const TAB_BLUE = 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400 bg-blue-50/40 dark:bg-blue-950/20'
const TAB_CYAN = 'border-cyan-600 text-cyan-600 dark:border-cyan-400 dark:text-cyan-400 bg-cyan-50/40 dark:bg-cyan-950/20'
const INPUT_CLS = 'w-full px-3.5 py-2.5 rounded-xl bg-white dark:bg-zinc-800 border border-[#E5E7EB] dark:border-zinc-700 text-xs text-[#111827] dark:text-zinc-100 placeholder-[#9CA3AF] focus:outline-none focus:border-[#4B5563]'

const WORKSPACE_TABS = [
  { id: 'prototypes', label: 'Fikir & Viral Prototipleme', act: TAB_BLUE, bAct: 'bg-blue-600 text-white' },
  { id: 'analytics', label: 'Performans & Trendler', act: TAB_CYAN, bAct: 'bg-cyan-600 text-white' },
  { id: 'tables', label: 'İçerik Tabloları & Arşiv', act: TAB_BLUE, bAct: 'bg-blue-600 text-white' },
  { id: 'templates', label: 'Shorts Şablonları', act: TAB_CYAN, bAct: 'bg-cyan-600 text-white' },
] as const

const TimeFilterBar: FC<{
  value: '1_month' | '1_year' | 'all'
  onChange: (val: '1_month' | '1_year' | 'all') => void
}> = ({ value, onChange }) => (
  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-2xl bg-white dark:bg-zinc-900 border border-[#E5E7EB] dark:border-zinc-800 shadow-xs">
    <div>
      <h4 className="text-xs font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
        Zaman Aralığı &amp; Kapsam
      </h4>
      <p className="text-[11px] text-zinc-500">
        Grafikler ve tablolar seçilen kategoriye göre anlık hesaplanır.
      </p>
    </div>

    <div className="inline-flex items-center p-1 rounded-xl bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/80 dark:border-zinc-700/80 self-start sm:self-auto">
      {(
        [
          { id: '1_month', label: 'Son 1 Ay', badge: '30G' },
          { id: '1_year', label: 'Son 1 Sene', badge: '1Y' },
          { id: 'all', label: 'Tüm Zamanlar', badge: 'Tümü' },
        ] as const
      ).map((cat) => (
        <button
          key={cat.id}
          type="button"
          onClick={() => onChange(cat.id)}
          className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer inline-flex items-center gap-1.5 ${
            value === cat.id
              ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs border border-zinc-200/60 dark:border-zinc-700'
              : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200'
          }`}
        >
          <span>{cat.label}</span>
          <span
            className={`text-[10px] px-1 py-0.2 rounded font-mono ${
              value === cat.id
                ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300'
                : 'bg-zinc-200/60 dark:bg-zinc-700/60 text-zinc-500'
            }`}
          >
            {cat.badge}
          </span>
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
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<'prototypes' | 'analytics' | 'tables' | 'templates'>('prototypes')

  const TPL_KEY = 'hustler_channel_shorts_templates_v2'
  const [channelShortsTemplates, setChannelShortsTemplates] = useState<Record<string, ChannelShortsTemplate[]>>(() => {
    try {
      const raw = localStorage.getItem(TPL_KEY)
      return raw ? (JSON.parse(raw) as Record<string, ChannelShortsTemplate[]>) : {}
    } catch {
      return {}
    }
  })
  const [isPickingFile, setIsPickingFile] = useState(false)
  const [selectedShortsTemplate, setSelectedShortsTemplate] = useState<ChannelShortsTemplate | null>(null)

  const saveTemplates = (updated: Record<string, ChannelShortsTemplate[]>) => {
    setChannelShortsTemplates(updated)
    try {
      localStorage.setItem(TPL_KEY, JSON.stringify(updated))
    } catch {
      // ignore
    }
  }

  const handlePickShortsTemplate = async () => {
    if (!activeChannel) return
    setIsPickingFile(true)
    try {
      const selected = await secureInvoke<string | null>('plugin:dialog|open', {
        options: {
          title: '9:16 Shorts Şablon Videosu Seçin',
          filters: [{ name: 'Video', extensions: ['mp4', 'mov', 'webm', 'mkv'] }],
          multiple: false,
          directory: false,
        },
      })
      if (!selected || typeof selected !== 'string') return
      const rawFileName = selected.split(/[\\/]/).pop() || 'Shorts_Sablonu.mp4'
      const newTemplate: ChannelShortsTemplate = {
        id: `tpl_${Date.now()}`,
        channelId: activeChannel.id,
        title: rawFileName.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' '),
        filePath: selected,
        format: '9:16',
        addedAt: Date.now(),
      }
      saveTemplates({
        ...channelShortsTemplates,
        [activeChannel.id]: [newTemplate, ...(channelShortsTemplates[activeChannel.id] || [])],
      })
    } catch {
      // ignore
    } finally {
      setIsPickingFile(false)
    }
  }

  const handleDeleteShortsTemplate = (tplId: string) => {
    if (!activeChannel) return
    saveTemplates({
      ...channelShortsTemplates,
      [activeChannel.id]: (channelShortsTemplates[activeChannel.id] || []).filter((t) => t.id !== tplId),
    })
  }

  // İlk yüklemede kartların boşluktaki başlangıç konumlarını belirle
  const initialPositions = useMemo(() => {
    const map: Record<string, Position> = {}
    channels.forEach((ch, idx) => {
      // 2 sütunlu ferah başlangıç grid'i (sonrasında serbest sürüklenebilir)
      const col = idx % 2
      const row = Math.floor(idx / 2)
      map[ch.id] = {
        x: 56 + col * 400,
        y: 72 + row * 290,
      }
    })
    return map
  }, [channels])

  const handlePositionChange = (id: string, pos: Position) => {
    setPositions((prev) => ({ ...prev, [id]: pos }))
  }

  const activeChannel = channels.find((c) => c.id === activeChannelId) ?? null
  const liveStats = activeChannel ? channelLiveStats[activeChannel.id] : null

  // Aktif kanal değiştiğinde AI özetini senkronize et ve gerekirse canlı istatistikleri çek
  useEffect(() => {
    if (activeChannel) {
      const hasCustom =
        activeChannel.ai_summary &&
        !activeChannel.ai_summary.includes('İçerik analizi bekleniyor')
      setSummaryInput(
        hasCustom
          ? activeChannel.ai_summary || ''
          : generateDefaultAiSummary(
              activeChannel.name,
              activeChannel.description,
              activeChannel.channel_url,
              liveStats
            )
      )
      setDeskImgFailed(false)
      setIsEditingAiSummary(false)

      if (!channelLiveStats[activeChannel.id]) {
        void fetchChannelLiveStats(activeChannel.id)
      }
    }
  }, [activeChannel?.id, activeChannel?.ai_summary, liveStats])

  const handleCreateSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !channelUrl.trim()) return

    const created = await createChannel({
      name: name.trim(),
      channel_url: channelUrl.trim(),
      description: description.trim(),
    })

    if (created) {
      setName('')
      setChannelUrl('')
      setDescription('')
      setIsCreating(false)
    }
  }

  const handleResearchSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!activeChannel || !query.trim() || isChannelResearching) return
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
    const fallback = generateDefaultAiSummary(
      activeChannel.name,
      activeChannel.description,
      activeChannel.channel_url,
      liveStats
    )
    try {
      const topTitles = [...(liveStats?.shorts || []), ...(liveStats?.videos || [])]
        .sort((a, b) => (b.view_count ?? 0) - (a.view_count ?? 0))
        .slice(0, 4)
        .map((v) => `${v.title} (${formatCount(v.view_count)})`)
        .join(', ')
      const promptMsg = `${activeChannel.name} kanalı için (Abone: ${liveStats?.subscribers_formatted || 'Bilinmiyor'}, Ort. İzlenme: ${liveStats?.avg_views_formatted || 'Bilinmiyor'}, Niş: ${liveStats?.niche_query || activeChannel.description || 'Genel'}, En çok izlenenler: ${topTitles || 'Yok'}) maksimum 4 kısa satırlık [NİŞ], [PERFORMANS], [KURGU RİTMİ] ve [AKSİYON] başlıklarıyla gerçekçi kanal kimlik özeti çıkar.`
      const res = await getIpcClient().proxyRequest('POST', '/api/v1/pipeline/chat', {
        message: promptMsg,
        history: [],
        active_view: 'channels',
        channel_id: activeChannel.id,
      })
      const body = (res?.body ?? {}) as { reply?: string }
      const refreshed = body.reply?.replace(/\*/g, '').trim() || fallback
      setSummaryInput(refreshed)
      await updateChannelSummary(activeChannel.id, refreshed)
    } catch {
      setSummaryInput(fallback)
      await updateChannelSummary(activeChannel.id, fallback)
    } finally {
      setIsRegeneratingAi(false)
    }
  }

  // Canlı YouTube Video ve Shorts Listesi (Ham & Genişletilmiş Veri Kümeleri)
  const rawLongVideos: RealVideoItem[] = useMemo(() => {
    if (!liveStats) return []
    return (liveStats.videos || []).map((v) => ({ ...v, type: 'video' as const }))
  }, [liveStats])

  const rawShortVideos: RealVideoItem[] = useMemo(() => {
    if (!liveStats) return []
    return (liveStats.shorts || []).map((s) => ({ ...s, type: 'short' as const }))
  }, [liveStats])

  // 3 Zaman Kategorisine Göre Dinamik Filtreleme (Son 1 Ay, Son 1 Sene, Tüm Zamanlar)
  const filteredLongVideos: RealVideoItem[] = useMemo(() => {
    if (timeCategory === 'all') return rawLongVideos
    const maxDays = timeCategory === '1_month' ? 30 : 365
    return rawLongVideos.filter((v, idx) => {
      const days = v.days_ago ?? (idx * 6 + 1)
      return days <= maxDays
    })
  }, [rawLongVideos, timeCategory])

  const filteredShortVideos: RealVideoItem[] = useMemo(() => {
    if (timeCategory === 'all') return rawShortVideos
    const maxDays = timeCategory === '1_month' ? 30 : 365
    return rawShortVideos.filter((s, idx) => {
      const days = s.days_ago ?? (idx * 3 + 1)
      return days <= maxDays
    })
  }, [rawShortVideos, timeCategory])

  const allVideos: RealVideoItem[] = useMemo(() => {
    return [...rawLongVideos, ...rawShortVideos]
  }, [rawLongVideos, rawShortVideos])

  // Global Viral Benchmark & Kanal Formatına Göre Prototip Havuzu
  const prototypes = useMemo(() => {
    if (!activeChannel) return []
    return deriveGlobalViralPrototypes(
      activeChannel.name,
      activeChannel.description || '',
      activeChannel.channel_url,
      channelIdeas,
      liveStats
    )
  }, [activeChannel?.name, activeChannel?.description, activeChannel?.channel_url, channelIdeas, liveStats])

  const filteredPrototypes = useMemo(() => {
    if (prototypeFormatFilter === 'all') return prototypes
    return prototypes.filter((p) => p.format === prototypeFormatFilter)
  }, [prototypes, prototypeFormatFilter])

  const shortsPrototypesCount = useMemo(
    () => prototypes.filter((p) => p.format === 'short').length,
    [prototypes]
  )
  const videosPrototypesCount = useMemo(
    () => prototypes.filter((p) => p.format === 'video').length,
    [prototypes]
  )

  // 1. Durum: Kanal Oluşturma Formu Açık
  if (isCreating) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 justify-center items-center">
        <form
          onSubmit={handleCreateSubmit}
          className={`w-full max-w-xl ${CARD_CLS} space-y-4`}
        >
          <div className="flex items-center justify-between pb-2 border-b border-[#F3F4F6] dark:border-zinc-800">
            <h3 className="text-sm font-semibold text-[#111827] dark:text-zinc-100 tracking-tight">
              Yeni Kanal Oluştur
            </h3>
            <button
              type="button"
              onClick={() => setIsCreating(false)}
              className="text-xs text-[#6B7280] hover:text-[#111827] dark:hover:text-zinc-200 transition-colors cursor-pointer"
            >
              Kapat
            </button>
          </div>

          <div className="space-y-3.5">
            <div className="space-y-1">
              <label className="text-[12px] font-medium text-[#4B5563] dark:text-zinc-300">
                Kanal Başlığı *
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="örn. Bilim & Gelecek Shorts"
                className={INPUT_CLS}
              />
            </div>

            <div className="space-y-1">
              <label className="text-[12px] font-medium text-[#4B5563] dark:text-zinc-300">
                Kanal URL Adresi *
              </label>
              <input
                type="url"
                required
                value={channelUrl}
                onChange={(e) => setChannelUrl(e.target.value)}
                placeholder="örn. https://youtube.com/@bilimgelecek"
                className={INPUT_CLS}
              />
            </div>

            <div className="space-y-1">
              <label className="text-[12px] font-medium text-[#4B5563] dark:text-zinc-300">
                Açıklama / Niş Bilgisi
              </label>
              <textarea
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="örn. Popüler bilim, astrofizik ve teknoloji odaklı dikey video kurguları"
                className={`${INPUT_CLS} resize-none`}
              />
            </div>
          </div>

          <div className="flex justify-end gap-2.5 pt-3">
            <button
              type="button"
              onClick={() => setIsCreating(false)}
              className="px-4 py-2 rounded-xl text-xs font-medium text-[#6B7280] dark:text-zinc-400 hover:bg-[#F3F4F6] dark:hover:bg-zinc-800 transition-colors cursor-pointer"
            >
              İptal
            </button>
            <button
              type="submit"
              disabled={!name.trim() || !channelUrl.trim()}
              className="px-5 py-2 rounded-xl text-xs font-semibold bg-[#111827] hover:bg-[#1F2937] text-white shadow-xs transition-all cursor-pointer disabled:opacity-50"
            >
              Kanalı Kaydet
            </button>
          </div>
        </form>
      </div>
    )
  }

  // 2. Durum: Kanal İçi Çalışma Masası Açık
  if (activeChannel) {
    const avatarData = resolveChannelAvatar(activeChannel.channel_url, activeChannel.name)
    const effectiveAvatarUrl = liveStats?.avatar_url || activeChannel.avatar_url || avatarData.avatarUrl

    const totalVideosCount = filteredLongVideos.length
    const totalShortsCount = filteredShortVideos.length
    const totalContent = totalVideosCount + totalShortsCount
    const videoRatio = totalContent > 0 ? Math.round((totalVideosCount / totalContent) * 100) : 50
    const shortsRatio = totalContent > 0 ? 100 - videoRatio : 50

    const effectiveAnalytics =
      timeCategory === 'all' && liveStats?.analytics && liveStats.analytics.has_data
        ? liveStats.analytics
        : deriveFallbackAnalytics(filteredLongVideos, filteredShortVideos)

    return (
      <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 select-text">
        <div className="max-w-7xl mx-auto w-full space-y-6">
          {/* Üst Navigasyon Çubuğu: Geri Dön & Yenile & Canlı Durum */}
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => selectChannel(null)}
              className="px-3.5 py-1.5 rounded-xl text-xs font-medium text-[#4B5563] hover:text-[#111827] bg-white dark:bg-zinc-900 border border-[#E5E7EB] dark:border-zinc-800 shadow-2xs hover:bg-[#F9FAFB] dark:hover:bg-zinc-800 transition-colors cursor-pointer"
            >
              ← Kanallara Dön (Çalışma Alanı)
            </button>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={() => fetchChannelLiveStats(activeChannel.id, true)}
                disabled={isLiveStatsLoading}
                className="px-3 py-1.5 rounded-xl text-xs font-medium bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-300 shadow-2xs transition-all cursor-pointer inline-flex items-center gap-1.5"
                title="YouTube üzerinden verileri yeniden çek"
              >
                <SpinIcon className={`w-3.5 h-3.5 ${isLiveStatsLoading ? 'animate-spin' : ''}`} />
                <span>{isLiveStatsLoading ? 'Veriler Çekiliyor...' : 'Canlı Verileri Yenile'}</span>
              </button>

              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-[11px] font-mono text-emerald-700 dark:text-emerald-300">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>ORİJİNAL YOUTUBE VERİSİ</span>
              </div>
            </div>
          </div>

          {/* Üst Sekme Navigasyonu (Sekme Opsiyonları Üstte Yer Alır) */}
          <div className="flex items-center border-b border-zinc-200 dark:border-zinc-800 gap-2 overflow-x-auto">
            {WORKSPACE_TABS.map((tab) => {
              const isActive = activeWorkspaceTab === tab.id
              const tplCount = (activeChannel && channelShortsTemplates[activeChannel.id]) ? channelShortsTemplates[activeChannel.id].length : 0
              const count =
                tab.id === 'prototypes'
                  ? prototypes.length
                  : tab.id === 'tables'
                  ? totalContent
                  : tab.id === 'templates'
                  ? tplCount
                  : 'Canlı'
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveWorkspaceTab(tab.id)}
                  className={`px-4 py-2.5 text-xs font-semibold rounded-t-xl transition-all cursor-pointer border-b-2 flex items-center gap-2 shrink-0 ${
                    isActive ? tab.act : 'border-transparent text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200'
                  }`}
                >
                  <span>{tab.label}</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono font-bold ${
                      isActive ? tab.bAct : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400'
                    }`}
                  >
                    {count}
                  </span>
                </button>
              )
            })}
          </div>

          {/* 2 Sütunlu Ana Grid: Sol Profil & AI Strateji Paneli vs Sağ Ferah Çalışma Masası */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* SOL SÜTUN: Profil Kutusu + AI Kanal Algısı (4 Kolon) */}
            <div className="lg:col-span-4 space-y-4">
              {/* 1. Kanal Profil Kutusu */}
              <div className={`${CARD_CLS} space-y-4`}>
                {/* Profil Fotoğrafı & Başlık */}
                <div className="flex items-start gap-3.5">
                  <div className="relative w-16 h-16 sm:w-20 sm:h-20 rounded-2xl overflow-hidden border-2 border-white dark:border-zinc-800 shadow-md ring-2 ring-zinc-200/80 dark:ring-zinc-700 bg-zinc-100 dark:bg-zinc-800 shrink-0 flex items-center justify-center">
                    {!deskImgFailed ? (
                      <img
                        src={effectiveAvatarUrl}
                        alt={activeChannel.name}
                        onError={() => setDeskImgFailed(true)}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span className="text-2xl font-bold text-zinc-800 dark:text-zinc-200">
                        {avatarData.fallbackLetter}
                      </span>
                    )}
                    <div
                      className="absolute -bottom-1 -right-1 bg-red-600 rounded-full p-1 ring-2 ring-white dark:ring-zinc-900"
                      title="Resmi YouTube Kanalı"
                    >
                      <YtBadge />
                    </div>
                  </div>

                  <div className="space-y-1 min-w-0 flex-1">
                    <h2 className="text-base sm:text-lg font-bold tracking-tight text-[#111827] dark:text-zinc-100 truncate">
                      {liveStats?.channel_name || activeChannel.name}
                    </h2>
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-cyan-50 text-cyan-700 dark:bg-cyan-950/60 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-800">
                      ✓ Doğrulanmış Kanal
                    </span>
                    <a
                      href={activeChannel.channel_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-[#2563EB] dark:text-blue-400 hover:underline block font-mono truncate pt-0.5"
                    >
                      {activeChannel.channel_url} ↗
                    </a>
                  </div>
                </div>

                {/* Niş Açıklaması */}
                {(liveStats?.description || activeChannel.description) && (
                  <p className="text-xs text-[#4B5563] dark:text-zinc-400 leading-relaxed line-clamp-3 pt-1 border-t border-zinc-100 dark:border-zinc-800/80">
                    {liveStats?.description || activeChannel.description}
                  </p>
                )}

                {/* 2'li Hızlı İstatistik Kartları */}
                <div className="grid grid-cols-2 gap-2 pt-1 border-t border-zinc-100 dark:border-zinc-800/80">
                  <div className="p-2.5 rounded-xl bg-[#F9FAFB] dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800">
                    <span className="text-[10px] uppercase font-medium text-zinc-400 block">Resmi Abone</span>
                    <span className="text-base font-bold font-mono text-zinc-900 dark:text-zinc-100 block">
                      {liveStats?.subscribers_formatted || (isLiveStatsLoading ? '...' : 'Bilinmiyor')}
                    </span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[#F9FAFB] dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800">
                    <span className="text-[10px] uppercase font-medium text-zinc-400 block">İçerik Havuzu</span>
                    <span className="text-base font-bold font-mono text-zinc-900 dark:text-zinc-100 block">
                      {totalContent}
                    </span>
                  </div>
                </div>

                {/* Format Dağılım Çubuğu */}
                <div className="space-y-1.5 pt-1 border-t border-zinc-100 dark:border-zinc-800/80">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-zinc-500 font-medium">Format Dengesi</span>
                    <span className="font-mono text-zinc-700 dark:text-zinc-300">%{videoRatio} / %{shortsRatio}</span>
                  </div>
                  <div className="w-full h-2 rounded-full overflow-hidden bg-zinc-200 dark:bg-zinc-700 flex">
                    <div style={{ width: `${videoRatio}%` }} className="bg-blue-600" />
                    <div style={{ width: `${shortsRatio}%` }} className="bg-cyan-500" />
                  </div>
                </div>

                {/* Platform Entegrasyon Rozeti */}
                <div className="p-2.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200/60 dark:border-zinc-800 text-[11px] space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-600 dark:text-zinc-400 font-medium">YouTube:</span>
                    <span className="font-semibold text-cyan-600 dark:text-cyan-400 font-mono text-[10px]">Bağlandı (Doğrulandı)</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-500">TikTok / IG:</span>
                    <span className="text-zinc-400 font-mono text-[10px]">Bağlantı Yok</span>
                  </div>
                </div>
              </div>

              {/* 2. Yapay Zeka Kanal Algısı & Stratejik Kimlik Kartı */}
              <div className={`${CARD_CLS} space-y-3`}>
                <div className="flex items-center justify-between pb-2.5 border-b border-[#F3F4F6] dark:border-zinc-800">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
                      <BoltIcon />
                    </div>
                    <div>
                      <h3 className="text-xs font-bold text-[#111827] dark:text-zinc-100 tracking-tight">
                        AI Kanal Algısı &amp; Kimlik
                      </h3>
                      <p className="text-[10px] text-zinc-500">
                        Üretim bu stratejik ton ile kurgulanır.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      disabled={isRegeneratingAi}
                      onClick={handleRegenerateAi}
                      className="px-2 py-1 rounded-lg text-[10px] font-medium text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 transition-colors cursor-pointer inline-flex items-center gap-1"
                      title="AI ile kanalı yeniden analiz et"
                    >
                      <SpinIcon className={`w-2.5 h-2.5 ${isRegeneratingAi ? 'animate-spin' : ''}`} />
                      <span>{isRegeneratingAi ? '...' : 'Yenile'}</span>
                    </button>

                    {!isEditingAiSummary ? (
                      <button
                        type="button"
                        onClick={() => setIsEditingAiSummary(true)}
                        className="px-2.5 py-1 rounded-lg text-[10px] font-semibold bg-[#111827] text-white hover:bg-zinc-800 transition-colors cursor-pointer"
                      >
                        Düzenle
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={handleSaveSummary}
                        className="px-2.5 py-1 rounded-lg text-[10px] font-semibold bg-emerald-600 hover:bg-emerald-700 text-white transition-colors cursor-pointer"
                      >
                        Kaydet
                      </button>
                    )}
                  </div>
                </div>

                {isEditingAiSummary ? (
                  <div className="space-y-1.5">
                    <textarea
                      rows={6}
                      value={summaryInput}
                      onChange={(e) => setSummaryInput(e.target.value)}
                      className="w-full text-xs font-mono p-2.5 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-[#F9FAFB] dark:bg-zinc-800/80 text-[#111827] dark:text-zinc-100 focus:outline-none focus:border-zinc-900 leading-relaxed resize-y"
                    />
                    <div className="flex justify-end">
                      <button
                        type="button"
                        onClick={() => setIsEditingAiSummary(false)}
                        className="text-[10px] text-zinc-500 hover:underline cursor-pointer"
                      >
                        İptal
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="whitespace-pre-line text-[11px] text-zinc-700 dark:text-zinc-300 leading-relaxed bg-[#F9FAFB] dark:bg-zinc-800/40 p-3 rounded-xl border border-zinc-200/80 dark:border-zinc-800 font-sans select-text">
                    {summaryInput}
                  </div>
                )}
              </div>
            </div>

            {/* SAĞ SÜTUN: Ferah Çalışma Masası (8 Kolon) */}
            <div className="lg:col-span-8 space-y-6">
              {/* SEKME 1: FİKİR & VİRAL PROTOTİPLEME */}
              {activeWorkspaceTab === 'prototypes' && (
                <div className={`${CARD_CLS} space-y-5`}>
                  {/* Üst Başlık & Durum Rozetleri */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F3F4F6] dark:border-zinc-800">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
                        <BoltIcon />
                      </div>
                      <div>
                        <h3 className="text-base font-bold text-[#111827] dark:text-zinc-100 tracking-tight">
                          Global Viral Benchmark &amp; Format Prototipleme
                        </h3>
                        <p className="text-xs text-zinc-500">
                          Kanal nişine göre dünyada yüksek etkileşim yakalamış doğrulanmış viral referanslar.
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-cyan-50 text-cyan-700 dark:bg-cyan-950/60 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-800 flex items-center gap-1.5 font-semibold">
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
                        BENCHMARK AKTİF
                      </span>
                      <span className="text-xs font-mono font-medium px-2.5 py-1 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
                        {prototypes.length} Referans
                      </span>
                    </div>
                  </div>

                  {/* Kontroller: Sol Format Sekmeleri vs Sağ Kompakt Niş Filtreleme */}
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    {/* Format Filtre Sekmeleri */}
                    <div className="inline-flex items-center p-1 rounded-xl bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/80 dark:border-zinc-700/80 self-start">
                      {([
                        { id: 'all', label: 'Tümü', cnt: prototypes.length, act: 'text-zinc-900 dark:text-zinc-100 border-zinc-200/60 dark:border-zinc-700', bCls: 'bg-zinc-200/60 dark:bg-zinc-700/60 text-zinc-600 dark:text-zinc-300' },
                        { id: 'short', label: 'Dikey Shorts (9:16)', cnt: shortsPrototypesCount, act: 'text-cyan-600 dark:text-cyan-400 border-cyan-200/60 dark:border-cyan-800/40', bCls: 'bg-cyan-50 dark:bg-cyan-950/60 text-cyan-600 dark:text-cyan-400' },
                        { id: 'video', label: 'Yatay Video (16:9)', cnt: videosPrototypesCount, act: 'text-blue-600 dark:text-blue-400 border-blue-200/60 dark:border-blue-800/40', bCls: 'bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400' },
                      ] as const).map((f) => (
                        <button
                          key={f.id}
                          type="button"
                          onClick={() => setPrototypeFormatFilter(f.id)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer inline-flex items-center gap-1.5 ${
                            prototypeFormatFilter === f.id
                              ? `bg-white dark:bg-zinc-900 shadow-xs border ${f.act}`
                              : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200'
                          }`}
                        >
                          <span>{f.label}</span>
                          <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${f.bCls}`}>{f.cnt}</span>
                        </button>
                      ))}
                    </div>

                    {/* Sağ: Kompakt Niş Konu Analiz Formu */}
                    <form onSubmit={handleResearchSubmit} className="flex items-center gap-2 max-w-md w-full">
                      <div className="relative flex-1">
                        <input
                          type="text"
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                          placeholder="Alt niş konusu filtrele / derin analiz..."
                          className="w-full pl-8 pr-3 py-1.5 rounded-xl bg-[#F9FAFB] dark:bg-zinc-800/80 border border-[#E5E7EB] dark:border-zinc-700 text-xs text-[#111827] dark:text-zinc-100 placeholder-[#9CA3AF] focus:outline-none focus:border-[#111827] focus:bg-white dark:focus:bg-zinc-800"
                        />
                        <span className="text-xs text-zinc-400 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none">⌕</span>
                      </div>

                      <button
                        type="submit"
                        disabled={!query.trim() || isChannelResearching}
                        className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-[#111827] hover:bg-[#1F2937] dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white text-white disabled:opacity-40 transition-all cursor-pointer shrink-0 inline-flex items-center gap-1.5 shadow-2xs"
                      >
                        {isChannelResearching ? (
                          <>
                            <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            <span>İnceleniyor...</span>
                          </>
                        ) : (
                          <span>Derin Analiz Et</span>
                        )}
                      </button>

                      {channelIdeas.length > 0 && (
                        <button
                          type="button"
                          onClick={() => {
                            setQuery('')
                            useFlowStore.setState({ channelIdeas: [] })
                          }}
                          title="Otomatik vitrine geri dön"
                          className="px-2.5 py-1.5 rounded-xl text-xs text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 cursor-pointer"
                        >
                          Sıfırla
                        </button>
                      )}
                    </form>
                  </div>

                  {/* Ferah Yatay Stüdyo Benchmark Kartları */}
                  <div className="space-y-4 pt-1">
                    {filteredPrototypes.length === 0 ? (
                      <div className="p-8 rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800 text-center text-xs text-zinc-500">
                        {isLiveStatsLoading || isChannelResearching
                          ? 'Gerçek YouTube niş ve kanal verileri taranıyor...'
                          : 'Henüz gerçek içerik verisi bulunamadı. Üstteki arama kutusundan konu taraması başlatın veya Canlı Verileri Yenile butonuna tıklayın.'}
                      </div>
                    ) : (
                      filteredPrototypes.map((proto) => {
                      const isShort = proto.format === 'short'
                      return (
                        <div
                          key={proto.id}
                          className={`p-5 rounded-2xl border transition-all duration-200 space-y-3.5 ${
                            isShort
                              ? 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:border-cyan-400 dark:hover:border-cyan-600/60 shadow-xs'
                              : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:border-blue-400 dark:hover:border-blue-600/60 shadow-xs'
                          }`}
                        >
                          {/* Üst Şerit: Rozetler, Başlık ve Harici Link */}
                          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-3 border-b border-zinc-100 dark:border-zinc-800/80">
                            <div className="space-y-1.5 flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-bold border font-mono ${
                                    isShort
                                      ? 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20'
                                      : 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20'
                                  }`}
                                >
                                  {isShort ? 'SHORTS (9:16)' : 'VİDEO (16:9)'}
                                </span>
                                <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                                  {proto.categoryLabel}
                                </span>
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 font-semibold">
                                  SKOR: {proto.viralScore}/100
                                </span>
                              </div>

                              <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 leading-snug">
                                {proto.globalTitle}
                              </h4>
                            </div>

                            <div className="flex sm:flex-col items-end gap-1.5 shrink-0">
                              <a
                                href={proto.globalUrl}
                                target="_blank"
                                rel="noreferrer"
                                className={`text-xs font-semibold ${
                                  isShort ? 'text-cyan-600 dark:text-cyan-400' : 'text-blue-600 dark:text-blue-400'
                                } hover:underline inline-flex items-center gap-0.5 font-mono`}
                                title="YouTube üzerinde global referans içeriği aç"
                              >
                                <span>YouTube Referansı</span>
                                <span>↗</span>
                              </a>

                              <div className="flex items-center gap-2 text-[11px] font-mono text-zinc-500">
                                <span className="flex items-center gap-1 font-semibold text-zinc-800 dark:text-zinc-200">
                                  <TrendUpIcon />
                                  {proto.globalViewsFormatted}
                                </span>
                                <span>•</span>
                                <span>{proto.durationText}</span>
                                <span>•</span>
                                <span className="text-cyan-600 dark:text-cyan-400 font-medium">{proto.retentionBadge}</span>
                              </div>
                            </div>
                          </div>

                          {/* Orta Gövde: 2 Kolonlu Ferah Karşılaştırma */}
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                            {/* Sol: Viral Kanca Dinamiği */}
                            <div className="p-3.5 rounded-xl bg-[#F9FAFB] dark:bg-zinc-800/40 border border-zinc-200/70 dark:border-zinc-800 space-y-1.5">
                              <span className="text-[10px] uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-500 block">
                                Neden Viral Oldu? (Kanca Stratejisi)
                              </span>
                              <p className="text-xs text-zinc-600 dark:text-zinc-300 leading-relaxed font-sans">
                                {proto.hookAnalysis}
                              </p>
                            </div>

                            {/* Sağ: Kanalınız İçin Prototip Kurgu */}
                            <div className="p-3.5 rounded-xl bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200/60 dark:border-blue-800/40 space-y-1.5">
                              <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400">
                                <span>Kanalınız İçin Prototip Kurgu</span>
                                <span className="text-zinc-400 font-normal lowercase font-sans">hazır kurgu</span>
                              </div>
                              <p className="text-xs font-bold text-zinc-900 dark:text-zinc-100">
                                {proto.prototypeTitle}
                              </p>
                              <p className="text-xs text-zinc-600 dark:text-zinc-400 italic leading-relaxed">
                                &ldquo;{proto.prototypeHook}&rdquo;
                              </p>
                            </div>
                          </div>

                          {/* Alt Aksiyon Çubuğu */}
                          <div className="pt-1 flex items-center justify-between gap-3">
                            <span className="text-xs text-zinc-400 font-medium hidden sm:inline">
                              Tek tıkla üretim akışına aktar ve senaryoyu oluştur
                            </span>
                            <button
                              type="button"
                              onClick={() => {
                                selectIdeaFromChannelAndStartFlow(activeChannel.id, {
                                  id: proto.id,
                                  title: proto.prototypeTitle,
                                  hook: proto.prototypeHook,
                                  score: proto.viralScore,
                                })
                              }}
                              className="w-full sm:w-auto px-4 py-2 rounded-xl text-xs font-semibold bg-[#111827] hover:bg-[#1F2937] dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white text-white shadow-xs transition-all cursor-pointer inline-flex items-center justify-center gap-1.5"
                            >
                              <span>Bu Prototiple Başla (Senaryo)</span>
                              <ArrowRightIcon />
                            </button>
                          </div>
                        </div>
                      )
                    })
                    )}
                  </div>
                </div>
              )}

          {/* SEKME 2: PERFORMANS & TRENDLER */}
          {activeWorkspaceTab === 'analytics' && (
            <div className="space-y-6">
              {/* Zaman Kategorisi Filtre Çubuğu */}
              <TimeFilterBar value={timeCategory} onChange={setTimeCategory} />

              {/* Örneklem Performans Metrikleri Grid'i (3 Kolon) */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  { title: 'Ort. Video İzlenme', val: liveStats?.avg_views_formatted || (isLiveStatsLoading ? '...' : 'Veri Yok'), sub: allVideos.length > 0 ? `${allVideos.length} Gerçek İçerik İncelendi` : 'Canlı Veri Bekleniyor', vCls: 'text-zinc-900 dark:text-zinc-100', sCls: 'text-emerald-600 dark:text-emerald-400' },
                  { title: 'İncelenen Videolar', val: `${totalVideosCount} Video`, sub: 'Uzun Format Kurgular', vCls: 'text-blue-600 dark:text-blue-400', sCls: 'text-zinc-400' },
                  { title: 'İncelenen Shorts', val: `${totalShortsCount} Shorts`, sub: 'Dikey 9:16 Kurgular', vCls: 'text-cyan-600 dark:text-cyan-400', sCls: 'text-zinc-400' },
                ].map((m) => (
                  <div key={m.title} className="p-3.5 rounded-xl bg-white dark:bg-zinc-900 border border-[#E5E7EB] dark:border-zinc-800 space-y-1 shadow-2xs">
                    <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider block">{m.title}</span>
                    <span className={`text-2xl font-bold font-mono block ${m.vCls}`}>{m.val}</span>
                    <span className={`text-[10px] font-medium block ${m.sCls}`}>{m.sub}</span>
                  </div>
                ))}
              </div>

              {/* Analitik Grafikler (2 Ayrı Çizgi Grafiği + Daire Grafiği) */}
              <div className="space-y-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Grafik 1: Uzun Videolar Çizgi Grafiği */}
                  <ChannelTrendChart
                    variant="video"
                    analytics={effectiveAnalytics}
                    title="Uzun Videolar İzlenme Trendi"
                    subtitle="3-içerik hareketli ortalama (Rolling Avg)"
                    colorTheme="blue"
                  />

                  {/* Grafik 2: Shorts Videoları Çizgi Grafiği */}
                  <ChannelTrendChart
                    variant="short"
                    analytics={effectiveAnalytics}
                    title="Shorts İzlenme Trendi"
                    subtitle="3-içerik hareketli ortalama (Rolling Avg)"
                    colorTheme="cyan"
                  />
                </div>

                {/* Daire Grafiği */}
                <ChannelDistributionChart analytics={effectiveAnalytics} />
              </div>
            </div>
          )}

          {/* SEKME 3: İÇERİK TABLOLARI & ARŞİV */}
          {activeWorkspaceTab === 'tables' && (
            <div className="space-y-6">
              {/* Zaman Kategorisi Filtre Çubuğu */}
              <TimeFilterBar value={timeCategory} onChange={setTimeCategory} />

              {/* TABLO 1: Uzun Videolar İçerik ve Performans Tablosu */}
              <VideoPerformanceTable
                title="Uzun Videolar İçerik ve Performans Tablosu"
                subtitle="YouTube üzerinden taranan herkese açık yatay videolar."
                countLabel={`${filteredLongVideos.length} Video Listelendi`}
                badgeText="VİDEO"
                badgeColor="blue"
                videos={filteredLongVideos}
                isLoading={isLiveStatsLoading}
                emptyMessage="Bu zaman aralığında uzun video bulunamadı."
              />

              {/* TABLO 2: Shorts Videoları İçerik ve Performans Tablosu */}
              <VideoPerformanceTable
                title="Shorts İçerik ve Performans Tablosu"
                subtitle="YouTube üzerinden taranan herkese açık 9:16 Shorts dikey videoları."
                countLabel={`${filteredShortVideos.length} Shorts Listelendi`}
                badgeText="SHORTS"
                badgeColor="cyan"
                videos={filteredShortVideos}
                isLoading={isLiveStatsLoading}
                emptyMessage="Bu zaman aralığında Shorts bulunamadı."
              />

              {/* TABLO 3: Kanal Analiz & Sistem Metrikleri Doğrulama Tablosu */}
              <div className={`${CARD_CLS} space-y-4`}>
                <div>
                  <h3 className="text-base font-bold text-[#111827] dark:text-zinc-100 tracking-tight">
                    Kanal Analitik &amp; Doğrulama Tablosu
                  </h3>
                  <p className="text-xs text-zinc-500">
                    API verileri ve SQLite veritabanı doğrulama dökümü.
                  </p>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse font-sans">
                    <thead>
                      <tr className="border-b border-zinc-200 dark:border-zinc-800 text-zinc-500 uppercase tracking-wider text-[10px]">
                        <th className="py-2.5 px-3">Metrik Tanımı</th>
                        <th className="py-2.5 px-3">Ölçülen Değer</th>
                        <th className="py-2.5 px-3">Veri Kaynağı</th>
                        <th className="py-2.5 px-3 text-right">Doğrulama Durumu</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/60 font-mono text-xs">
                      {[
                        ['YouTube Resmi Abone', liveStats?.subscribers_formatted || 'Bilinmiyor', 'YouTube API', 1, ''],
                        ['Taranan Gerçek Video', `${totalVideosCount} Video`, 'YouTube /videos', 1, ''],
                        ['Taranan Gerçek Shorts', `${totalShortsCount} Shorts`, 'YouTube /shorts', 1, ''],
                        ['Örneklem Ort. İzlenme', liveStats?.avg_views_formatted || 'Hesaplanmadı', 'YouTube Ortalama', 1, ''],
                        ['Yerel Üretilen Senaryolar', `${activeChannel.metrics.total_scripts} Senaryo`, 'SQLite scripts', 0, 'text-cyan-600 dark:text-cyan-400'],
                        ['Kanal Araştırma Havuzu', `${activeChannel.metrics.total_research} Fikir`, 'SQLite discovery', 0, ''],
                        ['Sistem Viral Puanı', `${activeChannel.metrics.avg_viral_score ?? 0} / 100`, 'AI Algoritma', 0, 'text-cyan-600 dark:text-cyan-400'],
                      ].map(([label, val, src, isLive, valCls], idx) => (
                        <tr key={idx} className="hover:bg-zinc-50/80 dark:hover:bg-zinc-800/40">
                          <td className="py-3 px-3 font-sans font-medium text-zinc-900 dark:text-zinc-100">{label}</td>
                          <td className={`py-3 px-3 font-bold ${valCls || 'text-zinc-900 dark:text-zinc-100'}`}>{val}</td>
                          <td className="py-3 px-3 font-sans text-zinc-500">{src}</td>
                          <td className="py-3 px-3 text-right">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border font-sans ${
                              isLive
                                ? 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20'
                                : 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20'
                            }`}>
                              {isLive ? 'Canlı Doğrulandı' : 'SQLite Bütünlüğü'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* SEKME 4: KANAL SHORTS ŞABLONLARI (TIKTOK / REELS TARZI 9:16 VİDEO GRİD'İ) */}
          {activeWorkspaceTab === 'templates' && (
            <div className="space-y-4" data-testid="channel-templates-panel">
              <div className="flex items-center justify-between pb-3 border-b border-[#F3F4F6] dark:border-zinc-800">
                <div>
                  <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 tracking-tight flex items-center gap-2">
                    <span>Shorts Kurgu Şablonları</span>
                    <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 font-bold border border-cyan-500/20">
                      {((activeChannel && channelShortsTemplates[activeChannel.id]) || []).length} Şablon
                    </span>
                  </h4>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    3D derinlikli 9:16 video şablonları. Fare ile üzerine gelindiğinde otomatik oynatılır, tıklandığında kurgu detayına girilir.
                  </p>
                </div>
              </div>

              {/* 3D Yatay Açılı Monokrom Şablon Vitrini: Şablonlar ve Sağında Her Zaman Duran (+) Ekle Kartı */}
              <div className="flex flex-wrap items-center gap-7 p-4 min-h-[380px] overflow-x-auto" style={{ perspective: '1400px' }}>
                {((activeChannel && channelShortsTemplates[activeChannel.id]) || []).map((tpl) => (
                  <ShortsTemplateCard
                    key={tpl.id}
                    template={tpl}
                    onSelect={(t) => setSelectedShortsTemplate(t)}
                    onDelete={(id) => handleDeleteShortsTemplate(id)}
                  />
                ))}

                {/* Eğer hiç şablon yoksa tek başına durur; şablon varsa en son eklenen şablonun sağında yer alır */}
                <AddShortsTemplateCard
                  onClick={handlePickShortsTemplate}
                  disabled={isPickingFile}
                />
              </div>

              {/* Tıklanan Şablonun İçerisine Girildiğinde Açılan Kurgu ve Oynatıcı Paneli */}
              {selectedShortsTemplate && (
                <div
                  className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-xs"
                  onClick={() => setSelectedShortsTemplate(null)}
                >
                  <div
                    className="bg-white dark:bg-zinc-900 rounded-3xl p-5 max-w-sm w-full space-y-4 border border-zinc-200 dark:border-zinc-800 shadow-2xl relative select-none"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="flex items-center justify-between pb-2 border-b border-zinc-100 dark:border-zinc-800">
                      <div className="min-w-0 pr-2">
                        <span className="text-[10px] font-mono font-bold text-zinc-400 dark:text-zinc-500 block uppercase tracking-wider">
                          Shorts Şablon İnceleme
                        </span>
                        <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 truncate">
                          {selectedShortsTemplate.title}
                        </h4>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSelectedShortsTemplate(null)}
                        className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 p-1 text-xs cursor-pointer"
                        title="Kapat"
                      >
                        ✕
                      </button>
                    </div>

                    <div className="relative aspect-[9/16] w-full rounded-2xl overflow-hidden bg-black ring-1 ring-zinc-800 shadow-inner">
                      <video
                        src={toSafeAssetUrl(selectedShortsTemplate.filePath)}
                        className="w-full h-full object-cover"
                        controls
                        autoPlay
                        playsInline
                        loop
                      />
                    </div>

                    <div className="space-y-1 text-xs">
                      <p className="font-mono text-[10.5px] text-zinc-400 truncate" title={selectedShortsTemplate.filePath}>
                        {selectedShortsTemplate.filePath}
                      </p>
                      <span className="inline-flex items-center gap-1.5 text-cyan-600 dark:text-cyan-400 text-[11px] font-semibold font-mono">
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500" />
                        Kurgu ve Ritim Analizine Hazır (9:16)
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={() => {
                        setSelectedShortsTemplate(null)
                      }}
                      className="w-full py-2.5 rounded-xl text-xs font-bold bg-black dark:bg-white text-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 shadow-xs transition-all cursor-pointer"
                    >
                      Bu Şablonla İçerik ve Ses Kurgusu Başlat →
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  // 3. Durum: Henüz Hiç Kanal Yok (Tam Prototip: Create First Channel)
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

  // 4. Durum: Kanallar Var — Boşlukta Sürüklenebilir ve Taşınabilir Kutucuklar (Canvas)
  return (
    <div
      className="flex-1 w-full h-full relative overflow-auto select-none p-6 studio-grid-lines"
      data-testid="channels-canvas"
    >
      {/* Sol Üst Bilgi: Kanallar Başlığı ve Sayacı */}
      <div className="absolute top-5 left-6 z-30 pointer-events-none select-none">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 uppercase tracking-wider">
            Kanal Çalışma Masaları
          </span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-zinc-200/70 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">
            {channels.length}
          </span>
        </div>
        <p className="text-[11px] text-zinc-400 dark:text-zinc-500 mt-0.5">
          Kartları serbestçe sürükleyip çalışma alanınıza göre konumlandırabilirsiniz
        </p>
      </div>

      {/* Sağ Üst Sabit Aksiyon: Yeni Kanal Butonu */}
      <div className="absolute top-5 right-6 z-40">
        <button
          type="button"
          onClick={() => setIsCreating(true)}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-[#111827] dark:bg-zinc-100 dark:text-zinc-900 text-white hover:bg-zinc-800 dark:hover:bg-white shadow-2xs transition-all cursor-pointer"
        >
          <span className="text-sm leading-none">+</span>
          <span>Yeni Kanal Ekle</span>
        </button>
      </div>

      {/* Boşlukta Sürüklenebilir Kanal Kutucukları */}
      <div className="relative w-full h-[1400px] min-w-[900px]">
        {channels.map((channel) => {
          const currentPos = positions[channel.id] ?? initialPositions[channel.id] ?? { x: 56, y: 72 }
          return (
            <DraggableChannelCard
              key={channel.id}
              channel={channel}
              initialPosition={currentPos}
              onPositionChange={handlePositionChange}
              onSelect={(id) => selectChannel(id)}
              onDelete={(id) => {
                if (confirm(`"${channel.name}" kanalını silmek istediğinizden emin misiniz?`)) {
                  void deleteChannel(id)
                }
              }}
            />
          )
        })}
      </div>
    </div>
  )
}
