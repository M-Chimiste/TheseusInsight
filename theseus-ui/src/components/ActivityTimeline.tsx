import { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Collapse,
  IconButton,
  List,
  ListItem,
  CircularProgress,
  Chip,
  useTheme,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Psychology as BrainIcon,
  Search as SearchIcon,
  Assessment as AssessmentIcon,
  Compress as CompressIcon,
  Article as ArticleIcon,
  AutoAwesome as AutoAwesomeIcon,
  PictureAsPdf as PdfIcon,
} from '@mui/icons-material';

export interface ProcessedEvent {
  title: string;
  data: any;
  timestamp?: string;
  node?: string;
}

interface ActivityTimelineProps {
  processedEvents: ProcessedEvent[];
  isLoading: boolean;
  currentProgress?: {
    current_node?: string;
    status?: string;
    description?: string;
    [key: string]: any;
  };
}

export function ActivityTimeline({
  processedEvents,
  isLoading,
  currentProgress,
}: ActivityTimelineProps) {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const theme = useTheme();

  const getEventIcon = (title: string, node?: string) => {
    // Use theme-aware colors for better contrast in both light and dark modes
    const iconProps = { 
      fontSize: 'small' as const, 
      sx: { 
        color: theme.palette.mode === 'dark' ? 'primary.light' : 'primary.main',
        opacity: 0.9
      }
    };
    
    if (node === 'query_planner' || title.toLowerCase().includes('planning')) {
      return <BrainIcon {...iconProps} />;
    } else if (node === 'retriever_unified' || title.toLowerCase().includes('searching')) {
      return <SearchIcon {...iconProps} />;
    } else if (node === 'evidence_selector' || title.toLowerCase().includes('evaluating')) {
      return <AssessmentIcon {...iconProps} />;
    } else if (node === 'scratchpad_compress' || title.toLowerCase().includes('compressing')) {
      return <CompressIcon {...iconProps} />;
    } else if (node === 'full_text_processor' || title.toLowerCase().includes('pdf') || title.toLowerCase().includes('processing')) {
      return <PdfIcon {...iconProps} />;
    } else if (node === 'answer_generator' || title.toLowerCase().includes('generating')) {
      return <ArticleIcon {...iconProps} />;
    } else if (isLoading && processedEvents.length === 0) {
      return <CircularProgress size={16} sx={{ color: 'primary.main' }} />;
    }
    return <AutoAwesomeIcon {...iconProps} />;
  };

  const getNodeDisplayName = (node?: string) => {
    switch (node) {
      case 'query_planner':
        return 'Query Planning';
      case 'retriever_unified':
        return 'Source Retrieval';
      case 'evidence_selector':
        return 'Evidence Selection';
      case 'scratchpad_compress':
        return 'Evidence Compression';
      case 'full_text_processor':
        return 'PDF Processing';
      case 'answer_generator':
        return 'Answer Generation';
      default:
        return 'Processing';
    }
  };

  useEffect(() => {
    if (isLoading && processedEvents.length === 0) {
      setIsExpanded(true);
    }
  }, [isLoading, processedEvents]);

  // Theme-aware background colors for better contrast
  const getIconBackground = () => {
    return theme.palette.mode === 'dark' 
      ? 'rgba(255, 255, 255, 0.08)' 
      : theme.palette.grey[100];
  };

  const getTimelineColor = () => {
    return theme.palette.mode === 'dark'
      ? 'rgba(255, 255, 255, 0.12)'
      : theme.palette.grey[200];
  };

  const getCurrentActivityBackground = () => {
    return theme.palette.mode === 'dark'
      ? 'rgba(33, 150, 243, 0.12)'  // primary with low opacity for dark mode
      : theme.palette.primary.light;
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardHeader
        title={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="subtitle1">Research Progress</Typography>
            {currentProgress?.current_node && (
              <Chip
                label={getNodeDisplayName(currentProgress.current_node)}
                size="small"
                color="primary"
                variant="outlined"
              />
            )}
          </Box>
        }
        action={
          <IconButton
            onClick={() => setIsExpanded(!isExpanded)}
            size="small"
          >
            {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
        }
        sx={{ pb: 1 }}
      />
      
      <Collapse in={isExpanded}>
        <CardContent sx={{ pt: 0, maxHeight: 300, overflow: 'auto' }}>
          {isLoading && processedEvents.length === 0 ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 2 }}>
              <CircularProgress size={20} sx={{ color: 'primary.main' }} />
              <Typography variant="body2" color="text.secondary">
                {currentProgress?.description || 'Starting research...'}
              </Typography>
            </Box>
          ) : (
            <List dense sx={{ py: 0 }}>
              {processedEvents.map((event, index) => (
                <ListItem key={index} sx={{ py: 1, px: 0, position: 'relative' }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, width: '100%' }}>
                    <Box sx={{ 
                      minWidth: 32, 
                      height: 32, 
                      borderRadius: '50%', 
                      bgcolor: getIconBackground(),
                      border: theme.palette.mode === 'dark' ? '1px solid rgba(255, 255, 255, 0.12)' : 'none',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      mt: 0.5
                    }}>
                      {getEventIcon(event.title, event.node)}
                    </Box>
                    
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography variant="body2" fontWeight="medium" gutterBottom>
                        {event.title}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        {typeof event.data === "string"
                          ? event.data
                          : Array.isArray(event.data)
                          ? event.data.join(", ")
                          : JSON.stringify(event.data)}
                      </Typography>
                      {event.timestamp && (
                        <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 0.5 }}>
                          {new Date(event.timestamp).toLocaleTimeString()}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                  
                  {/* Connection line to next item */}
                  {index < processedEvents.length - 1 && (
                    <Box
                      sx={{
                        position: 'absolute',
                        left: 15,
                        top: 40,
                        bottom: -8,
                        width: 2,
                        bgcolor: getTimelineColor()
                      }}
                    />
                  )}
                </ListItem>
              ))}
              
              {/* Show current activity if still loading */}
              {isLoading && processedEvents.length > 0 && currentProgress && (
                <ListItem sx={{ py: 1, px: 0, position: 'relative' }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, width: '100%' }}>
                    <Box sx={{ 
                      minWidth: 32, 
                      height: 32, 
                      borderRadius: '50%', 
                      bgcolor: getCurrentActivityBackground(),
                      border: theme.palette.mode === 'dark' ? '1px solid rgba(33, 150, 243, 0.3)' : 'none',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      mt: 0.5
                    }}>
                      <CircularProgress size={16} sx={{ color: 'primary.main' }} />
                    </Box>
                    
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <Typography variant="body2" fontWeight="medium">
                          {currentProgress.status || 'Processing...'}
                        </Typography>
                        {/* Show document progress indicator (e.g., "3/20") */}
                        {currentProgress.document_progress && (
                          <Chip
                            label={currentProgress.document_progress}
                            size="small"
                            color="primary"
                            sx={{ height: 20, fontSize: '0.75rem' }}
                          />
                        )}
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {currentProgress.description || 'Working on your research...'}
                      </Typography>
                    </Box>
                  </Box>
                </ListItem>
              )}
            </List>
          )}
          
          {!isLoading && processedEvents.length === 0 && (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Typography variant="body2" color="text.secondary">
                No activity to display.
              </Typography>
              <Typography variant="caption" color="text.disabled">
                Timeline will update during processing.
              </Typography>
            </Box>
          )}
        </CardContent>
      </Collapse>
    </Card>
  );
} 