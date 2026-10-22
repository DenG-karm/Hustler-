import { createContext, useContext, useEffect, useState, useMemo, type ReactNode } from 'react'

export type Theme = 'light'
export type ResolvedTheme = 'light'

export interface ThemeContextValue {
  theme: Theme
  resolvedTheme: ResolvedTheme
  setTheme: (theme: Theme) => void
}

const THEME_STORAGE_KEY = 'hustler-theme-preference'

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

export interface ThemeProviderProps {
  children: ReactNode
  defaultTheme?: Theme
  storageKey?: string
}

export function ThemeProvider({
  children,
  storageKey = THEME_STORAGE_KEY,
}: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>('light')
  const resolvedTheme: ResolvedTheme = 'light'

  // Koyu temayı kaldır ve daima açık temayı zorla
  useEffect(() => {
    if (typeof document === 'undefined') return
    const root = document.documentElement
    root.classList.remove('dark')
    root.style.colorScheme = 'light'
    try {
      localStorage.setItem(storageKey, 'light')
    } catch {
      // Ignore
    }
  }, [storageKey])

  const setTheme = (_newTheme: Theme) => {
    setThemeState('light')
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
