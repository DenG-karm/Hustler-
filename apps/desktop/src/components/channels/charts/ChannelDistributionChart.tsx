import { useState, type FC } from 'react'
import type { ChannelAnalytics, PieSlice } from '../../../store/flowTypes'

interface ChannelDistributionChartProps {
  analytics?: ChannelAnalytics
}

const BOX = 'p-5 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs space-y-3'
const B_SEP = 'border-b border-zinc-100 dark:border-zinc-800'

export const ViralMultiplierCard: FC<{ outliers?: ChannelAnalytics['outliers'] }> = ({ outliers = [] }) => {
  if (!outliers.length) return null
  const maxMult = Math.max(1, ...outliers.map((o) => o.multiplier))
  return (
    <div className={BOX}>
      <div className={`flex items-center justify-between pb-2 ${B_SEP}`}>
        <div>
          <h3 className="text-xs font-bold text-zinc-900 dark:text-zinc-100">Viral Çarpan Analizi</h3>
          <p className="text-[10px] text-zinc-500">Ortalamanın üzerinde izlenen içerikler</p>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold">
          {outliers.length} Outlier
        </span>
      </div>
      <div className="space-y-2.5 pt-1">
        {outliers.map((o, i) => (
          <div key={o.id || i} className="space-y-1">
            <div className="flex items-center justify-between text-xs gap-2">
              <span className="truncate font-medium text-zinc-800 dark:text-zinc-200 flex-1 text-[11px]" title={o.title}>
                {o.title}
              </span>
              <span className="font-mono text-[10px] text-zinc-400 shrink-0">{o.view_count_formatted}</span>
              <span className="px-1.5 py-0.5 rounded font-mono text-[10px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
                {o.multiplier_formatted}
              </span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
              <div
                style={{ width: `${Math.max(8, Math.round((o.multiplier / maxMult) * 100))}%` }}
                className={`h-full rounded-full ${o.type === 'short' ? 'bg-cyan-500' : 'bg-blue-600'}`}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export const ViewTierDistributionCard: FC<{ tiers?: ChannelAnalytics['view_tiers'] }> = ({ tiers = [] }) => {
  if (!tiers.length) return null
  return (
    <div className={BOX}>
      <div className={`${B_SEP} pb-2`}>
        <h3 className="text-xs font-bold text-zinc-900 dark:text-zinc-100">İzlenme Kademesi Dağılımı</h3>
        <p className="text-[10px] text-zinc-500">İzlenme yoğunluk histogramı</p>
      </div>
      <div className="space-y-2.5 pt-1">
        {tiers.map((t) => (
          <div key={t.label} className="space-y-1">
            <div className="flex items-center justify-between text-xs font-mono text-[11px]">
              <span className="font-semibold text-zinc-700 dark:text-zinc-300">{t.label}</span>
              <span className="text-zinc-500">{t.count} içerik (%{t.percentage})</span>
            </div>
            <div className="w-full h-2 rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
              <div
                style={{ width: `${Math.max(t.count > 0 ? 6 : 0, t.percentage)}%` }}
                className="h-full rounded-full bg-blue-600"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export const ChannelDistributionChart: FC<ChannelDistributionChartProps> = ({ analytics }) => {
  const [hoveredSlice, setHoveredSlice] = useState<PieSlice | null>(null)
  const pieData = analytics?.pie_chart
  const slices = pieData?.slices || []

  if (!pieData || !slices.length) {
    return (
      <div className={`${BOX} flex flex-col items-center justify-center min-h-[200px] text-center`}>
        <p className="text-xs text-zinc-500 font-medium">İçerik Dağılım Grafiği</p>
        <p className="text-[11px] text-zinc-400">Henüz taranmış içerik bulunmuyor.</p>
      </div>
    )
  }

  const size = 152
  const strokeWidth = 22
  const radius = (size - strokeWidth) / 2
  const circ = 2 * Math.PI * radius
  const center = size / 2
  let acc = 0

  return (
    <div className={BOX}>
      <div className={`flex items-center justify-between ${B_SEP} pb-3`}>
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Format Dağılımı</h3>
          <p className="text-[11px] text-zinc-500">İzlenme payı</p>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">
          Toplam: {pieData.total_views_formatted}
        </span>
      </div>

      <div className="flex flex-col sm:flex-row items-center gap-6 justify-between pt-1">
        <div className="relative w-38 h-38 shrink-0 flex items-center justify-center">
          <svg width={size} height={size} className="-rotate-90 overflow-visible select-none">
            <circle cx={center} cy={center} r={radius} fill="transparent" stroke="currentColor" className="text-zinc-100 dark:text-zinc-800" strokeWidth={strokeWidth} />
            {slices.map((s) => {
              const dash = (s.percentage / 100) * circ
              const offset = -((acc / 100) * circ)
              acc += s.percentage
              return (
                <circle
                  key={s.type}
                  cx={center}
                  cy={center}
                  r={radius}
                  fill="transparent"
                  stroke={s.color}
                  strokeWidth={hoveredSlice?.type === s.type ? strokeWidth + 4 : strokeWidth}
                  strokeDasharray={`${dash} ${circ - dash}`}
                  strokeDashoffset={offset}
                  strokeLinecap="round"
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredSlice(s)}
                  onMouseLeave={() => setHoveredSlice(null)}
                />
              )
            })}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center">
            <span className="text-base font-bold font-mono text-zinc-900 dark:text-zinc-100">
              {hoveredSlice ? `%${hoveredSlice.percentage}` : pieData.total_views_formatted}
            </span>
            <span className="text-[10px] text-zinc-400 truncate max-w-[80px]">{hoveredSlice ? hoveredSlice.label : 'Toplam'}</span>
          </div>
        </div>

        <div className="flex-1 w-full space-y-2">
          {slices.map((s) => (
            <div key={s.type} onMouseEnter={() => setHoveredSlice(s)} onMouseLeave={() => setHoveredSlice(null)} className="p-3 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/40 cursor-pointer">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: s.color }} />
                  <span className="font-semibold text-zinc-800 dark:text-zinc-200">{s.label} ({s.count})</span>
                </div>
                <span className="font-bold font-mono text-zinc-900 dark:text-zinc-100">%{s.percentage} • {s.total_views_formatted}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
