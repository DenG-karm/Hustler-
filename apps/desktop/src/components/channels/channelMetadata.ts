/**
 * Hustler Desktop — Kanal Gerçek Üstveri ve Formatlayıcı Araçları
 * Sahte veya simüle veri üretimi KESİNLİKLE YASAKTIR.
 * Yalnızca resmi YouTube API / canlı web üstverileri ve yerel SQLite verileri kullanılır.
 */

export interface ChannelAvatarData {
  handle: string | null
  avatarUrl: string
  fallbackLetter: string
}

/**
 * Sayısal veriyi (ör: 6630000) insan tarafından okunabilir metne dönüştürür (6.63M, 45.2K).
 */
export function formatCount(count: number | null | undefined): string {
  if (count == null || isNaN(Number(count))) return 'Bilinmiyor'
  const v = Number(count)
  if (v >= 1e9) return `${(v / 1e9).toFixed(2)}B`
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)}M`
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`
  return v.toLocaleString('tr-TR')
}

/**
 * YouTube bağlantısından kanal kullanıcı tanıtıcısını (@handle) çözümler.
 */
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

/**
 * Kanal için yapay zeka algısı ve stratejik profil özeti taslağı üretir.
 */
export function generateDefaultAiSummary(
  name: string,
  description: string,
  url: string,
  liveStats?: ChannelLiveStats | null
): string {
  const n = (name || 'Kanal').trim()
  const h = resolveChannelAvatar(url, name).handle || n
  if (liveStats) {
    const subs = liveStats.subscribers_formatted || 'Bilinmiyor'
    const avg = liveStats.avg_views_formatted || 'Bilinmiyor'
    const vCount = (liveStats.videos || []).length
    const sCount = (liveStats.shorts || []).length
    const niche = liveStats.niche_query || description || 'Genel'
    const topItem = [...(liveStats.shorts || []), ...(liveStats.videos || [])].sort(
      (a, b) => (b.view_count ?? 0) - (a.view_count ?? 0)
    )[0]
    const topStr = topItem
      ? `${topItem.title} (${formatCount(topItem.view_count)} izlenme)`
      : 'Henüz içerik yok'
    return `[NİŞ]: ${niche}\n[METRİKLER]: ${subs} abone | Ort. ${avg} izlenme (${vCount} Video / ${sCount} Shorts)\n[EN GÜÇLÜ İÇERİK]: ${topStr}\n[STRATEJİ]: ${n} (${h}) kanalının en yüksek izlenen kurgu ritmini 9:16 dikey formatta ölçeklendir.`
  }
  const d = (description || '').trim() || 'İçerik analizi bekleniyor'
  return `[KANAL]: ${n} (${h})\n[NİŞ]: ${d}\n[DURUM]: Canlı YouTube verileri çekildiğinde gerçek metrik ve strateji analizi güncellenir.`
}

import type { ChannelAnalytics, ChannelLiveStats, RealVideoItem, TrendPoint, PieSlice, LineChartData } from '../../store/flowTypes'

function buildLineData(
  items: { id?: string | null; title?: string; type: 'video' | 'short'; views: number }[]
): LineChartData {
  if (!items.length) {
    return { points: [], max_val: 0, min_val: 0, avg_val: 0, avg_val_formatted: '0', trend_direction: 'stable' }
  }
  const views = items.map((i) => i.views)
  const total = views.reduce((a, b) => a + b, 0)
  const max = Math.max(...views)
  const min = Math.min(...views)
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
  return {
    points,
    max_val: max,
    min_val: min,
    avg_val: avg,
    avg_val_formatted: formatCount(avg),
    trend_direction: 'stable',
  }
}

/**
 * Kanalın video ve shorts listesinden Çizgi ve Daire grafiği için analitik üretir (Fallback).
 */
export function deriveFallbackAnalytics(
  videos: RealVideoItem[] = [],
  shorts: RealVideoItem[] = []
): ChannelAnalytics {
  const vItems = videos.map((v) => ({ id: v.id, title: v.title || 'Video', type: 'video' as const, views: v.view_count || 0 }))
  const sItems = shorts.map((s) => ({ id: s.id, title: s.title || 'Shorts', type: 'short' as const, views: s.view_count || 0 }))
  const all = [...vItems, ...sItems]

  const emptyLine = { points: [], max_val: 0, min_val: 0, avg_val: 0, avg_val_formatted: '0', trend_direction: 'stable' as const }

  if (!all.length) {
    return {
      has_data: false,
      line_chart: emptyLine,
      videos_line_chart: emptyLine,
      shorts_line_chart: emptyLine,
      pie_chart: { slices: [], total_views: 0, total_views_formatted: '0' },
      summary: { median_views: 0, median_views_formatted: '0', max_views: 0, max_views_formatted: '0', min_views: 0, total_views: 0, total_views_formatted: '0', sample_count: 0 },
    }
  }

  const overallLine = buildLineData(all)
  const videosLine = buildLineData(vItems)
  const shortsLine = buildLineData(sItems)

  const views = all.map((i) => i.views)
  const total = views.reduce((a, b) => a + b, 0)
  const max = Math.max(...views)
  const min = Math.min(...views)
  const avg = Math.round(total / all.length)

  const vSum = vItems.reduce((a, b) => a + b.views, 0)
  const sSum = sItems.reduce((a, b) => a + b.views, 0)

  const slices: PieSlice[] = []
  if (videos.length) {
    slices.push({
      type: 'video',
      label: 'Yatay Video',
      color: '#3B82F6',
      count: videos.length,
      total_views: vSum,
      total_views_formatted: formatCount(vSum),
      percentage: total > 0 ? Math.round((vSum / total) * 1000) / 10 : 50,
    })
  }
  if (shorts.length) {
    slices.push({
      type: 'short',
      label: 'Dikey Shorts',
      color: '#06B6D4',
      count: shorts.length,
      total_views: sSum,
      total_views_formatted: formatCount(sSum),
      percentage: total > 0 ? Math.round((sSum / total) * 1000) / 10 : 50,
    })
  }

  return {
    has_data: true,
    line_chart: overallLine,
    videos_line_chart: videosLine,
    shorts_line_chart: shortsLine,
    pie_chart: { slices, total_views: total, total_views_formatted: formatCount(total) },
    summary: { median_views: avg, median_views_formatted: formatCount(avg), max_views: max, max_views_formatted: formatCount(max), min_views: min, total_views: total, total_views_formatted: formatCount(total), sample_count: all.length },
  }
}
