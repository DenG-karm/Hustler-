/**
 * Hustler Desktop — Tauri Event Bridge İstemcisi (K-703)
 *
 * MİMARİ KURAL: POLLING KESİNLİKLE YASAKTIR.
 * FastAPI'den gelen asenkron ilerleme (%0-100), log akışları ve uyarılar
 * Rust üzerinden Tauri'nin `Window::emit` mekanizması ile bu modüle aktarılır.
 *
 * Bağlantı kopmalarında Rust katmanındaki exponential backoff ile arayüz
 * bilgilendirilir ('connecting' | 'connected' | 'reconnecting' | 'disconnected').
 */

import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import type { ProblemDetails } from './problemDetails'

export interface BaseHustlerEvent {
  type: string
}

export interface JobProgressEvent extends BaseHustlerEvent {
  type: 'job_progress'
  job_id: string
  progress: number
  step?: string
  status?: string
}

export interface JobCompletedEvent extends BaseHustlerEvent {
  type: 'job_completed'
  job_id: string
  output_path?: string
  status?: string
}

export interface JobFailedEvent extends BaseHustlerEvent {
  type: 'job_failed'
  job_id: string
  error?: ProblemDetails | string
  status?: string
}

export interface JobCancelledEvent extends BaseHustlerEvent {
  type: 'job_cancelled'
  job_id: string
  status?: string
}

export interface LlmLoopWarningEvent extends BaseHustlerEvent {
  type: 'llm_loop_warning'
  message: string
  iteration?: number
  limit?: number
}

export interface LogStreamEvent extends BaseHustlerEvent {
  type: 'log'
  level: 'info' | 'warn' | 'error' | 'debug'
  message: string
  timestamp?: string
}

export type HustlerEvent =
  | JobProgressEvent
  | JobCompletedEvent
  | JobFailedEvent
  | JobCancelledEvent
  | LlmLoopWarningEvent
  | LogStreamEvent
  | BaseHustlerEvent

export interface ConnectionStatePayload {
  state: 'connecting' | 'connected' | 'reconnecting' | 'disconnected'
  attempt?: number
}

export type EventHandler = (event: HustlerEvent) => void
export type ConnectionHandler = (state: ConnectionStatePayload) => void

export interface EventBridgeClient {
  onEvent(handler: EventHandler): Promise<() => void>
  onConnectionState(handler: ConnectionHandler): Promise<() => void>
}

// Gerçek Tauri Event İstemcisi
export const tauriEventBridge: EventBridgeClient = {
  async onEvent(handler: EventHandler): Promise<() => void> {
    try {
      const unlisten: UnlistenFn = await listen<HustlerEvent>('hustler:event', (evt) => {
        handler(evt.payload)
      })
      return unlisten
    } catch (e) {
      // Vitest / Node ortamında listen bulunamazsa no-op dön
      return () => {}
    }
  },

  async onConnectionState(handler: ConnectionHandler): Promise<() => void> {
    try {
      const unlisten: UnlistenFn = await listen<ConnectionStatePayload>(
        'hustler:connection_state',
        (evt) => {
          handler(evt.payload)
        }
      )
      return unlisten
    } catch (e) {
      return () => {}
    }
  },
}

let activeBridge: EventBridgeClient = tauriEventBridge

export function setEventBridge(bridge: EventBridgeClient): void {
  activeBridge = bridge
}

export function resetEventBridge(): void {
  activeBridge = tauriEventBridge
}

export function getEventBridge(): EventBridgeClient {
  return activeBridge
}

