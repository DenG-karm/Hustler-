import { useState, useRef, useEffect, type FC, type MouseEvent as ReactMouseEvent } from 'react'
import type { ChannelItem } from '../../store/flowTypes'
import { useFlowStore } from '../../store/flowStore'
import { resolveChannelAvatar } from './channelMetadata'
import { AppIcon } from '../ui/AppIcon'

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
  const [imgFailed, setImgFailed] = useState(false)

  const cardRef = useRef<HTMLDivElement>(null)
  const posRef = useRef<Position>(initialPosition)
  const rafId = useRef<number | null>(null)
  const hasMovedRef = useRef<boolean>(false)

  useEffect(() => {
    posRef.current = initialPosition
    setPosition(initialPosition)
    if (cardRef.current && !isDragging) {
      cardRef.current.style.transform = `translate3d(${initialPosition.x}px, ${initialPosition.y}px, 0)`
    }
  }, [initialPosition.x, initialPosition.y, isDragging])

  useEffect(() => () => { if (rafId.current !== null) cancelAnimationFrame(rafId.current) }, [])

  const handleMouseDown = (e: ReactMouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    if (target.closest('button,a,input,textarea')) return
    e.preventDefault()
    setIsDragging(true)
    hasMovedRef.current = false

    const startX = e.clientX
    const startY = e.clientY
    const originX = posRef.current.x
    const originY = posRef.current.y
    let latestX = originX
    let latestY = originY

    const handleMouseMove = (moveEvent: globalThis.MouseEvent) => {
      const deltaX = moveEvent.clientX - startX
      const deltaY = moveEvent.clientY - startY
      if (!hasMovedRef.current && (Math.abs(deltaX) > 3 || Math.abs(deltaY) > 3)) hasMovedRef.current = true
      latestX = Math.max(12, originX + deltaX)
      latestY = Math.max(12, originY + deltaY)
      if (rafId.current === null) {
        rafId.current = requestAnimationFrame(() => {
          if (cardRef.current) cardRef.current.style.transform = `translate3d(${latestX}px, ${latestY}px, 0)`
          rafId.current = null
        })
      }
    }

    const handleMouseUp = () => {
      if (rafId.current !== null) { cancelAnimationFrame(rafId.current); rafId.current = null }
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

  const avatarData = resolveChannelAvatar(channel.channel_url, channel.name)
  const liveStats = useFlowStore((s) => s.channelLiveStats)[channel.id]
  const effectiveAvatar = liveStats?.avatar_url || channel.avatar_url || avatarData.avatarUrl

  return (
    <div
      ref={cardRef}
      onMouseDown={handleMouseDown}
      onClick={() => { if (!hasMovedRef.current) onSelect?.(channel.id) }}
      style={{ transform: `translate3d(${position.x}px, ${position.y}px, 0)`, position: 'absolute', top: 0, left: 0 }}
      className={`w-[360px] bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 select-none ${
        isDragging ? 'cursor-grabbing shadow-2xl z-50 scale-[1.015]' : 'cursor-grab shadow-sm hover:shadow-lg z-10'
      }`}
      data-testid={`channel-card-${channel.id}`}
    >
      <div className="flex items-start justify-between gap-3 pb-3 border-b border-zinc-100 dark:border-zinc-800">
        <div className="flex items-center gap-3 min-w-0">
          <div className="relative w-11 h-11 rounded-xl overflow-hidden border border-zinc-200 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-800 shrink-0 flex items-center justify-center">
            {!imgFailed ? (
              <img src={effectiveAvatar} alt={channel.name} onError={() => setImgFailed(true)} className="w-full h-full object-cover" loading="lazy" />
            ) : (
              <span className="font-bold text-sm text-zinc-800 dark:text-zinc-200">{avatarData.fallbackLetter}</span>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-100 truncate">{channel.name}</h3>
            <a
              href={channel.channel_url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline truncate font-mono block"
            >
              {channel.channel_url.replace(/^https?:\/\/(www\.)?/, '')} ↗
            </a>
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <span className="text-zinc-400 p-1 cursor-grab font-mono">⠿</span>
          {onDelete && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onDelete(channel.id) }}
              className="p-1 text-zinc-400 hover:text-red-500 rounded-md cursor-pointer flex items-center justify-center"
              aria-label="Kanalı Sil"
            >
              <AppIcon name="close" className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="mt-3 min-h-[38px] flex items-center">
        <p className="text-xs text-zinc-500 line-clamp-2">
          {channel.description || 'Bu kanal için niş açıklaması henüz girilmedi.'}
        </p>
      </div>

      <div className="grid grid-cols-4 gap-1.5 mt-4 p-2.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800 text-center font-mono">
        <div className="space-y-0.5"><span className="block text-[9.5px] font-semibold uppercase text-zinc-400">Abone</span><span className="text-[13px] font-bold block text-red-600 dark:text-red-400 truncate">{liveStats?.subscribers_formatted || '—'}</span></div>
        <div className="space-y-0.5"><span className="block text-[9.5px] font-semibold uppercase text-zinc-400">Araştırma</span><span className="text-[13px] font-bold block text-zinc-900 dark:text-zinc-100">{channel.metrics.total_research}</span></div>
        <div className="space-y-0.5"><span className="block text-[9.5px] font-semibold uppercase text-zinc-400">Senaryo</span><span className="text-[13px] font-bold block text-emerald-600 dark:text-emerald-400">{channel.metrics.total_scripts}</span></div>
        <div className="space-y-0.5"><span className="block text-[9.5px] font-semibold uppercase text-zinc-400">Viral</span><span className="text-[13px] font-bold block text-amber-600 dark:text-amber-400">{channel.metrics.avg_viral_score ?? 0}</span></div>
      </div>

      <div className="mt-4 pt-3.5 border-t border-zinc-100 dark:border-zinc-800 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-[11px] font-medium text-zinc-500">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          Hazır
        </span>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onSelect?.(channel.id) }}
          className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-zinc-900 dark:bg-zinc-100 dark:text-zinc-900 text-white cursor-pointer"
        >
          Masayı Aç →
        </button>
      </div>
    </div>
  )
}
