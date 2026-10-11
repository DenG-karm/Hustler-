import React from 'react'
import { FLOW_STEPS, type FlowStep, useFlowStore } from '../../store/flowStore'

interface StepMeta {
  key: FlowStep
  label: string
  number: number
}

const STEP_METAS: StepMeta[] = [
  { key: 'TOPIC', label: 'Konu', number: 1 },
  { key: 'TOP20', label: 'Top 20', number: 2 },
  { key: 'SCRIPT', label: 'Senaryo', number: 3 },
  { key: 'AUDIO', label: 'Ses', number: 4 },
  { key: 'ASSETS', label: 'Görseller', number: 5 },
  { key: 'PREVIEW', label: 'Önizleme', number: 6 },
  { key: 'RENDER', label: 'Render', number: 7 },
]

export const FlowStepper: React.FC = () => {
  const currentStep = useFlowStore((s) => s.currentStep)
  const isStepValid = useFlowStore((s) => s.isStepValid)
  const goToStep = useFlowStore((s) => s.goToStep)

  const currentIndex = FLOW_STEPS.indexOf(currentStep)

  return (
    <div className="w-full bg-surface border-b border-border py-md px-lg" data-testid="flow-stepper">
      <div className="flex items-center justify-between max-w-5xl mx-auto">
        {STEP_METAS.map((step, idx) => {
          const isActive = step.key === currentStep
          const isCompleted = idx < currentIndex || isStepValid(step.key).valid
          const isPast = idx < currentIndex

          return (
            <React.Fragment key={step.key}>
              <button
                type="button"
                onClick={() => {
                  try {
                    goToStep(step.key)
                  } catch {
                    // Store seviyesinde engellendi, sessizce geç
                  }
                }}
                className={`flex items-center gap-xs focus:outline-none transition-colors ${
                  isActive
                    ? 'text-accent font-bold'
                    : isPast
                    ? 'text-text-primary hover:text-accent cursor-pointer'
                    : 'text-text-muted cursor-not-allowed'
                }`}
                data-testid={`step-indicator-${step.key}`}
              >
                <span
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-colors ${
                    isActive
                      ? 'bg-accent text-accent-fg ring-2 ring-accent/30'
                      : isCompleted && isPast
                      ? 'bg-success text-white'
                      : 'bg-surface-hover text-text-muted border border-border'
                  }`}
                >
                  {isCompleted && isPast ? '✓' : step.number}
                </span>
                <span className="hidden sm:inline text-xs">{step.label}</span>
              </button>

              {idx < STEP_METAS.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-2 rounded transition-colors ${
                    idx < currentIndex ? 'bg-success' : 'bg-border'
                  }`}
                />
              )}
            </React.Fragment>
          )
        })}
      </div>
    </div>
  )
}
