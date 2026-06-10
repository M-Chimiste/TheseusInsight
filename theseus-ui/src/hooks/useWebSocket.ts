import { useState, useEffect, useRef } from 'react';
import type { TaskMetadata } from '../components/newsletter/types';
import { TaskChannel } from '../services/taskChannel';

export const WebSocketReadyState = {
  CONNECTING: 0,
  OPEN: 1,
  CLOSING: 2,
  CLOSED: 3,
} as const;

export type WebSocketReadyState = typeof WebSocketReadyState[keyof typeof WebSocketReadyState];

interface WebSocketOptions {
  onOpen?: (event: WebSocketEventMap['open']) => void;
  onClose?: (event: WebSocketEventMap['close']) => void;
  onError?: (event: WebSocketEventMap['error']) => void;
  onMessage?: (event: WebSocketEventMap['message']) => void;
  retryOnError?: boolean;
  reconnectIntervalMs?: number;
  maxRetries?: number;
}

// This should match the structure your backend sends for status updates.
export interface RunStatusPayload {
  taskId: string;
  nodes: NodeStatusPayload[];
  overallStatus: 'pending' | 'processing' | 'completed' | 'failed';
  currentStep?: string | null;
  progress?: number | null;
  message?: string | null;
  result?: Record<string, any> | null;
  error?: string | null;
  metadata?: TaskMetadata | null;
}

export interface NodeStatusPayload {
  nodeId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';
  message: string;
  progress?: number; // Typically 0-100 or 0-1
  timestamp: string;
}

export interface UseWebSocketReturn {
  lastMessage: RunStatusPayload | null;
  readyState: WebSocketReadyState;
  error: Event | null;
  sendMessage: (message: string | ArrayBufferLike | Blob | ArrayBufferView) => void;
  disconnect: () => void;
  connect: () => void;
}

const PLACEHOLDER_TASK_IDS = {
  newsletter: 'dummy-newsletter-task-id',
  podcast: 'dummy-podcast-task-id',
  visualizer: 'dummy-visualizer-task-id',
};

/**
 * Task-progress WebSocket hook. Since F4 this is a thin React adapter
 * over services/taskChannel.ts (which owns connect/retry/persistence);
 * the public API is unchanged.
 */
export const useWebSocket = (
  taskId: string | null,
  type: 'newsletter' | 'podcast' | 'visualizer',
  options?: WebSocketOptions
): UseWebSocketReturn => {
  const [lastMessage, setLastMessage] = useState<RunStatusPayload | null>(null);
  const [readyState, setReadyState] = useState<WebSocketReadyState>(WebSocketReadyState.CLOSED);
  const [error, setError] = useState<Event | null>(null);
  const channelRef = useRef<TaskChannel | null>(null);

  const connect = () => {
    if (!taskId || taskId === PLACEHOLDER_TASK_IDS[type]) {
      setReadyState(WebSocketReadyState.CLOSED);
      return;
    }
    if (channelRef.current && channelRef.current.readyState !== WebSocketReadyState.CLOSED) {
      return;
    }

    setReadyState(WebSocketReadyState.CONNECTING);
    setError(null);

    // dummy guard mirrors the original: placeholder tasks never persist
    const persist = !taskId.includes('dummy');
    const channel = new TaskChannel(type, taskId, {
      onStateChange: (state) => setReadyState(state as WebSocketReadyState),
      onRestore: (payload) => setLastMessage(payload as RunStatusPayload),
      onMessage: (payload, event) => {
        setLastMessage(payload as RunStatusPayload);
        if (options?.onMessage) options.onMessage(event);
      },
      onOpen: (event) => {
        setError(null);
        if (options?.onOpen) options.onOpen(event);
      },
      onError: (event) => {
        setError(event);
        if (options?.onError) options.onError(event);
      },
      onClose: (event) => {
        if (options?.onClose) options.onClose(event);
      },
    }, {
      retryOnError: options?.retryOnError,
      reconnectIntervalMs: options?.reconnectIntervalMs,
      maxRetries: options?.maxRetries,
      storage: persist ? sessionStorage : null,
    });
    channelRef.current = channel;
    channel.connect();
  };

  const disconnect = () => {
    if (channelRef.current) {
      channelRef.current.disconnect();
      channelRef.current = null;
      setReadyState(WebSocketReadyState.CLOSED);
    }
  };

  const sendMessage = (message: string | ArrayBufferLike | Blob | ArrayBufferView) => {
    if (channelRef.current) {
      channelRef.current.send(message);
    } else {
      console.warn('useWebSocket: WebSocket not open. Cannot send message.');
    }
  };

  useEffect(() => {
    if (taskId && taskId !== PLACEHOLDER_TASK_IDS[type]) {
      connect();
    } else {
      disconnect();
    }
    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, type]);

  return { lastMessage, readyState, error, sendMessage, connect, disconnect };
};
