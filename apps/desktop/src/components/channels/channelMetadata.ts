import type { ChannelAnalytics, ChannelLiveStats, RealVideoItem, TrendPoint, PieSlice, LineChartData } from '../../store/flowTypes'

export interface ChannelAvatarData {
  handle: string | null
  avatarUrl: string
  fallbackLetter: string
}

export function formatCount(count: number | null | undefined): string {
  if (count == null || isNaN(Number(count))) return '-'
  const v = Number(count)
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`
  return `${v}`
}

export function resolveChannelAvatar(url: string, name: string): ChannelAvatarData {
  const u = (url || '').trim()
  const fallbackLetter = (name || 'K').trim().charAt(0).toUpperCase() || 'K'
  const m = u.match(/@([a-zA-Z0-9_.-]+)/) || u.match(/youtube\.com\/(?:c\/|user\/)?([a-zA-Z0-9_.-]+)/)
  const h = m && !['channel', 'watch', 'shorts', 'feed'].includes(m[1]) ? m[1] : null
  return {
    handle: h ? `@${h}` : null,
    avatarUrl: h ? `https://unavatar.io/youtube/@${h}` : `https://ui-avatars.com/api/?name=${encodeURIComponent(name || 'K')}&background=111827&color=fff`,
    fallbackLetter,
  }
}

export function generateDefaultAiSummary(name: string, description: string, url: string, liveStats?: ChannelLiveStats | null): string {
  const n = (name || 'Kanal').trim()
  const h = resolveChannelAvatar(url, name).handle || n
  if (liveStats) {
    const top = [...(liveStats.shorts || []), ...(liveStats.videos || [])].sort((a, b) => (b.view_count ?? 0) - (a.view_count ?? 0))[0]
    return `[NİŞ]: ${liveStats.niche_query || description || 'Genel'}\n[METRİK]: ${liveStats.subscribers_formatted || '-'} | ${liveStats.avg_views_formatted || '-'}\n[LİDER]: ${top?.title || '-'}`
  }
  return `[KANAL]: ${n} (${h})\n[NİŞ]: ${(description || '').trim() || 'Analiz'}`
}

const EMPTY_LINE: LineChartData = { points: [], max_val: 0, min_val: 0, avg_val: 0, avg_val_formatted: '0', trend_direction: 'stable' }
const EMPTY_SUM = { median_views: 0, median_views_formatted: '0', max_views: 0, max_views_formatted: '0', min_views: 0, total_views: 0, total_views_formatted: '0', sample_count: 0 }

function buildLineData(items: { id?: string | null; title?: string; type: 'video' | 'short'; views: number }[]): LineChartData {
  if (!items.length) return EMPTY_LINE
  const views = items.map((i) => i.views)
  const total = views.reduce((a, b) => a + b, 0)
  const avg = Math.round(total / items.length)
  const points: TrendPoint[] = items.map((item, idx) => {
    const slice = items.slice(Math.max(0, idx - 2), idx + 1)
    const rolling = Math.round(slice.reduce((acc, c) => acc + c.views, 0) / slice.length)
    return {
      index: idx + 1,
      id: item.id || null,
      title: item.title || '',
      type: item.type,
      view_count: item.views,
      view_count_formatted: formatCount(item.views),
      rolling_avg: rolling,
      rolling_avg_formatted: formatCount(rolling),
    }
  })
  return { points, max_val: Math.max(...views), min_val: Math.min(...views), avg_val: avg, avg_val_formatted: formatCount(avg), trend_direction: 'stable' }
}

export function deriveFallbackAnalytics(videos: RealVideoItem[] = [], shorts: RealVideoItem[] = []): ChannelAnalytics {
  const vItems = videos.map((v) => ({ id: v.id, title: v.title || 'Video', type: 'video' as const, views: v.view_count || 0 }))
  const sItems = shorts.map((s) => ({ id: s.id, title: s.title || 'Shorts', type: 'short' as const, views: s.view_count || 0 }))
  const all = [...vItems, ...sItems]
  if (!all.length) {
    return { has_data: false, line_chart: EMPTY_LINE, videos_line_chart: EMPTY_LINE, shorts_line_chart: EMPTY_LINE, pie_chart: { slices: [], total_views: 0, total_views_formatted: '0' }, outliers: [], view_tiers: [], summary: EMPTY_SUM }
  }
  const views = all.map((i) => i.views)
  const total = views.reduce((a, b) => a + b, 0)
  const max = Math.max(...views)
  const avg = Math.round(total / all.length)
  const outliers = [...all].sort((a, b) => b.views - a.views).slice(0, 6).map((item) => {
    const mult = avg > 0 ? Math.round((item.views / avg) * 100) / 100 : 1
    return { id: item.id || null, title: item.title, type: item.type, view_count: item.views, view_count_formatted: formatCount(item.views), multiplier: mult, multiplier_formatted: `${mult.toFixed(1)}x` }
  })
  const view_tiers = ([['0 - 10K', 0, 1e4], ['10K - 50K', 1e4, 5e4], ['50K - 250K', 5e4, 25e4], ['250K+', 25e4, 1e15]] as const).map(([label, low, high]) => {
    const cnt = all.filter((i) => i.views >= low && i.views < high).length
    return { label, count: cnt, percentage: Math.round((cnt / all.length) * 1000) / 10 }
  })
  const vSum = vItems.reduce((a, b) => a + b.views, 0)
  const sSum = sItems.reduce((a, b) => a + b.views, 0)
  const mkSlice = (type: 'video' | 'short', label: string, color: string, count: number, sum: number): PieSlice => ({
    type, label, color, count, total_views: sum, total_views_formatted: formatCount(sum), percentage: total > 0 ? Math.round((sum / total) * 1000) / 10 : 50
  })
  const slices: PieSlice[] = []
  if (videos.length) slices.push(mkSlice('video', 'Yatay Video', '#3B82F6', videos.length, vSum))
  if (shorts.length) slices.push(mkSlice('short', 'Dikey Shorts', '#06B6D4', shorts.length, sSum))
  return {
    has_data: true,
    line_chart: buildLineData(all),
    videos_line_chart: buildLineData(vItems),
    shorts_line_chart: buildLineData(sItems),
    pie_chart: { slices, total_views: total, total_views_formatted: formatCount(total) },
    outliers,
    view_tiers,
    summary: { median_views: avg, median_views_formatted: formatCount(avg), max_views: max, max_views_formatted: formatCount(max), min_views: Math.min(...views), total_views: total, total_views_formatted: formatCount(total), sample_count: all.length },
  }
}
