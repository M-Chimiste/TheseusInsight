import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  TaskChannel, buildTaskWebSocketUrl, persistLastMessage, restoreLastMessage,
} from './taskChannel'

class MockWebSocket {
  static instances: MockWebSocket[] = []
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  url: string
  readyState = MockWebSocket.CONNECTING
  sent: unknown[] = []
  onopen: ((e: Event) => void) | null = null
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: ((e: Event) => void) | null = null
  onclose: ((e: CloseEvent) => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }
  send(data: unknown) { this.sent.push(data) }
  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.(new CloseEvent('close'))
  }
  // test helpers
  simulateOpen() { this.readyState = MockWebSocket.OPEN; this.onopen?.(new Event('open')) }
  simulateMessage(payload: unknown) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(payload) }))
  }
  simulateError() { this.onerror?.(new Event('error')) }
}

describe('taskChannel', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
    sessionStorage.clear()
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('builds the /ws/{type}/{id} URL', () => {
    expect(buildTaskWebSocketUrl('newsletter', 'abc')).toMatch(/\/ws\/newsletter\/abc$/)
  })

  it('parses messages and persists them under the frozen storage keys', () => {
    const onMessage = vi.fn()
    const ch = new TaskChannel('newsletter', 't1', { onMessage })
    ch.connect()
    const ws = MockWebSocket.instances[0]
    ws.simulateOpen()
    ws.simulateMessage({ overallStatus: 'processing', progress: 40 })

    expect(onMessage).toHaveBeenCalledWith(
      { overallStatus: 'processing', progress: 40 }, expect.anything())
    expect(JSON.parse(sessionStorage.getItem('ws_last_message_t1')!))
      .toEqual({ overallStatus: 'processing', progress: 40 })
    expect(sessionStorage.getItem('ws_last_message_timestamp_t1')).toBeTruthy()
  })

  it('restores a recent persisted message on open', () => {
    persistLastMessage('t2', { overallStatus: 'processing', progress: 70 })
    const onRestore = vi.fn()
    const ch = new TaskChannel('podcast', 't2', { onRestore })
    ch.connect()
    MockWebSocket.instances[0].simulateOpen()
    expect(onRestore).toHaveBeenCalledWith({ overallStatus: 'processing', progress: 70 })
  })

  it('does not restore messages older than the age window', () => {
    sessionStorage.setItem('ws_last_message_t3', JSON.stringify({ progress: 1 }))
    sessionStorage.setItem('ws_last_message_timestamp_t3',
      String(Date.now() - 11 * 60 * 1000))
    expect(restoreLastMessage('t3')).toBeNull()
  })

  it('retries on error up to maxRetries', () => {
    const ch = new TaskChannel('newsletter', 't4', {}, {
      retryOnError: true, maxRetries: 2, reconnectIntervalMs: 1000,
    })
    ch.connect()
    expect(MockWebSocket.instances).toHaveLength(1)

    MockWebSocket.instances[0].readyState = MockWebSocket.CLOSED
    MockWebSocket.instances[0].simulateError()
    vi.advanceTimersByTime(1000)
    expect(MockWebSocket.instances).toHaveLength(2)

    MockWebSocket.instances[1].readyState = MockWebSocket.CLOSED
    MockWebSocket.instances[1].simulateError()
    vi.advanceTimersByTime(1000)
    expect(MockWebSocket.instances).toHaveLength(3)

    // third error exceeds maxRetries — no further reconnects
    MockWebSocket.instances[2].readyState = MockWebSocket.CLOSED
    MockWebSocket.instances[2].simulateError()
    vi.advanceTimersByTime(5000)
    expect(MockWebSocket.instances).toHaveLength(3)
  })

  it('disconnect cancels pending retries', () => {
    const ch = new TaskChannel('newsletter', 't5', {}, {
      retryOnError: true, reconnectIntervalMs: 1000,
    })
    ch.connect()
    MockWebSocket.instances[0].readyState = MockWebSocket.CLOSED
    MockWebSocket.instances[0].simulateError()
    ch.disconnect()
    vi.advanceTimersByTime(5000)
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('storage: null disables persistence', () => {
    const ch = new TaskChannel('mindmap', 't6', {}, { storage: null })
    ch.connect()
    const ws = MockWebSocket.instances[0]
    ws.simulateOpen()
    ws.simulateMessage({ progress: 5 })
    expect(sessionStorage.getItem('ws_last_message_t6')).toBeNull()
  })
})
