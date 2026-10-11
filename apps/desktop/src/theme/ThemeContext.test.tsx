import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider, useTheme } from './ThemeContext'

function ThemeTestConsumer() {
  const { theme, resolvedTheme, setTheme } = useTheme()
  return (
    <div>
      <span data-testid="current-theme">{theme}</span>
      <span data-testid="resolved-theme">{resolvedTheme}</span>
      <button onClick={() => setTheme('light')}>Light Yap</button>
      <button onClick={() => setTheme('dark')}>Dark Yap</button>
      <button onClick={() => setTheme('system')}>System Yap</button>
    </div>
  )
}

describe('Theme Engine (ThemeProvider & useTheme)', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.className = ''
  })

  it('provides default theme and updates documentElement class on dark theme', async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider defaultTheme="light">
        <ThemeTestConsumer />
      </ThemeProvider>,
    )

    expect(screen.getByTestId('current-theme')).toHaveTextContent('light')
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)

    // Switch to dark
    await user.click(screen.getByRole('button', { name: /dark yap/i }))

    expect(screen.getByTestId('current-theme')).toHaveTextContent('dark')
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('hustler-theme-preference')).toBe('dark')
  })

  it('switches back to light theme and removes dark class', async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider defaultTheme="dark">
        <ThemeTestConsumer />
      </ThemeProvider>,
    )

    expect(document.documentElement.classList.contains('dark')).toBe(true)

    // Switch to light
    await user.click(screen.getByRole('button', { name: /light yap/i }))

    expect(screen.getByTestId('current-theme')).toHaveTextContent('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('hustler-theme-preference')).toBe('light')
  })

  it('resolves system theme based on prefers-color-scheme media query', () => {
    render(
      <ThemeProvider defaultTheme="system">
        <ThemeTestConsumer />
      </ThemeProvider>,
    )

    expect(screen.getByTestId('current-theme')).toHaveTextContent('system')
    // In our test setup, matchMedia query with dark returned false -> light
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('light')
  })

  it('throws an error if useTheme is used outside of ThemeProvider', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<ThemeTestConsumer />)).toThrow(
      'useTheme must be used within a ThemeProvider',
    )
    consoleError.mockRestore()
  })
})
