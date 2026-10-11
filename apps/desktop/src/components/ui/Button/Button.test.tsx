import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from './Button'

describe('Button Component', () => {
  it('renders button with children text', () => {
    render(<Button>Projeyi Başlat</Button>)
    const button = screen.getByRole('button', { name: /projeyi başlat/i })
    expect(button).toBeInTheDocument()
  })

  it('applies primary variant classes by default', () => {
    render(<Button>Kaydet</Button>)
    const button = screen.getByRole('button')
    expect(button).toHaveClass('bg-primary')
    expect(button).toHaveClass('text-primary-fg')
  })

  it('applies secondary variant classes correctly', () => {
    render(<Button variant="secondary">İptal</Button>)
    const button = screen.getByRole('button')
    expect(button).toHaveClass('bg-secondary')
    expect(button).toHaveClass('text-secondary-fg')
  })

  it('applies outline variant classes correctly', () => {
    render(<Button variant="outline">Detaylar</Button>)
    const button = screen.getByRole('button')
    expect(button).toHaveClass('border-border')
    expect(button).toHaveClass('text-text-primary')
  })

  it('applies destructive variant classes correctly', () => {
    render(<Button variant="destructive">Sil</Button>)
    const button = screen.getByRole('button')
    expect(button).toHaveClass('bg-destructive')
    expect(button).toHaveClass('text-destructive-fg')
  })

  it('applies size classes correctly', () => {
    const { rerender } = render(<Button size="sm">Küçük</Button>)
    expect(screen.getByRole('button')).toHaveClass('text-xs')

    rerender(<Button size="lg">Büyük</Button>)
    expect(screen.getByRole('button')).toHaveClass('text-base')
  })

  it('triggers onClick handler when clicked', async () => {
    const handleClick = vi.fn()
    const user = userEvent.setup()
    render(<Button onClick={handleClick}>Tıkla</Button>)

    await user.click(screen.getByRole('button'))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('does not trigger onClick when disabled', async () => {
    const handleClick = vi.fn()
    const user = userEvent.setup()
    render(<Button disabled onClick={handleClick}>Kilitli</Button>)

    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
    expect(button).toHaveClass('disabled:opacity-50')

    await user.click(button)
    expect(handleClick).not.toHaveBeenCalled()
  })

  it('displays loading spinner and prevents clicks when isLoading=true', async () => {
    const handleClick = vi.fn()
    const user = userEvent.setup()
    render(
      <Button isLoading onClick={handleClick}>
        Render Alınıyor
      </Button>,
    )

    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
    expect(screen.getByTestId('button-spinner')).toBeInTheDocument()

    await user.click(button)
    expect(handleClick).not.toHaveBeenCalled()
  })

  it('merges custom className with design tokens', () => {
    render(<Button className="custom-test-class">Özel</Button>)
    const button = screen.getByRole('button')
    expect(button).toHaveClass('custom-test-class')
    expect(button).toHaveClass('bg-primary')
  })
})
