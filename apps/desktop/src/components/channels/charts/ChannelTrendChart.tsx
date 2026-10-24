import { useState, useId, type FC } from 'react'
import type { ChannelAnalytics, LineChartData, TrendPoint } from '../../../store/flowTypes'

export interface ChannelTrendChartProps {
  analytics?: ChannelAnalytics
  lineData?: LineChartData
  variant?: 'video' | 'short' | 'all'
  title?: string
  subtitle?: string
  colorTheme?: 'blue' | 'cyan' | 'rose' | 'emerald' | 'indigo'
}

const ICON_PATHS: Record<string, string> = {
  cyan: 'M13 10V3L4 14h7v7l9-11h-7z',
  rose: 'M13 10V3L4 14h7v7l9-11h-7z',
  blue: 'M3 17l6-6 4 4 8-8M21 12V7h-5',
  emerald: 'M4 19v-7h4v7H4zm6 0V9h4v10h-4zm6 0V4h4v15h-4z',
}

const TrendThemeIcon = ({
  theme,
  className = 'w-3.5 h-3.5',
}: {
  theme: 'rose' | 'blue' | 'cyan' | 'emerald' | 'indigo'
  className?: string
}) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d={ICON_PATHS[theme] || 'M15 10l5-3v10l-5-3M4 6h11v12H4z'} />
  </svg>
)

export const ChannelTrendChart: FC<ChannelTrendChartProps> = ({
  analytics,
  lineData: directLineData,
  variant = 'all',
  title: customTitle,
  subtitle: customSubtitle,
  colorTheme: customColorTheme,
}) => {
  const [activePoint, setActivePoint] = useState<TrendPoint | null>(null)
  const gradId = useId()

  // Hangi veri setinin kullanılacağını belirle
  const lineData =
    directLineData ||
    (variant === 'video'
      ? analytics?.videos_line_chart || analytics?.line_chart
      : variant === 'short'
      ? analytics?.shorts_line_chart || analytics?.line_chart
      : analytics?.line_chart)

  const points = lineData?.points || []

  // Tema ve başlık yapılandırması
  const isShortVariant = variant === 'short'
  const colorTheme = customColorTheme || (isShortVariant ? 'rose' : 'blue')

  const title =
    customTitle ||
    (isShortVariant
      ? 'Shorts İzlenme Trendi (Zaman Serisi)'
      : variant === 'video'
      ? 'Uzun Videolar İzlenme Trendi (Zaman Serisi)'
      : 'Video İzlenme Trendi (Zaman Serisi)')

  const subtitle =
    customSubtitle ||
    'Pandas & NumPy ile hesaplanan 3-içerik hareketli ortalama (Rolling Avg)'

  const themeColors = {
    cyan: ['#0891B2', '#67E8F9', '#06B6D4', 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400', 'fill-cyan-600'],
    rose: ['#F43F5E', '#FDA4AF', '#F43F5E', 'bg-rose-500/10 text-rose-600 dark:text-rose-400', 'fill-rose-500'],
    blue: ['#2563EB', '#93C5FD', '#3B82F6', 'bg-blue-500/10 text-blue-600 dark:text-blue-400', 'fill-blue-600'],
    emerald: ['#059669', '#6EE7B7', '#10B981', 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400', 'fill-emerald-600'],
    indigo: ['#4F46E5', '#A5B4FC', '#6366F1', 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400', 'fill-indigo-600'],
  }[colorTheme]
  const [primary, secondary, gradientStop, badgeBg, circleFill] = themeColors

  if (!lineData || points.length === 0) {
    return (
      <div className="p-6 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs flex flex-col items-center justify-center min-h-[220px] text-center">
        <TrendThemeIcon theme={colorTheme} className="w-8 h-8 mb-1 text-zinc-300 dark:text-zinc-700" />
        <p className="text-xs text-zinc-500 font-medium">{title}</p>
        <p className="text-[11px] text-zinc-400 mt-0.5">Henüz yeterli izlenme verisi bulunmuyor.</p>
      </div>
    )
  }

  // Koordinat haritalama (SVG viewBox: 0 0 520 160)
  const svgWidth = 520
  const svgHeight = 160
  const paddingLeft = 36
  const paddingRight = 20
  const paddingTop = 24
  const paddingBottom = 28

  const chartW = svgWidth - paddingLeft - paddingRight
  const chartH = svgHeight - paddingTop - paddingBottom

  const maxVal = Math.max(1, lineData.max_val)
  const minVal = 0

  const getX = (idx: number) => {
    if (points.length <= 1) return paddingLeft + chartW / 2
    return paddingLeft + (idx / (points.length - 1)) * chartW
  }

  const getY = (val: number) => {
    const norm = (val - minVal) / (maxVal - minVal)
    return paddingTop + chartH - norm * chartH
  }

  // Çizgi ve Dolgu Path'leri
  const pathD = points
    .map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${getX(idx).toFixed(1)} ${getY(p.view_count).toFixed(1)}`)
    .join(' ')

  const areaD = `${pathD} L ${getX(points.length - 1).toFixed(1)} ${(paddingTop + chartH).toFixed(1)} L ${getX(0).toFixed(1)} ${(paddingTop + chartH).toFixed(1)} Z`

  // 3-noktalı hareketli ortalama kesikli çizgisi (NumPy/Pandas)
  const rollingD = points
    .map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${getX(idx).toFixed(1)} ${getY(p.rolling_avg).toFixed(1)}`)
    .join(' ')

  return (
    <div className="p-6 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs space-y-4">
      {/* Üst Başlık & Trend Rozeti */}
      <div className="flex items-center justify-between border-b border-[#F3F4F6] dark:border-zinc-800 pb-3">
        <div className="flex items-center gap-2.5">
          <div className={`w-7 h-7 rounded-lg ${badgeBg} flex items-center justify-center`}>
            <TrendThemeIcon theme={colorTheme} className="w-3.5 h-3.5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[#111827] dark:text-zinc-100 tracking-tight">
              {title}
            </h3>
            <p className="text-[11px] text-zinc-500">
              {subtitle}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
              lineData.trend_direction === 'up'
                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                : lineData.trend_direction === 'down'
                ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border-rose-200 dark:border-rose-800'
                : 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700'
            }`}
          >
            {lineData.trend_direction === 'up' ? '↗ Yükselen Trend' : lineData.trend_direction === 'down' ? '↘ Düşüş Eğilimi' : 'Dengeli Trend'}
          </span>
        </div>
      </div>

      {/* SVG Çizgi Grafiği Alanı */}
      <div className="relative w-full">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-auto overflow-visible select-none"
        >
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={gradientStop} stopOpacity="0.25" />
              <stop offset="100%" stopColor={gradientStop} stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Yatay Kılavuz Çizgileri */}
          {[0, 0.5, 1].map((ratio) => {
            const y = paddingTop + chartH - ratio * chartH
            const labelVal = Math.round(minVal + ratio * (maxVal - minVal))
            const labelFormatted =
              labelVal >= 1e6
                ? `${(labelVal / 1e6).toFixed(1)}M`
                : labelVal >= 1e3
                ? `${(labelVal / 1e3).toFixed(0)}K`
                : `${labelVal}`

            return (
              <g key={ratio}>
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={svgWidth - paddingRight}
                  y2={y}
                  stroke="currentColor"
                  className="text-zinc-200 dark:text-zinc-800/80"
                  strokeDasharray="3 3"
                  strokeWidth="1"
                />
                <text
                  x={paddingLeft - 6}
                  y={y + 3}
                  textAnchor="end"
                  className="fill-zinc-400 dark:fill-zinc-600 text-[9px] font-mono"
                >
                  {labelFormatted}
                </text>
              </g>
            )
          })}

          {/* Alan Dolgusu (Gradient Area) */}
          <path d={areaD} fill={`url(#${gradId})`} />

          {/* Hareketli Ortalama Kesikli Çizgisi (NumPy/Pandas) */}
          <path
            d={rollingD}
            fill="none"
            stroke={secondary}
            strokeWidth="1.5"
            strokeDasharray="4 3"
            className="opacity-80 dark:opacity-60"
          />

          {/* Ana İzlenme Çizgisi */}
          <path
            d={pathD}
            fill="none"
            stroke={primary}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Veri Noktaları (Circles) */}
          {points.map((p, idx) => {
            const cx = getX(idx)
            const cy = getY(p.view_count)
            const isHovered = activePoint?.id === p.id

            return (
              <g key={p.id || idx}>
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 6 : 4}
                  className={`transition-all duration-150 cursor-pointer ${circleFill} stroke-white dark:stroke-zinc-900`}
                  strokeWidth="2"
                  onMouseEnter={() => setActivePoint(p)}
                  onMouseLeave={() => setActivePoint(null)}
                />
                {/* X Ekseni Numarası */}
                <text
                  x={cx}
                  y={svgHeight - 8}
                  textAnchor="middle"
                  className="fill-zinc-400 dark:fill-zinc-500 text-[9px] font-mono"
                >
                  #{idx + 1}
                </text>
              </g>
            )
          })}
        </svg>

        {/* Hover Tooltip Baloncuğu */}
        {activePoint && (
          <div className="absolute top-2 right-4 p-2.5 rounded-xl bg-zinc-900/95 dark:bg-white/95 text-white dark:text-zinc-900 shadow-lg text-xs pointer-events-none transition-all duration-150 border border-white/10 dark:border-black/10 z-10 max-w-[220px]">
            <div className="flex items-center gap-1.5 mb-1">
              <span
                className={`w-2 h-2 rounded-full ${
                  activePoint.type === 'short' ? 'bg-rose-500' : 'bg-blue-500'
                }`}
              />
              <span className="font-semibold truncate">
                {activePoint.type === 'short' ? 'Dikey Shorts' : 'Uzun Video'}
              </span>
            </div>
            <p className="text-[11px] opacity-90 line-clamp-1 mb-1 font-medium">
              {activePoint.title}
            </p>
            <div className="flex items-center justify-between gap-3 text-[10px] font-mono pt-1 border-t border-white/10 dark:border-black/10">
              <span className="opacity-70">İzlenme:</span>
              <span className="font-bold">{activePoint.view_count_formatted}</span>
            </div>
            <div className="flex items-center justify-between gap-3 text-[10px] font-mono opacity-80">
              <span className="opacity-70">Hareketli Ort:</span>
              <span>{activePoint.rolling_avg_formatted}</span>
            </div>
          </div>
        )}
      </div>

      {/* Alt Bilgi & Lejant */}
      <div className="flex items-center justify-between pt-2 border-t border-[#F3F4F6] dark:border-zinc-800 text-[11px] text-zinc-500">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 rounded" style={{ backgroundColor: primary }} />
            <span>Gerçek İzlenme</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="w-2.5 h-0.5 border-b border-dashed"
              style={{ borderColor: secondary, backgroundColor: secondary }}
            />
            <span>3'lü Hareketli Ort.</span>
          </span>
        </div>
        <span className="font-mono text-[10px]">
          Ortalama: {lineData.avg_val_formatted} • {points.length} İçerik
        </span>
      </div>
    </div>
  )
}
