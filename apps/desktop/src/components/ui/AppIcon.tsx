import type { FC } from 'react'

const PATHS = {
  film: 'M2 4h20v16H2zm0 4.5h20M2 15.5h20M8 4v4.5M16 4v4.5M8 15.5V20M16 15.5V20',
  bolt: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
  play: 'M6 4.5v15l13-7.5-13-7.5z',
  pause: 'M6 4h4v16H6zm8 0h4v16h-4z',
  rewind: 'M19 5.5l-9 6.5 9 6.5V5.5zM8 5.5H5v13h3V5.5z',
  home: 'M3 10.5L12 3l9 7.5V20a1.5 1.5 0 01-1.5 1.5h-4.5v-6h-6v6H4.5A1.5 1.5 0 013 20v-9.5z',
  settings: 'M12 15a3 3 0 100-6 3 3 0 000 6zm7.4-3a7.4 7.4 0 00-.1-.9l2.1-1.6-2-3.5-2.5 1a7.4 7.4 0 00-1.6-.9l-.4-2.6h-4l-.4 2.6a7.4 7.4 0 00-1.6.9l-2.5-1-2 3.5 2.1 1.6a7.4 7.4 0 000 1.8l-2.1 1.6 2 3.5 2.5-1a7.4 7.4 0 001.6.9l.4 2.6h4l.4-2.6a7.4 7.4 0 001.6-.9l2.5 1 2-3.5-2.1-1.6a7.4 7.4 0 00.1-.9z',
  spark: 'M12 2l2.4 6.6L21 11l-6.6 2.4L12 20l-2.4-6.6L3 11l6.6-2.4L12 2z',
  close: 'M18 6L6 18M6 6l12 12',
  menu: 'M4 6h16M4 12h16M4 18h16',
  edit: 'M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.1 2.1 0 013 3L12 15l-4 1 1-4 9.5-9.5z',
  send: 'M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z',
  trend: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6',
  right: 'M9 5l7 7-7 7',
  left: 'M15 19l-7-7 7-7',
  check: 'M5 13l4 4L19 7',
  spin: 'M4 4v5h.58M19.9 11A8 8 0 004.6 9M20 20v-5h-.58M4.1 13a8 8 0 0015.3 2',
  plus: 'M12 5v14M5 12h14',
  chart: 'M3 3v18h18M7 16l4-4 4 4 5-6',
  copy: 'M8 4v12a2 2 0 002 2h8a2 2 0 002-2V4a2 2 0 00-2-2h-8a2 2 0 00-2 2zM4 8v12a2 2 0 002 2h8',
} as const

export type AppIconName = keyof typeof PATHS

const FILLED = 'play pause rewind'

export const AppIcon: FC<{ name: AppIconName; className?: string }> = ({ name, className = 'w-4 h-4' }) => {
  const isFilled = FILLED.includes(name)
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill={isFilled ? 'currentColor' : 'none'}
      stroke={isFilled ? 'none' : 'currentColor'}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
