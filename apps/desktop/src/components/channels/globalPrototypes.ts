import type { ChannelLiveStats, DiscoveryItem, RealVideoItem, VideoIdea } from '../../store/flowTypes'
import { formatCount } from './channelMetadata'

export interface GlobalViralPrototype {
  id: string
  format: 'short' | 'video'
  globalTitle: string
  globalUrl: string
  globalViewsFormatted: string
  retentionBadge: string
  durationText: string
  hookAnalysis: string
  prototypeTitle: string
  prototypeHook: string
  viralScore: number
  categoryLabel: string
}

const fmtDuration = (sec: number | null | undefined, isShort: boolean): string => {
  if (!sec || sec <= 0) return isShort ? '0:45' : '-'
  const s = Math.round(sec)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

const calcScore = (views: number): number => {
  if (views <= 0) return 60
  return Math.min(99, Math.max(55, Math.round(50 + Math.log10(views) * 7.2)))
}

function fromIdea(idea: VideoIdea, channelName: string): GlobalViralPrototype {
  const isShort = idea.format ? idea.format === 'short' : (idea.duration ?? 45) <= 65
  const views = idea.viewCount ?? 0
  const srcChannel = idea.channelName || 'YouTube'
  const url =
    idea.url ||
    (idea.id && !idea.id.startsWith('fallback_') && !idea.id.startsWith('idea_')
      ? `https://www.youtube.com/${isShort ? 'shorts/' : 'watch?v='}${idea.id}`
      : `https://www.youtube.com/results?search_query=${encodeURIComponent(idea.title)}`)

  return {
    id: idea.id,
    format: isShort ? 'short' : 'video',
    globalTitle: idea.title,
    globalUrl: url,
    globalViewsFormatted: views > 0 ? `${formatCount(views)} İzlenme` : 'Yeni / Veri Yok',
    retentionBadge: srcChannel,
    durationText: idea.durationText || fmtDuration(idea.duration, isShort),
    hookAnalysis: `Gerçek YouTube Verisi (${srcChannel}): ${formatCount(views)} izlenme alan doğrulanmış içerik.`,
    prototypeTitle: `${channelName}: ${idea.title}`,
    prototypeHook: idea.hook || idea.title,
    viralScore: Math.round(idea.score || calcScore(views)),
    categoryLabel: 'Canlı Niş Taraması',
  }
}

function fromChannelVideo(vid: RealVideoItem, channelName: string): GlobalViralPrototype {
  const isShort = vid.type === 'short'
  const views = vid.view_count ?? 0
  const score = calcScore(views)
  const url =
    vid.url ||
    (vid.id
      ? `https://www.youtube.com/${isShort ? 'shorts/' : 'watch?v='}${vid.id}`
      : `https://www.youtube.com/results?search_query=${encodeURIComponent(vid.title)}`)

  return {
    id: vid.id || `ch_${vid.title.slice(0, 12)}`,
    format: isShort ? 'short' : 'video',
    globalTitle: vid.title,
    globalUrl: url,
    globalViewsFormatted: views > 0 ? `${formatCount(views)} İzlenme` : 'Bilinmiyor',
    retentionBadge: vid.published_text || 'Kanal İçeriği',
    durationText: fmtDuration(vid.duration, isShort),
    hookAnalysis: `${channelName} kanalının kendi gerçek içeriği (${formatCount(views)} izlenme).`,
    prototypeTitle: vid.title,
    prototypeHook: `${vid.title} — Kanalın en yüksek etkileşimli kurgu yapısını devam ettir.`,
    viralScore: score,
    categoryLabel: 'Kanalın Gerçek İçeriği',
  }
}

function fromBenchmarkItem(item: DiscoveryItem, channelName: string): GlobalViralPrototype {
  const vid = item.video_id || item.id || ''
  const isShort = item.format ? item.format === 'short' : (item.duration ?? 45) <= 65
  const views = item.view_count ?? 0
  const srcChannel = item.channel_name || 'YouTube Niş'
  const url =
    item.url ||
    (vid
      ? `https://www.youtube.com/${isShort ? 'shorts/' : 'watch?v='}${vid}`
      : `https://www.youtube.com/results?search_query=${encodeURIComponent(item.title)}`)

  return {
    id: vid || `bm_${item.title.slice(0, 12)}`,
    format: isShort ? 'short' : 'video',
    globalTitle: item.title,
    globalUrl: url,
    globalViewsFormatted: views > 0 ? `${formatCount(views)} İzlenme` : 'Bilinmiyor',
    retentionBadge: srcChannel,
    durationText: item.duration_text || fmtDuration(item.duration, isShort),
    hookAnalysis: `Niş Rakip Analizi (${srcChannel}): Bu başlık ve süre (${item.duration_text || fmtDuration(item.duration, isShort)}) nişte ${formatCount(views)} izlenmeye ulaştı.`,
    prototypeTitle: `${channelName}: ${item.title}`,
    prototypeHook: item.hook || item.title,
    viralScore: Math.round(item.score || calcScore(views)),
    categoryLabel: 'Otomatik Niş Taraması',
  }
}

export function deriveGlobalViralPrototypes(
  channelName: string,
  _channelDescription: string,
  _channelUrl: string,
  customIdeas?: VideoIdea[],
  liveStats?: ChannelLiveStats | null
): GlobalViralPrototype[] {
  if (customIdeas && customIdeas.length > 0) {
    return customIdeas.map((idea) => fromIdea(idea, channelName))
  }

  if (!liveStats) return []

  const results: GlobalViralPrototype[] = []
  const seenIds = new Set<string>()

  const benchmarks = liveStats.niche_benchmarks || []
  for (const bm of benchmarks) {
    const proto = fromBenchmarkItem(bm, channelName)
    if (!seenIds.has(proto.id)) {
      seenIds.add(proto.id)
      results.push(proto)
    }
  }

  const ownVideos = [...(liveStats.shorts || []), ...(liveStats.videos || [])].sort(
    (a, b) => (b.view_count ?? 0) - (a.view_count ?? 0)
  )
  for (const v of ownVideos.slice(0, 8)) {
    const proto = fromChannelVideo(v, channelName)
    if (!seenIds.has(proto.id)) {
      seenIds.add(proto.id)
      results.push(proto)
    }
  }

  return results
}
