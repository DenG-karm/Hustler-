import React, { Suspense, lazy } from 'react'
import { useFlowStore } from '../../store/flowStore'
import { FlowStepper } from './FlowStepper'
import { TimerPanel } from '../timer/TimerPanel'
import { TopicScreen } from './TopicScreen'
import { Top20Screen } from './Top20Screen'

const ScriptScreen = lazy(() =>
  import('./ScriptScreen').then((m) => ({ default: m.ScriptScreen }))
)
const AudioScreen = lazy(() =>
  import('./AudioScreen').then((m) => ({ default: m.AudioScreen }))
)
const AssetsScreen = lazy(() =>
  import('./AssetsScreen').then((m) => ({ default: m.AssetsScreen }))
)
const PreviewScreen = lazy(() =>
  import('./PreviewScreen').then((m) => ({ default: m.PreviewScreen }))
)
const RenderScreen = lazy(() =>
  import('./RenderScreen').then((m) => ({ default: m.RenderScreen }))
)

export const FlowContainer: React.FC = () => {
  const currentStep = useFlowStore((s) => s.currentStep)

  const renderActiveScreen = () => {
    switch (currentStep) {
      case 'TOPIC':
        return <TopicScreen />
      case 'TOP20':
        return <Top20Screen />
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
        return null
    }
  }

  return (
    <div className="flex flex-col h-full bg-app text-text-primary" data-testid="flow-container">
      {/* K-702 Adım Göstergesi (Stepper) */}
      <FlowStepper />

      {/* K-707 Süre Paneli & 15 Dk SLA İzleme */}
      <div className="px-lg pt-sm">
        <TimerPanel />
      </div>

      {/* Aktif Ekran İçeriği */}
      <div className="flex-1 overflow-y-auto p-lg">
        <Suspense
          fallback={
            <div className="flex items-center justify-center py-xl text-xs font-mono text-text-muted">
              Ekran yükleniyor...
            </div>
          }
        >
          {renderActiveScreen()}
        </Suspense>
      </div>
    </div>
  )
}
