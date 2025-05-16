import { useEffect, useState } from 'react';
import { io, Socket } from 'socket.io-client';

export function useWebSocketProgress(runId: string) {
  const [status, setStatus] = useState<string>('connecting');
  const [socket, setSocket] = useState<Socket | null>(null);

  useEffect(() => {
    const newSocket = io('http://localhost:8000', {
      path: '/ws',
      query: { runId },
    });

    newSocket.on('connect', () => {
      setStatus('connected');
    });

    newSocket.on('disconnect', () => {
      setStatus('disconnected');
    });

    newSocket.on('progress', (data) => {
      setStatus(data.status);
    });

    setSocket(newSocket);

    return () => {
      newSocket.close();
    };
  }, [runId]);

  return { status, socket };
} 