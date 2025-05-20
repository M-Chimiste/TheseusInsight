import { useState, useEffect, useRef } from 'react';

export enum WebSocketReadyState {
  CONNECTING = 0,
  OPEN = 1,
  CLOSING = 2,
  CLOSED = 3,
}

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
// Based on previous discussions and main.py/tasks.py
export interface RunStatusPayload {
  taskId: string;
  nodes: NodeStatusPayload[];
  overallStatus: 'pending' | 'processing' | 'completed' | 'failed';
  error?: string | null;
  // Add any other fields your backend sends at the top level of the status message
}

export interface NodeStatusPayload {
  nodeId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';
  message: string;
  progress?: number; // Typically 0-100 or 0-1
  timestamp: string;
  // Add any other fields specific to a node's status
}


export interface UseWebSocketReturn {
  lastMessage: RunStatusPayload | null;
  readyState: WebSocketReadyState;
  error: Event | null;
  sendMessage: (message: string | ArrayBufferLike | Blob | ArrayBufferView) => void;
  disconnect: () => void;
  connect: () => void;
}

const DEFAULT_RETRY_INTERVAL = 5000; // 5 seconds
const DEFAULT_MAX_RETRIES = 5;

export const useWebSocket = (
  taskId: string | null,
  type: 'newsletter' | 'podcast', // Or any other types you might have
  options?: WebSocketOptions
): UseWebSocketReturn => {
  const [lastMessage, setLastMessage] = useState<RunStatusPayload | null>(null);
  const [readyState, setReadyState] = useState<WebSocketReadyState>(WebSocketReadyState.CLOSED);
  const [error, setError] = useState<Event | null>(null);
  const webSocketRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef<number>(0);

  const constructWebSocketUrl = (currentTaskId: string, currentType: 'newsletter' | 'podcast'): string => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Assuming your backend runs on port 8000. Adjust if different.
    const host = window.location.hostname;
    // Use import.meta.env.DEV for client-side check in Vite
    const isDevelopment = import.meta.env.DEV;
    const port = isDevelopment ? ':8000' : (window.location.port ? `:${window.location.port}` : '');
    return `${protocol}//${host}${port}/ws/${currentType}/${currentTaskId}`;
  };

  const connect = () => {
    if (!taskId) {
      // console.log('useWebSocket: No taskId provided, not connecting.');
      setReadyState(WebSocketReadyState.CLOSED);
      return;
    }
    if (webSocketRef.current && readyState !== WebSocketReadyState.CLOSED && readyState !== WebSocketReadyState.CLOSING) {
      // console.log('useWebSocket: Already connected or connecting.');
      return;
    }

    const url = constructWebSocketUrl(taskId, type);
    // console.log(`useWebSocket: Attempting to connect to ${url}`);
    setReadyState(WebSocketReadyState.CONNECTING);
    setError(null);

    const ws = new WebSocket(url);
    webSocketRef.current = ws;

    ws.onopen = (event) => {
      // console.log(`useWebSocket: Connected to ${url}`);
      setReadyState(WebSocketReadyState.OPEN);
      setError(null);
      retryCountRef.current = 0; // Reset retry count on successful connection
      if (options?.onOpen) options.onOpen(event);
    };

    ws.onmessage = (event) => {
      // console.log('useWebSocket: Message received:', event.data);
      try {
        const parsedData = JSON.parse(event.data as string);
        setLastMessage(parsedData as RunStatusPayload); // Assume it's RunStatusPayload
        if (options?.onMessage) options.onMessage(event);
      } catch (e) {
        console.error('useWebSocket: Failed to parse message data:', e);
        // Optionally set an error state or a specific lastMessage format for parse errors
      }
    };

    ws.onerror = (event) => {
      console.error('useWebSocket: WebSocket error:', event);
      setError(event);
      setReadyState(WebSocketReadyState.CLOSED); // Move to closed on error
      if (options?.onError) options.onError(event);

      if (options?.retryOnError && (options.maxRetries === undefined || retryCountRef.current < options.maxRetries)) {
        retryCountRef.current += 1;
        // console.log(`useWebSocket: Retrying connection (attempt ${retryCountRef.current})...`);
        setTimeout(connect, options.reconnectIntervalMs || DEFAULT_RETRY_INTERVAL);
      }
    };

    ws.onclose = (event) => {
      // console.log(`useWebSocket: Disconnected from ${url}`, event.reason);
      // Don't automatically set to CLOSED if it was an error, onerror handles that.
      // Only set to closed if it wasn't an error that triggered the closure or if it's a clean close.
      if (readyState !== WebSocketReadyState.CLOSED) { // Avoid setting state if already handled by error
          setReadyState(WebSocketReadyState.CLOSED);
      }
      if (webSocketRef.current === ws) { // Ensure we are acting on the current WebSocket instance
        webSocketRef.current = null;
      }
      if (options?.onClose) options.onClose(event);
    };
  };

  const disconnect = () => {
    if (webSocketRef.current) {
      // console.log('useWebSocket: Disconnecting...');
      webSocketRef.current.close(1000, 'User initiated disconnect'); // 1000 is a normal closure
      webSocketRef.current = null;
      setReadyState(WebSocketReadyState.CLOSED);
    }
  };

  const sendMessage = (message: string | ArrayBufferLike | Blob | ArrayBufferView) => {
    if (webSocketRef.current && webSocketRef.current.readyState === WebSocketReadyState.OPEN) {
      webSocketRef.current.send(message);
    } else {
      console.warn('useWebSocket: WebSocket not open. Cannot send message.');
    }
  };

  useEffect(() => {
    if (taskId) {
      connect();
    } else {
      disconnect(); // Disconnect if taskId becomes null
    }

    return () => {
      // console.log('useWebSocket: Cleaning up WebSocket connection.');
      disconnect();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, type]); // Reconnect if taskId or type changes

  return { lastMessage, readyState, error, sendMessage, connect, disconnect };
}; 