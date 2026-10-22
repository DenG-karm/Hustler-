import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Sidebar, type SidebarItem } from './Sidebar'

const mockItems: SidebarItem[] = [
  { id: 'channels', label: 'Kanallar', badge: 3, active: true },
  { id: 'library', label: 'Kütüphane' },
  { id: 'templates', label: 'Şablonlar' },
  { id: 'settings', label: 'Ayarlar' },
]

describe('Sidebar Component', () => {
  it('renders sidebar with title and all items in expanded state by default', () => {
    render(<Sidebar title="Hustler" subtitle="v1.0 Studio" items={mockItems} />)

    expect(screen.getByText('Hustler')).toBeInTheDocument()
    expect(screen.getByText('v1.0 Studio')).toBeInTheDocument()
    expect(screen.getByText('Kanallar')).toBeInTheDocument()
    expect(screen.getByText('Kütüphane')).toBeInTheDocument()
    expect(screen.getByText('Şablonlar')).toBeInTheDocument()
    expect(screen.getByText('Ayarlar')).toBeInTheDocument()
    expect(screen.getByRole('complementary')).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('complementary')).toHaveClass('w-60')
  })

  it('highlights the active item with soft zinc surface and 2px teal rail without ring/outline', () => {
    render(<Sidebar items={mockItems} />)

    const activeItem = screen.getByRole('button', { name: /kanallar/i })
    expect(activeItem).toHaveClass('dark:bg-zinc-800/80')
    expect(activeItem).toHaveClass('font-medium')
    expect(activeItem).toHaveClass('outline-none')
  })

  it('toggles collapse state when toggle button is clicked and hides footer text when collapsed', async () => {
    const handleToggle = vi.fn()
    const user = userEvent.setup()
    render(<Sidebar title="Hustler" items={mockItems} onToggleCollapse={handleToggle} />)

    const aside = screen.getByRole('complementary')
    const toggleButton = screen.getByRole('button', { name: /sidebarı daralt/i })

    expect(aside).toHaveAttribute('aria-expanded', 'true')
    expect(aside).toHaveClass('w-60')

    // Click to collapse
    await user.click(toggleButton)

    expect(handleToggle).toHaveBeenCalledWith(true)
    expect(aside).toHaveAttribute('aria-expanded', 'false')
    expect(aside).toHaveClass('w-16')
    expect(screen.queryByText('Hustler')).not.toBeInTheDocument()
    expect(screen.getByTestId('sidebar-footer-collapsed')).toHaveAttribute(
      'title',
      'Hustler Core v1.0.0 — Zero-Net Aktif',
    )

    // Click to expand again
    const expandButton = screen.getByRole('button', { name: /sidebarı genişlet/i })
    await user.click(expandButton)

    expect(handleToggle).toHaveBeenCalledWith(false)
    expect(aside).toHaveAttribute('aria-expanded', 'true')
    expect(aside).toHaveClass('w-60')
  })

  it('triggers item onClick handler when an item is clicked', async () => {
    const handleItemClick = vi.fn()
    const itemsWithAction: SidebarItem[] = [
      { id: 'library', label: 'Kütüphane', onClick: handleItemClick },
    ]
    const user = userEvent.setup()

    render(<Sidebar items={itemsWithAction} />)
    await user.click(screen.getByRole('button', { name: /kütüphane/i }))

    expect(handleItemClick).toHaveBeenCalledTimes(1)
  })

  it('renders custom footer when provided in expanded mode', () => {
    render(
      <Sidebar
        items={mockItems}
        footer={<div data-testid="sidebar-footer">v1.0.0 Pro</div>}
      />,
    )

    expect(screen.getByTestId('sidebar-footer')).toBeInTheDocument()
    expect(screen.getByText('v1.0.0 Pro')).toBeInTheDocument()
  })
})

