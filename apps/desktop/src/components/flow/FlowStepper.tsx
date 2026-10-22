import React from 'react'
import { type FlowStep, useFlowStore } from '../../store/flowStore'
import { resolveChannelAvatar } from '../channels/channelMetadata'

export interface StudioStep {
  number: number
  key: FlowStep
  label: string
  sublabel: string
  isActive: boolean
  isCompleted: boolean
  isLocked: boolean
  onClick: () => void
}

export const FlowStepper: React.FC = () => {
  const currentStep = useFlowStore((s) => s.currentStep)
  const selectedIdea = useFlowStore((s) => s.selectedIdea)
  const script = useFlowStore((s) => s.script)
  const audio = useFlowStore((s) => s.audio)
  const assets = useFlowStore((s) => s.assets)
  const preview = useFlowStore((s) => s.preview)
  const render = useFlowStore((s) => s.render)
  const goToStep = useFlowStore((s) => s.goToStep)
  const setActiveView = useFlowStore((s) => s.setActiveView)
  const channels = useFlowStore((s) => s.channels)
  const activeChannelId = useFlowStore((s) => s.activeChannelId)

  const activeChannel = channels.find((c) => c.id === activeChannelId) ?? null

  // Step 1: Kanal Masası & Fikir Keşfi
  const isStep1Completed =
    selectedIdea !== null || ['SCRIPT', 'AUDIO', 'ASSETS', 'PREVIEW', 'RENDER'].includes(currentStep)

  // Step 2: Senaryo & İddia (Script)
  const isStep2Active = currentStep === 'SCRIPT'
  const isStep2Completed =
    Boolean(script?.isApproved) || ['AUDIO', 'ASSETS', 'PREVIEW', 'RENDER'].includes(currentStep)
  const isStep2Locked = !isStep1Completed && !isStep2Active

  // Step 3: Ses & Zamanlama (Audio)
  const isStep3Active = currentStep === 'AUDIO'
  const isStep3Completed =
    Boolean(audio?.audioPath) || ['ASSETS', 'PREVIEW', 'RENDER'].includes(currentStep)
  const isStep3Locked = !script && !isStep3Active

  // Step 4: Varlık & Slot (Assets)
  const isStep4Active = currentStep === 'ASSETS'
  const isStep4Completed =
    Boolean(assets?.allSlotsFilled) || ['PREVIEW', 'RENDER'].includes(currentStep)
  const isStep4Locked = !isStep3Completed && !isStep4Active

  // Step 5: Önizleme (Preview)
  const isStep5Active = currentStep === 'PREVIEW'
  const isStep5Completed =
    Boolean(preview?.isVerified) || currentStep === 'RENDER'
  const isStep5Locked = !isStep4Completed && !isStep5Active

  // Step 6: Render & Çıktı (Render)
  const isStep6Active = currentStep === 'RENDER'
  const isStep6Completed = render?.status === 'COMPLETED'
  const isStep6Locked = !isStep5Completed && !isStep6Active

  const steps: StudioStep[] = [
    {
      number: 1,
      key: 'TOPIC',
      label: 'Kanal Masası',
      sublabel: 'Fikir & Araştırma',
      isActive: false,
      isCompleted: true,
      isLocked: false,
      onClick: () => {
        setActiveView('channels')
      },
    },
    {
      number: 2,
      key: 'SCRIPT',
      label: 'Senaryo',
      sublabel: '3 Perde & İddia',
      isActive: isStep2Active,
      isCompleted: isStep2Completed && !isStep2Active,
      isLocked: isStep2Locked,
      onClick: () => {
        if (!isStep2Locked) {
          try {
            goToStep('SCRIPT')
          } catch {
            // no-op
          }
        }
      },
    },
    {
      number: 3,
      key: 'AUDIO',
      label: 'Ses Sentezi',
      sublabel: 'TTS & Zamanlama',
      isActive: isStep3Active,
      isCompleted: isStep3Completed && !isStep3Active,
      isLocked: isStep3Locked,
      onClick: () => {
        if (!isStep3Locked) {
          try {
            goToStep('AUDIO')
          } catch {
            useFlowStore.setState({ currentStep: 'AUDIO', errorMessage: null })
          }
        }
      },
    },
    {
      number: 4,
      key: 'ASSETS',
      label: 'Görsel Slotlar',
      sublabel: '9:16 Medya & Slot',
      isActive: isStep4Active,
      isCompleted: isStep4Completed && !isStep4Active,
      isLocked: isStep4Locked,
      onClick: () => {
        if (!isStep4Locked) {
          try {
            goToStep('ASSETS')
          } catch {
            // no-op
          }
        }
      },
    },
    {
      number: 5,
      key: 'PREVIEW',
      label: 'Önizleme',
      sublabel: 'Kare Kontrolü',
      isActive: isStep5Active,
      isCompleted: isStep5Completed && !isStep5Active,
      isLocked: isStep5Locked,
      onClick: () => {
        if (!isStep5Locked) {
          try {
            goToStep('PREVIEW')
          } catch {
            // no-op
          }
        }
      },
    },
    {
      number: 6,
      key: 'RENDER',
      label: 'Render',
      sublabel: 'FFmpeg Çıktısı',
      isActive: isStep6Active,
      isCompleted: isStep6Completed,
      isLocked: isStep6Locked,
      onClick: () => {
        if (!isStep6Locked) {
          try {
            goToStep('RENDER')
          } catch {
            // no-op
          }
        }
      },
    },
  ]

  const avatarData = activeChannel
    ? resolveChannelAvatar(activeChannel.channel_url, activeChannel.name)
    : null

  return (
    <nav
      className="w-full bg-white dark:bg-zinc-900 border-b border-[#E5E7EB] dark:border-zinc-800 px-6 py-3 select-none shrink-0 shadow-xs"
      aria-label="Üretim Akış Adımları"
      data-testid="flow-stepper"
    >
      <div className="flex items-center justify-between max-w-7xl mx-auto gap-4">
        {/* Sol: Aktif Kanal Bilgisi ve Masaya Hızlı Dönüş */}
        <div className="flex items-center gap-3 shrink-0">
          <button
            type="button"
            onClick={() => setActiveView('channels')}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-[#E5E7EB] dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/60 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-200 text-xs font-medium transition-colors cursor-pointer group"
            title="Kanal Masasına Dön"
          >
            <svg className="w-3.5 h-3.5 text-zinc-500 group-hover:-translate-x-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            <span className="hidden sm:inline">Kanal Masası</span>
          </button>

          {activeChannel && avatarData && (
            <div className="hidden md:flex items-center gap-2 pl-2 border-l border-[#E5E7EB] dark:border-zinc-800">
              <img
                src={avatarData.avatarUrl}
                alt={activeChannel.name}
                className="w-6 h-6 rounded-full object-cover ring-1 ring-black/5 dark:ring-white/10"
                onError={(e) => {
                  ;(e.currentTarget as HTMLElement).style.display = 'none'
                }}
              />
              <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 max-w-[130px] truncate">
                {activeChannel.name}
              </span>
            </div>
          )}
        </div>

        {/* Orta/Sağ: Modern 6 Adımlı Stepper Barı */}
        <div className="flex items-center gap-1.5 sm:gap-2 overflow-x-auto py-1 scrollbar-none">
          {steps.map((step, idx) => {
            return (
              <React.Fragment key={step.number}>
                <button
                  type="button"
                  onClick={step.onClick}
                  disabled={step.isLocked}
                  aria-current={step.isActive ? 'step' : undefined}
                  data-testid={`studio-step-${step.number}`}
                  data-test-key={`step-indicator-${step.key}`}
                  className={`group relative flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-medium transition-all duration-200 outline-none ring-0 ${
                    step.isActive
                      ? 'bg-[#111827] dark:bg-white text-white dark:text-zinc-900 shadow-xs scale-[1.02]'
                      : step.isCompleted
                      ? 'bg-zinc-100 dark:bg-zinc-800/80 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200/80 dark:hover:bg-zinc-700/80 cursor-pointer'
                      : step.isLocked
                      ? 'opacity-40 cursor-not-allowed text-zinc-400 dark:text-zinc-600'
                      : 'text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer'
                  }`}
                >
                  {/* Durum Rozeti / Numaratör */}
                  <div
                    className={`w-5 h-5 rounded-lg flex items-center justify-center text-[10px] font-bold transition-colors shrink-0 ${
                      step.isActive
                        ? 'bg-white/20 dark:bg-black/10 text-white dark:text-zinc-900'
                        : step.isCompleted
                        ? 'bg-emerald-500 text-white'
                        : 'bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-400'
                    }`}
                  >
                    {step.isCompleted ? (
                      <svg
                        className="w-3 h-3 stroke-[3]"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <span>{step.number}</span>
                    )}
                  </div>

                  {/* Adım Başlığı */}
                  <div className="flex flex-col text-left">
                    <span className="truncate whitespace-nowrap">
                      {step.label}
                    </span>
                  </div>
                </button>

                {/* Adımlar Arası İnce Nokta / Çizgi */}
                {idx < steps.length - 1 && (
                  <div className="w-2 sm:w-3 h-[1px] bg-zinc-200 dark:bg-zinc-800 shrink-0" aria-hidden="true" />
                )}
              </React.Fragment>
            )
          })}
        </div>
      </div>
    </nav>
  )
}
