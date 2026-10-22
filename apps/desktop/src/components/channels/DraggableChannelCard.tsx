import { useState, useRef, useEffect, type FC, type MouseEvent as ReactMouseEvent } from 'react'
import type { ChannelItem } from '../../store/flowTypes'
import { useFlowStore } from '../../store/flowStore'
import { resolveChannelAvatar } from './channelMetadata'

export interface Position {
  x: number
  y: number
}

export interface DraggableChannelCardProps {
  channel: ChannelItem
  initialPosition: Position
  onPositionChange?: (id: string, pos: Position) => void
  onSelect?: (id: string) => void
  onDelete?: (id: string) => void
}

export const DraggableChannelCard: FC<DraggableChannelCardProps> = ({
  channel,
  initialPosition,
  onPositionChange,
  onSelect,
  onDelete,
}) => {
  const [position, setPosition] = useState<Position>(initialPosition)
  const [isDragging, setIsDragging] = useState(false)

  const cardRef = useRef<HTMLDivElement>(null)
  const posRef = useRef<Position>(initialPosition)
  const rafId = useRef<number | null>(null)
  const hasMovedRef = useRef<boolean>(false)

  // initialPosition dışarıdan değiştiğinde senkronize et
  useEffect(() => {
    posRef.current = initialPosition
    setPosition(initialPosition)
    if (cardRef.current && !isDragging) {
      cardRef.current.style.transform = `translate3d(${initialPosition.x}px, ${initialPosition.y}px, 0)`
    }
  }, [initialPosition.x, initialPosition.y, isDragging])

  // Temizleme: Unmount esnasında bekleyen RAF varsa iptal et
  useEffect(() => {
    return () => {
      if (rafId.current !== null) {
        cancelAnimationFrame(rafId.current)
      }
    }
  }, [])

  const handleMouseDown = (e: ReactMouseEvent<HTMLDivElement>) => {
    // Buton, link veya form elemanına tıklandığında sürükleme başlatma
    const target = e.target as HTMLElement
    if (target.closest('button') || target.closest('a') || target.closest('input') || target.closest('textarea')) {
      return
    }

    e.preventDefault()
    setIsDragging(true)
    hasMovedRef.current = false

    const startX = e.clientX
    const startY = e.clientY
    const originX = posRef.current.x
    const originY = posRef.current.y
    let latestX = originX
    let latestY = originY

    // 60-144Hz Donanım Hızlandırmalı Akıcı Sürükleme (RAF + Direct Transform)
    const handleMouseMove = (moveEvent: globalThis.MouseEvent) => {
      const deltaX = moveEvent.clientX - startX
      const deltaY = moveEvent.clientY - startY

      if (!hasMovedRef.current && (Math.abs(deltaX) > 3 || Math.abs(deltaY) > 3)) {
        hasMovedRef.current = true
      }

      latestX = Math.max(12, originX + deltaX)
      latestY = Math.max(12, originY + deltaY)

      if (rafId.current === null) {
        rafId.current = requestAnimationFrame(() => {
          if (cardRef.current) {
            cardRef.current.style.transform = `translate3d(${latestX}px, ${latestY}px, 0)`
          }
          rafId.current = null
        })
      }
    }

    const handleMouseUp = () => {
      if (rafId.current !== null) {
        cancelAnimationFrame(rafId.current)
        rafId.current = null
      }

      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
      setIsDragging(false)

      if (hasMovedRef.current) {
        const finalPos = { x: latestX, y: latestY }
        posRef.current = finalPos
        setPosition(finalPos)
        onPositionChange?.(channel.id, finalPos)
      }
    }

    window.addEventListener('mousemove', handleMouseMove, { passive: true })
    window.addEventListener('mouseup', handleMouseUp)
  }

  const handleCardClick = () => {
    if (!hasMovedRef.current) {
      onSelect?.(channel.id)
    }
  }

  const [imgFailed, setImgFailed] = useState(false)
  const avatarData = resolveChannelAvatar(channel.channel_url, channel.name)
  const channelLiveStats = useFlowStore((s) => s.channelLiveStats)
  const liveStats = channelLiveStats[channel.id]
  const effectiveAvatar = liveStats?.avatar_url || channel.avatar_url || avatarData.avatarUrl

  return (
    <div
      ref={cardRef}
      onMouseDown={handleMouseDown}
      onClick={handleCardClick}
      style={{
        transform: `translate3d(${position.x}px, ${position.y}px, 0)`,
        position: 'absolute',
        top: 0,
        left: 0,
        willChange: isDragging ? 'transform' : 'auto',
      }}
      className={`w-[360px] bg-white dark:bg-zinc-900 border border-[#E5E7EB] dark:border-zinc-800 rounded-2xl p-5 select-none ${
        isDragging
          ? 'cursor-grabbing shadow-2xl ring-2 ring-[#111827]/15 dark:ring-white/15 z-50 scale-[1.015]'
          : 'cursor-grab shadow-sm hover:shadow-lg hover:border-zinc-300 dark:hover:border-zinc-700 z-10 transition-shadow duration-150'
      }`}
      data-testid={`channel-card-${channel.id}`}
    >
      {/* Üst Başlık Şeridi: Profil Fotoğrafı + İsim/URL + Aksiyonlar */}
      <div className="flex items-start justify-between gap-3 pb-3 border-b border-[#F3F4F6] dark:border-zinc-800/80">
        <div className="flex items-center gap-3 min-w-0">
          {/* Kanal Profil Fotoğrafı (YouTube Avatar) */}
          <div className="relative w-11 h-11 rounded-xl overflow-hidden border border-zinc-200/90 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-800 shadow-2xs shrink-0 flex items-center justify-center">
            {!imgFailed ? (
              <img
                src={effectiveAvatar}
                alt={channel.name}
                onError={() => setImgFailed(true)}
                className="w-full h-full object-cover"
                loading="lazy"
              />
            ) : (
              <span className="font-bold text-sm text-zinc-800 dark:text-zinc-200">
                {avatarData.fallbackLetter}
              </span>
            )}
            {/* YouTube Küçük İkon Rozeti */}
            <div className="absolute -bottom-0.5 -right-0.5 bg-red-600 rounded-full p-0.5 ring-1 ring-white dark:ring-zinc-900">
              <svg className="w-2.5 h-2.5 text-white" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19.6 3.2c-3.6-.3-11.6-.3-15.2 0C.5 3.5.05 5.8 0 12c.05 6.2.5 8.5 4.4 8.8 3.6.3 11.6.3 15.2 0 3.9-.3 4.4-2.6 4.4-8.8-.03-6.2-.5-8.5-4.4-8.8zM9 16V8l8 4-8 4z" />
              </svg>
            </div>
          </div>

          {/* Kanal Adı ve Bağlantı */}
          <div className="min-w-0 flex-1">
            <h3 className="text-[15px] font-semibold text-[#111827] dark:text-zinc-100 truncate tracking-tight leading-tight">
              {channel.name}
            </h3>
            <a
              href={channel.channel_url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-[11px] text-[#2563EB] dark:text-blue-400 hover:underline truncate font-mono inline-flex items-center gap-1 mt-0.5"
              title={channel.channel_url}
            >
              <span>{channel.channel_url.replace(/^https?:\/\/(www\.)?/, '')} ↗</span>
            </a>
          </div>
        </div>

        {/* Sağ Üst: Sürükleme Tutamacı ve Silme */}
        <div className="flex items-center gap-1 shrink-0 pt-0.5">
          <div
            className="text-zinc-400 dark:text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 p-1 rounded-md transition-colors cursor-grab active:cursor-grabbing text-base leading-none select-none font-mono"
            title="Sürükle ve Taşı"
          >
            ⠿
          </div>

          {onDelete && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                onDelete(channel.id)
              }}
              className="p-1 text-zinc-400 hover:text-red-500 rounded-md hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors cursor-pointer"
              title="Kanalı Sil"
              aria-label="Kanalı Sil"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-1 12a2 2 0 01-2 2H8a2 2 0 01-2-2L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Açıklama / Niş Metni */}
      <div className="mt-3 min-h-[38px] flex items-center">
        {channel.description ? (
          <p className="text-[12.5px] text-zinc-600 dark:text-zinc-400 line-clamp-2 leading-relaxed">
            {channel.description}
          </p>
        ) : (
          <p className="text-[12px] text-zinc-400 dark:text-zinc-500 italic">
            Bu kanal için niş açıklaması henüz girilmedi.
          </p>
        )}
      </div>

      {/* İstatistik Göstergeleri (Metrikler: Abone + SQLite Sayaçları) */}
      <div className="grid grid-cols-4 gap-1.5 mt-4 p-2.5 rounded-xl bg-zinc-50/90 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800 text-center font-mono">
        {[
          { lbl: 'Abone', val: liveStats?.subscribers_formatted || '—', cls: 'text-red-600 dark:text-red-400 font-bold' },
          { lbl: 'Araştırma', val: channel.metrics.total_research, cls: 'text-zinc-900 dark:text-zinc-100', border: true },
          { lbl: 'Senaryo', val: channel.metrics.total_scripts, cls: 'text-emerald-600 dark:text-emerald-400', border: true },
          { lbl: 'Viral Skor', val: channel.metrics.avg_viral_score ?? 0, cls: 'text-amber-600 dark:text-amber-400' },
        ].map((m, i) => (
          <div key={i} className={`space-y-0.5 ${m.border ? 'border-l border-zinc-200/60 dark:border-zinc-700/60' : ''}`}>
            <span className="block text-[9.5px] font-semibold uppercase font-sans text-zinc-400 truncate">{m.lbl}</span>
            <span className={`text-[13px] font-bold block truncate ${m.cls}`}>{m.val}</span>
          </div>
        ))}
      </div>

      {/* Alt Aksiyon Çubuğu: Durum & Masayı Aç */}
      <div className="mt-4 pt-3.5 border-t border-[#F3F4F6] dark:border-zinc-800/80 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-zinc-500 dark:text-zinc-400">
          <span className="w-2 h-2 rounded-full bg-emerald-500 ring-4 ring-emerald-500/10 shrink-0" />
          <span>Hazır</span>
        </div>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onSelect?.(channel.id)
          }}
          className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-[#111827] hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white text-white shadow-2xs transition-all cursor-pointer inline-flex items-center gap-1.5"
        >
          <span>Masayı Aç →</span>
        </button>
      </div>
    </div>
  )
}
