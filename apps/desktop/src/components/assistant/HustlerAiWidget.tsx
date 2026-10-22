import { useState, type FC } from 'react'

export interface HustlerAiWidgetProps {
  isOpen?: boolean
  onClose?: () => void
  onSelectPrompt?: (prompt: string) => void
}

const SUGGESTIONS = [
  'How to use channels?',
  'Integration tips',
  'Popular channels',
  'Connect network',
]

export const HustlerAiWidget: FC<HustlerAiWidgetProps> = ({
  isOpen = true,
  onClose,
  onSelectPrompt,
}) => {
  const [messages, setMessages] = useState<Array<{ sender: 'ai' | 'user'; text: string }>>([
    {
      sender: 'ai',
      text: 'Hi! Ready to get started? Let me know if you need help creating your first channel or setting up.',
    },
  ])
  const [inputValue, setInputValue] = useState('')

  if (!isOpen) return null

  const handleSend = () => {
    const trimmed = inputValue.trim()
    if (!trimmed) return

    setMessages((prev) => [...prev, { sender: 'user', text: trimmed }])
    setInputValue('')

    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'ai',
          text: `Got it! Click "+ Create first channel" in the center to set up your content niche.`,
        },
      ])
    }, 400)
  }

  const handleSuggestionClick = (prompt: string) => {
    setMessages((prev) => [...prev, { sender: 'user', text: prompt }])
    onSelectPrompt?.(prompt)

    setTimeout(() => {
      let reply = 'Channels allow you to group research, generate dedicated scripts, and track viral scores per YouTube niche.'
      if (prompt.includes('Integration')) {
        reply = 'Hustler works with local SQLite and Zero-Network security. All generation stays offline.'
      } else if (prompt.includes('network')) {
        reply = 'Local desktop proxy is connected to the SQLite database and Sidecar engine.'
      }
      setMessages((prev) => [...prev, { sender: 'ai', text: reply }])
    }, 400)
  }

  return (
    <aside
      className="w-[340px] h-[calc(100vh-6.5rem)] my-auto mr-6 bg-white dark:bg-zinc-900 rounded-2xl border border-[#E5E7EB] dark:border-zinc-800 shadow-sm flex flex-col justify-between p-4 shrink-0 select-none animate-in fade-in slide-in-from-right-4 duration-200"
      data-testid="hustler-ai-widget"
      aria-label="Hustler AI Assistant"
    >
      {/* Üst Başlık & Kapatma */}
      <div className="flex items-center justify-between pb-3 border-b border-[#F3F4F6] dark:border-zinc-800">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-md bg-[#F3F4F6] dark:bg-zinc-800 flex items-center justify-center text-[#374151] dark:text-zinc-200">
            {/* Robot İkonu */}
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="11" width="18" height="10" rx="2" />
              <circle cx="12" cy="5" r="2" />
              <path d="M12 7v4" />
              <line x1="8" y1="16" x2="8" y2="16" />
              <line x1="16" y1="16" x2="16" y2="16" />
            </svg>
          </div>
          <span className="text-[14px] font-semibold text-[#111827] dark:text-zinc-100 tracking-tight">
            Hustler AI
          </span>
        </div>

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="w-6 h-6 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center justify-center text-[#9CA3AF] hover:text-[#4B5563] dark:hover:text-zinc-200 transition-colors cursor-pointer"
            title="Close"
            aria-label="Close"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Mesaj Akışı */}
      <div className="flex-1 overflow-y-auto py-3 space-y-3 pr-1 text-xs">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`flex items-start gap-2 ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {m.sender === 'ai' && (
              <div className="w-5 h-5 rounded bg-[#F3F4F6] dark:bg-zinc-800 flex items-center justify-center text-[#4B5563] dark:text-zinc-300 shrink-0 mt-0.5">
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 14h16M7 10h10M10 6h4" />
                </svg>
              </div>
            )}
            <div
              className={`max-w-[85%] p-3.5 rounded-2xl leading-relaxed text-[13px] ${
                m.sender === 'user'
                  ? 'bg-[#111827] text-white rounded-tr-xs dark:bg-zinc-100 dark:text-zinc-900'
                  : 'bg-[#F3F4F6] text-[#374151] rounded-tl-xs dark:bg-zinc-800/90 dark:text-zinc-200'
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}
      </div>

      {/* Alt Kısım: Öneri Çipleri & Input */}
      <div className="pt-2 border-t border-[#F3F4F6] dark:border-zinc-800 space-y-3">
        {/* Öneri Çipleri */}
        <div className="flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => handleSuggestionClick(item)}
              className="px-3.5 py-1.5 rounded-full border border-[#E5E7EB] dark:border-zinc-700 bg-white dark:bg-zinc-800 text-[12px] text-[#4B5563] dark:text-zinc-300 hover:bg-[#F9FAFB] dark:hover:bg-zinc-700/60 hover:border-zinc-300 transition-colors shadow-2xs cursor-pointer"
            >
              {item}
            </button>
          ))}
        </div>

        {/* Input Kutusu */}
        <div className="relative flex items-center">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask Hustler AI..."
            className="w-full pl-3.5 pr-9 py-2.5 rounded-xl border border-[#E5E7EB] dark:border-zinc-700 bg-white dark:bg-zinc-800/80 text-[13px] text-[#111827] dark:text-zinc-100 placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#9CA3AF] dark:focus:border-zinc-500 transition-colors shadow-2xs"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={!inputValue.trim()}
            className="absolute right-2.5 p-1 text-[#9CA3AF] hover:text-[#4B5563] dark:hover:text-zinc-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
            title="Send"
            aria-label="Send"
          >
            {/* Kağıt Uçak İkonu */}
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3 21l18-9L3 3l3 9zm0 0h9" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
  )
}
