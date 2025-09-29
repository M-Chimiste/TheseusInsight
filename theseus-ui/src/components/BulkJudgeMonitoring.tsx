import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Alert,
  CircularProgress,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  Timeline as TimelineIcon,
  Queue as QueueIcon,
  Memory as MemoryIcon,
  Speed as SpeedIcon,
  Error as ErrorIcon,
  CheckCircle as SuccessIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { bulkOperationsApi } from '../services/api';



interface BulkJudgeMonitoringProps {
  jobId: string;
  onJobComplete?: () => void;
  onJobError?: (error: string) => void;
}

const BulkJudgeMonitoring: React.FC<BulkJudgeMonitoringProps> = ({
  jobId,
  onJobComplete,
  onJobError,
}) => {
  const queryClient = useQueryClient();
  const [isWebSocketConnected, setIsWebSocketConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const websocketRef = useRef<WebSocket | null>(null);

  // Query for job metrics
  const { data: jobMetrics, isLoading, refetch } = useQuery({
    queryKey: ['bulkJudgeMetrics', jobId],
    queryFn: () => bulkOperationsApi.getJobMetrics(jobId).then((res: any) => res.data),
    refetchInterval: isWebSocketConnected ? false : 10000, // 10 seconds if no WebSocket
  });

  // Mutations for job control
  const pauseMutation = useMutation({
    mutationFn: () => bulkOperationsApi.pauseJob(jobId).then((res: any) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bulkJudgeMetrics', jobId] });
    },
  });

  const resumeMutation = useMutation({
    mutationFn: () => bulkOperationsApi.resumeJob(jobId).then((res: any) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bulkJudgeMetrics', jobId] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => bulkOperationsApi.cancelJob(jobId).then((res: any) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bulkJudgeMetrics', jobId] });
      setShowCancelDialog(false);
      onJobComplete?.();
    },
  });

  const retryWorkerMutation = useMutation({
    mutationFn: (worker: any) => 
      bulkOperationsApi.retryWorker(worker.worker_id, worker.server_url, jobId).then((res: any) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bulkJudgeMetrics', jobId] });
    },
  });

  // WebSocket connection for real-time updates
  useEffect(() => {
    const connectWebSocket = () => {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/bulk-judge/${jobId}`;

        const websocket = new WebSocket(wsUrl);
        websocketRef.current = websocket;

        websocket.onopen = () => {
          setIsWebSocketConnected(true);
          console.log('WebSocket connected for bulk judge monitoring');
        };

        websocket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            setLastUpdate(new Date());

            if (message.type === 'bulk_judge_update' && message.data) {
              // Update the query cache with real-time data
              queryClient.setQueryData(['bulkJudgeMetrics', jobId], message.data);

              // Check for job completion
              if (message.data.status === 'completed') {
                onJobComplete?.();
              } else if (message.data.status === 'failed' && message.data.error_message) {
                onJobError?.(message.data.error_message);
              }
            } else if (message.type === 'error') {
              console.error('WebSocket error:', message.message);
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        websocket.onclose = () => {
          setIsWebSocketConnected(false);
          console.log('WebSocket disconnected for bulk judge monitoring');

          // Attempt to reconnect after a delay
          setTimeout(() => {
            if (!websocketRef.current || websocketRef.current.readyState === WebSocket.CLOSED) {
              connectWebSocket();
            }
          }, 5000);
        };

        websocket.onerror = (error) => {
          console.error('WebSocket error:', error);
          setIsWebSocketConnected(false);
        };

      } catch (error) {
        console.error('Failed to connect WebSocket:', error);
        setIsWebSocketConnected(false);
      }
    };

    connectWebSocket();

    return () => {
      if (websocketRef.current) {
        websocketRef.current.close();
      }
    };
  }, [jobId, queryClient, onJobComplete, onJobError]);

  // Format duration
  const formatDuration = (startTime?: string, endTime?: string) => {
    if (!startTime) return 'Not started';

    const start = new Date(startTime);
    const end = endTime ? new Date(endTime) : new Date();

    const durationMs = end.getTime() - start.getTime();
    const hours = Math.floor(durationMs / (1000 * 60 * 60));
    const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((durationMs % (1000 * 60)) / 1000);

    if (hours > 0) {
      return `${hours}h ${minutes}m ${seconds}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    } else {
      return `${seconds}s`;
    }
  };

  // Get status color
  const getStatusColor = (status: string): 'success' | 'warning' | 'info' | 'error' | 'default' => {
    switch (status) {
      case 'running': return 'success';
      case 'pending': return 'warning';
      case 'paused': return 'info';
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'canceled': return 'default';
      default: return 'default';
    }
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return <PlayIcon />;
      case 'pending': return <TimelineIcon />;
      case 'paused': return <PauseIcon />;
      case 'completed': return <SuccessIcon />;
      case 'failed': return <ErrorIcon />;
      case 'canceled': return <StopIcon />;
      default: return <TimelineIcon />;
    }
  };

  // Handle worker retry
  const handleRetryWorker = (worker: any) => {
    retryWorkerMutation.mutate(worker);
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (!jobMetrics) {
    return (
      <Alert severity="error">
        Failed to load job metrics for job {jobId}
      </Alert>
    );
  }

  const canPause = ['running', 'pending'].includes(jobMetrics.status);
  const canResume = jobMetrics.status === 'paused';
  const canCancel = ['running', 'pending', 'paused'].includes(jobMetrics.status);

  return (
    <Box>
      {/* Header with Job Info */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
            <Box display="flex" alignItems="center" gap={2}>
              <Typography variant="h5" fontWeight={600}>
                Bulk Judge Job: {jobId.slice(0, 8)}...
              </Typography>
              <Chip
                icon={getStatusIcon(jobMetrics.status)}
                label={jobMetrics.status.toUpperCase()}
                color={getStatusColor(jobMetrics.status)}
                variant="filled"
              />
              {isWebSocketConnected ? (
                <Chip label="Live" color="success" size="small" />
              ) : (
                <Chip label="Polling" color="warning" size="small" />
              )}
            </Box>

            <Box display="flex" gap={1}>
              {canPause && (
                <Button
                  variant="outlined"
                  startIcon={<PauseIcon />}
                  onClick={() => pauseMutation.mutate()}
                  disabled={pauseMutation.isPending}
                  size="small"
                >
                  Pause
                </Button>
              )}
              {canResume && (
                <Button
                  variant="outlined"
                  startIcon={<PlayIcon />}
                  onClick={() => resumeMutation.mutate()}
                  disabled={resumeMutation.isPending}
                  size="small"
                >
                  Resume
                </Button>
              )}
              {canCancel && (
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={() => setShowCancelDialog(true)}
                  size="small"
                >
                  Cancel
                </Button>
              )}
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={() => refetch()}
                size="small"
              >
                Refresh
              </Button>
            </Box>
          </Box>

          {/* Progress Bar */}
          <Box mb={2}>
            <Box display="flex" justifyContent="space-between" mb={1}>
              <Typography variant="body2">
                Progress: {jobMetrics.progress.current} / {jobMetrics.progress.total}
              </Typography>
              <Typography variant="body2">
                {jobMetrics.progress.percent.toFixed(1)}%
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={jobMetrics.progress.percent}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>

          {/* Job Details */}
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 3 }}>
              <Typography variant="body2" color="textSecondary">
                Duration
              </Typography>
              <Typography variant="body1">
                {formatDuration(jobMetrics.timestamps.started_at, jobMetrics.timestamps.completed_at)}
              </Typography>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <Typography variant="body2" color="textSecondary">
                Started
              </Typography>
              <Typography variant="body1">
                {jobMetrics.timestamps.started_at ?
                  new Date(jobMetrics.timestamps.started_at).toLocaleString() :
                  'Not started'
                }
              </Typography>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <Typography variant="body2" color="textSecondary">
                Last Update
              </Typography>
              <Typography variant="body1">
                {lastUpdate.toLocaleString()}
              </Typography>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <Typography variant="body2" color="textSecondary">
                Estimated Completion
              </Typography>
              <Typography variant="body1">
                {jobMetrics.progress.percent > 0 ?
                  `${Math.ceil((100 - jobMetrics.progress.percent) / jobMetrics.progress.percent)} min` :
                  'Calculating...'
                }
              </Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Queue Metrics */}
      {jobMetrics.queue_metrics && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Card sx={{ height: '100%' }}>
              <CardContent sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <Box display="flex" alignItems="center" gap={1} mb={2}>
                  <QueueIcon color="primary" />
                  <Typography variant="h6">Queue Status</Typography>
                </Box>
                <Box sx={{ flex: 1, display: 'flex', alignItems: 'center' }}>
                  <Grid container spacing={2} sx={{ width: '100%' }}>
                    <Grid size={{ xs: 6 }}>
                      <Box textAlign="center">
                        <Typography variant="h4" color="warning.main">
                          {jobMetrics.queue_metrics.pending_tasks}
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Pending
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Box textAlign="center">
                        <Typography variant="h4" color="info.main">
                          {jobMetrics.queue_metrics.in_progress_tasks}
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          In Progress
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Box textAlign="center">
                        <Typography variant="h4" color="success.main">
                          {jobMetrics.queue_metrics.completed_tasks}
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Completed
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Box textAlign="center">
                        <Typography variant="h4" color="error.main">
                          {jobMetrics.queue_metrics.failed_tasks}
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Failed
                        </Typography>
                      </Box>
                    </Grid>
                  </Grid>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Card sx={{ height: '100%' }}>
              <CardContent sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <Box display="flex" alignItems="center" gap={1} mb={2}>
                  <SpeedIcon color="primary" />
                  <Typography variant="h6">Performance</Typography>
                </Box>
                <Box sx={{ flex: 1, display: 'flex', alignItems: 'center' }}>
                  <Grid container spacing={2} sx={{ width: '100%' }}>
                    <Grid size={{ xs: 6 }}>
                      <Box textAlign="center">
                        <Typography variant="h4">
                          {jobMetrics.worker_metrics ?
                            `${(jobMetrics.worker_metrics.reduce((sum: number, w: any) => sum + w.tasks_processed, 0) /
                              Math.max(1, (Date.now() - new Date(jobMetrics.timestamps.started_at || '').getTime()) / 60000)).toFixed(1)} tasks/min` :
                            '0.0 tasks/min'
                          }
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Throughput
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Box textAlign="center">
                        <Typography variant="h4" color="primary.main">
                          {jobMetrics.worker_metrics ?
                            jobMetrics.worker_metrics.filter((w: any) => w.status === 'active').length :
                            0
                          }
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Active Workers
                        </Typography>
                      </Box>
                    </Grid>
                  </Grid>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Worker Metrics */}
      {jobMetrics.worker_metrics && jobMetrics.worker_metrics.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box display="flex" alignItems="center" gap={1} mb={2}>
              <MemoryIcon color="primary" />
              <Typography variant="h6">Worker Status</Typography>
            </Box>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Worker ID</TableCell>
                    <TableCell>Server</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Tasks Processed</TableCell>
                    <TableCell>Last Heartbeat</TableCell>
                    <TableCell>Failure Info</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {jobMetrics.worker_metrics.map((worker: any) => (
                    <TableRow key={worker.worker_id}>
                      <TableCell>{worker.worker_id}</TableCell>
                      <TableCell>{worker.server_url}</TableCell>
                      <TableCell>
                        <Chip
                          label={worker.status}
                          color={
                            worker.status === 'active' ? 'success' :
                            worker.status === 'failed' ? 'error' :
                            worker.status === 'inactive' ? 'default' : 'warning'
                          }
                          size="small"
                        />
                      </TableCell>
                      <TableCell>{worker.tasks_processed}</TableCell>
                      <TableCell>
                        {worker.last_heartbeat ?
                          new Date(worker.last_heartbeat).toLocaleTimeString() :
                          'Never'
                        }
                      </TableCell>
                      <TableCell>
                        {worker.status === 'failed' ? (
                          <Box>
                            <Typography variant="body2" color="error" sx={{ fontWeight: 'bold' }}>
                              {worker.failure_reason || 'Unknown error'}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Failures: {worker.failure_count || 0}
                              {worker.last_failure_at && (
                                <> • Last: {new Date(worker.last_failure_at).toLocaleTimeString()}</>
                              )}
                            </Typography>
                          </Box>
                        ) : (
                          <Typography variant="body2" color="text.secondary">-</Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        {worker.status === 'failed' && (
                          <Button
                            size="small"
                            variant="outlined"
                            color="primary"
                            onClick={() => handleRetryWorker(worker)}
                            startIcon={<PlayIcon />}
                          >
                            Retry
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* Error Display */}
      {jobMetrics.error_message && (
        <Alert severity="error" sx={{ mb: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            Job Error
          </Typography>
          {jobMetrics.error_message}
        </Alert>
      )}

      {/* Cancel Confirmation Dialog */}
      <Dialog open={showCancelDialog} onClose={() => setShowCancelDialog(false)}>
        <DialogTitle>Cancel Bulk Judge Job</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to cancel this bulk judge job? This action cannot be undone.
            Any in-progress tasks will be completed, but remaining tasks will be canceled.
          </Typography>
          {jobMetrics.queue_metrics && (
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              Current progress: {jobMetrics.queue_metrics.completed_tasks} of {jobMetrics.queue_metrics.total_tasks} tasks completed.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowCancelDialog(false)}>Keep Running</Button>
          <Button
            onClick={() => cancelMutation.mutate()}
            color="error"
            variant="contained"
            disabled={cancelMutation.isPending}
          >
            {cancelMutation.isPending ? <CircularProgress size={20} /> : 'Cancel Job'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default BulkJudgeMonitoring;
