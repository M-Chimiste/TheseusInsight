/**
 * Framework-free WebSocket channel for task progress (F4).
 *
 * Owns the lifecycle that useWebSocket/useMindMap used to roll
 * separately: URL construction, connect/reconnect with retry, JSON
 * parsing, and last-message persistence for refresh recovery.
 *
 * Storage keys are a compatibility contract — in-flight tasks must
 * survive a deploy of this code:
 *   ws_last_message_${taskId}
 *   ws_last_message_timestamp_${taskId}
 */

export const DEFAULT_RETRY_INTERVAL_MS = 5000;
export const DEFAULT_MAX_RESTORE_AGE_MS = 10 * 60 * 1000;

export interface TaskChannelHandlers {
  onMessage?: (payload: unknown, event: MessageEvent) => void;
  /** Fired on open when a persisted message was restored from storage. */
  onRestore?: (payload: unknown) => void;
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
  onError?: (event: Event) => void;
  onStateChange?: (readyState: number) => void;
}

export interface TaskChannelOptions {
  retryOnError?: boolean;
  reconnectIntervalMs?: number;
  maxRetries?: number;
  /** Pass null to disable persistence (e.g. secondary mindmap channels). */
  storage?: Storage | null;
  maxRestoreAgeMs?: number;
}

export function buildTaskWebSocketUrl(taskType: string, taskId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.hostname;
  const isDevelopment = import.meta.env.DEV;
  const port = isDevelopment ? ':8000' : (window.location.port ? `:${window.location.port}` : '');
  return `${protocol}//${host}${port}/ws/${taskType}/${taskId}`;
}

export function persistLastMessage(
  taskId: string,
  payload: unknown,
  storage: Storage | null = sessionStorage,
): void {
  if (!storage) return;
  try {
    storage.setItem(`ws_last_message_${taskId}`, JSON.stringify(payload));
    storage.setItem(`ws_last_message_timestamp_${taskId}`, Date.now().toString());
  } catch {
    // Quota exceeded — drop silently, matching the original behavior.
  }
}

export function restoreLastMessage(
  taskId: string,
  storage: Storage | null = sessionStorage,
  maxAgeMs: number = DEFAULT_MAX_RESTORE_AGE_MS,
): unknown | null {
  if (!storage) return null;
  try {
    const storedMessage = storage.getItem(`ws_last_message_${taskId}`);
    const storedTimestamp = storage.getItem(`ws_last_message_timestamp_${taskId}`);
    if (storedMessage && storedTimestamp) {
      const timestamp = parseInt(storedTimestamp);
      if (Date.now() - timestamp < maxAgeMs) {
        return JSON.parse(storedMessage);
      }
    }
  } catch (e) {
    console.error('Failed to restore last message:', e);
  }
  return null;
}

export class TaskChannel {
  readonly taskType: string;
  readonly taskId: string;
  private handlers: TaskChannelHandlers;
  private options: TaskChannelOptions;
  private ws: WebSocket | null = null;
  private retryCount = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private disposed = false;

  constructor(
    taskType: string,
    taskId: string,
    handlers: TaskChannelHandlers = {},
    options: TaskChannelOptions = {},
  ) {
    this.taskType = taskType;
    this.taskId = taskId;
    this.handlers = handlers;
    this.options = options;
  }

  get readyState(): number {
    return this.ws ? this.ws.readyState : WebSocket.CLOSED;
  }

  private get storage(): Storage | null {
    return this.options.storage === undefined ? sessionStorage : this.options.storage;
  }

  connect(): void {
    if (this.disposed) return;
    if (this.ws && this.ws.readyState !== WebSocket.CLOSED && this.ws.readyState !== WebSocket.CLOSING) {
      return; // already connected or connecting
    }

    const url = buildTaskWebSocketUrl(this.taskType, this.taskId);
    const ws = new WebSocket(url);
    this.ws = ws;
    this.handlers.onStateChange?.(WebSocket.CONNECTING);

    ws.onopen = (event) => {
      this.retryCount = 0;
      this.handlers.onStateChange?.(WebSocket.OPEN);

      const restored = restoreLastMessage(this.taskId, this.storage, this.options.maxRestoreAgeMs);
      if (restored !== null) {
        this.handlers.onRestore?.(restored);
      }

      this.handlers.onOpen?.(event);
    };

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data as string);
        persistLastMessage(this.taskId, parsed, this.storage);
        this.handlers.onMessage?.(parsed, event);
      } catch (e) {
        console.error('TaskChannel: failed to parse message data:', e, event.data);
      }
    };

    ws.onerror = (event) => {
      this.handlers.onStateChange?.(WebSocket.CLOSED);
      this.handlers.onError?.(event);

      const { retryOnError, maxRetries, reconnectIntervalMs } = this.options;
      if (retryOnError && !this.disposed && (maxRetries === undefined || this.retryCount < maxRetries)) {
        this.retryCount += 1;
        this.retryTimer = setTimeout(() => this.connect(), reconnectIntervalMs ?? DEFAULT_RETRY_INTERVAL_MS);
      }
    };

    ws.onclose = (event) => {
      if (this.ws === ws) {
        this.ws = null;
      }
      this.handlers.onStateChange?.(WebSocket.CLOSED);
      this.handlers.onClose?.(event);
    };
  }

  send(data: string | ArrayBufferLike | Blob | ArrayBufferView): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    } else {
      console.warn('TaskChannel: WebSocket not open. Cannot send message.');
    }
  }

  disconnect(code = 1000, reason = 'User initiated disconnect'): void {
    this.disposed = true;
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    if (this.ws) {
      this.ws.close(code, reason);
      this.ws = null;
    }
  }
}
