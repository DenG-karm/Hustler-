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

const BOX = 'p-5 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs space-y-3'

export const ChannelTrendChart: FC<ChannelTrendChartProps> = ({
  analytics,
  lineData: directLineData,
  variant = 'all',
  title = 'Video İzlenme Trendi',
  subtitle = '3-içerik hareketli ortalama (Rolling Avg)',
  colorTheme = 'blue',
}) => {
  const [activePoint, setActivePoint] = useState<TrendPoint | null>(null)
  const gradId = useId()

  const lineData =
    directLineData ||
    (variant === 'video'
      ? analytics?.videos_line_chart || analytics?.line_chart
      : variant === 'short'
      ? analytics?.shorts_line_chart || analytics?.line_chart
      : analytics?.line_chart)

  const points = lineData?.points || []
  const [primary, secondary, gradientStop, circleFill] =
    colorTheme === 'cyan'
      ? ['#0891B2', '#67E8F9', '#06B6D4', 'fill-cyan-600']
      : ['#2563EB', '#93C5FD', '#3B82F6', 'fill-blue-600']

  if (!lineData || !points.length) {
    return (
      <div className={`${BOX} flex flex-col items-center justify-center min-h-[200px] text-center`}>
        <p className="text-xs text-zinc-500 font-medium">{title}</p>
        <p className="text-[11px] text-zinc-400">Henüz yeterli izlenme verisi bulunmuyor.</p>
      </div>
    )
  }

  const maxVal = Math.max(1, lineData.max_val)
  const getX = (i: number) => (points.length <= 1 ? 268 : 36 + (i / (points.length - 1)) * 464)
  const getY = (v: number) => 132 - (v / maxVal) * 108
  const line = (k: 'view_count' | 'rolling_avg') => points.map((p, i) => `${i ? 'L' : 'M'}${getX(i).toFixed(1)} ${getY(p[k]).toFixed(1)}`).join(' ')
  const pathD = line('view_count')
  const areaD = `${pathD} L${getX(points.length - 1).toFixed(1)} 132 L${getX(0).toFixed(1)} 132 Z`
  const rollingD = line('rolling_avg')

  return (
    <div className={BOX}>
      <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-2.5">
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{title}</h3>
          <p className="text-[11px] text-zinc-500">{subtitle}</p>
        </div>
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold border bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700">
          {lineData.trend_direction === 'up' ? '↗ Yükselen Trend' : lineData.trend_direction === 'down' ? '↘ Düşüş Eğilimi' : 'Dengeli Trend'}
        </span>
      </div>

      <div className="relative w-full">
        <svg viewBox="0 0 520 160" className="w-full h-auto overflow-visible select-none">
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={gradientStop} stopOpacity="0.25" />
              <stop offset="100%" stopColor={gradientStop} stopOpacity="0.0" />
            </linearGradient>
          </defs>
          {[0, 0.5, 1].map((ratio) => {
            const y = 132 - ratio * 108
            const v = Math.round(ratio * maxVal)
            const lbl = v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : `${v}`
            return (
              <g key={ratio}>
                <line x1={36} y1={y} x2={500} y2={y} stroke="currentColor" className="text-zinc-200 dark:text-zinc-800" strokeDasharray="3 3" />
                <text x={30} y={y + 3} textAnchor="end" className="fill-zinc-400 text-[9px] font-mono">{lbl}</text>
              </g>
            )
          })}
          <path d={areaD} fill={`url(#${gradId})`} />
          <path d={rollingD} fill="none" stroke={secondary} strokeWidth="1.5" strokeDasharray="4 3" />
          <path d={pathD} fill="none" stroke={primary} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          {points.map((p, idx) => (
            <g key={p.id || idx}>
              <circle
                cx={getX(idx)}
                cy={getY(p.view_count)}
                r={activePoint?.id === p.id ? 6 : 4}
                className={`cursor-pointer ${circleFill} stroke-white dark:stroke-zinc-900`}
                strokeWidth="2"
                onMouseEnter={() => setActivePoint(p)}
                onMouseLeave={() => setActivePoint(null)}
              />
              <text x={getX(idx)} y={152} textAnchor="middle" className="fill-zinc-400 text-[9px] font-mono">#{idx + 1}</text>
            </g>
          ))}
        </svg>

        {activePoint && (
          <div className="absolute top-2 right-4 p-2 rounded-xl bg-zinc-900 text-white shadow-lg text-xs pointer-events-none z-10 max-w-[200px]">
            <p className="text-[11px] truncate font-medium">{activePoint.title}</p>
            <div className="flex justify-between text-[10px] font-mono pt-1">
              <span>İzlenme:</span>
              <span className="font-bold">{activePoint.view_count_formatted}</span>
            </div>
            <div className="flex justify-between text-[10px] font-mono opacity-80">
              <span>Ort:</span>
              <span>{activePoint.rolling_avg_formatted}</span>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-zinc-100 dark:border-zinc-800 text-[11px] text-zinc-500 font-mono">
        <span>Gerçek İzlenme &amp; 3&apos;lü Ort.</span>
        <span>Ort: {lineData.avg_val_formatted} • {points.length} İçerik</span>
      </div>
    </div>
  )
}
