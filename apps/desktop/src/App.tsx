import { useState, useEffect, lazy, Suspense } from 'react'
import { FlowContainer } from './components/flow/FlowContainer'
import { ErrorModal } from './components/ui/ErrorModal'
import { ToastContainer } from './components/ui/ToastContainer'
import { StatusBar } from './components/ui/StatusBar/StatusBar'
import { ColdStartSplash } from './components/ui/ColdStartSplash'
import { HustlerAiWidget } from './components/assistant/HustlerAiWidget'
import { useFlowStore } from './store/flowStore'
import { useSupervisorStore } from './store/supervisorStore'

// Faz F9: React.lazy ile Dinamik Yükleme
const TemplateManager = lazy(() =>
  import('./components/templates/TemplateManager').then((m) => ({ default: m.TemplateManager }))
)
const ChannelsScreen = lazy(() =>
  import('./components/channels/ChannelsScreen').then((m) => ({ default: m.ChannelsScreen }))
)


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

  useEffect(() => {
    void loadChannels()
  }, [loadChannels])

  useEffect(() => {
    let unlisten: (() => void) | undefined
    subscribeEvents().then((fn) => {
      unlisten = fn
    })

    return () => {
      if (unlisten) unlisten()
    }
  }, [subscribeEvents])

  // K-708: Supervisor pencere kapanışı ve alt süreç sonlandırma yaşam döngüsü
  useEffect(() => {
    let unlisten: (() => void) | undefined
    initSupervisorLifecycle().then((fn) => {
      unlisten = fn
    })

    return () => {
      if (unlisten) unlisten()
    }
  }, [initSupervisorLifecycle])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#F8F9FA] dark:bg-zinc-950 text-text-primary" data-testid="app-root">
      {/* Ana Çalışma Alanı */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Üst Stüdyo Kontrol Çubuğu (Top Deck) */}
        <header className="h-16 flex items-center justify-between px-6 border-b border-[#EAECEF] dark:border-zinc-800 bg-white dark:bg-zinc-900 shrink-0 relative select-none">
          {/* Sol: Hamburger İkonu & Breadcrumb */}
          <div className="flex items-center gap-3 text-xs">
            <button
              type="button"
              onClick={() => {
                setActiveView('channels')
                selectChannel(null)
              }}
              className="p-1.5 -ml-1 text-[#4B5563] hover:text-[#111827] dark:text-zinc-400 dark:hover:text-zinc-100 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
              title="Kanallara Dön (Ana Sayfa)"
              aria-label="Kanallara Dön (Ana Sayfa)"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
              </svg>
            </button>

            <button
              type="button"
              onClick={() => {
                setActiveView('channels')
                selectChannel(null)
              }}
              className="flex items-center gap-1.5 text-xs cursor-pointer select-none bg-transparent border-0 p-0"
            >
              <span className="font-normal text-[#9CA3AF]">Workspace</span>
              <span className="text-[#D1D5DB] dark:text-zinc-600">/</span>
              <span className="font-semibold text-[#111827] dark:text-zinc-200">Main</span>
            </button>
          </div>

          {/* Orta: Ortalanmış Marka Başlığı */}
          <div className="absolute left-1/2 -translate-x-1/2 flex items-center justify-center">
            <button
              type="button"
              onClick={() => {
                setActiveView('channels')
                selectChannel(null)
              }}
              className="text-[22px] font-semibold tracking-tight text-[#111827] dark:text-zinc-100 cursor-pointer bg-transparent border-0 p-0"
            >
              Hustler
            </button>
          </div>

          {/* Sağ: Kontroller, Avatar, Bildirim & Ayarlar */}
          <div className="flex items-center gap-3 shrink-0">
            {/* K-703 Event Bridge Bağlantı Durumu */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono border ${
                connectionState === 'connected'
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                  : connectionState === 'reconnecting'
                  ? 'bg-warning/15 text-warning border-warning/30 animate-pulse'
                  : 'bg-zinc-200/60 dark:bg-zinc-800/60 text-zinc-500 dark:text-zinc-400 border-border/80'
              }`}
              data-testid="connection-status-indicator"
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  connectionState === 'connected'
                    ? 'bg-emerald-400'
                    : connectionState === 'reconnecting'
                    ? 'bg-warning'
                    : 'bg-zinc-500'
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

            {/* Ana Sayfa (Ev) Butonu */}
            <button
              type="button"
              onClick={() => {
                setActiveView('channels')
                selectChannel(null)
              }}
              className="p-1.5 rounded-lg border border-[#E5E7EB] dark:border-zinc-800 text-zinc-600 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer flex items-center gap-1.5 bg-white dark:bg-zinc-900 shadow-2xs"
              title="Ana Sayfaya Dön (Ev)"
              aria-label="Ana Sayfaya Dön (Ev)"
              data-testid="home-nav-btn"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
              </svg>
              <span className="hidden md:inline text-[11px] font-semibold">Ana Sayfa</span>
            </button>

            {/* Hustler AI Toggle Butonu */}
            <button
              type="button"
              onClick={() => setIsAiOpen(!isAiOpen)}
              className={`p-1.5 rounded-lg border text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer ${
                isAiOpen
                  ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 border-zinc-300 dark:border-zinc-700'
                  : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-2xs'
              }`}
              title="Hustler AI Asistanı"
              aria-label="Hustler AI Asistanı"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="10" rx="2" />
                <circle cx="12" cy="5" r="2" />
                <path d="M12 7v4" />
              </svg>
              <span className="hidden md:inline text-[11px] font-semibold">AI</span>
            </button>

            {/* Profil Avatarı */}
            <div
              className="w-7 h-7 rounded-full bg-zinc-200 dark:bg-zinc-700 border border-zinc-300 dark:border-zinc-600 flex items-center justify-center overflow-hidden shrink-0 shadow-2xs"
              title="Kullanıcı Profili"
            >
              <svg className="w-4 h-4 text-zinc-500 dark:text-zinc-300" viewBox="0 0 24 24" fill="currentColor">
                <path fillRule="evenodd" d="M7.5 6a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM3.751 20.105a8.25 8.25 0 0116.498 0 .75.75 0 01-.437.695A18.683 18.683 0 0112 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 01-.437-.695z" clipRule="evenodd" />
              </svg>
            </div>

            {/* Bildirim Zili (Kırmızı Noktalı) */}
            <button
              type="button"
              className="relative p-1.5 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
              title="Bildirimler"
              aria-label="Bildirimler"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
              </svg>
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-red-500 ring-2 ring-white dark:ring-zinc-900" />
            </button>

            {/* Ayarlar Dişlisi */}
            <button
              type="button"
              onClick={() => {
                setActiveView('settings')
              }}
              className="p-1.5 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
              title="Ayarlar"
              aria-label="Ayarlar"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
          </div>
        </header>

        {/* Ana İçerik ve Sağ Panel Grid */}
        <div className="flex-1 flex overflow-hidden relative">
          <div className="flex-1 overflow-hidden flex flex-col">
            {/* Sekme İçeriği */}
            {activeTab === 'pipeline' ? (
              <div className="flex-1 overflow-hidden">
                <FlowContainer />
              </div>
            ) : activeTab === 'templates' ? (
              <div className="flex-1 overflow-y-auto bg-[#F8F9FA] dark:bg-zinc-950">
                <Suspense fallback={<div className="p-xl text-center text-xs font-mono text-text-muted">ŞABLON MODÜLÜ YÜKLENİYOR...</div>}>
                  <TemplateManager />
                </Suspense>
              </div>
            ) : activeTab === 'channels' ? (
              <div className="flex-1 overflow-hidden">
                <Suspense fallback={<div className="p-xl text-center text-xs font-mono text-text-muted">KANAL ÇALIŞMA ALANI YÜKLENİYOR...</div>}>
                  <ChannelsScreen />
                </Suspense>
              </div>
            ) : activeTab === 'library' ? (
              <div className="flex-1 overflow-y-auto p-6 bg-[#F8F9FA] dark:bg-zinc-950">
                <div className="max-w-4xl mx-auto space-y-4">
                  <div className="p-4 rounded-xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs flex items-center justify-between">
                    <div>
                      <h2 className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">Yerel Varlık &amp; Önbellek Deposu</h2>
                      <p className="text-[11px] text-zinc-500">SHA-256 ses önbelleği ve 9:16 master çıktılar</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setActiveView('channels')}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#111827] hover:bg-[#1F2937] text-white shadow-2xs transition-all cursor-pointer"
                    >
                      Kanallara Dön
                    </button>
                  </div>
                </div>
              </div>
            ) : activeTab === 'settings' ? (
              <div className="flex-1 overflow-y-auto p-6 bg-[#F8F9FA] dark:bg-zinc-950">
                <div className="max-w-4xl mx-auto p-5 rounded-xl border border-[#E5E7EB] dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs">
                  <h2 className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 mb-3">Mimari Güvenlik ve Motor Parametreleri</h2>
                  <div className="grid grid-cols-2 gap-2 font-mono text-[11px] text-zinc-500">
                    <div className="p-2.5 rounded bg-zinc-100 dark:bg-zinc-900/90 border border-border/70 flex justify-between">
                      <span>Ağ Politikası:</span>
                      <span className="text-emerald-500 font-medium">ZERO-NETWORK</span>
                    </div>
                    <div className="p-2.5 rounded bg-zinc-100 dark:bg-zinc-900/90 border border-border/70 flex justify-between">
                      <span>Alt Süreç:</span>
                      <span className="text-teal-500 font-medium">JobObject</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          {/* Sağ Yan Panel: Hustler AI Asistan Kartı */}
          <HustlerAiWidget
            isOpen={isAiOpen}
            onClose={() => setIsAiOpen(false)}
          />
        </div>

        {/* Canlı Durum Çubuğu (Sidecar, SQLite, 15m SLA Timer, Tanılama .zip) */}
        <StatusBar />
      </main>

      {/* Soğuk Başlatma (Cold-Start) Karşılama Ekranı */}
      <ColdStartSplash />

      {/* Global K-703 Dialogs */}
      <ErrorModal />
      <ToastContainer />
    </div>
  )
}

export default App
