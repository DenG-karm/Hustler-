import React, { useEffect } from 'react'
import { useFlowStore } from '../../store/flowStore'
import { FlowStepper } from './FlowStepper'
import { TimerPanel } from '../timer/TimerPanel'
import { ScriptScreen } from './ScriptScreen'
import { AudioScreen } from './AudioScreen'
import { AssetsScreen } from './AssetsScreen'
import { PreviewScreen } from './PreviewScreen'
import { RenderScreen } from './RenderScreen'

export const FlowContainer: React.FC = () => {
  const currentStep = useFlowStore((s) => s.currentStep)
  const setActiveView = useFlowStore((s) => s.setActiveView)

  // Eski tasarımlara (TOPIC / TOP20) düşülürse derhal ana kanal masasına yönlendir
  useEffect(() => {
    if (currentStep === 'TOPIC' || currentStep === 'TOP20') {
      setActiveView('channels')
    }
  }, [currentStep, setActiveView])

  const renderActiveScreen = () => {
    switch (currentStep) {
      case 'SCRIPT':
        return <ScriptScreen />
      case 'AUDIO':
        return <AudioScreen />
      case 'ASSETS':
        return <AssetsScreen />
      case 'PREVIEW':
        return <PreviewScreen />
      case 'RENDER':
        return <RenderScreen />
      default:
        return (
          <div className="flex flex-col items-center justify-center p-12 text-center space-y-3">
            <p className="text-sm text-zinc-500">Kanal masasına yönlendiriliyorsunuz...</p>
            <button
              type="button"
              onClick={() => setActiveView('channels')}
              className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#111827] text-white cursor-pointer"
            >
              Kanal Masasına Dön
            </button>
          </div>
        )
    }
  }

  return (
    <div className="flex flex-col h-full bg-[#F8F9FA] dark:bg-zinc-950 text-text-primary" data-testid="flow-container">
      {/* K-702 Donanım Sekans Adım Göstergesi (Stepper) */}
      <FlowStepper />

      {/* K-707 Kompakt Timecode & 15 Dk SLA Telemetri Şeridi */}
      <div className="px-6 pt-3 shrink-0 max-w-7xl mx-auto w-full">
        <TimerPanel />
      </div>

      {/* Aktif Ekran İçeriği */}
      <div className="flex-1 overflow-y-auto px-6 py-6 max-w-7xl mx-auto w-full">
        {renderActiveScreen()}
      </div>
    </div>
  )
}
