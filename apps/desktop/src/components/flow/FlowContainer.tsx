import React from 'react'
import { useFlowStore } from '../../store/flowStore'
import { FlowStepper } from './FlowStepper'
import { TimerPanel } from '../timer/TimerPanel'
import { TopicScreen } from './TopicScreen'
import { Top20Screen } from './Top20Screen'
import { ScriptScreen } from './ScriptScreen'
import { AudioScreen } from './AudioScreen'
import { AssetsScreen } from './AssetsScreen'
import { PreviewScreen } from './PreviewScreen'
import { RenderScreen } from './RenderScreen'

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
        {renderActiveScreen()}
      </div>
    </div>
  )
}
