import { useState, useMemo, useEffect, type FC, type FormEvent } from 'react'
import { useFlowStore } from '../../store/flowStore'
import type { RealVideoItem } from '../../store/flowTypes'
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

const SpinIcon = ({ className = 'w-3.5 h-3.5' }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M16 9h5v-.001M3 20v-5m0 0h5m-5 0l3 3a8 8 0 0014-4M4 10a8 8 0 0114-4l3 3m0-5v5" />
  </svg>
)

const YtBadge = () => (
  <svg className="w-3.5 h-3.5 text-white" viewBox="0 0 24 24" fill="currentColor">
    <path d="M19.6 3.2c-3.6-.3-11.6-.3-15.2 0C.5 3.5.05 5.8 0 12c.05 6.2.5 8.5 4.4 8.8 3.6.3 11.6.3 15.2 0 3.9-.3 4.4-2.6 4.4-8.8-.03-6.2-.5-8.5-4.4-8.8zM9 16V8l8 4-8 4z" />
  </svg>
)

const FilmIcon = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z"
    />
  </svg>
)

const BoltIcon = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>
)

const TrendUpIcon = () => (
  <svg className="w-3 h-3 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.5 4.5 7.5-7.5M21 8.25V3m0 0h-5.25" />
  </svg>
)

const ArrowRightIcon = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
  </svg>
)

const CARD_CLS = 'p-6 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs'

const VideoPerformanceTable: FC<{
  title: string
  subtitle: string
  countLabel: string
  badgeText: string
  badgeColor: 'blue' | 'rose'
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
              : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
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
            : 'bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 border-rose-200 dark:border-rose-800/60'
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
                        : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'
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
                      className="text-blue-600 dark:text-blue-400 hover:underline font-semibold text-[11px]"
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

const WORKSPACE_TABS = [
  { id: 'prototypes', label: 'Fikir & Viral Prototipleme', act: 'border-purple-600 text-purple-600 dark:border-purple-400 dark:text-purple-400 bg-purple-50/40 dark:bg-purple-950/20', bAct: 'bg-purple-600 text-white' },
  { id: 'analytics', label: 'Performans & Trendler', act: 'border-emerald-600 text-emerald-600 dark:border-emerald-400 dark:text-emerald-400 bg-emerald-50/40 dark:bg-emerald-950/20', bAct: 'bg-emerald-600 text-white' },
  { id: 'tables', label: 'İçerik Tabloları & Arşiv', act: 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400 bg-blue-50/40 dark:bg-blue-950/20', bAct: 'bg-blue-600 text-white' },
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
  const channels = useFlowStore((s) => s.channels)
  const activeChannelId = useFlowStore((s) => s.activeChannelId)
  const isChannelsLoading = useFlowStore((s) => s.isChannelsLoading)
  const isChannelResearching = useFlowStore((s) => s.isChannelResearching)
  const channelIdeas = useFlowStore((s) => s.channelIdeas)
  const channelLiveStats = useFlowStore((s) => s.channelLiveStats)
  const isLiveStatsLoading = useFlowStore((s) => s.isLiveStatsLoading)
  const selectChannel = useFlowStore((s) => s.selectChannel)
  const createChannel = useFlowStore((s) => s.createChannel)
  const deleteChannel = useFlowStore((s) => s.deleteChannel)
  const updateChannelSummary = useFlowStore((s) => s.updateChannelSummary)
  const fetchChannelLiveStats = useFlowStore((s) => s.fetchChannelLiveStats)
  const researchChannelContent = useFlowStore((s) => s.researchChannelContent)
  const selectIdeaFromChannelAndStartFlow = useFlowStore(
    (s) => s.selectIdeaFromChannelAndStartFlow
  )

  const [isCreating, setIsCreating] = useState(false)
  const [name, setName] = useState('')
  const [channelUrl, setChannelUrl] = useState('')
  const [description, setDescription] = useState('')
  const [query, setQuery] = useState('')

  // Sürüklenebilir kartların serbest boşluktaki (x, y) konumları
  const [positions, setPositions] = useState<Record<string, Position>>({})

  // Kanal Detay Masası Durumları (AI Algı Düzenleme & Avatar & Zaman Filtresi)
  const [isEditingAiSummary, setIsEditingAiSummary] = useState(false)
  const [summaryInput, setSummaryInput] = useState('')
  const [deskImgFailed, setDeskImgFailed] = useState(false)
  const [isRegeneratingAi, setIsRegeneratingAi] = useState(false)
  const [timeCategory, setTimeCategory] = useState<'1_month' | '1_year' | 'all'>('all')
  const [prototypeFormatFilter, setPrototypeFormatFilter] = useState<'all' | 'short' | 'video'>('all')
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<'prototypes' | 'analytics' | 'tables'>('prototypes')

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
      setSummaryInput(
        activeChannel.ai_summary ||
          generateDefaultAiSummary(activeChannel.name, activeChannel.description, activeChannel.channel_url)
      )
      setDeskImgFailed(false)
      setIsEditingAiSummary(false)

      if (!channelLiveStats[activeChannel.id]) {
        void fetchChannelLiveStats(activeChannel.id)
      }
    }
  }, [activeChannel?.id, activeChannel?.ai_summary])

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
    setTimeout(async () => {
      const refreshed = generateDefaultAiSummary(activeChannel.name, activeChannel.description, activeChannel.channel_url)
      setSummaryInput(refreshed)
      await updateChannelSummary(activeChannel.id, refreshed)
      setIsRegeneratingAi(false)
    }, 500)
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
      channelIdeas
    )
  }, [activeChannel?.name, activeChannel?.description, activeChannel?.channel_url, channelIdeas])

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
                className="w-full px-3.5 py-2.5 rounded-xl bg-white dark:bg-zinc-800 border border-[#E5E7EB] dark:border-zinc-700 text-xs text-[#111827] dark:text-zinc-100 placeholder-[#9CA3AF] focus:outline-none focus:border-[#4B5563]"
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
                className="w-full px-3.5 py-2.5 rounded-xl bg-white dark:bg-zinc-800 border border-[#E5E7EB] dark:border-zinc-700 text-xs text-[#111827] dark:text-zinc-100 placeholder-[#9CA3AF] focus:outline-none focus:border-[#4B5563]"
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
                className="w-full px-3.5 py-2.5 rounded-xl bg-white dark:bg-zinc-800 border border-[#E5E7EB] dark:border-zinc-700 text-xs text-[#111827] dark:text-zinc-100 placeholder-[#9CA3AF] focus:outline-none focus:border-[#4B5563] resize-none"
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
              const count = tab.id === 'prototypes' ? prototypes.length : tab.id === 'tables' ? totalContent : 'Canlı'
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
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                      <svg className="w-2.5 h-2.5 stroke-[3]" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                      Doğrulanmış Kanal
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
                    <div style={{ width: `${shortsRatio}%` }} className="bg-rose-500" />
                  </div>
                </div>

                {/* Platform Entegrasyon Rozeti */}
                <div className="p-2.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200/60 dark:border-zinc-800 text-[11px] space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-600 dark:text-zinc-400 font-medium">YouTube:</span>
                    <span className="font-semibold text-emerald-600 dark:text-emerald-400 font-mono text-[10px]">Bağlandı (Doğrulandı)</span>
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
                    <div className="w-6 h-6 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
                      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
                      </svg>
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
                      <div className="w-8 h-8 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center shrink-0">
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
                        </svg>
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
                      <span className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 flex items-center gap-1.5 font-semibold">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
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
                      <button
                        type="button"
                        onClick={() => setPrototypeFormatFilter('all')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer inline-flex items-center gap-1.5 ${
                          prototypeFormatFilter === 'all'
                            ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs border border-zinc-200/60 dark:border-zinc-700'
                            : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200'
                        }`}
                      >
                        <span>Tümü</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-zinc-200/60 dark:bg-zinc-700/60 text-zinc-600 dark:text-zinc-300">
                          {prototypes.length}
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setPrototypeFormatFilter('short')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer inline-flex items-center gap-1.5 ${
                          prototypeFormatFilter === 'short'
                            ? 'bg-white dark:bg-zinc-900 text-rose-600 dark:text-rose-400 shadow-xs border border-rose-200/60 dark:border-rose-900/40'
                            : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200'
                        }`}
                      >
                        <span>Dikey Shorts (9:16)</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400">
                          {shortsPrototypesCount}
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setPrototypeFormatFilter('video')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer inline-flex items-center gap-1.5 ${
                          prototypeFormatFilter === 'video'
                            ? 'bg-white dark:bg-zinc-900 text-blue-600 dark:text-blue-400 shadow-xs border border-blue-200/60 dark:border-blue-900/40'
                            : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200'
                        }`}
                      >
                        <span>Yatay Video (16:9)</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400">
                          {videosPrototypesCount}
                        </span>
                      </button>
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
                        <svg className="w-3.5 h-3.5 text-zinc-400 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                        </svg>
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
                    {filteredPrototypes.map((proto) => {
                      const isShort = proto.format === 'short'
                      return (
                        <div
                          key={proto.id}
                          className={`p-5 rounded-2xl border transition-all duration-200 space-y-3.5 ${
                            isShort
                              ? 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:border-rose-400 dark:hover:border-rose-600/60 shadow-xs'
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
                                      ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'
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
                                className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-0.5 font-mono"
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
                                <span className="text-emerald-600 dark:text-emerald-400 font-medium">{proto.retentionBadge}</span>
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
                            <div className="p-3.5 rounded-xl bg-purple-50/50 dark:bg-purple-950/20 border border-purple-200/60 dark:border-purple-800/40 space-y-1.5">
                              <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-purple-600 dark:text-purple-400">
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
                    })}
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
                {/* Örneklem Ortalama İzlenme */}
                <div className="p-3.5 rounded-xl bg-white dark:bg-zinc-900 border border-[#E5E7EB] dark:border-zinc-800 space-y-1 shadow-2xs">
                  <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider block">
                    Ort. Video İzlenme
                  </span>
                  <span className="text-2xl font-bold font-mono text-zinc-900 dark:text-zinc-100 block">
                    {liveStats?.avg_views_formatted || (isLiveStatsLoading ? '...' : 'Veri Yok')}
                  </span>
                  <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium block">
                    {allVideos.length > 0 ? `${allVideos.length} Gerçek İçerik İncelendi` : 'Canlı Veri Bekleniyor'}
                  </span>
                </div>

                {/* Taranan Videolar */}
                <div className="p-3.5 rounded-xl bg-white dark:bg-zinc-900 border border-[#E5E7EB] dark:border-zinc-800 space-y-1 shadow-2xs">
                  <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider block">
                    İncelenen Videolar
                  </span>
                  <span className="text-2xl font-bold font-mono text-blue-600 dark:text-blue-400 block">
                    {totalVideosCount} Video
                  </span>
                  <span className="text-[10px] text-zinc-400 font-medium block">
                    Uzun Format Kurgular
                  </span>
                </div>

                {/* Taranan Shorts */}
                <div className="p-3.5 rounded-xl bg-white dark:bg-zinc-900 border border-[#E5E7EB] dark:border-zinc-800 space-y-1 shadow-2xs">
                  <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider block">
                    İncelenen Shorts
                  </span>
                  <span className="text-2xl font-bold font-mono text-rose-600 dark:text-rose-400 block">
                    {totalShortsCount} Shorts
                  </span>
                  <span className="text-[10px] text-zinc-400 font-medium block">
                    Dikey 9:16 Kurgular
                  </span>
                </div>
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
                    colorTheme="rose"
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
                badgeColor="rose"
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
                        { label: 'YouTube Resmi Abone', val: liveStats?.subscribers_formatted || 'Bilinmiyor', src: 'YouTube API', isLive: true },
                        { label: 'Taranan Gerçek Video', val: `${totalVideosCount} Video`, src: 'YouTube /videos', isLive: true },
                        { label: 'Taranan Gerçek Shorts', val: `${totalShortsCount} Shorts`, src: 'YouTube /shorts', isLive: true },
                        { label: 'Örneklem Ort. İzlenme', val: liveStats?.avg_views_formatted || 'Hesaplanmadı', src: 'YouTube Ortalama', isLive: true },
                        { label: 'Yerel Üretilen Senaryolar', val: `${activeChannel.metrics.total_scripts} Senaryo`, src: 'SQLite scripts', isLive: false, valCls: 'text-emerald-600 dark:text-emerald-400' },
                        { label: 'Kanal Araştırma Havuzu', val: `${activeChannel.metrics.total_research} Fikir`, src: 'SQLite discovery', isLive: false },
                        { label: 'Sistem Viral Puanı', val: `${activeChannel.metrics.avg_viral_score ?? 0} / 100`, src: 'AI Algoritma', isLive: false, valCls: 'text-amber-600 dark:text-amber-400' },
                      ].map((row, idx) => (
                        <tr key={idx} className="hover:bg-zinc-50/80 dark:hover:bg-zinc-800/40">
                          <td className="py-3 px-3 font-sans font-medium text-zinc-900 dark:text-zinc-100">{row.label}</td>
                          <td className={`py-3 px-3 font-bold ${row.valCls || 'text-zinc-900 dark:text-zinc-100'}`}>{row.val}</td>
                          <td className="py-3 px-3 font-sans text-zinc-500">{row.src}</td>
                          <td className="py-3 px-3 text-right">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border font-sans ${
                              row.isLive
                                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                                : 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20'
                            }`}>
                              {row.isLive ? 'Canlı Doğrulandı' : 'SQLite Bütünlüğü'}
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
            </div>
          </div>
        </div>
      </div>
    )
  }

  // 3. Durum: Henüz Hiç Kanal Yok (Tam Prototip: Create First Channel)
  if (channels.length === 0) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-hidden p-6 justify-center items-center">
        {isChannelsLoading ? (
          <div className="text-xs font-mono text-zinc-400">KANALLAR YÜKLENİYOR...</div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 select-none my-auto" data-testid="empty-channels-state">
            <button
              type="button"
              onClick={() => setIsCreating(true)}
              className="w-32 h-32 rounded-full border-2 border-dashed border-zinc-300 dark:border-zinc-700 hover:border-zinc-400 hover:bg-white/90 dark:hover:bg-zinc-800 flex items-center justify-center transition-all cursor-pointer group shadow-xs"
              aria-label="Create first channel"
            >
              <svg className="w-10 h-10 text-zinc-600 dark:text-zinc-400 group-hover:text-zinc-900 transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
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
      className="flex-1 w-full h-full relative overflow-auto select-none p-6"
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
