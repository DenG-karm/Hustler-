import { useState, useEffect } from 'react'
import { Sidebar, type SidebarItem } from './components/ui/Sidebar/Sidebar'
import { Button } from './components/ui/Button/Button'
import { useTheme } from './theme/ThemeContext'
import { FlowContainer } from './components/flow/FlowContainer'
import { ErrorModal } from './components/ui/ErrorModal'
import { ToastContainer } from './components/ui/ToastContainer'
import { useFlowStore } from './store/flowStore'

export function App() {
  const { theme, resolvedTheme, setTheme } = useTheme()
  const [activeTab, setActiveTab] = useState<'pipeline' | 'gallery' | 'channels' | 'library' | 'settings'>('pipeline')
  const [isRenderLoading, setIsRenderLoading] = useState(false)

  const connectionState = useFlowStore((s) => s.connectionState)
  const reconnectAttempt = useFlowStore((s) => s.reconnectAttempt)
  const subscribeEvents = useFlowStore((s) => s.subscribeEvents)

  useEffect(() => {
    let unlisten: (() => void) | undefined
    subscribeEvents().then((fn) => {
      unlisten = fn
    })

    return () => {
      if (unlisten) unlisten()
    }
  }, [subscribeEvents])

  const sidebarItems: SidebarItem[] = [
    {
      id: 'pipeline',
      label: 'Akış Stüdyosu (K-702)',
      badge: 7,
      active: activeTab === 'pipeline',
      onClick: () => setActiveTab('pipeline'),
    },
    {
      id: 'gallery',
      label: 'Bileşen Galerisi (K-701)',
      active: activeTab === 'gallery',
      onClick: () => setActiveTab('gallery'),
    },
    {
      id: 'channels',
      label: 'Kanallar',
      badge: 4,
      active: activeTab === 'channels',
      onClick: () => setActiveTab('channels'),
    },
    {
      id: 'library',
      label: 'Kütüphane',
      badge: 12,
      active: activeTab === 'library',
      onClick: () => setActiveTab('library'),
    },
    {
      id: 'settings',
      label: 'Ayarlar',
      active: activeTab === 'settings',
      onClick: () => setActiveTab('settings'),
    },
  ]

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-app text-text-primary" data-testid="app-root">
      {/* K-701 / K-702 Sidebar */}
      <Sidebar
        title="Hustler Studio"
        items={sidebarItems}
        footer={
          <div className="flex flex-col gap-xs text-xs text-text-muted">
            <span className="font-semibold text-text-secondary">Hustler Desktop</span>
            <span>Tasarım & Akış v2.0</span>
          </div>
        }
      />

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Top Navigation Bar */}
        <header className="flex items-center justify-between px-lg py-md border-b border-border bg-surface shrink-0">
          <div>
            <h1 className="text-xl font-bold text-text-primary tracking-tight">
              {activeTab === 'pipeline'
                ? 'Akış Ekranları & Durum Makinesi (K-702 & K-703)'
                : 'Tasarım Sistemi & Bileşen Galerisi (K-701)'}
            </h1>
            <p className="text-sm text-text-secondary">
              {activeTab === 'pipeline'
                ? 'Tauri Event Bridge, RFC 7807 Problem Details & Hard-Cancel'
                : 'Tauri, Vite, React, Tailwind CSS ve Vitest token mimarisi'}
            </p>
          </div>

          <div className="flex items-center gap-md">
            {/* K-703 Event Bridge Bağlantı Durumu */}
            <div
              className={`flex items-center gap-xs px-sm py-1 rounded-full text-xs font-mono border ${
                connectionState === 'connected'
                  ? 'bg-success/10 text-success border-success/30'
                  : connectionState === 'reconnecting'
                  ? 'bg-warning/10 text-warning border-warning/30 animate-pulse'
                  : 'bg-surface-hover text-text-muted border-border'
              }`}
              data-testid="connection-status-indicator"
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  connectionState === 'connected'
                    ? 'bg-success'
                    : connectionState === 'reconnecting'
                    ? 'bg-warning'
                    : 'bg-text-muted'
                }`}
              />
              <span>
                {connectionState === 'connected'
                  ? 'Event Stream Bağlı'
                  : connectionState === 'reconnecting'
                  ? `Yeniden Bağlanılıyor (${reconnectAttempt})`
                  : 'Bağlantı Bekleniyor'}
              </span>
            </div>

            {/* Theme Selector */}
            <div className="flex items-center gap-xs p-xs rounded-lg border border-border bg-surface-hover">
              <Button
                variant={theme === 'light' ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => setTheme('light')}
                aria-label="Açık Tema"
              >
                Açık
              </Button>
              <Button
                variant={theme === 'dark' ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => setTheme('dark')}
                aria-label="Koyu Tema"
              >
                Koyu
              </Button>
              <Button
                variant={theme === 'system' ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => setTheme('system')}
                aria-label="Sistem Teması"
              >
                Sistem ({resolvedTheme})
              </Button>
            </div>
          </div>
        </header>

        {/* Tab Body */}
        {activeTab === 'pipeline' ? (
          <div className="flex-1 overflow-hidden">
            <FlowContainer />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-lg space-y-xl max-w-5xl">
            {/* Section 1: Button Variants */}
            <section className="p-lg rounded-xl border border-border bg-surface space-y-md shadow-sm">
              <div className="border-b border-border-subtle pb-sm">
                <h2 className="text-lg font-semibold text-text-primary">Button Bileşeni Varyantları</h2>
                <p className="text-sm text-text-secondary">
                  Tüm renkler ve aralıklar global token değişkenlerinden beslenir.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-md">
                <Button variant="primary">Primary (Marka)</Button>
                <Button variant="secondary">Secondary</Button>
                <Button variant="outline">Outline</Button>
                <Button variant="ghost">Ghost</Button>
                <Button variant="destructive">Destructive (Tehlike)</Button>
              </div>
            </section>

            {/* Section 2: Button Sizes & States */}
            <section className="p-lg rounded-xl border border-border bg-surface space-y-md shadow-sm">
              <div className="border-b border-border-subtle pb-sm">
                <h2 className="text-lg font-semibold text-text-primary">Button Boyutları ve Durumları</h2>
                <p className="text-sm text-text-secondary">
                  Erişilebilir durumlar: normal, yükleniyor, kilitli.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-md">
                <Button size="sm" variant="secondary">
                  Küçük (sm)
                </Button>
                <Button size="md" variant="secondary">
                  Standart (md)
                </Button>
                <Button size="lg" variant="secondary">
                  Büyük (lg)
                </Button>
                <Button
                  variant="primary"
                  isLoading={isRenderLoading}
                  onClick={() => {
                    setIsRenderLoading(true)
                    setTimeout(() => setIsRenderLoading(false), 2000)
                  }}
                >
                  {isRenderLoading ? 'Render Alınıyor' : 'Tıkla (Spinner Testi)'}
                </Button>
                <Button variant="primary" disabled>
                  Devre Dışı (Disabled)
                </Button>
              </div>
            </section>
          </div>
        )}
      </main>

      {/* Global K-703 Dialogs */}
      <ErrorModal />
      <ToastContainer />
    </div>
  )
}

export default App
