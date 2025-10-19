import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  Chip,
  Alert,
  IconButton,
  Collapse,
  List,
  ListItem,
  Divider,
  Button,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  Delete as DeleteIcon,
  PlayArrow as PlayArrowIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

interface EmbeddingJob {
  job_id: string;
  operation: string;
  parameters: {
    start_date?: string;
    end_date?: string;
    model_name: string;
  };
  progress: {
    total_papers: number;
    processed_papers: number;
    offset: number;
  };
  statistics: {
    papers_embedded: number;
    papers_failed: number;
  };
  last_updated: string;
}

interface EmbeddingProgressProps {
  jobId?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export const EmbeddingProgress: React.FC<EmbeddingProgressProps> = ({
  jobId,
  autoRefresh = true,
  refreshInterval = 2000,
}) => {
  const [expanded, setExpanded] = useState(true);
  const queryClient = useQueryClient();

  // Fetch active embedding jobs
  const { data: jobs, isLoading, error, refetch } = useQuery<EmbeddingJob[]>({
    queryKey: ['embedding-jobs', jobId],
    queryFn: async () => {
      const response = await fetch('/api/embedding-service/jobs');
      if (!response.ok) throw new Error('Failed to fetch embedding jobs');
      return response.json();
    },
    refetchInterval: autoRefresh ? refreshInterval : false,
  });

  // Mutation for resuming a job
  const resumeJob = useMutation({
    mutationFn: async (jobId: string) => {
      const response = await fetch(`/api/embedding-service/jobs/${jobId}/resume`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to resume job');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['embedding-jobs'] });
    },
  });

  // Mutation for deleting a job
  const deleteJob = useMutation({
    mutationFn: async (jobId: string) => {
      const response = await fetch(`/api/embedding-service/jobs/${jobId}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete job');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['embedding-jobs'] });
    },
  });

  const formatDuration = (isoString: string) => {
    const start = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - start.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    
    if (diffHours > 0) return `${diffHours}h ${diffMins % 60}m ago`;
    if (diffMins > 0) return `${diffMins}m ago`;
    return 'Just now';
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent>
          <Typography>Loading embedding jobs...</Typography>
          <LinearProgress />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert severity="error">
        Failed to load embedding jobs: {error.message}
      </Alert>
    );
  }

  if (!jobs || jobs.length === 0) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            🧠 Embedding Operations
          </Typography>
          <Alert severity="info">
            No active embedding jobs
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            🧠 Embedding Operations ({jobs.length} active)
          </Typography>
          <Box>
            <IconButton onClick={() => refetch()} size="small">
              <RefreshIcon />
            </IconButton>
            <IconButton onClick={() => setExpanded(!expanded)} size="small">
              <ExpandMoreIcon
                sx={{
                  transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: '0.3s',
                }}
              />
            </IconButton>
          </Box>
        </Box>

        <Collapse in={expanded}>
          <List>
            {jobs.map((job, index) => {
              const progress = job.progress.total_papers > 0
                ? (job.progress.processed_papers / job.progress.total_papers) * 100
                : 0;
              
              const isHung = new Date().getTime() - new Date(job.last_updated).getTime() > 3600000; // 1 hour

              return (
                <React.Fragment key={job.job_id}>
                  {index > 0 && <Divider />}
                  <ListItem>
                    <Box sx={{ width: '100%' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                        <Typography variant="subtitle1">
                          {job.operation === 'embed_date_range' 
                            ? `Date Range: ${job.parameters.start_date || 'All'} to ${job.parameters.end_date || 'All'}`
                            : 'All Papers'}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          {isHung && (
                            <Chip
                              label="Hung"
                              color="warning"
                              size="small"
                              icon={<ErrorIcon />}
                            />
                          )}
                          {progress >= 100 && (
                            <Chip
                              label="Complete"
                              color="success"
                              size="small"
                              icon={<CheckCircleIcon />}
                            />
                          )}
                        </Box>
                      </Box>

                      <Box sx={{ mb: 1 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                          <Typography variant="body2" color="text.secondary">
                            {job.progress.processed_papers.toLocaleString()} / {job.progress.total_papers.toLocaleString()} papers
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {progress.toFixed(1)}%
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={progress}
                          sx={{ height: 8, borderRadius: 1 }}
                        />
                      </Box>

                      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 1 }}>
                        <Typography variant="caption" color="text.secondary">
                          ✅ Embedded: {job.statistics.papers_embedded.toLocaleString()}
                        </Typography>
                        {job.statistics.papers_failed > 0 && (
                          <Typography variant="caption" color="error">
                            ❌ Failed: {job.statistics.papers_failed.toLocaleString()}
                          </Typography>
                        )}
                        <Typography variant="caption" color="text.secondary">
                          🕐 {formatDuration(job.last_updated)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          🤖 {job.parameters.model_name}
                        </Typography>
                      </Box>

                      <Box sx={{ display: 'flex', gap: 1 }}>
                        {isHung && (
                          <Button
                            size="small"
                            startIcon={<PlayArrowIcon />}
                            onClick={() => resumeJob.mutate(job.job_id)}
                            disabled={resumeJob.isPending}
                          >
                            Resume
                          </Button>
                        )}
                        <Button
                          size="small"
                          color="error"
                          startIcon={<DeleteIcon />}
                          onClick={() => deleteJob.mutate(job.job_id)}
                          disabled={deleteJob.isPending}
                        >
                          Delete
                        </Button>
                      </Box>
                    </Box>
                  </ListItem>
                </React.Fragment>
              );
            })}
          </List>
        </Collapse>
      </CardContent>
    </Card>
  );
};

export default EmbeddingProgress;


