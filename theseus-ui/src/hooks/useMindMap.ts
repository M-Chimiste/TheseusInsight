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
  expandNode: (paperId: string, options?: Partial<MindMapExpandRequest>, merge?: boolean) => void;
  clearError: () => void;
  loadSavedMap: (data: MindMapData, seedPaper: PaperApiResponse | null) => void;
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
  // Flag to indicate whether the current operation is an incremental expand (merge) rather than a full regeneration
  const mergeModeRef = useRef<boolean>(false);
  const generationColorRef = useRef<number>(0);
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
      console.log('🔄 MindMap WebSocket Message:', {
        overallStatus: message.overallStatus,
        progress: message.progress,
        currentStep: message.currentStep,
        message: message.message,
        fullMessage: message
      });
      
      setState(prevState => {
        // Handle the RunStatus message format from the task manager
        switch (message.overallStatus) {
          case 'processing':
            console.log('📈 Updating UI state with progress:', message.progress, message.currentStep || message.message);
            return {
              ...prevState,
              isLoading: true,
              progress: message.progress || 0,
              currentStep: message.currentStep || message.message || 'Processing...',
              error: null,
            };
          
          case 'completed': {
            const incoming = message.result?.mindmap_data || null;

            // Reset merge flag for subsequent operations
            const wasMerge = mergeModeRef.current;
            mergeModeRef.current = false;

            if (!incoming) {
              return {
                ...prevState,
                isLoading: false,
                error: 'No mind-map data received from server',
              };
            }

            if (!wasMerge || !prevState.data) {
              // Reset generation color index on full regeneration
              generationColorRef.current = 0;
              // Ensure all nodes have colorIndex 0
              incoming.nodes = incoming.nodes.map((n: any) => ({ ...n, colorIndex: 0 }));
              // Full regeneration path (default behaviour)
              return {
                ...prevState,
                isLoading: false,
                progress: 100,
                currentStep: 'Completed',
                data: incoming,
                error: null,
              };
            }

            // Merge path – add new nodes/edges to existing graph
            try {
              const existingData = prevState.data;

              // Build lookup for existing nodes
              const nodeMap = new Map<string, any>(existingData.nodes.map((n) => [String(n.id), n]));
              const mergedNodes = [...existingData.nodes];

              // Increment generation color for this merge cycle
              generationColorRef.current = (generationColorRef.current + 1) % 6;
              const newColorIndex = generationColorRef.current;

              incoming.nodes.forEach((node: any) => {
                const idStr = String(node.id);
                if (!nodeMap.has(idStr)) {
                  const coloredNode = { ...node, colorIndex: newColorIndex };
                  nodeMap.set(idStr, coloredNode);
                  mergedNodes.push(coloredNode);
                }
              });

              // Build lookup for existing edges (treat as undirected)
              const edgeKey = (e: any) => `${Math.min(e.source_id, e.target_id)}-${Math.max(e.source_id, e.target_id)}`;
              const edgeSet = new Set<string>(existingData.edges.map(edgeKey));
              const mergedEdges = [...existingData.edges];

              incoming.edges.forEach((e: any) => {
                const key = edgeKey(e);
                if (!edgeSet.has(key)) {
                  edgeSet.add(key);
                  mergedEdges.push(e);
                }
              });

              const mergedData = {
                ...existingData,
                nodes: mergedNodes,
                edges: mergedEdges,
                generation_timestamp: incoming.generation_timestamp || new Date().toISOString(),
              } as typeof existingData;

              return {
                ...prevState,
                isLoading: false,
                progress: 100,
                currentStep: 'Expansion completed',
                data: mergedData,
                error: null,
              };
            } catch (mergeErr) {
              console.error('Error merging mind-map data:', mergeErr);
              return {
                ...prevState,
                isLoading: false,
                error: 'Failed to merge expanded nodes',
              };
            }
          }
          
          case 'failed':
            return {
              ...prevState,
              isLoading: false,
              error: message.message || 'Mind-map generation failed',
            };
          
          default:
            return prevState;
        }
      });
    } catch (error) {
      console.error('Error parsing WebSocket message:', error, event.data);
    }
  }, []);

  // Start mind-map generation
  const startMindMapGeneration = useCallback(async (
    paper: PaperApiResponse,
    options: Partial<MindMapExpandRequest> = {}
  ) => {
    console.log('🚀 STARTMINDMAPGENERATION FUNCTION CALLED!', { options });
    
    try {
      setState({
        isOpen: true,
        isLoading: true,
        progress: 0,
        currentStep: 'Initializing...',
        data: null,
        seedPaper: paper,
        error: null,
      });

      // Prepare request. Only include parameters explicitly provided in `options` so
      // that the backend can fall back to the orchestration defaults when a
      // particular value is not supplied by the user.
      const request: MindMapExpandRequest = {
        paper_id: paper.id.toString(),
        ...options,
      };

      console.log('🔧 Frontend sending request:', {
        originalOptions: options,
        finalRequest: request,
        expansionOrderFromOptions: options.expansion_order,
        expansionOrderInRequest: request.expansion_order
      });

      // Start the mind-map generation task
      const response = await mindMapApi.expandMindMap(request);
      const taskId = response.data.task_id;
      currentTaskIdRef.current = taskId;

      // Add a small delay to ensure backend task is ready
      await new Promise(resolve => setTimeout(resolve, 100));

      // Setup WebSocket connection for progress updates
      const ws = createWebSocket(taskId, 'mindmap');
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('✅ Mind-map WebSocket connected with task ID:', taskId);
      };

      ws.onmessage = handleWebSocketMessage;

      ws.onclose = (_event) => {
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

  // Expand a node – can be full regeneration or incremental merge based on `merge` flag
  const expandNode = useCallback((
    paperId: string,
    options?: Partial<MindMapExpandRequest>,
    merge: boolean = false
  ) => {
    if (!state.seedPaper) return;

    if (!merge) {
      // Original behaviour – full regeneration with new seed
      const expandPaper: PaperApiResponse = {
        ...state.seedPaper,
        id: parseInt(paperId),
      };
      startMindMapGeneration(expandPaper, options);
      return;
    }

    // Incremental merge mode
    (async () => {
      try {
        // Set merge mode flag so WebSocket handler knows to merge results
        mergeModeRef.current = true;

        setState(prev => ({
          ...prev,
          isLoading: true,
          progress: 0,
          currentStep: 'Expanding nodes...',
          error: null,
        }));

        const request: MindMapExpandRequest = {
          paper_id: paperId,
          ...options,
          expansion_order: 1, // Force single-order for incremental expansion
        };

        const response = await mindMapApi.expandMindMap(request);
        const taskId = response.data.task_id;
        currentTaskIdRef.current = taskId;

        // Wait briefly then open websocket for updates
        await new Promise(res => setTimeout(res, 100));

        const ws = createWebSocket(taskId, 'mindmap');
        wsRef.current = ws;

        ws.onopen = () => {
          console.log('✅ Incremental expand WebSocket connected', taskId);
        };

        ws.onmessage = handleWebSocketMessage;

        ws.onclose = () => {
          cleanupWebSocket();
        };

        ws.onerror = (err) => {
          console.error('Incremental expand WS error', err);
          setState(prev => ({
            ...prev,
            isLoading: false,
            error: 'Connection error during node expansion',
          }));
        };
      } catch (err) {
        console.error('Error starting incremental expansion', err);
        mergeModeRef.current = false;
        setState(prev => ({
          ...prev,
          isLoading: false,
          error: 'Failed to expand node',
        }));
      }
    })();
  }, [state.seedPaper, handleWebSocketMessage, cleanupWebSocket]);

  // Clear error
  const clearError = useCallback(() => {
    setState(prevState => ({
      ...prevState,
      error: null,
    }));
  }, []);

  // Load already generated mind-map data (saved reports)
  const loadSavedMap = useCallback((data: MindMapData, seed: PaperApiResponse | null) => {
    setState({
      isOpen: true,
      isLoading: false,
      data,
      error: null,
      progress: 100,
      currentStep: 'Loaded',
      seedPaper: seed,
    });
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
    loadSavedMap,
  };
}; 