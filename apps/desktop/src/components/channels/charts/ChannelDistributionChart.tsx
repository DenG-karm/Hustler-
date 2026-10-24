import { useState, type FC } from 'react'
import type { ChannelAnalytics, PieSlice } from '../../../store/flowTypes'

interface ChannelDistributionChartProps {
  analytics?: ChannelAnalytics
}

export const ChannelDistributionChart: FC<ChannelDistributionChartProps> = ({ analytics }) => {
  const [hoveredSlice, setHoveredSlice] = useState<PieSlice | null>(null)

  const pieData = analytics?.pie_chart
  const slices = pieData?.slices || []

  if (!pieData || slices.length === 0) {
    return (
      <div className="p-6 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs flex flex-col items-center justify-center min-h-[220px] text-center">
        <svg className="w-8 h-8 mb-1 text-zinc-300 dark:text-zinc-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6a7.5 7.5 0 107.5 7.5h-7.5V6z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 10.5H21A7.5 7.5 0 0013.5 3v7.5z" />
        </svg>
        <p className="text-xs text-zinc-500 font-medium">İçerik Dağılım Grafiği</p>
        <p className="text-[11px] text-zinc-400 mt-0.5">Henüz taranmış içerik bulunmuyor.</p>
      </div>
    )
  }

  // SVG Donut parametreleri
  const size = 160
  const strokeWidth = 24
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const center = size / 2

  let accumulatedPercent = 0

  return (
    <div className="p-6 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs space-y-4">
      {/* Üst Başlık */}
      <div className="flex items-center justify-between border-b border-[#F3F4F6] dark:border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 flex items-center justify-center">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6a7.5 7.5 0 107.5 7.5h-7.5V6z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 10.5H21A7.5 7.5 0 0013.5 3v7.5z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[#111827] dark:text-zinc-100 tracking-tight">
              Format &amp; İzlenme Dağılımı (Daire Grafiği)
            </h3>
            <p className="text-[11px] text-zinc-500">
              Pandas groupby analizi ile toplam izlenme payı
            </p>
          </div>
        </div>

        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">
          Toplam: {pieData.total_views_formatted} İzlenme
        </span>
      </div>

      {/* Donut Grafiği ve Lejant */}
      <div className="flex flex-col sm:flex-row items-center gap-6 justify-between pt-1">
        {/* SVG Donut / Halka Çizimi */}
        <div className="relative w-40 h-40 shrink-0 flex items-center justify-center">
          <svg
            width={size}
            height={size}
            className="rotate-[-90deg] overflow-visible select-none"
          >
            {/* Arka Plan Çemberi */}
            <circle
              cx={center}
              cy={center}
              r={radius}
              fill="transparent"
              stroke="currentColor"
              className="text-zinc-100 dark:text-zinc-800"
              strokeWidth={strokeWidth}
            />

            {/* Renkli Dilimler */}
            {slices.map((slice) => {
              const dashLength = (slice.percentage / 100) * circumference
              const strokeDasharray = `${dashLength} ${circumference - dashLength}`
              const strokeDashoffset = -((accumulatedPercent / 100) * circumference)
              accumulatedPercent += slice.percentage

              const isHovered = hoveredSlice?.type === slice.type

              return (
                <circle
                  key={slice.type}
                  cx={center}
                  cy={center}
                  r={radius}
                  fill="transparent"
                  stroke={slice.color}
                  strokeWidth={isHovered ? strokeWidth + 4 : strokeWidth}
                  strokeDasharray={strokeDasharray}
                  strokeDashoffset={strokeDashoffset}
                  strokeLinecap="round"
                  className="transition-all duration-200 cursor-pointer"
                  onMouseEnter={() => setHoveredSlice(slice)}
                  onMouseLeave={() => setHoveredSlice(null)}
                />
              )
            })}
          </svg>

          {/* Halka İçi Merkez Metrik */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center">
            {hoveredSlice ? (
              <>
                <span className="text-lg font-bold font-mono text-zinc-900 dark:text-zinc-100">
                  %{hoveredSlice.percentage}
                </span>
                <span className="text-[10px] text-zinc-500 font-medium truncate max-w-[80px]">
                  {hoveredSlice.label}
                </span>
              </>
            ) : (
              <>
                <span className="text-base font-bold font-mono text-zinc-900 dark:text-zinc-100">
                  {pieData.total_views_formatted}
                </span>
                <span className="text-[10px] text-zinc-400 font-medium">Toplam İzlenme</span>
              </>
            )}
          </div>
        </div>

        {/* Sağ Lejant Kartları */}
        <div className="flex-1 w-full space-y-2.5">
          {slices.map((slice) => {
            const isHovered = hoveredSlice?.type === slice.type
            return (
              <div
                key={slice.type}
                onMouseEnter={() => setHoveredSlice(slice)}
                onMouseLeave={() => setHoveredSlice(null)}
                className={`p-3 rounded-xl border transition-all cursor-pointer ${
                  isHovered
                    ? 'border-zinc-400 dark:border-zinc-600 bg-zinc-50 dark:bg-zinc-800/80 shadow-2xs'
                    : 'border-zinc-200/70 dark:border-zinc-800 bg-[#F9FAFB]/70 dark:bg-zinc-800/40 hover:bg-zinc-100/60 dark:hover:bg-zinc-800/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-3 h-3 rounded-full shrink-0"
                      style={{ backgroundColor: slice.color }}
                    />
                    <span className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
                      {slice.label}
                    </span>
                    <span className="text-[10px] text-zinc-400 font-mono">
                      ({slice.count} adet)
                    </span>
                  </div>
                  <span className="text-xs font-bold font-mono text-zinc-900 dark:text-zinc-100">
                    %{slice.percentage}
                  </span>
                </div>

                <div className="flex items-center justify-between text-[11px] text-zinc-500 font-mono pt-1.5 mt-1 border-t border-zinc-200/50 dark:border-zinc-700/50">
                  <span>Toplam İzlenme:</span>
                  <span className="font-semibold text-zinc-700 dark:text-zinc-300">
                    {slice.total_views_formatted}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
