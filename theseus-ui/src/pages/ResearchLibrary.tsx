import React, { useState } from 'react';
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
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Pagination,
  Paper,
  List,
  ListItem,
  ListItemText,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
} from '@mui/material';
import { Grid } from '@mui/material';
import {
  Search as SearchIcon,
  Visibility as VisibilityIcon,
  Download as DownloadIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  ContentCopy as ContentCopyIcon,
  FilterList as FilterListIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  researchAgentApi,
  type ResearchHistoryItem,
  type ResearchTaskResult 
} from '../services/api';

const ResearchLibrary: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedTask, setSelectedTask] = useState<ResearchTaskResult | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const itemsPerPage = 12;

  // Fetch research history
  const { 
    data: historyData, 
    isLoading, 
    isError,
    refetch 
  } = useQuery({
    queryKey: ['researchHistory', currentPage, statusFilter, searchQuery],
    queryFn: () => researchAgentApi.getHistory(
      itemsPerPage, 
      (currentPage - 1) * itemsPerPage, 
      statusFilter || undefined
    ),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Fetch task details
  const fetchTaskDetailsMutation = useMutation({
    mutationFn: (taskId: string) => researchAgentApi.getTaskResult(taskId),
    onSuccess: (response) => {
      setSelectedTask(response.data);
      setDetailDialogOpen(true);
    },
    onError: (error: any) => {
      setError(error.response?.data?.detail || 'Failed to fetch task details');
    },
  });

  // Delete task
  const deleteTaskMutation = useMutation({
    mutationFn: (taskId: string) => researchAgentApi.cancelTask(taskId),
    onSuccess: () => {
      setSuccess('Research task deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['researchHistory'] });
    },
    onError: (error: any) => {
      setError(error.response?.data?.detail || 'Failed to delete task');
    },
  });

  const handleSearch = () => {
    setCurrentPage(1);
    refetch();
  };

  const handleViewDetails = (taskId: string) => {
    fetchTaskDetailsMutation.mutate(taskId);
  };

  const handleDelete = (taskId: string) => {
    if (window.confirm('Are you sure you want to delete this research task?')) {
      deleteTaskMutation.mutate(taskId);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setSuccess('Copied to clipboard');
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      case 'running':
        return 'warning';
      case 'cancelled':
        return 'default';
      default:
        return 'default';
    }
  };

  const formatDuration = (startTime: string, endTime?: string) => {
    if (!endTime) return 'In progress';
    
    const start = new Date(startTime);
    const end = new Date(endTime);
    const durationMs = end.getTime() - start.getTime();
    const minutes = Math.floor(durationMs / 60000);
    const seconds = Math.floor((durationMs % 60000) / 1000);
    
    if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    }
    return `${seconds}s`;
  };

  const filteredHistory = historyData?.data?.items || [];
  const totalPages = Math.ceil((historyData?.data?.total || 0) / itemsPerPage);

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
        <CircularProgress />
      </Box>
    );
  }

  if (isError) {
    return (
      <Container maxWidth="lg" sx={{ py: 3 }}>
        <Alert severity="error">
          Failed to load research history. Please try again.
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Research Library
        </Typography>
        <Button
          startIcon={<RefreshIcon />}
          onClick={() => refetch()}
          variant="outlined"
        >
          Refresh
        </Button>
      </Box>

      {/* Alerts */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      {/* Search and Filter Controls */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              placeholder="Search research questions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              InputProps={{
                endAdornment: (
                  <IconButton onClick={handleSearch}>
                    <SearchIcon />
                  </IconButton>
                ),
              }}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <FormControl fullWidth>
              <InputLabel>Status Filter</InputLabel>
              <Select
                value={statusFilter}
                label="Status Filter"
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="completed">Completed</MenuItem>
                <MenuItem value="running">Running</MenuItem>
                <MenuItem value="failed">Failed</MenuItem>
                <MenuItem value="cancelled">Cancelled</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <Button
              fullWidth
              variant="contained"
              startIcon={<FilterListIcon />}
              onClick={handleSearch}
            >
              Apply Filters
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Research History Grid */}
      {filteredHistory.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No research tasks found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {searchQuery || statusFilter 
              ? 'Try adjusting your search criteria or filters.'
              : 'Start your first research task to see it here.'
            }
          </Typography>
        </Box>
      ) : (
        <>
          <Grid container spacing={3}>
            {filteredHistory.map((item: ResearchHistoryItem) => (
              <Grid size={{ xs: 12, md: 6, lg: 4 }} key={item.task_id}>
                <Card 
                  sx={{ 
                    height: '100%', 
                    display: 'flex', 
                    flexDirection: 'column',
                    '&:hover': { boxShadow: 4 }
                  }}
                >
                  <CardContent sx={{ flex: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                      <Chip
                        label={item.status}
                        color={getStatusColor(item.status) as any}
                        size="small"
                      />
                      <Typography variant="caption" color="text.secondary">
                        {new Date(item.created_at).toLocaleDateString()}
                      </Typography>
                    </Box>

                    <Typography 
                      variant="h6" 
                      gutterBottom 
                      sx={{ 
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        minHeight: '3em',
                      }}
                    >
                      {item.research_question}
                    </Typography>

                    {item.statistics && (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 2 }}>
                        <Chip
                          label={`${item.statistics.research_loops} loops`}
                          size="small"
                          variant="outlined"
                        />
                        <Chip
                          label={`${item.statistics.total_sources_found} sources`}
                          size="small"
                          variant="outlined"
                        />
                        <Chip
                          label={`${item.statistics.evidence_pieces} evidence`}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                    )}

                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      Duration: {formatDuration(item.created_at, item.completed_at)}
                    </Typography>
                  </CardContent>

                  <Box sx={{ p: 2, pt: 0 }}>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Button
                        size="small"
                        startIcon={<VisibilityIcon />}
                        onClick={() => handleViewDetails(item.task_id)}
                        disabled={fetchTaskDetailsMutation.isPending}
                      >
                        View
                      </Button>
                      <IconButton
                        size="small"
                        onClick={() => handleDelete(item.task_id)}
                        disabled={deleteTaskMutation.isPending}
                        color="error"
                      >
                        <DeleteIcon />
                      </IconButton>
                    </Box>
                  </Box>
                </Card>
              </Grid>
            ))}
          </Grid>

          {/* Pagination */}
          {totalPages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
              <Pagination
                count={totalPages}
                page={currentPage}
                onChange={(_, page) => setCurrentPage(page)}
                color="primary"
              />
            </Box>
          )}
        </>
      )}

      {/* Task Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => setDetailDialogOpen(false)}
        maxWidth="lg"
        fullWidth
        PaperProps={{ sx: { maxHeight: '90vh' } }}
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography variant="h6">Research Details</Typography>
            <Box>
              {selectedTask && (
                <>
                  <Tooltip title="Copy to clipboard">
                    <IconButton
                      onClick={() => copyToClipboard(selectedTask.final_answer || '')}
                    >
                      <ContentCopyIcon />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Download report">
                    <IconButton
                      onClick={() => downloadResult(selectedTask)}
                    >
                      <DownloadIcon />
                    </IconButton>
                  </Tooltip>
                </>
              )}
            </Box>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {selectedTask && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Research Question
              </Typography>
              <Typography variant="body1" sx={{ mb: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                {selectedTask.research_question}
              </Typography>

              <Typography variant="h6" gutterBottom>
                Final Answer
              </Typography>
              <Typography 
                variant="body1" 
                sx={{ mb: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}
              >
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
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{selectedTask.final_answer || 'No answer generated'}</ReactMarkdown>
                </Box>
              </Typography>

              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6">Research Statistics</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 6, md: 3 }}>
                      <Typography variant="body2" color="text.secondary">Research Loops</Typography>
                      <Typography variant="h6">{selectedTask.statistics?.research_loops || 0}</Typography>
                    </Grid>
                    <Grid size={{ xs: 6, md: 3 }}>
                      <Typography variant="body2" color="text.secondary">Total Sources</Typography>
                      <Typography variant="h6">{selectedTask.statistics?.total_sources_found || 0}</Typography>
                    </Grid>
                    <Grid size={{ xs: 6, md: 3 }}>
                      <Typography variant="body2" color="text.secondary">Selected Sources</Typography>
                      <Typography variant="h6">{selectedTask.statistics?.selected_sources || 0}</Typography>
                    </Grid>
                    <Grid size={{ xs: 6, md: 3 }}>
                      <Typography variant="body2" color="text.secondary">Evidence Pieces</Typography>
                      <Typography variant="h6">{selectedTask.statistics?.evidence_pieces || 0}</Typography>
                    </Grid>
                  </Grid>
                  <Box sx={{ mt: 2 }}>
                    <Chip
                      label={selectedTask.statistics?.evidence_sufficient ? 'Evidence Sufficient' : 'Evidence Insufficient'}
                      color={selectedTask.statistics?.evidence_sufficient ? 'success' : 'warning'}
                      sx={{ mr: 1 }}
                    />
                    {selectedTask.statistics?.compression_used && (
                      <Chip
                        label="Compression Used"
                        color="info"
                      />
                    )}
                  </Box>
                </AccordionDetails>
              </Accordion>

              {selectedTask.sub_queries.length > 0 && (
                <Accordion>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="h6">Sub-Queries ({selectedTask.sub_queries.length})</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <List>
                      {selectedTask.sub_queries.map((query, index) => (
                        <ListItem key={index} divider>
                          <ListItemText
                            primary={`${index + 1}. ${query}`}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </AccordionDetails>
                </Accordion>
              )}

              {selectedTask.evidence.length > 0 && (
                <Accordion>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="h6">Evidence ({selectedTask.evidence.length})</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    {selectedTask.evidence.map((evidence, index) => (
                      <Box key={index} sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" gutterBottom>
                          Evidence {index + 1}
                        </Typography>
                        <Typography 
                          variant="body2" 
                          sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 1 }}
                        >
                          <Box sx={{ 
                            '& p': { margin: '4px 0', lineHeight: 1.5 },
                            '& code': { 
                              backgroundColor: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)',
                              padding: '2px 4px', borderRadius: '4px', fontFamily: 'monospace', fontSize: '0.9em' 
                            },
                            '& ul, & ol': { margin: '4px 0', paddingLeft: '20px' },
                            '& li': { margin: '2px 0' }
                          }}>
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{evidence}</ReactMarkdown>
                          </Box>
                        </Typography>
                        {index < selectedTask.evidence.length - 1 && <Divider sx={{ mt: 2 }} />}
                      </Box>
                    ))}
                  </AccordionDetails>
                </Accordion>
              )}

              {selectedTask.compressed_notes && (
                <Accordion>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="h6">Compressed Notes</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Typography 
                      variant="body2" 
                      sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 1 }}
                    >
                      <Box sx={{ 
                        '& p': { margin: '4px 0', lineHeight: 1.5 },
                        '& code': { 
                          backgroundColor: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)',
                          padding: '2px 4px', borderRadius: '4px', fontFamily: 'monospace', fontSize: '0.9em' 
                        },
                        '& ul, & ol': { margin: '4px 0', paddingLeft: '20px' },
                        '& li': { margin: '2px 0' }
                      }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{selectedTask.compressed_notes}</ReactMarkdown>
                      </Box>
                    </Typography>
                  </AccordionDetails>
                </Accordion>
              )}

              <Box sx={{ mt: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  <strong>Task ID:</strong> {selectedTask.task_id}<br />
                  <strong>Created:</strong> {new Date(selectedTask.created_at).toLocaleString()}<br />
                  {selectedTask.completed_at && (
                    <>
                      <strong>Completed:</strong> {new Date(selectedTask.completed_at).toLocaleString()}<br />
                      <strong>Duration:</strong> {formatDuration(selectedTask.created_at, selectedTask.completed_at)}
                    </>
                  )}
                </Typography>
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default ResearchLibrary; 