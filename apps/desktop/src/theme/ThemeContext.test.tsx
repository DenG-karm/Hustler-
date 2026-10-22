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
    </div>
  )
}

describe('Theme Engine (Light Theme Only)', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.className = ''
  })

  it('provides default light theme and does not apply dark class', () => {
    render(
      <ThemeProvider defaultTheme="light">
        <ThemeTestConsumer />
      </ThemeProvider>,
    )

    expect(screen.getByTestId('current-theme')).toHaveTextContent('light')
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('removes dark class if previously present and enforces light mode', () => {
    document.documentElement.classList.add('dark')
    render(
      <ThemeProvider>
        <ThemeTestConsumer />
      </ThemeProvider>,
    )

    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('keeps theme as light when setTheme is called', async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <ThemeTestConsumer />
      </ThemeProvider>,
    )

    await user.click(screen.getByRole('button', { name: /light yap/i }))
    expect(screen.getByTestId('current-theme')).toHaveTextContent('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('throws an error if useTheme is used outside of ThemeProvider', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<ThemeTestConsumer />)).toThrow(
      'useTheme must be used within a ThemeProvider',
    )
    consoleError.mockRestore()
  })
})
