import { createContext, useContext, useEffect, useState, useMemo, type ReactNode } from 'react'

export type Theme = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

export interface ThemeContextValue {
  theme: Theme
  resolvedTheme: ResolvedTheme
  setTheme: (theme: Theme) => void
}

const THEME_STORAGE_KEY = 'hustler-theme-preference'

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

function getSystemTheme(): ResolvedTheme {
  if (typeof window === 'undefined') return 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export interface ThemeProviderProps {
  children: ReactNode
  defaultTheme?: Theme
  storageKey?: string
}

export function ThemeProvider({
  children,
  defaultTheme = 'system',
  storageKey = THEME_STORAGE_KEY,
}: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window === 'undefined') return defaultTheme
    try {
      const saved = localStorage.getItem(storageKey) as Theme | null
      if (saved && (saved === 'light' || saved === 'dark' || saved === 'system')) {
        return saved
      }
    } catch {
      // localStorage may fail in restricted environments
    }
    return defaultTheme
  })

  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(getSystemTheme)

  // Listen to system prefers-color-scheme changes
  useEffect(() => {
    if (typeof window === 'undefined') return

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = (e: MediaQueryListEvent) => {
      setSystemTheme(e.matches ? 'dark' : 'light')
    }

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange)
      return () => mediaQuery.removeEventListener('change', handleChange)
    } else {
      // Legacy browser support
      mediaQuery.addListener(handleChange)
      return () => mediaQuery.removeListener(handleChange)
    }
  }, [])

  const resolvedTheme: ResolvedTheme = useMemo(() => {
    return theme === 'system' ? systemTheme : theme
  }, [theme, systemTheme])

  // Apply `dark` class to <html> element at DOM level
  useEffect(() => {
    if (typeof document === 'undefined') return

    const root = document.documentElement
    if (resolvedTheme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }, [resolvedTheme])

  const setTheme = (newTheme: Theme) => {
    try {
      localStorage.setItem(storageKey, newTheme)
    } catch {
      // Ignore localStorage write error
    }
    setThemeState(newTheme)
  }

  const value = useMemo(
    () => ({
      theme,
      resolvedTheme,
      setTheme,
    }),
    [theme, resolvedTheme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
