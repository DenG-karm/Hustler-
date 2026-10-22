import { useState, type FC, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../../../lib/utils'
import hustlerLogoUrl from '../../../assets/HustlerLogo.png'

export interface SidebarItem {
  id: string
  label: string
  icon?: ReactNode
  badge?: string | number
  active?: boolean
  onClick?: () => void
}

export interface SidebarProps extends HTMLAttributes<HTMLElement> {
  title?: string
  subtitle?: string
  logo?: ReactNode
  items: SidebarItem[]
  isCollapsed?: boolean
  defaultCollapsed?: boolean
  onToggleCollapse?: (collapsed: boolean) => void
  footer?: ReactNode
}

const SIDEBAR_ICONS: Record<string, string> = {
  channels:
    'M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25',
  pipeline:
    'M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v7.269z',
  templates:
    'M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z',
  library:
    'M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z',
  settings:
    'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z M15 12a3 3 0 11-6 0 3 3 0 016 0z',
}

function getTechnicalIcon(id: string): ReactNode {
  const d = SIDEBAR_ICONS[id] ?? 'M9 12h6'
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d={d} />
    </svg>
  )
}

export const Sidebar: FC<SidebarProps> = ({
  title = 'Hustler',
  subtitle = 'v1.0 Studio',
  logo,
  items,
  isCollapsed: controlledCollapsed,
  defaultCollapsed = false,
  onToggleCollapse,
  footer,
  className,
  ...props
}) => {
  const [uncontrolledCollapsed, setUncontrolledCollapsed] = useState(defaultCollapsed)
  const isCollapsed = controlledCollapsed !== undefined ? controlledCollapsed : uncontrolledCollapsed

  const handleToggle = () => {
    const nextState = !isCollapsed
    if (controlledCollapsed === undefined) {
      setUncontrolledCollapsed(nextState)
    }
    onToggleCollapse?.(nextState)
  }

  const defaultLogoNode = (
    <img
      src={hustlerLogoUrl}
      alt="Hustler Logo"
      data-testid="sidebar-logo"
      className={cn(
        'object-contain select-none transition-all duration-200',
        isCollapsed
          ? 'w-9 h-9 drop-shadow-sm'
          : 'h-12 w-auto max-w-[170px] drop-shadow-md'
      )}
      draggable={false}
    />
  )

  return (
    <aside
      aria-expanded={!isCollapsed}
      className={cn(
        'flex flex-col h-full bg-surface border-r border-border transition-[width] duration-200 ease-out select-none shrink-0 overflow-hidden',
        isCollapsed ? 'w-16' : 'w-60',
        className,
      )}
      {...props}
    >
      {/* Üst Başlık (Header - h-16) */}
      <div className="h-16 flex items-center justify-between px-3 border-b border-border/80 shrink-0">
        {!isCollapsed ? (
          <>
            <div className="flex items-center min-w-0 flex-1 overflow-hidden">
              {logo || defaultLogoNode}
              {(title || subtitle) && (
                <div className="sr-only">
                  {title && <span>{title}</span>}
                  {subtitle && <span>{subtitle}</span>}
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={handleToggle}
              aria-label="Sidebarı Daralt"
              title="Sidebarı Daralt"
              className="w-7 h-7 rounded-md flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40 transition-colors shrink-0 cursor-pointer focus:outline-none"
            >
              <svg
                className="w-4 h-4"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.75}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={handleToggle}
            aria-label="Sidebarı Genişlet"
            title="Sidebarı Genişlet"
            className="w-10 h-10 mx-auto rounded-lg flex items-center justify-center text-zinc-600 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer focus:outline-none"
          >
            <svg
              className="w-5 h-5"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.75}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
        )}
      </div>

      {/* Navigasyon Öğeleri (Sade ve Yumuşak — Outline/Ring Yok) */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden px-2 py-2.5 space-y-1" aria-label="Ana Menü">
        {items.map((item) => {
          const isActive = !!item.active
          const renderedIcon = item.icon ?? getTechnicalIcon(item.id)
          return (
            <button
              key={item.id}
              type="button"
              onClick={item.onClick}
              title={isCollapsed ? item.label : undefined}
              className={cn(
                'group relative w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md text-xs transition-colors duration-150 text-left cursor-pointer outline-none ring-0 focus:outline-none focus:ring-0 focus-visible:outline-none focus-visible:ring-0',
                isActive
                  ? 'bg-zinc-200/80 dark:bg-zinc-800/80 text-zinc-900 dark:text-zinc-100 font-medium'
                  : 'text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200 hover:bg-zinc-200/50 dark:hover:bg-zinc-800/40',
                isCollapsed && 'justify-center px-0',
              )}
            >
              {/* Sol Kenarda 2px Yumuşak Vurgu Çizgisi */}
              {isActive && (
                <span
                  className="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-r bg-teal-400"
                  aria-hidden="true"
                />
              )}

              <span
                className={cn(
                  'shrink-0 flex items-center justify-center w-5 h-5 transition-colors',
                  isActive
                    ? 'text-teal-500 dark:text-teal-400'
                    : 'text-zinc-400 group-hover:text-zinc-700 dark:group-hover:text-zinc-200',
                )}
              >
                {renderedIcon}
              </span>

              {!isCollapsed && (
                <span className="truncate flex-1">{item.label}</span>
              )}

              {!isCollapsed && item.badge !== undefined && (
                <span
                  className={cn(
                    'px-1.5 py-0.5 text-[10px] font-mono rounded shrink-0',
                    isActive
                      ? 'bg-teal-500/15 text-teal-600 dark:text-teal-300 font-medium'
                      : 'bg-zinc-200/70 dark:bg-zinc-800/70 text-zinc-500 dark:text-zinc-400',
                  )}
                >
                  {item.badge}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Alt Bilgi (Footer - h-12) */}
      <div className="h-12 px-3 border-t border-border/80 flex items-center justify-between shrink-0 overflow-hidden mt-auto">
        {isCollapsed ? (
          <div
            className="w-full flex items-center justify-center"
            title="Hustler Core v1.0.0 — Zero-Net Aktif"
            data-testid="sidebar-footer-collapsed"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
            {footer && <div className="hidden">{footer}</div>}
          </div>
        ) : footer ? (
          <div className="w-full min-w-0 overflow-hidden">{footer}</div>
        ) : (
          <div className="w-full flex items-center justify-between gap-2 min-w-0 overflow-hidden">
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
              <span className="text-[11px] text-zinc-400 truncate">
                Yerel Motor (v1.0.0)
              </span>
            </div>
            <span className="px-1.5 py-0.5 rounded bg-zinc-800/80 text-zinc-300 border border-zinc-700/60 text-[9px] font-mono font-medium shrink-0">
              ZERO-NET
            </span>
          </div>
        )}
      </div>
    </aside>
  )
}


