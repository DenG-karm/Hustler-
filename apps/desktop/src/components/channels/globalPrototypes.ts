import type { ChannelLiveStats, VideoIdea } from '../../store/flowTypes'
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

const calcScore = (views: number): number => (views <= 0 ? 60 : Math.min(99, Math.max(55, Math.round(50 + Math.log10(views) * 7.2))))

const ytUrl = (id: string, title: string, isShort: boolean, rawUrl?: string | null): string =>
  rawUrl || (id && !id.startsWith('fallback_') && !id.startsWith('idea_') ? `https://www.youtube.com/${isShort ? 'shorts/' : 'watch?v='}${id}` : `https://www.youtube.com/results?search_query=${encodeURIComponent(title)}`)

const makeItem = (
  id: string,
  title: string,
  isShort: boolean,
  views: number,
  src: string,
  dur: string,
  pTitle: string,
  pHook: string,
  score: number,
  cat: string,
  rawUrl?: string | null
): GlobalViralPrototype => ({
  id,
  format: isShort ? 'short' : 'video',
  globalTitle: title,
  globalUrl: ytUrl(id, title, isShort, rawUrl),
  globalViewsFormatted: views > 0 ? `${formatCount(views)} İzlenme` : '-',
  retentionBadge: src,
  durationText: dur,
  hookAnalysis: `${src}: ${formatCount(views)}`,
  prototypeTitle: pTitle,
  prototypeHook: pHook,
  viralScore: Math.round(score),
  categoryLabel: cat,
})

export function deriveGlobalViralPrototypes(
  channelName: string,
  _channelDescription: string,
  _channelUrl: string,
  customIdeas?: VideoIdea[],
  liveStats?: ChannelLiveStats | null
): GlobalViralPrototype[] {
  if (customIdeas?.length) {
    return customIdeas.map((i) => {
      const isShort = i.format ? i.format === 'short' : (i.duration ?? 45) <= 65
      const v = i.viewCount ?? 0
      const src = i.channelName || 'YouTube'
      return makeItem(
        i.id,
        i.title,
        isShort,
        v,
        src,
        i.durationText || fmtDuration(i.duration, isShort),
        `${channelName}: ${i.title}`,
        i.hook || i.title,
        i.score || calcScore(v),
        'Canlı Niş',
        i.url
      )
    })
  }
  if (!liveStats) return []
  const results: GlobalViralPrototype[] = []
  const seen = new Set<string>()

  const pool: [string, string, boolean, number, string, string, string, string, string, string | null | undefined][] = []
  for (const bm of liveStats.niche_benchmarks || []) {
    const isShort = bm.format ? bm.format === 'short' : (bm.duration ?? 45) <= 65
    pool.push([
      bm.video_id || bm.id || `bm_${bm.title.slice(0, 12)}`,
      bm.title,
      isShort,
      bm.view_count ?? 0,
      bm.channel_name || 'YouTube Niş',
      bm.duration_text || fmtDuration(bm.duration, isShort),
      `${channelName}: ${bm.title}`,
      bm.hook || bm.title,
      'Otomatik Niş',
      bm.url,
    ])
  }
  const own = [...(liveStats.shorts || []), ...(liveStats.videos || [])].sort((a, b) => (b.view_count ?? 0) - (a.view_count ?? 0))
  for (const v of own.slice(0, 8)) {
    const isShort = v.type === 'short'
    const cnt = v.view_count ?? 0
    pool.push([
      v.id || `ch_${v.title.slice(0, 12)}`,
      v.title,
      isShort,
      cnt,
      v.published_text || 'Kanal',
      fmtDuration(v.duration, isShort),
      v.title,
      v.title,
      'Kanal İçeriği',
      v.url,
    ])
  }

  for (const [id, title, isShort, cnt, src, dur, pTitle, pHook, cat, rawUrl] of pool) {
    if (seen.has(id)) continue
    seen.add(id)
    results.push(makeItem(id, title, isShort, cnt, src, dur, pTitle, pHook, calcScore(cnt), cat, rawUrl))
  }
  return results
}
