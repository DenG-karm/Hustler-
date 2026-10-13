/**
 * Hustler Desktop — Pano Entegrasyonu ve Toplu Prompt Birleştirici (K-705)
 *
 * MİMARİ KURAL: ZERO WEB API & NATIVE TAURI CLIPBOARD
 * navigator.clipboard KESİNLİKLE KULLANILMAZ.
 * Kopyalama işlemi doğrudan Tauri IPC (@tauri-apps/api/core invoke)
 * üzerinden plugin:clipboard|write_text komutu ile yürütülür.
 *
 * MİMARİ KURAL: TOKEN OPTIMIZE FORMAT
 * Veri (Konu, Fikir, Senaryo, Sahneler, İddialar) LLM için minimum token
 * harcayacak şekilde boşluklardan arındırılmış Compact Key-Value formatında birleştirilir.
 *
 * MİMARİ KURAL: SNAPSHOT TESTİ
 * Çıktı biçimi src/test/clipboard-prompt.test.ts içerisindeki Vitest
 * toMatchSnapshot() ile kilitlenmiştir.
 */

import { invoke } from '@tauri-apps/api/core'
import type { FlowState } from '../store/flowStore'

/**
 * FlowSnapshot — Senaryo akışının kopyalanabilir kesiti.
 */
export interface FlowSnapshot {
  topic: string
  selectedIdea: {
    id: string
    title: string
    hook: string
    score: number
  }
  script: {
    id: string
    title: string
    hook: string
    fullText: string
    scenes: Array<{
      order: number
      narration: string
      visualPrompt: string
    }>
    claims: Array<{
      id: string
      text: string
      verified: boolean
    }>
  }
  audioVoiceId: string
  renderProfile: 'DRAFT' | 'FINAL'
}

/**
 * Compact Key-Value formatında LLM için minimum token harcayan prompt üretir.
 * Boşluk normalize edilir, sahne sırası order'a göre garanti edilir.
 */
export function buildClipboardPrompt(snapshot: FlowSnapshot): string {
  const scenes = snapshot.script.scenes
    .sort((a, b) => a.order - b.order)
    .map((s) => `[${s.order}] ${s.narration.trim()} | visual:${s.visualPrompt.trim()}`)
    .join('\n')

  const claims = snapshot.script.claims
    .map((c) => `[${c.verified ? 'OK' : 'PENDING'}] ${c.text.trim()}`)
    .join('\n')

  const lines: string[] = [
    `TOPIC:${snapshot.topic.trim()}`,
    `IDEA_ID:${snapshot.selectedIdea.id}`,
    `IDEA_TITLE:${snapshot.selectedIdea.title.trim()}`,
    `IDEA_HOOK:${snapshot.selectedIdea.hook.trim()}`,
    `IDEA_SCORE:${snapshot.selectedIdea.score}`,
    `SCRIPT_ID:${snapshot.script.id}`,
    `SCRIPT_TITLE:${snapshot.script.title.trim()}`,
    `SCRIPT_HOOK:${snapshot.script.hook.trim()}`,
    `SCRIPT_TEXT:${snapshot.script.fullText.trim()}`,
    `SCENES:\n${scenes}`,
    `CLAIMS:\n${claims}`,
    `VOICE:${snapshot.audioVoiceId}`,
    `RENDER:${snapshot.renderProfile}`,
  ]

  return lines.join('\n')
}

/**
 * Tauri native clipboard invoke çağrısı.
 * navigator.clipboard KULLANILMAZ — Tauri Rust IPC üzerinden pano yazılır.
 */
export async function clipboardWrite(text: string): Promise<void> {
  await invoke('plugin:clipboard|write_text', { text })
}

/**
 * FlowState nesnesini FlowSnapshot'a eşler.
 */
export function extractFlowSnapshot(state: Partial<FlowState>): FlowSnapshot {
  return {
    topic: state.topic?.trim() || '',
    selectedIdea: state.selectedIdea
      ? {
          id: state.selectedIdea.id,
          title: state.selectedIdea.title?.trim() || '',
          hook: state.selectedIdea.hook?.trim() || '',
          score: state.selectedIdea.score ?? 0,
        }
      : {
          id: '',
          title: '',
          hook: '',
          score: 0,
        },
    script: {
      id: state.script?.id || '',
      title: state.script?.title?.trim() || '',
      hook: state.script?.hook?.trim() || '',
      fullText: state.script?.fullText?.trim() || '',
      scenes: (state.script?.scenes || []).map((scene) => ({
        order: scene.order,
        narration: scene.narration,
        visualPrompt: scene.visualPrompt,
      })),
      claims: (state.script?.claims || []).map((claim) => ({
        id: claim.id,
        text: claim.text,
        verified: claim.verified,
      })),
    },
    audioVoiceId: state.audio?.voiceId || 'tr-TR-Standard-A',
    renderProfile: state.render?.profile || 'DRAFT',
  }
}
