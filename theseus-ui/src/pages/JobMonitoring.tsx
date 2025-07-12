import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  LinearProgress,
  Alert,
  AlertTitle,
  Chip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  CircularProgress,
  Tooltip,
  Grid,
} from '@mui/material';
import {
  Play,
  Pause,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  XCircle,
  Clock,
  Activity,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

interface Job {
  id: string;
  job_type: string;
  status: string;
  progress_current: number;
  progress_total: number | null;
  progress_percent: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  last_checkpoint_at: string | null;
  created_at: string;
}

interface JobStatistics {
  job_type: string;
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  running_jobs: number;
  avg_runtime_minutes: number;
  success_rate: number;
}

const JobMonitoring: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeJobs, setActiveJobs] = useState<Job[]>([]);
  const [statistics, setStatistics] = useState<JobStatistics[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedJobType, setSelectedJobType] = useState<string>('all');
  const [refreshInterval, setRefreshInterval] = useState<number>(5000);

  // Fetch job data
  const fetchJobs = async () => {
    try {
      const params = new URLSearchParams();
      if (selectedStatus !== 'all') params.append('status', selectedStatus);
      if (selectedJobType !== 'all') params.append('job_type', selectedJobType);

      const response = await fetch(`/api/jobs?${params}`);
      if (!response.ok) throw new Error('Failed to fetch jobs');
      const data = await response.json();
      setJobs(data.jobs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch jobs');
    }
  };

  // Fetch active jobs
  const fetchActiveJobs = async () => {
    try {
      const response = await fetch('/api/jobs/active');
      if (!response.ok) throw new Error('Failed to fetch active jobs');
      const data = await response.json();
      setActiveJobs(data);
    } catch (err) {
      console.error('Failed to fetch active jobs:', err);
    }
  };

  // Fetch statistics
  const fetchStatistics = async () => {
    try {
      const response = await fetch('/api/jobs/statistics');
      if (!response.ok) throw new Error('Failed to fetch statistics');
      const data = await response.json();
      setStatistics(data.statistics);
    } catch (err) {
      console.error('Failed to fetch statistics:', err);
    }
  };

  // Initial data load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchJobs(), fetchActiveJobs(), fetchStatistics()]);
      setLoading(false);
    };
    loadData();
  }, [selectedStatus, selectedJobType]);

  // Auto-refresh for active jobs
  useEffect(() => {
    if (refreshInterval > 0) {
      const interval = setInterval(() => {
        fetchActiveJobs();
        if (activeJobs.length > 0) {
          fetchJobs();
        }
      }, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [refreshInterval, activeJobs.length]);

  // Helper functions
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Activity size={16} color="#2196f3" />;
      case 'completed':
        return <CheckCircle size={16} color="#4caf50" />;
      case 'failed':
        return <XCircle size={16} color="#f44336" />;
      case 'cancelled':
        return <AlertCircle size={16} color="#ff9800" />;
      default:
        return <Clock size={16} color="#757575" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'primary';
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      case 'cancelled':
        return 'warning';
      default:
        return 'default';
    }
  };

  const formatDuration = (started: string | null, completed: string | null) => {
    if (!started) return '-';
    const start = new Date(started);
    const end = completed ? new Date(completed) : new Date();
    const diff = end.getTime() - start.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ${hours % 24}h`;
    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    return `${minutes}m`;
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
  };

  // Cancel job
  const cancelJob = async (jobId: string) => {
    try {
      const response = await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
      if (!response.ok) throw new Error('Failed to cancel job');
      await fetchJobs();
      await fetchActiveJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel job');
    }
  };

  // Resume job
  const resumeJob = async (jobId: string) => {
    try {
      const response = await fetch(`/api/jobs/${jobId}/resume`, { method: 'POST' });
      if (!response.ok) throw new Error('Failed to resume job');
      await fetchJobs();
      await fetchActiveJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resume job');
    }
  };

  // Chart data
  const pieData = statistics.map((stat) => ({
    name: stat.job_type,
    value: stat.total_jobs,
    completed: stat.completed_jobs,
    failed: stat.failed_jobs,
  }));

  const barData = statistics.map((stat) => ({
    job_type: stat.job_type,
    success_rate: stat.success_rate,
    avg_runtime: stat.avg_runtime_minutes,
  }));

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Job Monitoring Dashboard
        </Typography>
        <Box display="flex" gap={2}>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Refresh Rate</InputLabel>
            <Select
              value={refreshInterval}
              label="Refresh Rate"
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
            >
              <MenuItem value={0}>No auto-refresh</MenuItem>
              <MenuItem value={2000}>2 seconds</MenuItem>
              <MenuItem value={5000}>5 seconds</MenuItem>
              <MenuItem value={10000}>10 seconds</MenuItem>
              <MenuItem value={30000}>30 seconds</MenuItem>
            </Select>
          </FormControl>
          <Button
            variant="outlined"
            startIcon={<RefreshCw size={16} />}
            onClick={() => fetchJobs()}
          >
            Refresh
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          <AlertTitle>Error</AlertTitle>
          {error}
        </Alert>
      )}

      {/* Active Jobs */}
      {activeJobs.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Active Jobs
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Currently running or pending jobs
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {activeJobs.map((job) => (
                <Paper key={job.id} sx={{ p: 2 }} variant="outlined">
                  <Box display="flex" justifyContent="space-between" alignItems="start" mb={1}>
                    <Box>
                      <Box display="flex" alignItems="center" gap={1}>
                        {getStatusIcon(job.status)}
                        <Typography variant="subtitle1">{job.job_type}</Typography>
                        <Chip
                          label={job.status}
                          size="small"
                          color={getStatusColor(job.status) as any}
                        />
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        Started: {formatDate(job.started_at)}
                      </Typography>
                    </Box>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<Pause size={14} />}
                      onClick={() => cancelJob(job.id)}
                    >
                      Cancel
                    </Button>
                  </Box>
                  <Box>
                    <Box display="flex" justifyContent="space-between" mb={0.5}>
                      <Typography variant="body2">Progress</Typography>
                      <Typography variant="body2">
                        {job.progress_current} / {job.progress_total || '?'}
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={job.progress_percent}
                      sx={{ height: 8, borderRadius: 1 }}
                    />
                    <Typography variant="caption" color="text.secondary" align="right" display="block">
                      {job.progress_percent.toFixed(1)}%
                    </Typography>
                  </Box>
                </Paper>
              ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Statistics */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Job Distribution
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={(entry) => `${entry.name}: ${entry.value}`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {pieData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Performance Metrics
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={barData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="job_type" />
                  <YAxis yAxisId="left" orientation="left" stroke="#8884d8" />
                  <YAxis yAxisId="right" orientation="right" stroke="#82ca9d" />
                  <RechartsTooltip />
                  <Bar yAxisId="left" dataKey="success_rate" fill="#8884d8" name="Success Rate (%)" />
                  <Bar yAxisId="right" dataKey="avg_runtime" fill="#82ca9d" name="Avg Runtime (min)" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Job History */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Job History
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Recent and historical job runs
          </Typography>

          <Box display="flex" gap={2} mb={2}>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Status</InputLabel>
              <Select
                value={selectedStatus}
                label="Status"
                onChange={(e) => setSelectedStatus(e.target.value)}
              >
                <MenuItem value="all">All Statuses</MenuItem>
                <MenuItem value="pending">Pending</MenuItem>
                <MenuItem value="running">Running</MenuItem>
                <MenuItem value="completed">Completed</MenuItem>
                <MenuItem value="failed">Failed</MenuItem>
                <MenuItem value="cancelled">Cancelled</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel>Job Type</InputLabel>
              <Select
                value={selectedJobType}
                label="Job Type"
                onChange={(e) => setSelectedJobType(e.target.value)}
              >
                <MenuItem value="all">All Job Types</MenuItem>
                <MenuItem value="harvest_judge">Harvest & Judge</MenuItem>
                <MenuItem value="bulk_judge">Bulk Judge</MenuItem>
                <MenuItem value="embedding_backfill">Embedding Backfill</MenuItem>
                <MenuItem value="newsletter_generation">Newsletter Generation</MenuItem>
              </Select>
            </FormControl>
          </Box>

          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Status</TableCell>
                  <TableCell>Job Type</TableCell>
                  <TableCell>Progress</TableCell>
                  <TableCell>Duration</TableCell>
                  <TableCell>Started</TableCell>
                  <TableCell>Completed</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={1}>
                        {getStatusIcon(job.status)}
                        <Chip
                          label={job.status}
                          size="small"
                          color={getStatusColor(job.status) as any}
                        />
                      </Box>
                    </TableCell>
                    <TableCell>{job.job_type}</TableCell>
                    <TableCell>
                      {job.progress_total ? (
                        <Box display="flex" alignItems="center" gap={1}>
                          <LinearProgress
                            variant="determinate"
                            value={job.progress_percent}
                            sx={{ width: 80, height: 6 }}
                          />
                          <Typography variant="caption" color="text.secondary">
                            {job.progress_percent.toFixed(0)}%
                          </Typography>
                        </Box>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>{formatDuration(job.started_at, job.completed_at)}</TableCell>
                    <TableCell>{formatDate(job.started_at)}</TableCell>
                    <TableCell>{formatDate(job.completed_at)}</TableCell>
                    <TableCell>
                      {(job.status === 'failed' || job.status === 'cancelled') && (
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={<Play size={14} />}
                          onClick={() => resumeJob(job.id)}
                        >
                          Resume
                        </Button>
                      )}
                      {job.error_message && (
                        <Tooltip title={job.error_message}>
                          <IconButton size="small">
                            <AlertCircle size={16} color="#f44336" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Box>
  );
};

export default JobMonitoring;