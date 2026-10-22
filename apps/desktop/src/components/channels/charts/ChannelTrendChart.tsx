import { useState, useId, type FC } from 'react'
import type { ChannelAnalytics, LineChartData, TrendPoint } from '../../../store/flowTypes'

export interface ChannelTrendChartProps {
  analytics?: ChannelAnalytics
  lineData?: LineChartData
  variant?: 'video' | 'short' | 'all'
  title?: string
  subtitle?: string
  colorTheme?: 'blue' | 'rose' | 'emerald' | 'indigo'
}

const TrendThemeIcon = ({
  theme,
  className = 'w-3.5 h-3.5',
}: {
  theme: 'rose' | 'blue' | 'emerald' | 'indigo'
  className?: string
}) => {
  if (theme === 'rose') {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    )
  }
  if (theme === 'blue') {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.5 4.5 7.5-7.5M21 8.25V3m0 0h-5.25" />
      </svg>
    )
  }
  if (theme === 'emerald') {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
        />
      </svg>
    )
  }
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z"
      />
    </svg>
  )
}

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
    rose: {
      primary: '#F43F5E',
      secondary: '#FDA4AF',
      gradientStop: '#F43F5E',
      badgeBg: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
      circleFill: 'fill-rose-500',
    },
    blue: {
      primary: '#2563EB',
      secondary: '#93C5FD',
      gradientStop: '#3B82F6',
      badgeBg: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
      circleFill: 'fill-blue-600',
    },
    emerald: {
      primary: '#059669',
      secondary: '#6EE7B7',
      gradientStop: '#10B981',
      badgeBg: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
      circleFill: 'fill-emerald-600',
    },
    indigo: {
      primary: '#4F46E5',
      secondary: '#A5B4FC',
      gradientStop: '#6366F1',
      badgeBg: 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400',
      circleFill: 'fill-indigo-600',
    },
  }[colorTheme]

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
          <div className={`w-7 h-7 rounded-lg ${themeColors.badgeBg} flex items-center justify-center`}>
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
          {lineData.trend_direction === 'up' && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 flex items-center gap-1">
              <svg className="w-3 h-3 stroke-[2.5]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
              </svg>
              Yükselen Trend
            </span>
          )}
          {lineData.trend_direction === 'down' && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200 dark:border-rose-800 flex items-center gap-1">
              <svg className="w-3 h-3 stroke-[2.5]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 4.5l15 15m0 0V8.25m0 11.25H8.25" />
              </svg>
              Düşüş Eğilimi
            </span>
          )}
          {lineData.trend_direction === 'stable' && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700">
              Dengeli Trend
            </span>
          )}
          <span className="text-[10px] font-mono text-zinc-400 hidden sm:inline">
            Zirve: {lineData.max_val ? lineData.points.find((p) => p.view_count === lineData.max_val)?.view_count_formatted || '0' : '0'}
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
              <stop offset="0%" stopColor={themeColors.gradientStop} stopOpacity="0.25" />
              <stop offset="100%" stopColor={themeColors.gradientStop} stopOpacity="0.0" />
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
            stroke={themeColors.secondary}
            strokeWidth="1.5"
            strokeDasharray="4 3"
            className="opacity-80 dark:opacity-60"
          />

          {/* Ana İzlenme Çizgisi */}
          <path
            d={pathD}
            fill="none"
            stroke={themeColors.primary}
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
                  className={`transition-all duration-150 cursor-pointer ${themeColors.circleFill} stroke-white dark:stroke-zinc-900`}
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
            <span className="w-2.5 h-0.5 rounded" style={{ backgroundColor: themeColors.primary }} />
            <span>Gerçek İzlenme</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="w-2.5 h-0.5 border-b border-dashed"
              style={{ borderColor: themeColors.secondary, backgroundColor: themeColors.secondary }}
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
