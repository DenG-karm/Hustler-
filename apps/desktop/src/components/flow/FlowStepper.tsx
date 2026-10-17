import React from 'react'
import { type FlowStep, useFlowStore } from '../../store/flowStore'

export interface StudioStep {
  number: number
  key: FlowStep
  label: string
  sublabel: string
  icon: string
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

  // Step 1: Keşif (Topic & Top20)
  const isStep1Active = currentStep === 'TOPIC' || currentStep === 'TOP20'
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
  const isStep3Locked = !isStep2Completed && !isStep3Active

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
      label: 'Keşif',
      sublabel: 'Konu & Top 20',
      icon: '🔍',
      isActive: isStep1Active,
      isCompleted: isStep1Completed && !isStep1Active,
      isLocked: false,
      onClick: () => {
        try {
          goToStep(selectedIdea ? 'TOP20' : 'TOPIC')
        } catch {
          // Engellendiyse sessizce geç
        }
      },
    },
    {
      number: 2,
      key: 'SCRIPT',
      label: 'Senaryo & İddia',
      sublabel: 'Metin & Doğrulama',
      icon: '✍️',
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
      label: 'Ses & Zamanlama',
      sublabel: 'TTS & AudioCache',
      icon: '🎙️',
      isActive: isStep3Active,
      isCompleted: isStep3Completed && !isStep3Active,
      isLocked: isStep3Locked,
      onClick: () => {
        if (!isStep3Locked) {
          try {
            goToStep('AUDIO')
          } catch {
            // no-op
          }
        }
      },
    },
    {
      number: 4,
      key: 'ASSETS',
      label: 'Varlık & Slot',
      sublabel: 'Görseller & Müzik',
      icon: '🖼️',
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
      icon: '👁️',
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
      label: 'Render & Çıktı',
      sublabel: 'FFmpeg & Dağıtım',
      icon: '⚡',
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

  return (
    <nav
      className="w-full bg-surface/90 backdrop-blur-md border-b border-border/80 px-lg py-sm shadow-sm select-none"
      aria-label="Üretim Akış Adımları"
      data-testid="flow-stepper"
    >
      <div className="flex items-center justify-between max-w-6xl mx-auto gap-xs sm:gap-sm">
        {steps.map((step, idx) => {
          return (
            <React.Fragment key={step.number}>
              {/* Adım Düğmesi */}
              <button
                type="button"
                onClick={step.onClick}
                disabled={step.isLocked}
                aria-current={step.isActive ? 'step' : undefined}
                data-testid={`studio-step-${step.number}`}
                data-test-key={`step-indicator-${step.key}`}
                className={`group relative flex items-center gap-xs sm:gap-sm py-1.5 px-2 sm:px-3 rounded-xl transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                  step.isActive
                    ? 'bg-primary/10 border border-primary/30 shadow-sm shadow-primary/10'
                    : step.isCompleted
                    ? 'hover:bg-surface-hover cursor-pointer border border-transparent hover:border-border'
                    : step.isLocked
                    ? 'opacity-40 cursor-not-allowed border border-transparent'
                    : 'hover:bg-surface-hover cursor-pointer border border-transparent'
                }`}
              >
                {/* Rozet / İkon */}
                <div
                  className={`w-7 h-7 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center font-bold text-xs transition-all duration-200 shrink-0 ${
                    step.isActive
                      ? 'bg-gradient-to-tr from-primary to-purple-500 text-white shadow-md shadow-primary/30 ring-2 ring-primary/40 scale-105'
                      : step.isCompleted
                      ? 'bg-emerald-500/15 text-emerald-500 border border-emerald-500/30'
                      : step.isLocked
                      ? 'bg-surface-hover text-text-muted border border-border/40'
                      : 'bg-surface-hover text-text-secondary border border-border'
                  }`}
                >
                  {step.isCompleted ? (
                    <svg
                      className="w-4 h-4 stroke-[2.5]"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  ) : step.isLocked ? (
                    <svg
                      className="w-3.5 h-3.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                      />
                    </svg>
                  ) : (
                    <span>{step.number}</span>
                  )}
                </div>

                {/* Adım Metinleri */}
                <div className="flex flex-col text-left">
                  <div className="flex items-center gap-1">
                    <span
                      className={`text-xs font-semibold tracking-tight transition-colors ${
                        step.isActive
                          ? 'text-primary font-bold'
                          : step.isCompleted
                          ? 'text-text-primary group-hover:text-primary'
                          : 'text-text-muted'
                      }`}
                    >
                      {step.number}. {step.label}
                    </span>
                    {step.isCompleted && (
                      <span className="text-[10px] text-emerald-500 font-bold hidden md:inline">
                        ✓
                      </span>
                    )}
                  </div>
                  <span
                    className={`text-[10px] hidden lg:inline truncate max-w-[100px] transition-colors ${
                      step.isActive
                        ? 'text-primary/80 font-medium'
                        : 'text-text-muted'
                    }`}
                  >
                    {step.sublabel}
                  </span>
                </div>
              </button>

              {/* Adımlar Arası Bağlantı Çizgisi */}
              {idx < steps.length - 1 && (
                <div
                  className={`flex-1 h-[2px] min-w-[8px] sm:min-w-[16px] rounded-full transition-colors duration-300 ${
                    step.isCompleted
                      ? 'bg-emerald-500/50'
                      : step.isActive
                      ? 'bg-gradient-to-r from-primary/50 to-border'
                      : 'bg-border/60'
                  }`}
                  aria-hidden="true"
                />
              )}
            </React.Fragment>
          )
        })}
      </div>
    </nav>
  )
}
