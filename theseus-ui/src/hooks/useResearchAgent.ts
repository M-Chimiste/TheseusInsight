import { useState, useEffect, useCallback, useRef } from 'react';
import { researchAgentApi, createWebSocket } from '../services/api';

export interface LiteratureReviewSummary {
  paper_id: number;
  title: string;
  summary: string;
  rationale: string;
  relevance_score: number;
}

export interface LiteratureReviewResult {
  id: number;
  research_question: string;
  summaries: LiteratureReviewSummary[];
  created_ts: string;
  total_papers: number;
  trace_log: any[];
  report_text?: string;
  short_summary?: string;
  activity_log?: any[];
}

export interface ResearchAgentProgress {
  taskId: string;
  status: 'processing' | 'completed' | 'failed';
  progress: number;
  current_step: string;
  message: string;
}

export interface ResearchAgentState {
  isRunning: boolean;
  currentTask: string | null;
  progress: number;
  currentStep: string;
  message: string;
  logs: string[];
  result: LiteratureReviewResult | null;
  recentReviews: LiteratureReviewResult[];
  error: string | null;
  loading: boolean;
}

const initialState: ResearchAgentState = {
  isRunning: false,
  currentTask: null,
  progress: 0,
  currentStep: '',
  message: '',
  logs: [],
  result: null,
  recentReviews: [],
  error: null,
  loading: false,
};

export const useResearchAgent = () => {
  const [state, setState] = useState<ResearchAgentState>(initialState);
  const wsRef = useRef<WebSocket | null>(null);

  const fetchReview = useCallback(async (reviewId: number) => {
    try {
      const response = await researchAgentApi.getReview(reviewId);
      setState(prev => ({
        ...prev,
        result: response.data,
      }));
    } catch (error) {
      console.error('Error fetching review:', error);
    }
  }, []);

  const fetchRecentReviews = useCallback(async () => {
    try {
      const response = await researchAgentApi.getRecentReviews(10);
      setState(prev => ({
        ...prev,
        recentReviews: response.data,
      }));
    } catch (error) {
      console.error('Error fetching recent reviews:', error);
    }
  }, []);

  // Fetch recent reviews on hook initialization
  useEffect(() => {
    fetchRecentReviews();
  }, [fetchRecentReviews]);

  // Clean up WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const addLog = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setState(prev => ({
      ...prev,
      logs: [...prev.logs, `[${timestamp}] ${message}`]
    }));
  }, []);

  const updateProgress = useCallback((progress: number, step: string, message: string = '') => {
    setState(prev => ({
      ...prev,
      progress,
      currentStep: step,
      message,
    }));
  }, []);

  const connectWebSocket = useCallback((taskId: string) => {
    try {
      wsRef.current = createWebSocket(taskId, 'research-agent');
      
      wsRef.current.onopen = () => {
        addLog('WebSocket connected');
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Handle the TaskManager format (RunStatus)
          if (data.overallStatus) {
            const status = data.overallStatus;
            const progress = data.progress || 0;
            const message = data.message || '';
            const currentStep = data.currentStep || '';
            const error = data.error;
            
            updateProgress(progress, currentStep, message);
            addLog(`${progress}% - ${currentStep || message || status}`);
            
            if (status === 'completed') {
              setState(prev => ({
                ...prev,
                isRunning: false,
                progress: 100,
                currentStep: 'Completed',
                message: 'Literature review completed successfully',
              }));
              addLog('Literature review completed!');
              
              // Refresh recent reviews to show the new result
              fetchRecentReviews();
            } else if (status === 'failed') {
              setState(prev => ({
                ...prev,
                isRunning: false,
                error: error || 'An error occurred',
              }));
              addLog(`Error: ${error || 'Unknown error'}`);
            }
          }
          // Fallback for legacy format (if any)
          else if (data.type === 'progress') {
            updateProgress(data.progress || 0, data.current_step || '', data.message || '');
            addLog(`Progress: ${data.progress}% - ${data.current_step || data.message}`);
          } else if (data.type === 'log') {
            addLog(data.message || data.status || 'Log entry');
          } else if (data.type === 'completed') {
            setState(prev => ({
              ...prev,
              isRunning: false,
              progress: 100,
              currentStep: 'Completed',
              message: 'Literature review completed successfully',
            }));
            addLog('Literature review completed!');
            
            // Fetch the result
            if (data.review_id) {
              fetchReview(data.review_id);
            }
            fetchRecentReviews();
          } else if (data.type === 'error') {
            setState(prev => ({
              ...prev,
              isRunning: false,
              error: data.message || 'An error occurred',
            }));
            addLog(`Error: ${data.message || 'Unknown error'}`);
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
          addLog('Error parsing WebSocket message');
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        addLog('WebSocket connection error');
      };

      wsRef.current.onclose = () => {
        addLog('WebSocket disconnected');
      };
    } catch (error) {
      console.error('Error connecting WebSocket:', error);
      addLog('Failed to connect WebSocket');
    }
  }, [addLog, updateProgress]);

  const startResearch = useCallback(async (researchQuestion: string) => {
    if (!researchQuestion.trim()) {
      setState(prev => ({ ...prev, error: 'Please enter a research question' }));
      return;
    }

    setState(prev => ({
      ...prev,
      isRunning: true,
      progress: 0,
      currentStep: 'Initializing research agent...',
      message: 'Starting literature review',
      logs: [],
      error: null,
      result: null,
      loading: true,
    }));

    addLog('Starting literature review...');
    addLog(`Research Question: ${researchQuestion}`);

    try {
      const response = await researchAgentApi.runResearch(researchQuestion);
      const { task_id } = response.data;
      
      setState(prev => ({
        ...prev,
        currentTask: task_id,
        loading: false,
      }));

      addLog(`Task created: ${task_id}`);
      
      // Connect to WebSocket for real-time updates
      connectWebSocket(task_id);
      
    } catch (error: any) {
      console.error('Error starting research:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to start research';
      
      setState(prev => ({
        ...prev,
        isRunning: false,
        error: errorMessage,
        loading: false,
      }));
      
      addLog(`Error: ${errorMessage}`);
    }
  }, [addLog, connectWebSocket]);

  const stopResearch = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    
    // TODO: Implement actual abort API call when backend supports it
    // if (state.currentTask) {
    //   settingsApi.abortTask(state.currentTask);
    // }
    
    setState(prev => ({
      ...prev,
      isRunning: false,
      currentTask: null,
      currentStep: 'Stopped by user',
      message: 'Research stopped',
    }));
    
    addLog('Research stopped by user');
  }, []);

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  const clearResult = useCallback(() => {
    setState(prev => ({ ...prev, result: null }));
  }, []);

  return {
    ...state,
    startResearch,
    stopResearch,
    fetchReview,
    fetchRecentReviews,
    clearError,
    clearResult,
  };
}; 