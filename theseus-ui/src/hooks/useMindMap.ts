import { useState, useCallback, useRef, useEffect } from 'react';
import { mindMapApi, createWebSocket } from '../services/api';
import type { 
  PaperApiResponse, 
  MindMapExpandRequest, 
  MindMapData
} from '../services/api';

export interface MindMapState {
  isOpen: boolean;
  isLoading: boolean;
  data: MindMapData | null;
  error: string | null;
  progress: number;
  currentStep: string;
  seedPaper: PaperApiResponse | null;
}

export interface UseMindMapReturn {
  state: MindMapState;
  openMindMap: (paper: PaperApiResponse, options?: Partial<MindMapExpandRequest>) => void;
  closeMindMap: () => void;
  expandNode: (paperId: string, options?: Partial<MindMapExpandRequest>) => void;
  clearError: () => void;
}

export const useMindMap = (): UseMindMapReturn => {
  const [state, setState] = useState<MindMapState>({
    isOpen: false,
    isLoading: false,
    data: null,
    error: null,
    progress: 0,
    currentStep: '',
    seedPaper: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const currentTaskIdRef = useRef<string | null>(null);

  // Cleanup WebSocket connection
  const cleanupWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    currentTaskIdRef.current = null;
  }, []);

  // Handle WebSocket messages
  const handleWebSocketMessage = useCallback((event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data);
      
      setState(prevState => {
        // Handle the RunStatus message format from the task manager
        switch (message.overallStatus) {
          case 'processing':
            return {
              ...prevState,
              isLoading: true,
              progress: message.progress || 0,
              currentStep: message.currentStep || message.message || 'Processing...',
              error: null,
            };
          
          case 'completed':
            const incoming = message.result?.mindmap_data || null;
            if (!incoming) {
              return {
                ...prevState,
                isLoading: false,
                progress: 100,
                currentStep: 'Completed',
              };
            }

            let mergedData = incoming;
            if (prevState.data) {
              const existingNodeIds = new Set(prevState.data.nodes?.map(n => n.id));
              const existingEdgeIds = new Set(prevState.data.edges?.map((e: any) => `${e.source_id}-${e.target_id}`));

              const newNodes = (incoming.nodes || []).filter((n: any) => !existingNodeIds.has(n.id));
              const newEdges = (incoming.edges || []).filter((e: any) => {
                const id = `${e.source_id}-${e.target_id}`;
                return !existingEdgeIds.has(id);
              });

              mergedData = {
                ...prevState.data,
                nodes: [...(prevState.data.nodes || []), ...newNodes],
                edges: [...(prevState.data.edges || []), ...newEdges],
              } as any;
            }

            return {
              ...prevState,
              isLoading: false,
              progress: 100,
              currentStep: 'Completed',
              data: mergedData,
              error: null,
            };
          
          case 'failed':
            return {
              ...prevState,
              isLoading: false,
              progress: 0,
              currentStep: '',
              error: message.error || message.message || 'Mind-map generation failed',
            };
          
          case 'pending':
            return {
              ...prevState,
              isLoading: true,
              progress: 0,
              currentStep: 'Initializing...',
              error: null,
            };
          
          default:
            return prevState;
        }
      });
    } catch (error) {
      setState(prevState => ({
        ...prevState,
        isLoading: false,
        error: 'Failed to process mind-map update',
      }));
    }
  }, []);

  // Start mind-map generation
  const startMindMapGeneration = useCallback(async (
    paper: PaperApiResponse,
    options: Partial<MindMapExpandRequest> = {}
  ) => {
    try {
      setState(prevState => ({
        ...prevState,
        isLoading: true,
        progress: 0,
        currentStep: 'Initializing...',
        error: null,
        seedPaper: paper,
      }));

      // Prepare request
      const request: MindMapExpandRequest = {
        paper_id: paper.id.toString(),
        k: 15,
        similarity_threshold: 0.3,
        layout_algorithm: 'force',
        ...options,
      };

      // Start the mind-map generation task
      const response = await mindMapApi.expandMindMap(request);
      const taskId = response.data.task_id;
      currentTaskIdRef.current = taskId;

      // Setup WebSocket connection for progress updates
      const ws = createWebSocket(taskId, 'mindmap');
      wsRef.current = ws;

      ws.onopen = () => {
        // console.log('Mind-map WebSocket connected');
      };

      ws.onmessage = handleWebSocketMessage;

      ws.onclose = (_event) => {
        /* console.log('Mind-map WebSocket disconnected', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean
        }); */
        cleanupWebSocket();
      };

      ws.onerror = (error) => {
        console.error('Mind-map WebSocket error:', error);
        setState(prevState => ({
          ...prevState,
          isLoading: false,
          error: 'Connection error during mind-map generation',
        }));
      };

    } catch (error) {
      console.error('Error starting mind-map generation:', error);
      setState(prevState => ({
        ...prevState,
        isLoading: false,
        error: 'Failed to start mind-map generation',
      }));
    }
  }, [handleWebSocketMessage, cleanupWebSocket]);

  // Open mind-map
  const openMindMap = useCallback((
    paper: PaperApiResponse,
    options?: Partial<MindMapExpandRequest>
  ) => {
    setState(prevState => ({
      ...prevState,
      isOpen: true,
      data: null,
      error: null,
    }));

    startMindMapGeneration(paper, options);
  }, [startMindMapGeneration]);

  // Close mind-map
  const closeMindMap = useCallback(() => {
    cleanupWebSocket();
    setState({
      isOpen: false,
      isLoading: false,
      data: null,
      error: null,
      progress: 0,
      currentStep: '',
      seedPaper: null,
    });
  }, [cleanupWebSocket]);

  // Expand a node (generate new mind-map with different seed)
  const expandNode = useCallback((
    paperId: string,
    options?: Partial<MindMapExpandRequest>
  ) => {
    if (!state.seedPaper) return;

    // Create a temporary paper object for expansion
    const expandPaper: PaperApiResponse = {
      ...state.seedPaper,
      id: parseInt(paperId),
    };

    startMindMapGeneration(expandPaper, options);
  }, [state.seedPaper, startMindMapGeneration]);

  // Clear error
  const clearError = useCallback(() => {
    setState(prevState => ({
      ...prevState,
      error: null,
    }));
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanupWebSocket();
    };
  }, [cleanupWebSocket]);

  return {
    state,
    openMindMap,
    closeMindMap,
    expandNode,
    clearError,
  };
}; 