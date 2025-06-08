import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Paper,
  IconButton,
  Tooltip,
  Alert,
  Snackbar,
  CircularProgress,
  Chip,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  useTheme,
  Collapse,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  Science as ScienceIcon,
  Send as SendIcon,
  Stop as StopIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  ContentCopy as CopyIcon,
  Check as CheckIcon,
  Refresh as RefreshIcon,
  Timeline as TimelineIcon,
  Search as SearchIcon,
  Psychology as PsychologyIcon,
  Create as CreateIcon,
  AutoAwesome as SmartIcon,
} from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import { useResearchAgent } from '../hooks/useResearchAgent';
import { useLayout } from '../contexts/LayoutContext';
import CollapsibleContent from '../components/CollapsibleContent';

// Helper function to extract and process thinking content
const processThinkingContent = (content: string) => {
  if (!content) return { cleanContent: '', thinkingContent: null };
  
  // Look for <think> and </think> tags
  const thinkRegex = /<think>([\s\S]*?)<\/think>/gi;
  const matches = content.match(thinkRegex);
  
  if (matches) {
    // Extract thinking content (remove the tags)
    const thinkingContent = matches.map(match => 
      match.replace(/<\/?think>/gi, '').trim()
    ).join('\n\n');
    
    // Remove thinking content from the main content
    const cleanContent = content.replace(thinkRegex, '').trim();
    
    return { cleanContent, thinkingContent };
  }
  
  return { cleanContent: content, thinkingContent: null };
};

// Types based on the new LangGraph implementation
interface ProcessedEvent {
  title: string;
  data: any;
}

interface ConversationMessage {
  id: string;
  type: 'human' | 'ai';
  content: string;
}

interface ActivityTimelineProps {
  processedEvents: ProcessedEvent[];
  isLoading: boolean;
}

// Activity Timeline Component
const ActivityTimeline: React.FC<ActivityTimelineProps> = ({ processedEvents, isLoading }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const theme = useTheme();

  const getEventIcon = (title: string) => {
    const titleLower = title.toLowerCase();
    if (titleLower.includes('generating') || titleLower.includes('query')) {
      return <SearchIcon sx={{ fontSize: 16, color: theme.palette.primary.main }} />;
    } else if (titleLower.includes('research') || titleLower.includes('search')) {
      return <ScienceIcon sx={{ fontSize: 16, color: theme.palette.secondary.main }} />;
    } else if (titleLower.includes('reflection') || titleLower.includes('thinking')) {
      return <PsychologyIcon sx={{ fontSize: 16, color: theme.palette.warning.main }} />;
    } else if (titleLower.includes('finalizing') || titleLower.includes('answer')) {
      return <CreateIcon sx={{ fontSize: 16, color: theme.palette.success.main }} />;
    }
    return <TimelineIcon sx={{ fontSize: 16, color: theme.palette.text.secondary }} />;
  };

  useEffect(() => {
    if (!isLoading && processedEvents.length > 0) {
      setIsCollapsed(true);
    }
  }, [isLoading, processedEvents]);

  return (
    <Card 
      variant="outlined" 
      sx={{ 
        mb: 2, 
        backgroundColor: alpha(theme.palette.primary.main, 0.02),
        borderColor: alpha(theme.palette.primary.main, 0.1)
      }}
    >
      <CardContent sx={{ pb: '16px !important' }}>
        <Box 
          sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            cursor: 'pointer',
            mb: isCollapsed ? 0 : 2
          }}
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <TimelineIcon sx={{ fontSize: 20, color: theme.palette.primary.main }} />
            <Typography variant="subtitle2" color="primary" fontWeight={600}>
              Research Progress
            </Typography>
          </Box>
          {isCollapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
        </Box>
        
        <Collapse in={!isCollapsed}>
          <Box sx={{ maxHeight: 300, overflow: 'auto' }}>
            {isLoading && processedEvents.length === 0 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 2 }}>
                <CircularProgress size={16} />
                <Typography variant="body2" color="text.secondary">
                  Initializing research...
                </Typography>
              </Box>
            )}
            
            {processedEvents.map((event, index) => (
              <Box key={index} sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, py: 1 }}>
                <Box sx={{ pt: 0.5 }}>
                  {getEventIcon(event.title)}
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="body2" fontWeight={500} sx={{ mb: 0.5 }}>
                    {event.title}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {typeof event.data === 'string' 
                      ? event.data 
                      : Array.isArray(event.data)
                        ? event.data.join(', ')
                        : JSON.stringify(event.data)
                    }
                  </Typography>
                </Box>
              </Box>
            ))}
            
            {isLoading && processedEvents.length > 0 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 1 }}>
                <CircularProgress size={16} />
                <Typography variant="body2" color="text.secondary">
                  Processing...
                </Typography>
              </Box>
            )}
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  );
};

// Message Component
interface MessageBubbleProps {
  message: ConversationMessage;
  isLast: boolean;
  isLoading: boolean;
  liveActivity?: ProcessedEvent[];
  historicalActivity?: ProcessedEvent[];
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ 
  message, 
  isLast, 
  isLoading, 
  liveActivity, 
  historicalActivity 
}) => {
  const [copied, setCopied] = useState(false);
  const theme = useTheme();

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  const activityForThisBubble = isLast && isLoading ? liveActivity : historicalActivity;
  const showActivity = activityForThisBubble && activityForThisBubble.length > 0;

  return (
    <Box sx={{ mb: 3 }}>
      {message.type === 'human' ? (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Paper
            elevation={1}
            sx={{
              p: 2,
              maxWidth: '80%',
              backgroundColor: theme.palette.primary.main,
              color: theme.palette.primary.contrastText,
              borderRadius: 3,
              borderBottomRightRadius: 1,
            }}
          >
            <Typography variant="body1">
              {message.content}
            </Typography>
          </Paper>
        </Box>
      ) : (
        <Box>
          {showActivity && (
            <ActivityTimeline
              processedEvents={activityForThisBubble}
              isLoading={isLast && isLoading}
            />
          )}
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
            <Box sx={{ flex: 1 }}>
              {(() => {
                const { cleanContent, thinkingContent } = processThinkingContent(message.content);
                return (
                  <Box>
                    {/* Main message content without thinking */}
                    {cleanContent && (
                      <Paper
                        variant="outlined"
                        sx={{
                          p: 2,
                          borderRadius: 3,
                          borderBottomLeftRadius: 1,
                          backgroundColor: alpha(theme.palette.background.paper, 0.8),
                          mb: thinkingContent ? 2 : 0
                        }}
                      >
                        <ReactMarkdown
                          components={{
                            h1: ({ children }) => <Typography variant="h5" gutterBottom>{children}</Typography>,
                            h2: ({ children }) => <Typography variant="h6" gutterBottom>{children}</Typography>,
                            h3: ({ children }) => <Typography variant="subtitle1" gutterBottom>{children}</Typography>,
                            p: ({ children }) => <Typography variant="body1" paragraph>{children}</Typography>,
                            a: ({ children, href }) => (
                              <Chip 
                                label={children} 
                                component="a" 
                                href={href} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                clickable 
                                size="small" 
                                sx={{ mx: 0.5 }}
                              />
                            ),
                            ul: ({ children }) => <Box component="ul" sx={{ pl: 2, mb: 2 }}>{children}</Box>,
                            ol: ({ children }) => <Box component="ol" sx={{ pl: 2, mb: 2 }}>{children}</Box>,
                            li: ({ children }) => <Typography component="li" variant="body1">{children}</Typography>,
                            blockquote: ({ children }) => (
                              <Box 
                                sx={{ 
                                  borderLeft: 4, 
                                  borderColor: theme.palette.divider, 
                                  pl: 2, 
                                  py: 1, 
                                  my: 2,
                                  fontStyle: 'italic',
                                  backgroundColor: alpha(theme.palette.action.hover, 0.3)
                                }}
                              >
                                {children}
                              </Box>
                            ),
                            code: ({ children }) => (
                              <Typography 
                                component="code" 
                                sx={{ 
                                  backgroundColor: alpha(theme.palette.action.hover, 0.5),
                                  px: 0.5,
                                  py: 0.25,
                                  borderRadius: 0.5,
                                  fontFamily: 'monospace',
                                  fontSize: '0.875rem'
                                }}
                              >
                                {children}
                              </Typography>
                            ),
                            pre: ({ children }) => (
                              <Paper
                                variant="outlined"
                                sx={{
                                  p: 2,
                                  my: 2,
                                  backgroundColor: alpha(theme.palette.action.hover, 0.1),
                                  overflow: 'auto',
                                  fontFamily: 'monospace',
                                  fontSize: '0.875rem'
                                }}
                              >
                                {children}
                              </Paper>
                            ),
                          }}
                        >
                          {cleanContent}
                        </ReactMarkdown>
                      </Paper>
                    )}
                    
                    {/* Thinking content in collapsible section */}
                    {thinkingContent && (
                      <CollapsibleContent
                        content={thinkingContent}
                        type="thinking"
                        defaultExpanded={false}
                      />
                    )}
                  </Box>
                );
              })()}
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
                <Tooltip title={copied ? "Copied!" : "Copy message"}>
                  <IconButton size="small" onClick={handleCopy}>
                    {copied ? <CheckIcon fontSize="small" /> : <CopyIcon fontSize="small" />}
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>
          </Box>
        </Box>
      )}
    </Box>
  );
};

// Main Research Agent Component
const ResearchAgent: React.FC = () => {
  const navigate = useNavigate();
  const { currentDrawerWidth } = useLayout();
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [effort, setEffort] = useState<'low' | 'medium' | 'high'>('medium');
  const [isLoading, setIsLoading] = useState(false);
  const [liveActivity, setLiveActivity] = useState<ProcessedEvent[]>([]);
  const [historicalActivities, setHistoricalActivities] = useState<Record<string, ProcessedEvent[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [websocket, setWebsocket] = useState<WebSocket | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const {
    recentReviews,
    fetchRecentReviews,
  } = useResearchAgent();

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, liveActivity]);

  // Clean up WebSocket on unmount
  useEffect(() => {
    return () => {
      if (websocket) {
        websocket.close();
      }
    };
  }, [websocket]);

  const connectWebSocket = useCallback((taskId: string) => {
    if (websocket) {
      websocket.close();
    }

    const ws = new WebSocket(`ws://localhost:8000/ws/research-agent/${taskId}`);
    
    ws.onopen = () => {
      console.log('WebSocket connected for task:', taskId);
    };

    ws.onmessage = (event) => {
      try {
        const status = JSON.parse(event.data);
        
        // Process different types of updates from our existing research agent
        if (status.message) {
          // Convert our existing progress messages to ProcessedEvent format
          const eventTitle = status.currentStep || 'Research Progress';
          const eventData = status.message;
          
          const processedEvent: ProcessedEvent = {
            title: eventTitle,
            data: eventData
          };
          
          setLiveActivity(prev => [...prev, processedEvent]);
        }

        if (status.overallStatus === 'completed' && status.result) {
          // Handle completion - add AI response
          const aiMessage: ConversationMessage = {
            id: Date.now().toString(),
            type: 'ai',
            content: status.result.report_text || 'Research completed successfully.'
          };
          
          setMessages(prev => [...prev, aiMessage]);
          
          // Store historical activity for this message
          setHistoricalActivities(prev => ({
            ...prev,
            [aiMessage.id]: [...liveActivity]
          }));
          
          setIsLoading(false);
          setLiveActivity([]);
          setSuccess('Research completed successfully!');
        } else if (status.overallStatus === 'failed') {
          setError(status.error || 'Research failed');
          setIsLoading(false);
          setLiveActivity([]);
        }
      } catch (err) {
        console.error('Error parsing WebSocket message:', err);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setError('Connection error during research');
      setIsLoading(false);
    };

    ws.onclose = () => {
      console.log('WebSocket connection closed');
    };

    setWebsocket(ws);
  }, [websocket, liveActivity]);

  const handleSubmit = async (submittedInputValue: string, selectedEffort: string) => {
    if (!submittedInputValue.trim() || isLoading) return;

    // Clear any previous errors
    setError(null);
    setLiveActivity([]);

    // Add user message
    const userMessage: ConversationMessage = {
      id: Date.now().toString(),
      type: 'human',
      content: submittedInputValue
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      // Convert effort to our API parameters
      let num_papers_target = 5;
      let max_steps = 10;
      
      switch (selectedEffort) {
        case 'low':
          num_papers_target = 3;
          max_steps = 5;
          break;
        case 'medium':
          num_papers_target = 5;
          max_steps = 10;
          break;
        case 'high':
          num_papers_target = 10;
          max_steps = 20;
          break;
      }

      // Convert messages to conversation history
      const conversation_history = messages.map(msg => ({
        role: msg.type === 'human' ? 'user' : 'assistant',
        content: msg.content
      }));

      // Start research via our API
      const response = await fetch('/api/research-agent/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          research_question: submittedInputValue,
          num_papers_target,
          max_steps,
          conversation_history
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to start research');
      }

      const result = await response.json();
      
      // Connect to WebSocket for progress updates
      connectWebSocket(result.task_id);

    } catch (err) {
      console.error('Error starting research:', err);
      setError(err instanceof Error ? err.message : 'Failed to start research');
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    if (websocket) {
      websocket.close();
    }
    setIsLoading(false);
    setLiveActivity([]);
  };

  const handleNewSearch = () => {
    if (websocket) {
      websocket.close();
    }
    setMessages([]);
    setLiveActivity([]);
    setHistoricalActivities({});
    setIsLoading(false);
    setError(null);
    setSuccess(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(inputValue, effort);
    }
  };

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      {/* Fixed Header */}
      <Box 
        sx={{ 
          position: 'fixed',
          top: '84px', // Account for main app header height
          left: `${currentDrawerWidth}px`, // Dynamic sidebar width
          right: 0,
          zIndex: 1100,
          p: 3, 
          borderBottom: 1, 
          borderColor: 'divider',
          backgroundColor: 'background.paper',
          transition: 'left 0.3s', // Smooth transition when sidebar toggles
        }}
      >
        <Typography 
          variant="h4" 
          component="h1" 
          gutterBottom 
          sx={{ display: 'flex', alignItems: 'center', gap: 2 }}
        >
          <ScienceIcon fontSize="large" color="primary" />
          Research Agent
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Powered by LangGraph and local-first search
        </Typography>
      </Box>

      {/* Scrollable Main Content */}
      <Box 
        sx={{ 
          flex: 1, 
          overflow: 'auto',
          pt: '120px', // Add top padding to account for fixed header (84px app header + ~36px component header)
          pb: '200px' // Add padding to ensure content isn't hidden behind fixed input
        }}
      >
        {messages.length === 0 ? (
          // Welcome Screen
          <Box 
            sx={{ 
              height: '100%',
              display: 'flex', 
              flexDirection: 'column', 
              alignItems: 'center', 
              justifyContent: 'center',
              gap: 4,
              p: 4
            }}
          >
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h3" component="h2" gutterBottom color="primary">
                Welcome
              </Typography>
              <Typography variant="h6" color="text.secondary">
                How can I help you today?
              </Typography>
            </Box>
          </Box>
        ) : (
          // Chat Messages
          <Box sx={{ p: 3 }}>
            <Box sx={{ maxWidth: 800, mx: 'auto' }}>
              {messages.map((message, index) => {
                const isLast = index === messages.length - 1;
                return (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    isLast={isLast}
                    isLoading={isLoading}
                    liveActivity={liveActivity}
                    historicalActivity={historicalActivities[message.id]}
                  />
                );
              })}
              
              {/* Live loading indicator for new AI response */}
              {isLoading && (messages.length === 0 || messages[messages.length - 1].type === 'human') && (
                <Box sx={{ mb: 3 }}>
                  {liveActivity.length > 0 ? (
                    <ActivityTimeline processedEvents={liveActivity} isLoading={true} />
                  ) : (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 2 }}>
                      <CircularProgress size={20} />
                      <Typography variant="body2" color="text.secondary">
                        Processing your request...
                      </Typography>
                    </Box>
                  )}
                </Box>
              )}
              
              <div ref={chatEndRef} />
            </Box>
          </Box>
        )}
      </Box>

      {/* Fixed Input Form at Bottom */}
      <Box 
        sx={{ 
          position: 'fixed',
          bottom: 0,
          left: `${currentDrawerWidth}px`, // Dynamic sidebar width
          right: 0,
          p: 3, 
          borderTop: 1, 
          borderColor: 'divider',
          backgroundColor: 'background.paper',
          zIndex: 1000,
          transition: 'left 0.3s', // Smooth transition when sidebar toggles
        }}
      >
        <Box sx={{ maxWidth: 800, mx: 'auto' }}>
          <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
            <TextField
              fullWidth
              multiline
              maxRows={4}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="What research question would you like me to investigate?"
              disabled={isLoading}
              variant="outlined"
              sx={{ mb: 2 }}
            />
            
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Effort</InputLabel>
                  <Select
                    value={effort}
                    label="Effort"
                    onChange={(e) => setEffort(e.target.value as 'low' | 'medium' | 'high')}
                    disabled={isLoading}
                  >
                    <MenuItem value="low">Low</MenuItem>
                    <MenuItem value="medium">Medium</MenuItem>
                    <MenuItem value="high">High</MenuItem>
                  </Select>
                </FormControl>
                
                <Tooltip title="Refresh recent reviews">
                  <IconButton onClick={fetchRecentReviews} disabled={isLoading}>
                    <RefreshIcon />
                  </IconButton>
                </Tooltip>
              </Box>
              
              <Box sx={{ display: 'flex', gap: 1 }}>
                {messages.length > 0 && (
                  <Button
                    variant="outlined"
                    onClick={handleNewSearch}
                    startIcon={<SmartIcon />}
                    disabled={isLoading}
                  >
                    New Search
                  </Button>
                )}
                
                {isLoading ? (
                  <Button
                    variant="contained"
                    color="error"
                    onClick={handleCancel}
                    startIcon={<StopIcon />}
                  >
                    Stop
                  </Button>
                ) : (
                  <Button
                    variant="contained"
                    onClick={() => handleSubmit(inputValue, effort)}
                    disabled={!inputValue.trim()}
                    startIcon={<SendIcon />}
                  >
                    Search
                  </Button>
                )}
              </Box>
            </Box>
          </Paper>

          {/* Research Library Link */}
          {recentReviews.length > 0 && (
            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, mb: 1 }}>
                <ScienceIcon sx={{ fontSize: 20, color: 'primary.main' }} />
                <Typography variant="subtitle1" color="primary">
                  Research Library ({recentReviews.length} studies)
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Browse and search your historical research
              </Typography>
              <Button
                variant="contained"
                size="small"
                startIcon={<ScienceIcon />}
                onClick={() => navigate('/research-library')}
              >
                View Research Library
              </Button>
            </Paper>
          )}
        </Box>
      </Box>

      {/* Snackbars */}
      <Snackbar
        open={Boolean(error)}
        autoHideDuration={6000}
        onClose={() => setError(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert onClose={() => setError(null)} severity="error">
          {error}
        </Alert>
      </Snackbar>

      <Snackbar
        open={Boolean(success)}
        autoHideDuration={4000}
        onClose={() => setSuccess(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert onClose={() => setSuccess(null)} severity="success">
          {success}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ResearchAgent; 