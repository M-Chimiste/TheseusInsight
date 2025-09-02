import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  CardHeader,
  Button,
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
  Tabs,
  Tab,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,

  IconButton,
  Tooltip,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Timeline as TimelineIcon,
  Refresh as RefreshIcon,
  Queue as QueueIcon,
  Memory as MemoryIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  History as HistoryIcon,
  Clear as ClearIcon,
  FilterList as FilterIcon,
  DeleteSweep as ClearQueueIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { bulkOperationsApi, type ActiveJob } from '../services/api';
import BulkJudgeMonitoring from '../components/BulkJudgeMonitoring';



const JobMonitoring: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();

  const [selectedTab, setSelectedTab] = useState(0);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobToCancel, setJobToCancel] = useState<ActiveJob | null>(null);

  // Job history state
  const [jobHistoryLimit, setJobHistoryLimit] = useState(50);
  const [jobTypeFilter, setJobTypeFilter] = useState<string>('');

  // Queue management state
  const [clearQueueDialog, setClearQueueDialog] = useState(false);
  const [clearJobId, setClearJobId] = useState<string>('');
  const [clearStatusFilter, setClearStatusFilter] = useState<string>('');

  // Get job ID from URL params
  useEffect(() => {
    const jobId = searchParams.get('jobId');
    if (jobId) {
      setSelectedJobId(jobId);
      setSelectedTab(3); // Switch to monitoring tab (now tab 3)
    }
  }, [searchParams]);

  // Query for active jobs
  const { data: activeJobsData, isLoading: jobsLoading, refetch: refetchJobs } = useQuery({
    queryKey: ['activeJobs'],
    queryFn: () => bulkOperationsApi.getActiveJobs().then((res: any) => res.data),
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  // Query for server metrics
  const { data: serverMetrics, isLoading: serverLoading } = useQuery({
    queryKey: ['serverMetrics'],
    queryFn: () => bulkOperationsApi.getServerMetrics().then((res: any) => res.data),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Query for queue status
  const { data: queueStatus, isLoading: queueLoading } = useQuery({
    queryKey: ['queueStatus'],
    queryFn: () => bulkOperationsApi.getQueueStatus().then((res: any) => res.data),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Query for job history
  const { data: jobHistoryData, isLoading: historyLoading, refetch: refetchHistory } = useQuery({
    queryKey: ['jobHistory', jobHistoryLimit, jobTypeFilter],
    queryFn: () => bulkOperationsApi.getJobHistory({
      limit: jobHistoryLimit,
      job_type: jobTypeFilter || undefined
    }).then((res: any) => res.data),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Mutations for job control
  const pauseMutation = useMutation({
    mutationFn: (jobId: string) => bulkOperationsApi.pauseJob(jobId).then((res: any) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activeJobs'] });
    },
  });

  const resumeMutation = useMutation({
    mutationFn: (jobId: string) => bulkOperationsApi.resumeJob(jobId).then((res: any) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activeJobs'] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => bulkOperationsApi.cancelJob(jobId).then((res: any) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activeJobs'] });
      setJobToCancel(null);
    },
  });

  // Mutation for clearing queue
  const clearQueueMutation = useMutation({
    mutationFn: (params: { job_id?: string; status_filter?: string }) =>
      bulkOperationsApi.clearQueue(params).then((res: any) => res.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['queueStatus'] });
      queryClient.invalidateQueries({ queryKey: ['activeJobs'] });
      setClearQueueDialog(false);
      setClearJobId('');
      setClearStatusFilter('');
      // Could show success notification here
      console.log('Queue cleared successfully:', data);
    },
    onError: (error) => {
      console.error('Failed to clear queue:', error);
      // Could show error notification here
    },
  });

  // Handlers
  const handleJobSelect = (job: ActiveJob) => {
    setSelectedJobId(job.job_id);
    setSelectedTab(1);
    setSearchParams({ jobId: job.job_id });
  };

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setSelectedTab(newValue);
    if (newValue === 0) {
      setSelectedJobId(null);
      setSearchParams({});
    }
  };

  const handleClearQueue = () => {
    const params: { job_id?: string; status_filter?: string } = {};
    if (clearJobId) params.job_id = clearJobId;
    if (clearStatusFilter) params.status_filter = clearStatusFilter;
    clearQueueMutation.mutate(params);
  };

  const handleJobHistoryFilter = () => {
    refetchHistory();
  };

  const handleJobComplete = () => {
    refetchJobs();
    // Could show a success notification here
  };

  const handleJobError = (error: string) => {
    console.error('Job error:', error);
    // Could show an error notification here
  };

  // Format duration
  const formatDuration = (startTime?: string) => {
    if (!startTime) return 'Not started';

    const start = new Date(startTime);
    const now = new Date();

    const durationMs = now.getTime() - start.getTime();
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
      case 'running': return <PlayIcon fontSize="small" />;
      case 'pending': return <TimelineIcon fontSize="small" />;
      case 'paused': return <PauseIcon fontSize="small" />;
      case 'completed': return <SuccessIcon fontSize="small" />;
      case 'failed': return <ErrorIcon fontSize="small" />;
      case 'canceled': return <StopIcon fontSize="small" />;
      default: return <TimelineIcon fontSize="small" />;
    }
  };

  const activeJobs = activeJobsData?.active_jobs || [];
  const bulkJudgeJobs = activeJobs.filter((job: ActiveJob) => job.job_type === 'bulk_judge');

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Typography variant="h4" fontWeight={600} gutterBottom>
        Job Monitoring Dashboard
      </Typography>
      <Typography variant="body1" color="text.secondary" gutterBottom>
        Monitor active jobs, view job history, and manage the processing queue.
      </Typography>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={selectedTab} onChange={handleTabChange} aria-label="Job monitoring tabs">
          <Tab icon={<TimelineIcon />} label="Active Jobs" />
          <Tab icon={<HistoryIcon />} label="Job History" />
          <Tab icon={<QueueIcon />} label="Queue Management" />
          <Tab
            icon={<TimelineIcon />}
            label={selectedJobId ? `Monitor Job ${selectedJobId.slice(0, 8)}...` : "Monitor Job"}
            disabled={!selectedJobId}
          />
        </Tabs>
      </Box>

      {/* Active Jobs Tab */}
      {selectedTab === 0 && (
        <Grid container spacing={3}>
          {/* Summary Cards */}
          <Grid size={{ xs: 12, md: 3 }}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4" color="success.main" fontWeight={600}>
                    {bulkJudgeJobs.filter((job: ActiveJob) => job.status === 'running').length}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Running Jobs
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4" color="warning.main" fontWeight={600}>
                    {bulkJudgeJobs.filter((job: ActiveJob) => job.status === 'pending').length}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Pending Jobs
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4" color="info.main" fontWeight={600}>
                    {bulkJudgeJobs.filter((job: ActiveJob) => job.status === 'paused').length}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Paused Jobs
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4" color="text.primary" fontWeight={600}>
                    {bulkJudgeJobs.length}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total Active
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Active Jobs Table */}
          <Grid size={{ xs: 12 }}>
            <Card>
              <CardHeader
                title="Active Jobs"
                action={
                  <Button
                    variant="outlined"
                    startIcon={<RefreshIcon />}
                    onClick={() => refetchJobs()}
                    disabled={jobsLoading}
                    size="small"
                  >
                    Refresh
                  </Button>
                }
              />
              <CardContent>
                {jobsLoading ? (
                  <Box display="flex" justifyContent="center" p={3}>
                    <CircularProgress />
                  </Box>
                ) : bulkJudgeJobs.length === 0 ? (
                  <Alert severity="info">
                    No active bulk judge jobs found. Start a new job from the Bulk Operations page.
                  </Alert>
                ) : (
                  <TableContainer component={Paper} variant="outlined">
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Job ID</TableCell>
                          <TableCell>Status</TableCell>
                          <TableCell>Progress</TableCell>
                          <TableCell>Duration</TableCell>
                          <TableCell>Mode</TableCell>
                          <TableCell>Actions</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {bulkJudgeJobs.map((job: ActiveJob) => (
                          <TableRow key={job.job_id}>
                            <TableCell>
                              <Typography variant="body2" fontFamily="monospace">
                                {job.job_id.slice(0, 12)}...
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Chip
                                icon={getStatusIcon(job.status)}
                                label={job.status}
                                color={getStatusColor(job.status)}
                                size="small"
                              />
                            </TableCell>
                            <TableCell>
                              <Box>
                                <Typography variant="body2">
                                  {job.progress.current} / {job.progress.total}
                                </Typography>
                                <LinearProgress
                                  variant="determinate"
                                  value={job.progress.percent}
                                  sx={{ width: 100, mt: 0.5 }}
                                />
                              </Box>
                            </TableCell>
                            <TableCell>
                              {formatDuration(job.started_at)}
                            </TableCell>
                            <TableCell>
                              {job.multi_server ? (
                                <Chip label={`${job.servers?.length || 0} servers`} color="primary" size="small" />
                              ) : (
                                <Chip label="Single server" color="default" size="small" />
                              )}
                            </TableCell>
                            <TableCell>
                              <Box display="flex" gap={1}>
                                <Button
                                  variant="outlined"
                                  size="small"
                                  onClick={() => handleJobSelect(job)}
                                >
                                  Monitor
                                </Button>
                                {['running', 'pending'].includes(job.status) && (
                                  <Button
                                    variant="outlined"
                                    size="small"
                                    startIcon={<PauseIcon />}
                                    onClick={() => pauseMutation.mutate(job.job_id)}
                                    disabled={pauseMutation.isPending}
                                  >
                                    Pause
                                  </Button>
                                )}
                                {job.status === 'paused' && (
                                  <Button
                                    variant="outlined"
                                    size="small"
                                    startIcon={<PlayIcon />}
                                    onClick={() => resumeMutation.mutate(job.job_id)}
                                    disabled={resumeMutation.isPending}
                                  >
                                    Resume
                                  </Button>
                                )}
                                {['running', 'pending', 'paused'].includes(job.status) && (
                                  <Button
                                    variant="outlined"
                                    size="small"
                                    color="error"
                                    startIcon={<StopIcon />}
                                    onClick={() => setJobToCancel(job)}
                                  >
                                    Cancel
                                  </Button>
                                )}
                              </Box>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Server Health Overview */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1} mb={2}>
                  <MemoryIcon color="primary" />
                  <Typography variant="h6">Server Health</Typography>
                </Box>

                {serverLoading ? (
                  <Box display="flex" justifyContent="center" p={2}>
                    <CircularProgress size={24} />
                  </Box>
                ) : serverMetrics ? (
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 4 }}>
                      <Box textAlign="center">
                        <Typography variant="h4" color="success.main">
                          {serverMetrics.summary.healthy}
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Healthy
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid size={{ xs: 4 }}>
                      <Box textAlign="center">
                        <Typography variant="h4" color="error.main">
                          {serverMetrics.summary.unhealthy}
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Unhealthy
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid size={{ xs: 4 }}>
                      <Box textAlign="center">
                        <Typography variant="h4" color="textSecondary">
                          {serverMetrics.summary.total}
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Total
                        </Typography>
                      </Box>
                    </Grid>
                  </Grid>
                ) : (
                  <Typography color="textSecondary">No server data available</Typography>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Queue Status */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1} mb={2}>
                  <QueueIcon color="primary" />
                  <Typography variant="h6">Queue Status</Typography>
                </Box>

                {queueLoading ? (
                  <Box display="flex" justifyContent="center" p={2}>
                    <CircularProgress size={24} />
                  </Box>
                ) : queueStatus ? (
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 6 }}>
                      <Box textAlign="center">
                        <Typography variant="h4" color="warning.main">
                          {queueStatus.queue_stats.pending_tasks || 0}
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Pending
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Box textAlign="center">
                        <Typography variant="h4" color="info.main">
                          {queueStatus.queue_stats.in_progress_tasks || 0}
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          In Progress
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Box textAlign="center">
                        <Typography variant="h4" color="success.main">
                          {queueStatus.queue_stats.completed_tasks || 0}
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Completed
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid size={{ xs: 6 }}>
                      <Box textAlign="center">
                        <Typography variant="h4" color="error.main">
                          {queueStatus.queue_stats.failed_tasks || 0}
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          Failed
                        </Typography>
                      </Box>
                    </Grid>
                  </Grid>
                ) : (
                  <Typography color="textSecondary">No queue data available</Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Job History Tab */}
      {selectedTab === 1 && (
        <Grid container spacing={3}>
          {/* Filters */}
          <Grid size={{ xs: 12 }}>
            <Card>
              <CardContent>
                <Box display="flex" gap={2} alignItems="center" flexWrap="wrap">
                  <FormControl size="small" sx={{ minWidth: 120 }}>
                    <InputLabel>Job Type</InputLabel>
                    <Select
                      value={jobTypeFilter}
                      label="Job Type"
                      onChange={(e) => setJobTypeFilter(e.target.value)}
                    >
                      <MenuItem value="">All Types</MenuItem>
                      <MenuItem value="bulk_judge">Bulk Judge</MenuItem>
                      <MenuItem value="harvest_judge">Harvest Judge</MenuItem>
                      <MenuItem value="profile_aware_ingest">Profile Aware</MenuItem>
                    </Select>
                  </FormControl>

                  <FormControl size="small" sx={{ minWidth: 120 }}>
                    <InputLabel>Limit</InputLabel>
                    <Select
                      value={jobHistoryLimit}
                      label="Limit"
                      onChange={(e) => setJobHistoryLimit(Number(e.target.value))}
                    >
                      <MenuItem value={25}>25</MenuItem>
                      <MenuItem value={50}>50</MenuItem>
                      <MenuItem value={100}>100</MenuItem>
                    </Select>
                  </FormControl>

                  <Button
                    variant="outlined"
                    startIcon={<RefreshIcon />}
                    onClick={handleJobHistoryFilter}
                    disabled={historyLoading}
                    size="small"
                  >
                    Refresh
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Summary Statistics */}
          {jobHistoryData?.summary && (
            <Grid size={{ xs: 12 }}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 6, md: 3 }}>
                  <Card>
                    <CardContent>
                      <Box textAlign="center">
                        <Typography variant="h4" color="success.main" fontWeight={600}>
                          {jobHistoryData.summary.completed_jobs || 0}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Completed
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 3 }}>
                  <Card>
                    <CardContent>
                      <Box textAlign="center">
                        <Typography variant="h4" color="error.main" fontWeight={600}>
                          {jobHistoryData.summary.failed_jobs || 0}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Failed
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 3 }}>
                  <Card>
                    <CardContent>
                      <Box textAlign="center">
                        <Typography variant="h4" color="text.secondary" fontWeight={600}>
                          {jobHistoryData.summary.canceled_jobs || 0}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Canceled
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 3 }}>
                  <Card>
                    <CardContent>
                      <Box textAlign="center">
                        <Typography variant="h4" color="info.main" fontWeight={600}>
                          {jobHistoryData.summary.total_jobs || 0}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Total
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </Grid>
          )}

          {/* Job History Table */}
          <Grid size={{ xs: 12 }}>
            <Card>
              <CardHeader title="Job History" />
              <CardContent>
                {historyLoading ? (
                  <Box display="flex" justifyContent="center" p={3}>
                    <CircularProgress />
                  </Box>
                ) : !jobHistoryData?.jobs?.length ? (
                  <Alert severity="info">
                    No completed jobs found matching the current filters.
                  </Alert>
                ) : (
                  <TableContainer component={Paper} variant="outlined">
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Job ID</TableCell>
                          <TableCell>Type</TableCell>
                          <TableCell>Status</TableCell>
                          <TableCell>Started</TableCell>
                          <TableCell>Duration</TableCell>
                          <TableCell>Actions</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {jobHistoryData.jobs.map((job: any) => (
                          <TableRow key={job.job_id}>
                            <TableCell>
                              <Typography variant="body2" fontFamily="monospace">
                                {job.job_id.slice(0, 12)}...
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Chip
                                label={job.job_type.replace('_', ' ')}
                                size="small"
                                variant="outlined"
                              />
                            </TableCell>
                            <TableCell>
                              <Chip
                                icon={getStatusIcon(job.status)}
                                label={job.status}
                                color={getStatusColor(job.status)}
                                size="small"
                              />
                            </TableCell>
                            <TableCell>
                              <Typography variant="body2">
                                {job.started_at ? new Date(job.started_at).toLocaleString() : 'N/A'}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography variant="body2">
                                {job.duration_seconds ?
                                  `${Math.floor(job.duration_seconds / 60)}m ${job.duration_seconds % 60}s` :
                                  'N/A'
                                }
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Tooltip title="View Details">
                                <IconButton size="small">
                                  <TimelineIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Queue Management Tab */}
      {selectedTab === 2 && (
        <Grid container spacing={3}>
          {/* Queue Statistics */}
          <Grid size={{ xs: 12, md: 4 }}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4" color="warning.main" fontWeight={600}>
                    {queueStatus?.queue_stats.pending_tasks || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Pending Tasks
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4" color="info.main" fontWeight={600}>
                    {queueStatus?.queue_stats.in_progress_tasks || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    In Progress
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4" color="success.main" fontWeight={600}>
                    {queueStatus?.queue_stats.completed_tasks || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Completed Today
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Queue Management Actions */}
          <Grid size={{ xs: 12 }}>
            <Card>
              <CardHeader
                title="Queue Management"
                action={
                  <Button
                    variant="outlined"
                    startIcon={<RefreshIcon />}
                    onClick={() => queryClient.invalidateQueries({ queryKey: ['queueStatus'] })}
                    disabled={queueLoading}
                    size="small"
                  >
                    Refresh
                  </Button>
                }
              />
              <CardContent>
                <Grid container spacing={2}>
                  <Grid size={{ xs: 12, md: 6 }}>
                    <Button
                      variant="outlined"
                      color="warning"
                      startIcon={<ClearQueueIcon />}
                      onClick={() => setClearQueueDialog(true)}
                      fullWidth
                    >
                      Clear Queue
                    </Button>
                  </Grid>
                  <Grid size={{ xs: 12, md: 6 }}>
                    <Button
                      variant="outlined"
                      startIcon={<FilterIcon />}
                      onClick={() => queryClient.invalidateQueries({ queryKey: ['queueStatus'] })}
                      fullWidth
                    >
                      Filter by Status
                    </Button>
                  </Grid>
                </Grid>

                {/* Active Jobs in Queue */}
                {queueStatus?.active_jobs?.length > 0 && (
                  <Box mt={3}>
                    <Typography variant="h6" gutterBottom>
                      Active Jobs in Queue
                    </Typography>
                    <TableContainer component={Paper} variant="outlined">
                      <Table>
                        <TableHead>
                          <TableRow>
                            <TableCell>Job ID</TableCell>
                            <TableCell>Tasks</TableCell>
                            <TableCell>Progress</TableCell>
                            <TableCell>Actions</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {queueStatus.active_jobs.map((job: any) => (
                            <TableRow key={job.job_id}>
                              <TableCell>
                                <Typography variant="body2" fontFamily="monospace">
                                  {job.job_id.slice(0, 12)}...
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Typography variant="body2">
                                  {job.total_tasks} total
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Typography variant="body2">
                                  {job.pending_tasks} pending, {job.in_progress_tasks} active
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Button
                                  size="small"
                                  variant="outlined"
                                  onClick={() => setClearJobId(job.job_id)}
                                  startIcon={<ClearIcon />}
                                >
                                  Clear
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Job Monitoring Tab */}
      {selectedTab === 3 && selectedJobId && (
        <BulkJudgeMonitoring
          jobId={selectedJobId}
          onJobComplete={handleJobComplete}
          onJobError={handleJobError}
        />
      )}

      {/* Clear Queue Dialog */}
      <Dialog open={clearQueueDialog} onClose={() => setClearQueueDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Clear Queue</DialogTitle>
        <DialogContent>
          <Typography gutterBottom>
            Clear tasks from the processing queue. This action cannot be undone.
          </Typography>

          <Box mt={2} display="flex" flexDirection="column" gap={2}>
            <TextField
              label="Job ID (optional)"
              value={clearJobId}
              onChange={(e) => setClearJobId(e.target.value)}
              placeholder="Leave empty to clear all jobs"
              size="small"
              fullWidth
            />

            <FormControl size="small" fullWidth>
              <InputLabel>Status Filter</InputLabel>
              <Select
                value={clearStatusFilter}
                label="Status Filter"
                onChange={(e) => setClearStatusFilter(e.target.value)}
              >
                <MenuItem value="">All Statuses</MenuItem>
                <MenuItem value="pending">Pending</MenuItem>
                <MenuItem value="leased">Leased</MenuItem>
                <MenuItem value="in_progress">In Progress</MenuItem>
                <MenuItem value="failed">Failed</MenuItem>
              </Select>
            </FormControl>
          </Box>

          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography variant="body2">
              This will permanently remove tasks from the queue. Make sure you want to proceed.
            </Typography>
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setClearQueueDialog(false)}>Cancel</Button>
          <Button
            onClick={handleClearQueue}
            color="error"
            variant="contained"
            disabled={clearQueueMutation.isPending}
            startIcon={clearQueueMutation.isPending ? <CircularProgress size={16} /> : <ClearQueueIcon />}
          >
            {clearQueueMutation.isPending ? 'Clearing...' : 'Clear Queue'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Cancel Job Dialog */}
      <Dialog open={!!jobToCancel} onClose={() => setJobToCancel(null)}>
        <DialogTitle>Cancel Bulk Judge Job</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to cancel the job {jobToCancel?.job_id.slice(0, 12)}...?
            This action cannot be undone.
          </Typography>
          {jobToCancel && (
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              Current progress: {jobToCancel.progress.current} of {jobToCancel.progress.total} tasks completed.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setJobToCancel(null)}>Keep Running</Button>
          <Button
            onClick={() => jobToCancel && cancelMutation.mutate(jobToCancel.job_id)}
            color="error"
            variant="contained"
            disabled={cancelMutation.isPending}
          >
            {cancelMutation.isPending ? <CircularProgress size={20} /> : 'Cancel Job'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default JobMonitoring;