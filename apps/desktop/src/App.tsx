import { useState, useEffect } from 'react'
import { FlowContainer } from './components/flow/FlowContainer'
import { ErrorModal } from './components/ui/ErrorModal'
import { ToastContainer } from './components/ui/ToastContainer'
import { StatusBar } from './components/ui/StatusBar/StatusBar'
import { ColdStartSplash } from './components/ui/ColdStartSplash'
import { HustlerAiWidget } from './components/assistant/HustlerAiWidget'
import { ChannelsScreen } from './components/channels/ChannelsScreen'
import { TemplateManager } from './components/templates/TemplateManager'
import { AppIcon } from './components/ui/AppIcon'
import { useFlowStore } from './store/flowStore'
import { useSupervisorStore } from './store/supervisorStore'


export function App() {
  const [isAiOpen, setIsAiOpen] = useState(true)

  const connectionState = useFlowStore((s) => s.connectionState)
  const reconnectAttempt = useFlowStore((s) => s.reconnectAttempt)
  const subscribeEvents = useFlowStore((s) => s.subscribeEvents)
  const initSupervisorLifecycle = useSupervisorStore((s) => s.initSupervisorLifecycle)
  const activeTab = useFlowStore((s) => s.activeView)
  const setActiveView = useFlowStore((s) => s.setActiveView)
  const selectChannel = useFlowStore((s) => s.selectChannel)
  const loadChannels = useFlowStore((s) => s.loadChannels)

  useEffect(() => { void loadChannels() }, [loadChannels])

  useEffect(() => {
    const handleToggleAi = () => setIsAiOpen((prev) => !prev)
    window.addEventListener('hustler:toggle-ai', handleToggleAi)
    return () => window.removeEventListener('hustler:toggle-ai', handleToggleAi)
  }, [])

  useEffect(() => {
    let unlisten: (() => void) | undefined
    subscribeEvents().then((fn) => { unlisten = fn })
    return () => { unlisten?.() }
  }, [subscribeEvents])

  useEffect(() => {
    let unlisten: (() => void) | undefined
    initSupervisorLifecycle().then((fn) => { unlisten = fn })
    return () => { unlisten?.() }
  }, [initSupervisorLifecycle])

  const goHome = () => {
    setActiveView('channels')
    selectChannel(null)
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#F8F9FA] dark:bg-zinc-950 text-text-primary" data-testid="app-root">
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        <header className="h-16 flex items-center justify-between px-6 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shrink-0 relative select-none">
          <div className="flex items-center gap-3 text-xs">
            <button type="button" onClick={goHome} className="flex items-center gap-1.5 text-xs cursor-pointer bg-transparent border-0 p-0">
              <span className="text-zinc-400">Workspace</span>
              <span className="text-zinc-300 dark:text-zinc-600">/</span>
              <span className="font-semibold text-zinc-900 dark:text-zinc-200">Main</span>
            </button>
          </div>

          <div className="absolute left-1/2 -translate-x-1/2 flex items-center justify-center">
            <button type="button" onClick={goHome} className="text-[22px] font-semibold tracking-tight text-zinc-900 dark:text-zinc-100 cursor-pointer bg-transparent border-0 p-0">
              Hustler
            </button>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono border ${
                connectionState === 'connected'
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                  : connectionState === 'reconnecting'
                  ? 'bg-warning/15 text-warning border-warning/30 animate-pulse'
                  : 'bg-zinc-200/60 dark:bg-zinc-800/60 text-zinc-500 border-zinc-300 dark:border-zinc-700'
              }`}
              data-testid="connection-status-indicator"
            >
              <span className={`w-1.5 h-1.5 rounded-full ${connectionState === 'connected' ? 'bg-emerald-400' : connectionState === 'reconnecting' ? 'bg-warning' : 'bg-zinc-500'}`} />
              <span>
                {connectionState === 'connected' ? 'Event Stream Bağlı' : connectionState === 'reconnecting' ? `Yeniden Bağlanılıyor (${reconnectAttempt})` : 'Bağlantı Bekleniyor'}
              </span>
            </div>

            <button
              type="button"
              onClick={goHome}
              className="p-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer flex items-center gap-1.5 bg-white dark:bg-zinc-900"
              title="Ana Sayfaya Dön"
              aria-label="Ana Sayfaya Dön"
              data-testid="home-nav-btn"
            >
              <AppIcon name="home" className="w-3.5 h-3.5" />
              <span className="hidden md:inline text-[11px] font-semibold">Ana Sayfa</span>
            </button>

            <button
              type="button"
              onClick={() => setIsAiOpen(!isAiOpen)}
              className={`p-1.5 rounded-lg border text-xs font-medium flex items-center gap-1.5 cursor-pointer ${
                isAiOpen ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 border-zinc-300 dark:border-zinc-700' : 'text-zinc-500 border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900'
              }`}
              title="Hustler AI Asistanı"
              aria-label="Hustler AI Asistanı"
            >
              <AppIcon name="spark" className="w-3.5 h-3.5 text-zinc-900 dark:text-zinc-100" />
              <span className="hidden md:inline text-[11px] font-semibold">AI</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveView('settings')}
              className="p-1.5 text-zinc-400 hover:text-zinc-600 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer text-sm leading-none flex items-center justify-center"
              title="Ayarlar"
              aria-label="Ayarlar"
            >
              <AppIcon name="settings" className="w-3.5 h-3.5" />
            </button>
          </div>
        </header>

        <div className="flex-1 flex overflow-hidden relative">
          <div className="flex-1 overflow-hidden flex flex-col">
            {activeTab === 'pipeline' ? (
              <div className="flex-1 overflow-hidden"><FlowContainer /></div>
            ) : activeTab === 'templates' ? (
              <div className="flex-1 overflow-y-auto"><TemplateManager /></div>
            ) : activeTab === 'channels' ? (
              <div className="flex-1 overflow-hidden"><ChannelsScreen /></div>
            ) : (
              <div className="flex-1 overflow-y-auto p-6">
                <div className="max-w-4xl mx-auto p-5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-between">
                  <div>
                    <h2 className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">Mimari Güvenlik ve Sistem Parametreleri</h2>
                    <p className="text-[11px] text-zinc-500 font-mono mt-1">ZERO-NETWORK • JobObject • SHA-256 Önbellek</p>
                  </div>
                  <button type="button" onClick={goHome} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-zinc-900 text-white cursor-pointer">Kanallara Dön</button>
                </div>
              </div>
            )}
          </div>
          <div className="z-50 flex shrink-0">
            <HustlerAiWidget isOpen={isAiOpen} onClose={() => setIsAiOpen(false)} />
          </div>
        </div>

        <StatusBar />
      </main>
      <ColdStartSplash />
      <ErrorModal />
      <ToastContainer />
    </div>
  )
}

export default App
