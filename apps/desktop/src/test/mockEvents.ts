/**
 * Hustler Desktop — Test-Only Mock Event Bridge
 * Bu modül yalnızca vitest testleri için mock event ve bağlantı durumlarını simüle eder.
 * Üretim koduna (production bundle) dahil edilmez.
 */

import type { EventHandler, ConnectionHandler, HustlerEvent, ConnectionStatePayload, EventBridgeClient } from '../lib/events'

const mockEventListeners = new Set<EventHandler>()
const mockConnectionListeners = new Set<ConnectionHandler>()

export const mockEventBridge: EventBridgeClient = {
  async onEvent(handler: EventHandler): Promise<() => void> {
    mockEventListeners.add(handler)
    return () => {
      mockEventListeners.delete(handler)
    }
  },

  async onConnectionState(handler: ConnectionHandler): Promise<() => void> {
    mockConnectionListeners.add(handler)
    return () => {
      mockConnectionListeners.delete(handler)
    }
  },
}

export function emitMockEvent(event: HustlerEvent): void {
  for (const listener of mockEventListeners) {
    listener(event)
  }
}

export function emitMockConnectionState(state: ConnectionStatePayload): void {
  for (const listener of mockConnectionListeners) {
    listener(state)
  }
}

export function clearMockListeners(): void {
  mockEventListeners.clear()
  mockConnectionListeners.clear()
}
