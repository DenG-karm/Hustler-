import { useState, type FC, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../../../lib/utils'
import { Button } from '../Button/Button'

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
  logo?: ReactNode
  items: SidebarItem[]
  isCollapsed?: boolean
  defaultCollapsed?: boolean
  onToggleCollapse?: (collapsed: boolean) => void
  footer?: ReactNode
}

export const Sidebar: FC<SidebarProps> = ({
  title = 'Hustler',
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

  return (
    <aside
      aria-expanded={!isCollapsed}
      className={cn(
        'flex flex-col h-full bg-surface border-r border-border transition-all duration-200 select-none',
        isCollapsed ? 'w-16' : 'w-64',
        className,
      )}
      {...props}
    >
      {/* Sidebar Header */}
      <div className="flex items-center justify-between p-md border-b border-border min-h-[4rem]">
        {!isCollapsed && (
          <div className="flex items-center gap-sm overflow-hidden">
            {logo || (
              <div
                data-testid="sidebar-logo"
                className="w-8 h-8 rounded-md bg-primary flex items-center justify-center text-primary-fg font-bold text-sm shrink-0"
              >
                H
              </div>
            )}
            <span className="font-semibold text-text-primary truncate text-base">{title}</span>
          </div>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={handleToggle}
          aria-label={isCollapsed ? 'Sidebarı Genişlet' : 'Sidebarı Daralt'}
          className={cn('shrink-0 text-text-secondary hover:text-text-primary', isCollapsed && 'mx-auto')}
        >
          <svg
            className={cn('w-4 h-4 transition-transform duration-200', isCollapsed && 'rotate-180')}
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </Button>
      </div>

      {/* Navigation Items */}
      <nav className="flex-1 overflow-y-auto p-sm space-y-xs" aria-label="Ana Menü">
        {items.map((item) => {
          const isActive = !!item.active
          return (
            <button
              key={item.id}
              type="button"
              onClick={item.onClick}
              title={isCollapsed ? item.label : undefined}
              className={cn(
                'w-full flex items-center gap-md px-md py-sm rounded-md text-sm font-medium transition-colors text-left',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                isActive
                  ? 'bg-accent text-accent-fg font-semibold'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover',
                isCollapsed && 'justify-center px-sm',
              )}
            >
              {item.icon ? (
                <span className="shrink-0 text-base">{item.icon}</span>
              ) : (
                <span className="w-4 h-4 rounded-full bg-border shrink-0" />
              )}
              {!isCollapsed && (
                <span className="truncate flex-1">{item.label}</span>
              )}
              {!isCollapsed && item.badge !== undefined && (
                <span className="px-xs py-0.5 text-xs font-semibold rounded-full bg-surface-hover text-text-muted shrink-0">
                  {item.badge}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Sidebar Footer */}
      {footer && (
        <div className="p-md border-t border-border mt-auto">
          {footer}
        </div>
      )}
    </aside>
  )
}
