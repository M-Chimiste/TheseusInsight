import React, { useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Grid,
  Paper,
  LinearProgress,
  Chip,
  Alert,
  IconButton,
  Tooltip,
  Fade,
  CircularProgress,
} from '@mui/material';
import {
  Science as ScienceIcon,
  History as HistoryIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  Description as ReportIcon,
} from '@mui/icons-material';
import { useResearchAgent, type LiteratureReviewResult } from '../hooks/useResearchAgent';
import ReportViewer from '../components/ReportViewer';

const ResearchAgent: React.FC = () => {
  const [researchQuestion, setResearchQuestion] = useState('');
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [selectedReview, setSelectedReview] = useState<LiteratureReviewResult | null>(null);
  
  const {
    isRunning,
    currentTask,
    progress,
    currentStep,
    message,
    logs,
    result,
    recentReviews,
    error,
    loading,
    startResearch,
    stopResearch,
    fetchRecentReviews,
    clearError,
  } = useResearchAgent();

  const handleStartResearch = async () => {
    if (!researchQuestion.trim()) return;
    await startResearch(researchQuestion);
  };

  const handleStopResearch = () => {
    stopResearch();
  };

  const handleViewResult = (review: LiteratureReviewResult) => {
    setSelectedReview(review);
    setReportModalOpen(true);
  };

  const handleCloseReportModal = () => {
    setReportModalOpen(false);
    setSelectedReview(null);
  };

  const handleViewFullReport = () => {
    if (result) {
      handleViewResult(result);
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom component="div" sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
        <ScienceIcon fontSize="large" color="primary" />
        Research Agent
      </Typography>

      <Grid container spacing={3}>
        {/* Input Section */}
        <Grid size={{ xs: 12 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Start Literature Review
              </Typography>
              <Box sx={{ mb: 2 }}>
                <TextField
                  fullWidth
                  multiline
                  rows={3}
                  label="Research Question"
                  placeholder="Enter your research question here... (e.g., 'What are the latest advances in transformer architectures for natural language processing?')"
                  value={researchQuestion}
                  onChange={(e) => setResearchQuestion(e.target.value)}
                  disabled={isRunning}
                />
              </Box>
              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                <Button
                  variant="contained"
                  startIcon={loading ? <CircularProgress size={20} color="inherit" /> : (isRunning ? <StopIcon /> : <PlayIcon />)}
                  onClick={isRunning ? handleStopResearch : handleStartResearch}
                  disabled={(!researchQuestion.trim() && !isRunning) || loading}
                  color={isRunning ? "error" : "primary"}
                >
                  {loading ? 'Starting...' : (isRunning ? 'Stop Research' : 'Start Research')}
                </Button>
                <Tooltip title="Refresh recent reviews">
                  <IconButton onClick={fetchRecentReviews} disabled={loading}>
                    <RefreshIcon />
                  </IconButton>
                </Tooltip>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Progress Section */}
        {isRunning && (
          <Grid size={{ xs: 12 }}>
            <Fade in={true}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Research Progress
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    <LinearProgress 
                      variant="determinate" 
                      value={progress} 
                      sx={{ height: 8, borderRadius: 4 }}
                    />
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                      {progress}% Complete
                    </Typography>
                  </Box>
                  {currentStep && (
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      Current Step: {currentStep}
                    </Typography>
                  )}
                  {message && (
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {message}
                    </Typography>
                  )}
                  {currentTask && (
                    <Chip label={`Task ID: ${currentTask}`} size="small" variant="outlined" />
                  )}
                </CardContent>
              </Card>
            </Fade>
          </Grid>
        )}

        {/* Live Logs Section */}
        {(isRunning || logs.length > 0) && (
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Live Logs
                </Typography>
                <Paper 
                  sx={{ 
                    p: 2, 
                    height: 300, 
                    overflow: 'auto', 
                    backgroundColor: (theme) => theme.palette.mode === 'dark' ? 'grey.800' : 'grey.100',
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                    border: (theme) => `1px solid ${theme.palette.divider}`
                  }}
                >
                  {logs.map((log, index) => (
                    <Typography 
                      key={index} 
                      variant="body2" 
                      sx={{ mb: 0.5, color: 'text.primary' }}
                    >
                      {log}
                    </Typography>
                  ))}
                  {logs.length === 0 && !isRunning && (
                    <Typography variant="body2" color="text.secondary">
                      No logs yet...
                    </Typography>
                  )}
                  {logs.length === 0 && isRunning && (
                    <Typography variant="body2" color="text.secondary">
                      Waiting for logs...
                    </Typography>
                  )}
                </Paper>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Results Section */}
        {result && (
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Latest Results
                </Typography>
                <Typography variant="subtitle1" gutterBottom>
                  {result.research_question}
                </Typography>
                <Box sx={{ mb: 2 }}>
                  <Chip 
                    label={`${result.total_papers} papers found`} 
                    color="primary" 
                    size="small" 
                  />
                  <Chip 
                    label={formatTimestamp(result.created_ts)} 
                    size="small" 
                    sx={{ ml: 1 }}
                  />
                </Box>
                {result.summaries.slice(0, 3).map((summary) => (
                  <Box key={summary.paper_id} sx={{ mb: 2, p: 1, backgroundColor: 'grey.50', borderRadius: 1 }}>
                    <Typography variant="subtitle2">
                      {summary.title} (Score: {summary.relevance_score.toFixed(2)})
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.875rem' }}>
                      {summary.summary.substring(0, 150)}...
                    </Typography>
                  </Box>
                ))}
                {result.report_text && (
                  <Button
                    variant="outlined"
                    startIcon={<ReportIcon />}
                    size="small"
                    onClick={handleViewFullReport}
                  >
                    View Full Report
                  </Button>
                )}
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Error Section */}
        {error && (
          <Grid size={{ xs: 12 }}>
            <Alert severity="error" onClose={() => clearError()}>
              {error}
            </Alert>
          </Grid>
        )}

        {/* Recent Reviews Section */}
        <Grid size={{ xs: 12 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <HistoryIcon />
                Recent Literature Reviews
              </Typography>
              {recentReviews.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No literature reviews yet. Start your first research above!
                </Typography>
              ) : (
                <Grid container spacing={2}>
                  {recentReviews.map((review) => (
                     <Grid size={{ xs: 12, md: 6, lg: 4 }} key={review.id}>
                       <Card variant="outlined" sx={{ cursor: 'pointer' }} onClick={() => handleViewResult(review)}>
                         <CardContent>
                           <Typography variant="subtitle1" noWrap>
                             {review.research_question}
                           </Typography>
                           <Box sx={{ mt: 1, mb: 1 }}>
                             <Chip 
                               label={`${review.total_papers} papers`} 
                               size="small" 
                               variant="outlined"
                             />
                           </Box>
                           <Typography variant="caption" color="text.secondary">
                             {formatTimestamp(review.created_ts)}
                           </Typography>
                         </CardContent>
                       </Card>
                     </Grid>
                   ))}
                </Grid>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <ReportViewer
        open={reportModalOpen}
        onClose={handleCloseReportModal}
        review={selectedReview}
      />
    </Box>
  );
};

export default ResearchAgent; 