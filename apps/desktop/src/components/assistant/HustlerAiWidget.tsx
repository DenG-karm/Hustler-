import { useState, useEffect, type FC, type MouseEvent as ReactMouseEvent } from 'react'
import { getIpcClient } from '../../lib/ipc'
import { useFlowStore } from '../../store/flowStore'
import { AppIcon } from '../ui/AppIcon'

export interface HustlerAiWidgetProps {
  isOpen?: boolean
  onClose?: () => void
  onSelectPrompt?: (prompt: string) => void
}

interface ChatMessage {
  sender: 'ai' | 'user'
  text: string
}

interface ChatThread {
  id: string
  title: string
  updatedAt: number
  messages: ChatMessage[]
}

interface ChatReplyBody {
  reply?: string
  provider?: string
}

const STORAGE_KEY = 'hustler_ai_threads_v1'
const WELCOME_TEXT = 'Hustler AI devrede.'
const SUGGESTIONS = ['Sistem analizi', 'Kanal durumu', 'Shorts stratejisi']
const BUBBLE = 'border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800'

const createDefaultThread = (): ChatThread => ({
  id: `thr_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
  title: 'Yeni Sohbet',
  updatedAt: Date.now(),
  messages: [{ sender: 'ai', text: WELCOME_TEXT }],
})

const loadThreads = (): ChatThread[] => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as ChatThread[]
      if (Array.isArray(parsed) && parsed.length > 0) return parsed
    }
  } catch {
    // ignore
  }
  return [createDefaultThread()]
}

export const HustlerAiWidget: FC<HustlerAiWidgetProps> = ({
  isOpen = true,
  onClose,
  onSelectPrompt,
}) => {
  const [threads, setThreads] = useState<ChatThread[]>(loadThreads)
  const [activeId, setActiveId] = useState<string>(() => threads[0]?.id || '')
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [providerLabel, setProviderLabel] = useState('Gemini 2.5')
  const [isExpanded, setIsExpanded] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [panelWidth, setPanelWidth] = useState(360)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')

  const activeThread = threads.find((t) => t.id === activeId) ?? threads[0]
  const messages = activeThread?.messages ?? []

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(threads))
    } catch {
      /* ignore */
    }
  }, [threads])

  if (!isOpen) return null

  const updateThreadMessages = (id: string, next: ChatMessage[], autoTitle?: string) =>
    setThreads((prev) =>
      prev.map((t) =>
        t.id === id
          ? {
              ...t,
              title: autoTitle && t.title === 'Yeni Sohbet' ? autoTitle : t.title,
              updatedAt: Date.now(),
              messages: next,
            }
          : t
      )
    )

  const handleNewChat = () => {
    const fresh = createDefaultThread()
    setThreads((prev) => [fresh, ...prev])
    setActiveId(fresh.id)
    setEditingId(null)
  }

  const handleDeleteThread = (id: string, e: ReactMouseEvent) => {
    e.stopPropagation()
    setThreads((prev) => {
      const rem = prev.filter((t) => t.id !== id)
      const next = rem.length ? rem : [createDefaultThread()]
      if (activeId === id || !rem.length) setActiveId(next[0].id)
      return next
    })
  }

  const startRename = (t: ChatThread, e: ReactMouseEvent) => {
    e.stopPropagation()
    setEditingId(t.id)
    setEditTitle(t.title)
  }

  const commitRename = (id: string) => {
    const v = editTitle.trim()
    if (v) setThreads((prev) => prev.map((t) => (t.id === id ? { ...t, title: v } : t)))
    setEditingId(null)
  }

  const handleResizeStart = (e: ReactMouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startW = panelWidth
    const onMove = (ev: MouseEvent) =>
      setPanelWidth(Math.min(820, Math.max(300, startW + startX - ev.clientX)))
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  const sendMessage = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isLoading || !activeThread) return

    const tid = activeThread.id
    const st = useFlowStore.getState()
    const nextHistory: ChatMessage[] = [...messages, { sender: 'user', text: trimmed }]
    updateThreadMessages(tid, nextHistory, trimmed.slice(0, 26))
    setInputValue('')
    setIsLoading(true)

    try {
      const res = await getIpcClient().proxyRequest('POST', '/api/v1/pipeline/chat', {
        message: trimmed,
        history: nextHistory.slice(-8).map((m) => ({ role: m.sender, text: m.text })),
        active_view: st.activeView,
        channel_id: st.activeChannelId,
        current_topic: st.topic || null,
        current_step: st.currentStep,
      })
      const body = (res?.body ?? {}) as ChatReplyBody
      if (body.provider) setProviderLabel(body.provider.includes('gemini') ? 'Gemini 2.5' : body.provider)
      const clean = (body.reply ?? '').replace(/\*/g, '').trim() || 'Analiz tamamlandı.'
      updateThreadMessages(tid, [...nextHistory, { sender: 'ai', text: clean }])
    } catch {
      updateThreadMessages(tid, [...nextHistory, { sender: 'ai', text: 'Sidecar bağlantısı bekleniyor.' }])
    } finally {
      setIsLoading(false)
    }
  }

  const showSidebar = isExpanded || showHistory || panelWidth >= 540
  const iconBtnCls = 'w-6 h-6 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center justify-center text-zinc-500 cursor-pointer text-xs'

  return (
    <aside
      style={isExpanded ? undefined : { width: `${panelWidth}px` }}
      className={`${isExpanded ? 'fixed inset-3 z-50 shadow-2xl' : 'relative h-[calc(100vh-6.5rem)] my-auto mr-6 shadow-sm shrink-0'} bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 flex flex-col overflow-hidden select-none`}
      data-testid="hustler-ai-widget"
      aria-label="Hustler AI Assistant"
    >
      {!isExpanded && (
        <div onMouseDown={handleResizeStart} title="Genişlet / Daralt" className="absolute left-0 inset-y-0 w-2 cursor-ew-resize hover:bg-blue-500/20 z-20 flex items-center justify-center">
          <span className="w-0.5 h-8 rounded-full bg-zinc-300 dark:bg-zinc-700" />
        </div>
      )}

      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 dark:border-zinc-800 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          {!isExpanded && (
            <button type="button" onClick={() => setShowHistory(!showHistory)} className={iconBtnCls} title="Sohbet Geçmişi">
              <AppIcon name="menu" className="w-3.5 h-3.5" />
            </button>
          )}
          <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 truncate">Hustler AI</span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">{providerLabel}</span>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button type="button" onClick={handleNewChat} className="px-2 py-1 rounded-md text-[11px] font-semibold bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 cursor-pointer">+ Yeni</button>
          <button type="button" onClick={() => setIsExpanded(!isExpanded)} className={iconBtnCls} data-testid="ai-expand-btn">
            <AppIcon name={isExpanded ? 'left' : 'right'} className="w-3.5 h-3.5" />
          </button>
          {onClose && (
            <button type="button" onClick={onClose} className={iconBtnCls} title="Kapat">
              <AppIcon name="close" className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {showSidebar && (
          <div className="w-52 border-r border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/60 flex flex-col p-2.5 shrink-0">
            <button type="button" onClick={handleNewChat} className="w-full py-2 px-3 mb-2 rounded-xl text-xs font-semibold bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 cursor-pointer">+ Yeni Sohbet</button>
            <div className="text-[10px] font-mono uppercase text-zinc-400 px-2 py-1">Geçmiş ({threads.length})</div>
            <div className="flex-1 overflow-y-auto space-y-1">
              {threads.map((t) => {
                const isAct = t.id === activeThread?.id
                return (
                  <div
                    key={t.id}
                    onClick={() => setActiveId(t.id)}
                    className={`group flex items-center justify-between gap-1 px-2.5 py-2 rounded-xl text-xs cursor-pointer ${
                      isAct ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 font-semibold border border-zinc-200 dark:border-zinc-700' : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200/60'
                    }`}
                  >
                    {editingId === t.id ? (
                      <input
                        type="text"
                        autoFocus
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onBlur={() => commitRename(t.id)}
                        onKeyDown={(e) => e.key === 'Enter' && commitRename(t.id)}
                        onClick={(e) => e.stopPropagation()}
                        className="w-full bg-white dark:bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-400 text-xs focus:outline-none"
                      />
                    ) : (
                      <>
                        <span onDoubleClick={(e) => startRename(t, e)} className="truncate flex-1">{t.title}</span>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 shrink-0">
                          <button type="button" onClick={(e) => startRename(t, e)} className="p-0.5 text-zinc-400 hover:text-zinc-900 cursor-pointer" title="Düzenle">
                            <AppIcon name="edit" className="w-3 h-3" />
                          </button>
                          <button type="button" onClick={(e) => handleDeleteThread(t.id, e)} className="p-0.5 text-zinc-400 hover:text-rose-500 cursor-pointer" title="Sil">
                            <AppIcon name="close" className="w-3 h-3" />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        <div className="flex-1 flex flex-col justify-between p-4 overflow-hidden">
          <div className="flex-1 overflow-y-auto py-2 space-y-3 pr-1 text-xs">
            <div className={isExpanded ? 'max-w-3xl mx-auto space-y-3' : 'space-y-3'}>
              {messages.map((m, idx) => (
                <div key={idx} className={`flex items-start gap-2.5 ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {m.sender === 'ai' && (
                    <div className="w-6 h-6 rounded-lg bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-zinc-600 shrink-0 mt-0.5 font-mono text-[10px] font-bold">AI</div>
                  )}
                  <div className={`max-w-[85%] p-3.5 rounded-2xl leading-relaxed text-[13px] whitespace-pre-line select-text ${m.sender === 'user' ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900' : 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200'}`}>
                    {m.text.replace(/\*/g, '')}
                  </div>
                </div>
              ))}
              {isLoading && <div className="text-[11px] font-mono text-zinc-400 pl-8 animate-pulse">Analiz ediliyor...</div>}
            </div>
          </div>

          <div className={`pt-2 border-t border-zinc-100 dark:border-zinc-800 space-y-2.5 ${isExpanded ? 'max-w-3xl w-full mx-auto' : ''}`}>
            <div className="flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => { onSelectPrompt?.(item); void sendMessage(item) }}
                  className={`px-3 py-1 rounded-full ${BUBBLE} text-[11px] text-zinc-600 dark:text-zinc-300 cursor-pointer`}
                >
                  {item}
                </button>
              ))}
            </div>

            <div className="relative flex items-center">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && void sendMessage(inputValue)}
                placeholder="Hustler AI ile konuşun..."
                className={`w-full pl-3.5 pr-9 py-2.5 rounded-xl ${BUBBLE} text-[13px] text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:outline-none`}
              />
              <button type="button" onClick={() => void sendMessage(inputValue)} disabled={!inputValue.trim() || isLoading} className="absolute right-2.5 p-1 text-zinc-400 hover:text-zinc-700 disabled:opacity-30 cursor-pointer" title="Send">
                <AppIcon name="send" className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}
