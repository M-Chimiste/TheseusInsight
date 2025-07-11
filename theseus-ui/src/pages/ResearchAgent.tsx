import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Container,
  Paper,
  Chip,
  LinearProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  Send as SendIcon,
  ExpandMore as ExpandMoreIcon,
  ContentCopy as ContentCopyIcon,
  Download as DownloadIcon,
  Settings as SettingsIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useMutation } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  researchAgentApi, 
  createWebSocket,
  type ResearchTaskRequest,
  type ResearchTaskResponse,
  type ResearchTaskResult,
  type ResearchTaskStatus,
  type ResearchWebSocketMessage 
} from '../services/api';
import { ActivityTimeline, type ProcessedEvent } from '../components/ActivityTimeline';
import { useLayout } from '../contexts/LayoutContext';

interface ChatMessage {
  id: string;
  type: 'user' | 'system' | 'result';
  content: string;
  timestamp: Date;
  taskId?: string;
  result?: ResearchTaskResult;
}

interface ResearchProgress {
  status: string;
  currentNode?: string;
  progress?: any;
  timestamp: string;
}

interface PersistedResearchState {
  taskId: string;
  researchQuestion: string;
  startTime: string;
  messages: ChatMessage[];
}

// Local storage keys
const STORAGE_KEYS = {
  ACTIVE_RESEARCH: 'theseus_active_research',
  RESEARCH_STATE: 'theseus_research_state',
} as const;

const ResearchAgent: React.FC = () => {
  const { headerHeight } = useLayout(); // Get dynamic header height
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [isResearching, setIsResearching] = useState(false);
  const [researchProgress, setResearchProgress] = useState<ResearchProgress | null>(null);
  const [activityEvents, setActivityEvents] = useState<ProcessedEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [researchConfig, setResearchConfig] = useState<ResearchTaskRequest['config']>({});
  const [isReconnecting, setIsReconnecting] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);



  // Persist research state to localStorage
  const persistResearchState = (taskId: string, question: string, messages: ChatMessage[]) => {
    const state: PersistedResearchState = {
      taskId,
      researchQuestion: question,
      startTime: new Date().toISOString(),
      messages: messages.filter(m => m.taskId === taskId), // Only persist messages from this task
    };
    localStorage.setItem(STORAGE_KEYS.RESEARCH_STATE, JSON.stringify(state));
    localStorage.setItem(STORAGE_KEYS.ACTIVE_RESEARCH, taskId);
  };

  // Load persisted research state
  const loadPersistedState = (): PersistedResearchState | null => {
    try {
      const stateStr = localStorage.getItem(STORAGE_KEYS.RESEARCH_STATE);
      if (stateStr) {
        return JSON.parse(stateStr);
      }
    } catch (error) {
      console.error('Failed to load persisted research state:', error);
    }
    return null;
  };

  // Clear persisted state
  const clearPersistedState = () => {
    localStorage.removeItem(STORAGE_KEYS.RESEARCH_STATE);
    localStorage.removeItem(STORAGE_KEYS.ACTIVE_RESEARCH);
  };

  // Check for ongoing research and reconnect if needed
  const checkAndReconnectToActiveTask = async () => {
    const activeTaskId = localStorage.getItem(STORAGE_KEYS.ACTIVE_RESEARCH);
    if (!activeTaskId) return;

    setIsReconnecting(true);
    
    try {
      // Check if the task is still active
      const statusResponse = await researchAgentApi.getTaskStatus(activeTaskId);
      const taskStatus: ResearchTaskStatus = statusResponse.data;
      
      if (taskStatus.status === 'running' || taskStatus.status === 'pending') {
        // Task is still running, restore state and reconnect
        const persistedState = loadPersistedState();
        if (persistedState) {
          setCurrentTaskId(activeTaskId);
          setIsResearching(true);
          setMessages(prev => [...prev, ...persistedState.messages]);
          
          // Add reconnection message
          const reconnectMessage: ChatMessage = {
            id: `reconnect-${Date.now()}`,
            type: 'system',
            content: `🔄 Reconnected to ongoing research task: "${persistedState.researchQuestion}"`,
            timestamp: new Date(),
            taskId: activeTaskId,
          };
          setMessages(prev => [...prev, reconnectMessage]);
          
          // Connect to WebSocket (will be handled by the existing useEffect)
        }
      } else if (taskStatus.status === 'completed') {
        // Task completed while we were away, fetch results
        try {
          const resultResponse = await researchAgentApi.getTaskResult(activeTaskId);
          const result: ResearchTaskResult = resultResponse.data;
          
          const persistedState = loadPersistedState();
          if (persistedState) {
            setMessages(prev => [...prev, ...persistedState.messages]);
            
            // Add completion message
            const completionMessage: ChatMessage = {
              id: `completion-${Date.now()}`,
              type: 'system',
              content: `✅ Research completed while you were away: "${persistedState.researchQuestion}"`,
              timestamp: new Date(),
              taskId: activeTaskId,
            };
            
            const resultMessage: ChatMessage = {
              id: `result-${Date.now()}`,
              type: 'result',
              content: result.final_answer || 'Research completed',
              timestamp: new Date(),
              taskId: activeTaskId,
              result: result,
            };
            
            setMessages(prev => [...prev, completionMessage, resultMessage]);
          }
        } catch (err) {
          console.error('Failed to fetch completed task result:', err);
        }
        clearPersistedState();
      } else {
        // Task failed or cancelled, clean up
        clearPersistedState();
      }
    } catch (error) {
      console.error('Failed to check active task status:', error);
      // If we can't check status, assume task is no longer active
      clearPersistedState();
    } finally {
      setIsReconnecting(false);
    }
  };

  // Check for active tasks on component mount
  useEffect(() => {
    checkAndReconnectToActiveTask();
  }, []);

  // WebSocket connection management
  useEffect(() => {
    if (currentTaskId && isResearching) {
      const ws = createWebSocket(currentTaskId, 'research-agent');
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected for research task:', currentTaskId);
        setError(null); // Clear any connection errors
      };

      ws.onmessage = (event) => {
        try {
          const message: ResearchWebSocketMessage = JSON.parse(event.data);
          
          setResearchProgress({
            status: message.status,
            progress: message.progress,
            timestamp: message.timestamp,
          });

          // Add activity events based on progress updates
          if (message.progress) {
            const progress = message.progress;
            
            // Create activity event if we have meaningful progress info
            if (progress.status && progress.description) {
              const activityEvent: ProcessedEvent = {
                title: progress.status,
                data: progress.description,
                timestamp: message.timestamp,
                node: progress.current_node,
              };
              
              setActivityEvents(prev => {
                // Avoid duplicate consecutive events
                const lastEvent = prev[prev.length - 1];
                if (lastEvent && lastEvent.title === activityEvent.title && lastEvent.data === activityEvent.data) {
                  return prev;
                }
                return [...prev, activityEvent];
              });
            }
          }

          if (message.type === 'task_completed') {
            setIsResearching(false);
            clearPersistedState(); // Clear state when task completes
            
            if (message.status === 'completed' && message.results) {
              // Add completion event
              setActivityEvents(prev => [...prev, {
                title: 'Research Complete',
                data: 'Successfully generated comprehensive research report',
                timestamp: message.timestamp,
                node: 'answer_generator'
              }]);
              
              // Fetch full results
              fetchTaskResult(currentTaskId);
            } else if (message.status === 'failed') {
              // Add failure event
              setActivityEvents(prev => [...prev, {
                title: 'Research Failed',
                data: message.error_message || 'Research task encountered an error',
                timestamp: message.timestamp,
                node: 'error'
              }]);
              
              setError(message.error_message || 'Research task failed');
            }
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Connection error occurred. Attempting to reconnect...');
        
        // Attempt to reconnect after a delay
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
        reconnectTimeoutRef.current = setTimeout(() => {
          if (currentTaskId && isResearching) {
            console.log('Attempting to reconnect WebSocket...');
            checkAndReconnectToActiveTask();
          }
        }, 3000);
      };

      ws.onclose = () => {
        console.log('WebSocket connection closed');
      };

      return () => {
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
        ws.close();
        wsRef.current = null;
      };
    }
  }, [currentTaskId, isResearching]);

  // Persist state when messages or task ID changes
  useEffect(() => {
    if (currentTaskId && isResearching) {
      const currentQuestion = messages.find(m => m.type === 'user' && m.taskId === currentTaskId)?.content || '';
      persistResearchState(currentTaskId, currentQuestion, messages);
    }
  }, [currentTaskId, isResearching, messages]);

  // Fetch task result when research completes
  const fetchTaskResult = async (taskId: string) => {
    try {
      const response = await researchAgentApi.getTaskResult(taskId);
      const result: ResearchTaskResult = response.data;
      
      // Add result message to chat
      const resultMessage: ChatMessage = {
        id: `result-${Date.now()}`,
        type: 'result',
        content: result.final_answer || 'Research completed',
        timestamp: new Date(),
        taskId: taskId,
        result: result,
      };
      
      setMessages(prev => [...prev, resultMessage]);
      setCurrentTaskId(null);
      setResearchProgress(null);
      // Keep activity events visible after completion for a bit
      setTimeout(() => setActivityEvents([]), 5000);
    } catch (err) {
      console.error('Error fetching task result:', err);
      setError('Failed to fetch research results');
    }
  };

  // Start research mutation
  const startResearchMutation = useMutation({
    mutationFn: (request: ResearchTaskRequest) => researchAgentApi.startResearchTask(request),
    onSuccess: (response) => {
      const taskResponse: ResearchTaskResponse = response.data;
      setCurrentTaskId(taskResponse.task_id);
      setIsResearching(true);
      setError(null);
      setActivityEvents([]); // Clear previous activity events
      
      // Add system message
      const systemMessage: ChatMessage = {
        id: `system-${Date.now()}`,
        type: 'system',
        content: `Research task started (ID: ${taskResponse.task_id}). Analyzing your question and gathering evidence...`,
        timestamp: new Date(),
        taskId: taskResponse.task_id,
      };
      
      setMessages(prev => [...prev, systemMessage]);
    },
    onError: (error: any) => {
      setError(error.response?.data?.detail || 'Failed to start research task');
      setIsResearching(false);
    },
  });

  // Cancel research mutation
  const cancelResearchMutation = useMutation({
    mutationFn: (taskId: string) => researchAgentApi.cancelTask(taskId),
    onSuccess: () => {
      setIsResearching(false);
      setCurrentTaskId(null);
      setResearchProgress(null);
      setActivityEvents([]); // Clear activity events
      clearPersistedState(); // Clear persisted state
      
      const cancelMessage: ChatMessage = {
        id: `cancel-${Date.now()}`,
        type: 'system',
        content: 'Research task cancelled.',
        timestamp: new Date(),
      };
      
      setMessages(prev => [...prev, cancelMessage]);
    },
    onError: (error: any) => {
      setError(error.response?.data?.detail || 'Failed to cancel research task');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isResearching) return;

    // Add user message
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, userMessage]);

    // Start research
    const request: ResearchTaskRequest = {
      research_question: inputValue.trim(),
      config: researchConfig,
      save_to_library: true,
    };

    startResearchMutation.mutate(request);
    setInputValue('');
  };

  const handleCancel = () => {
    if (currentTaskId) {
      cancelResearchMutation.mutate(currentTaskId);
    }
  };

  const handleForceReconnect = () => {
    if (currentTaskId) {
      setError(null);
      checkAndReconnectToActiveTask();
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const downloadResult = (result: ResearchTaskResult) => {
    const content = `# Research Report: ${result.research_question}

## Final Answer
${result.final_answer || 'No answer generated'}

## Research Statistics
- Research Loops: ${result.statistics?.research_loops || 0}
- Total Sources Found: ${result.statistics?.total_sources_found || 0}
- Selected Sources: ${result.statistics?.selected_sources || 0}
- Evidence Pieces: ${result.statistics?.evidence_pieces || 0}
- Evidence Sufficient: ${result.statistics?.evidence_sufficient ? 'Yes' : 'No'}
- Compression Used: ${result.statistics?.compression_used ? 'Yes' : 'No'}

## Sub-Queries
${result.sub_queries.map((query, index) => `${index + 1}. ${query}`).join('\n')}

## Evidence
${result.evidence.map((evidence, index) => `### Evidence ${index + 1}\n${evidence}`).join('\n\n')}

${result.compressed_notes ? `## Compressed Notes\n${result.compressed_notes}` : ''}

---
Generated on: ${new Date(result.created_at).toLocaleString()}
Task ID: ${result.task_id}
`;

    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `research-report-${result.task_id}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const renderMessage = (message: ChatMessage) => {
    switch (message.type) {
      case 'user':
        return (
          <Box key={message.id} sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
            <Paper
              sx={{
                p: 2,
                maxWidth: '70%',
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                borderRadius: '18px 18px 4px 18px',
              }}
            >
              <Typography variant="body1">{message.content}</Typography>
              <Typography variant="caption" sx={{ opacity: 0.8, display: 'block', mt: 1 }}>
                {message.timestamp.toLocaleTimeString()}
              </Typography>
            </Paper>
          </Box>
        );

      case 'system':
        return (
          <Box key={message.id} sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
            <Chip
              label={message.content}
              variant="outlined"
              size="small"
              sx={{ maxWidth: '80%' }}
            />
          </Box>
        );

      case 'result':
        return (
          <Box key={message.id} sx={{ mb: 3 }}>
            <Paper
              sx={{
                p: 3,
                bgcolor: 'background.paper',
                borderRadius: '18px 18px 18px 4px',
                border: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="h6" color="primary">
                  Research Complete
                </Typography>
                <Box>
                  <Tooltip title="Copy to clipboard">
                    <IconButton
                      size="small"
                      onClick={() => copyToClipboard(message.content)}
                    >
                      <ContentCopyIcon />
                    </IconButton>
                  </Tooltip>
                  {message.result && (
                    <Tooltip title="Download report">
                      <IconButton
                        size="small"
                        onClick={() => downloadResult(message.result!)}
                      >
                        <DownloadIcon />
                      </IconButton>
                    </Tooltip>
                  )}
                </Box>
              </Box>

              <Typography variant="body1" sx={{ mb: 2 }}>
                <Box 
                  sx={{ 
                    '& h1, & h2, & h3, & h4, & h5, & h6': {
                      fontWeight: 'bold',
                      margin: '16px 0 8px 0',
                      '&:first-of-type': { marginTop: 0 }
                    },
                    '& h1': { fontSize: '1.5rem' },
                    '& h2': { fontSize: '1.25rem' },
                    '& h3': { fontSize: '1.1rem' },
                    '& p': {
                      margin: '8px 0',
                      lineHeight: 1.6
                    },
                    '& ul, & ol': {
                      margin: '8px 0',
                      paddingLeft: '24px'
                    },
                    '& li': {
                      margin: '4px 0'
                    },
                    '& code': {
                      backgroundColor: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)',
                      padding: '2px 4px',
                      borderRadius: '4px',
                      fontFamily: 'monospace',
                      fontSize: '0.9em'
                    },
                    '& pre': {
                      backgroundColor: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)',
                      padding: '12px',
                      borderRadius: '4px',
                      overflow: 'auto',
                      fontFamily: 'monospace'
                    },
                    '& blockquote': {
                      borderLeft: '4px solid',
                      borderColor: 'primary.main',
                      paddingLeft: '16px',
                      margin: '16px 0',
                      fontStyle: 'italic',
                      opacity: 0.8
                    },
                    '& table': {
                      width: '100%',
                      borderCollapse: 'collapse',
                      margin: '16px 0'
                    },
                    '& th, & td': {
                      border: '1px solid',
                      borderColor: 'divider',
                      padding: '8px 12px',
                      textAlign: 'left'
                    },
                    '& th': {
                      backgroundColor: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)',
                      fontWeight: 'bold'
                    }
                  }}
                >
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                </Box>
              </Typography>

              {message.result && (
                <Box>
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="subtitle2">Research Details</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                        <Chip
                          label={`${message.result.statistics?.research_loops || 0} loops`}
                          size="small"
                          variant="outlined"
                        />
                        <Chip
                          label={`${message.result.statistics?.total_sources_found || 0} sources`}
                          size="small"
                          variant="outlined"
                        />
                        <Chip
                          label={`${message.result.statistics?.evidence_pieces || 0} evidence`}
                          size="small"
                          variant="outlined"
                        />
                        {message.result.statistics?.compression_used && (
                          <Chip
                            label="Compressed"
                            size="small"
                            color="warning"
                            variant="outlined"
                          />
                        )}
                      </Box>

                      {message.result.sub_queries.length > 0 && (
                        <Box sx={{ mb: 2 }}>
                          <Typography variant="subtitle2" gutterBottom>
                            Sub-queries explored:
                          </Typography>
                          <List dense>
                            {message.result.sub_queries.map((query, index) => (
                              <ListItem key={index} sx={{ py: 0.5 }}>
                                <ListItemText
                                  primary={`${index + 1}. ${query}`}
                                  primaryTypographyProps={{ variant: 'body2' }}
                                />
                              </ListItem>
                            ))}
                          </List>
                        </Box>
                      )}
                    </AccordionDetails>
                  </Accordion>
                </Box>
              )}

              <Typography variant="caption" sx={{ opacity: 0.7, display: 'block', mt: 2 }}>
                {message.timestamp.toLocaleTimeString()}
              </Typography>
            </Paper>
          </Box>
        );

      default:
        return null;
    }
  };

  return (
    <Container maxWidth="lg" sx={{ pt: `${headerHeight + 32}px`, pb: 4 }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', height: `calc(100vh - ${headerHeight + 160}px)` }}>
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Research Agent
          </Typography>
          <Box>
            <Tooltip title="Research Configuration">
              <IconButton onClick={() => setConfigDialogOpen(true)}>
                <SettingsIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Error Alert with Reconnect option */}
        {error && (
          <Alert 
            severity="error" 
            sx={{ mb: 2 }} 
            onClose={() => setError(null)}
            action={
              currentTaskId && (
                <Button
                  color="inherit"
                  size="small"
                  startIcon={<RefreshIcon />}
                  onClick={handleForceReconnect}
                  disabled={isReconnecting}
                >
                  {isReconnecting ? 'Reconnecting...' : 'Reconnect'}
                </Button>
              )
            }
          >
            {error}
          </Alert>
        )}

        {/* Reconnection Indicator */}
        {isReconnecting && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CircularProgress size={16} />
              Checking for active research tasks and reconnecting...
            </Box>
          </Alert>
        )}

        {/* Progress Indicator */}
        {isResearching && researchProgress && (
          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ py: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  Status: {researchProgress.status}
                </Typography>
                <Button
                  size="small"
                  startIcon={<StopIcon />}
                  onClick={handleCancel}
                  disabled={cancelResearchMutation.isPending}
                >
                  Cancel
                </Button>
              </Box>
              <LinearProgress />
            </CardContent>
          </Card>
        )}

        {/* Activity Timeline */}
        {(isResearching || activityEvents.length > 0) && (
          <ActivityTimeline
            processedEvents={activityEvents}
            isLoading={isResearching}
            currentProgress={researchProgress?.progress}
          />
        )}

        {/* Messages Area */}
        <Box
          sx={{
            flex: 1,
            overflow: 'auto',
            p: 2,
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
            mb: 2,
          }}
        >
          {messages.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 8 }}>
              <Typography variant="h6" color="text.secondary" gutterBottom>
                Welcome to Research Agent
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Ask any research question and I'll analyze the literature to provide comprehensive answers.
              </Typography>
              {isReconnecting && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                  🔄 Checking for ongoing research tasks...
                </Typography>
              )}
            </Box>
          ) : (
            messages.map(renderMessage)
          )}
          <div ref={messagesEndRef} />
        </Box>

        {/* Input Area */}
        <Paper
          component="form"
          onSubmit={handleSubmit}
          sx={{
            p: 2,
            display: 'flex',
            alignItems: 'center',
            gap: 2,
          }}
        >
          <TextField
            fullWidth
            multiline
            maxRows={4}
            placeholder="Ask a research question..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={isResearching || isReconnecting}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
          />
          <Button
            type="submit"
            variant="contained"
            disabled={!inputValue.trim() || isResearching || isReconnecting}
            startIcon={isResearching ? <CircularProgress size={20} /> : <SendIcon />}
            sx={{ minWidth: 120 }}
          >
            {isResearching ? 'Researching...' : 'Research'}
          </Button>
        </Paper>
      </Box>

      {/* Configuration Dialog */}
      <Dialog
        open={configDialogOpen}
        onClose={() => setConfigDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Research Configuration</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <Typography variant="h6" gutterBottom>
              Search Configuration
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
              <TextField
                label="Local Search Limit"
                type="number"
                value={researchConfig?.search_config?.local_limit || 20}
                onChange={(e) =>
                  setResearchConfig(prev => ({
                    ...prev,
                    search_config: {
                      ...prev?.search_config,
                      local_limit: parseInt(e.target.value),
                    },
                  }))
                }
                sx={{ flex: 1 }}
              />
              <TextField
                label="External Search Limit"
                type="number"
                value={researchConfig?.search_config?.external_limit || 15}
                onChange={(e) =>
                  setResearchConfig(prev => ({
                    ...prev,
                    search_config: {
                      ...prev?.search_config,
                      external_limit: parseInt(e.target.value),
                    },
                  }))
                }
                sx={{ flex: 1 }}
              />
            </Box>

            <Typography variant="h6" gutterBottom>
              Evidence Configuration
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
              <TextField
                label="Min Evidence Threshold"
                type="number"
                value={researchConfig?.evidence_config?.min_evidence_threshold || 3}
                onChange={(e) =>
                  setResearchConfig(prev => ({
                    ...prev,
                    evidence_config: {
                      ...prev?.evidence_config,
                      min_evidence_threshold: parseInt(e.target.value),
                    },
                  }))
                }
                sx={{ flex: 1 }}
              />
              <TextField
                label="Quality Threshold"
                type="number"
                inputProps={{ step: 0.1, min: 0, max: 1 }}
                value={researchConfig?.evidence_config?.quality_threshold || 0.7}
                onChange={(e) =>
                  setResearchConfig(prev => ({
                    ...prev,
                    evidence_config: {
                      ...prev?.evidence_config,
                      quality_threshold: parseFloat(e.target.value),
                    },
                  }))
                }
                sx={{ flex: 1 }}
              />
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfigDialogOpen(false)}>Cancel</Button>
          <Button onClick={() => setConfigDialogOpen(false)} variant="contained">
            Save Configuration
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default ResearchAgent; 