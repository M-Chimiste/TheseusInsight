import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Switch,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Alert,
  Tooltip,
  CircularProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  FormHelperText,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  PlayArrow as PlayIcon,
  Schedule as ScheduleIcon,
  ExpandMore as ExpandMoreIcon,
  Error as ErrorIcon,
  CheckCircle as CheckCircleIcon,
  AccessTime as AccessTimeIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { scheduledTasksApi, profileApi } from '../services/api';
import type { ScheduledTask, ScheduledTaskCreate, ScheduledTaskUpdate } from '../services/api';

interface ScheduledTasksSettingsProps {
  onStatusChange?: (message: string, severity: 'success' | 'error' | 'info') => void;
}

const TASK_TYPES = [
  { value: 'newsletter', label: 'Newsletter Generation', description: 'Generate and send newsletters' },
  { value: 'trends_recomputation', label: 'Trends Analysis', description: 'Recompute research trends' },
  { value: 'database_cleanup', label: 'Database Cleanup', description: 'Clean up old data' },
];

const FREQUENCIES = [
  { value: 'hourly', label: 'Hourly' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
];

const DAYS_OF_WEEK = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
  { value: 6, label: 'Sunday' },
];

export const ScheduledTasksSettings: React.FC<ScheduledTasksSettingsProps> = ({ onStatusChange }) => {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<ScheduledTask | null>(null);
  const [formData, setFormData] = useState<Partial<ScheduledTaskCreate>>({
    name: '',
    task_type: 'newsletter',
    is_enabled: true,
    frequency: 'weekly',
    hour: 9,
    minute: 0,
    timezone: 'UTC',
    config: {},
  });

  // Fetch scheduled tasks
  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ['scheduledTasks'],
    queryFn: async () => {
      const response = await scheduledTasksApi.getTasks();
      return response.data;
    },
  });

  // Fetch profiles for newsletter tasks
  const { data: profiles = [] } = useQuery({
    queryKey: ['profiles'],
    queryFn: async () => {
      const response = await profileApi.getProfiles();
      return response.data;
    },
  });

  // Create task mutation
  const createTaskMutation = useMutation({
    mutationFn: scheduledTasksApi.createTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduledTasks'] });
      setDialogOpen(false);
      resetForm();
      onStatusChange?.('Scheduled task created successfully', 'success');
    },
    onError: (error: any) => {
      onStatusChange?.(`Failed to create task: ${error.response?.data?.detail || error.message}`, 'error');
    },
  });

  // Update task mutation
  const updateTaskMutation = useMutation({
    mutationFn: ({ id, update }: { id: number; update: ScheduledTaskUpdate }) =>
      scheduledTasksApi.updateTask(id, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduledTasks'] });
      setDialogOpen(false);
      setEditingTask(null);
      resetForm();
      onStatusChange?.('Scheduled task updated successfully', 'success');
    },
    onError: (error: any) => {
      onStatusChange?.(`Failed to update task: ${error.response?.data?.detail || error.message}`, 'error');
    },
  });

  // Delete task mutation
  const deleteTaskMutation = useMutation({
    mutationFn: scheduledTasksApi.deleteTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduledTasks'] });
      onStatusChange?.('Scheduled task deleted successfully', 'success');
    },
    onError: (error: any) => {
      onStatusChange?.(`Failed to delete task: ${error.response?.data?.detail || error.message}`, 'error');
    },
  });

  // Run task now mutation
  const runTaskNowMutation = useMutation({
    mutationFn: scheduledTasksApi.runTaskNow,
    onSuccess: () => {
      onStatusChange?.('Task execution started', 'info');
    },
    onError: (error: any) => {
      onStatusChange?.(`Failed to run task: ${error.response?.data?.detail || error.message}`, 'error');
    },
  });

  const resetForm = () => {
    setFormData({
      name: '',
      task_type: 'newsletter',
      is_enabled: true,
      frequency: 'weekly',
      hour: 9,
      minute: 0,
      timezone: 'UTC',
      config: {},
    });
  };

  const handleEditTask = (task: ScheduledTask) => {
    setEditingTask(task);
    setFormData({
      name: task.name,
      task_type: task.task_type as any,
      profile_id: task.profile_id,
      is_enabled: task.is_enabled,
      frequency: task.frequency as any,
      day_of_week: task.day_of_week,
      day_of_month: task.day_of_month,
      hour: task.hour,
      minute: task.minute,
      timezone: task.timezone,
      config: task.config,
    });
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    if (!formData.name || formData.hour === undefined) {
      onStatusChange?.('Please fill in all required fields', 'error');
      return;
    }

    if (editingTask) {
      updateTaskMutation.mutate({
        id: editingTask.id,
        update: formData as ScheduledTaskUpdate,
      });
    } else {
      createTaskMutation.mutate(formData as ScheduledTaskCreate);
    }
  };

  const formatNextRun = (nextRunAt?: string) => {
    if (!nextRunAt) return 'Not scheduled';
    const date = new Date(nextRunAt);
    const now = new Date();
    const diff = date.getTime() - now.getTime();
    
    if (diff < 0) return 'Overdue';
    if (diff < 3600000) return `In ${Math.floor(diff / 60000)} minutes`;
    if (diff < 86400000) return `In ${Math.floor(diff / 3600000)} hours`;
    return date.toLocaleString();
  };

  const getStatusChip = (task: ScheduledTask) => {
    if (!task.is_enabled) {
      return <Chip label="Disabled" size="small" />;
    }
    if (task.last_run_status === 'failed') {
      return <Chip label="Failed" size="small" color="error" icon={<ErrorIcon />} />;
    }
    if (task.last_run_status === 'completed') {
      return <Chip label="Success" size="small" color="success" icon={<CheckCircleIcon />} />;
    }
    return <Chip label="Active" size="small" color="primary" />;
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" p={3}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h6">
            <ScheduleIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            Scheduled Tasks
          </Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => {
              setEditingTask(null);
              resetForm();
              setDialogOpen(true);
            }}
          >
            Add Task
          </Button>
        </Box>

        {tasks.length === 0 ? (
          <Alert severity="info">
            No scheduled tasks configured. Click "Add Task" to create your first scheduled task.
          </Alert>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Schedule</TableCell>
                  <TableCell>Next Run</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {tasks.map((task) => (
                  <TableRow key={task.id}>
                    <TableCell>
                      <Typography variant="body2" fontWeight="medium">
                        {task.name}
                      </Typography>
                      {task.profile_name && (
                        <Typography variant="caption" color="text.secondary" display="block">
                          Profile: {task.profile_name}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>{task.task_type}</TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {task.frequency}
                        {task.frequency === 'daily' && ` at ${task.hour}:${String(task.minute).padStart(2, '0')}`}
                        {task.frequency === 'weekly' && ` on ${DAYS_OF_WEEK.find(d => d.value === task.day_of_week)?.label}`}
                        {task.frequency === 'monthly' && ` on day ${task.day_of_month}`}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={0.5}>
                        <AccessTimeIcon fontSize="small" color="action" />
                        <Typography variant="body2">
                          {formatNextRun(task.next_run_at)}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>{getStatusChip(task)}</TableCell>
                    <TableCell align="right">
                      <Tooltip title="Run Now">
                        <IconButton
                          size="small"
                          onClick={() => runTaskNowMutation.mutate(task.id)}
                          disabled={!task.is_enabled}
                        >
                          <PlayIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Edit">
                        <IconButton size="small" onClick={() => handleEditTask(task)}>
                          <EditIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => {
                            if (window.confirm(`Delete scheduled task "${task.name}"?`)) {
                              deleteTaskMutation.mutate(task.id);
                            }
                          }}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Add/Edit Dialog */}
        <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>{editingTask ? 'Edit Scheduled Task' : 'Add Scheduled Task'}</DialogTitle>
          <DialogContent>
            <Box display="flex" flexDirection="column" gap={2} mt={1}>
              <TextField
                label="Task Name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                fullWidth
                required
              />

              <FormControl fullWidth required>
                <InputLabel>Task Type</InputLabel>
                <Select
                  value={formData.task_type}
                  onChange={(e) => setFormData({ ...formData, task_type: e.target.value as any })}
                  label="Task Type"
                >
                  {TASK_TYPES.map((type) => (
                    <MenuItem key={type.value} value={type.value}>
                      <Box>
                        <Typography variant="body2">{type.label}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {type.description}
                        </Typography>
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {formData.task_type === 'newsletter' && (
                <FormControl fullWidth>
                  <InputLabel>Profile (Optional)</InputLabel>
                  <Select
                    value={formData.profile_id || ''}
                    onChange={(e) => setFormData({ ...formData, profile_id: e.target.value ? Number(e.target.value) : undefined })}
                    label="Profile (Optional)"
                  >
                    <MenuItem value="">
                      <em>None</em>
                    </MenuItem>
                    {profiles.map((profile) => (
                      <MenuItem key={profile.id} value={profile.id}>
                        {profile.name}
                      </MenuItem>
                    ))}
                  </Select>
                  <FormHelperText>
                    Select a profile to use its research interests and email recipients
                  </FormHelperText>
                </FormControl>
              )}

              <FormControl fullWidth required>
                <InputLabel>Frequency</InputLabel>
                <Select
                  value={formData.frequency}
                  onChange={(e) => setFormData({ ...formData, frequency: e.target.value as any })}
                  label="Frequency"
                >
                  {FREQUENCIES.map((freq) => (
                    <MenuItem key={freq.value} value={freq.value}>
                      {freq.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {formData.frequency === 'weekly' && (
                <FormControl fullWidth required>
                  <InputLabel>Day of Week</InputLabel>
                  <Select
                    value={formData.day_of_week || 0}
                    onChange={(e) => setFormData({ ...formData, day_of_week: Number(e.target.value) })}
                    label="Day of Week"
                  >
                    {DAYS_OF_WEEK.map((day) => (
                      <MenuItem key={day.value} value={day.value}>
                        {day.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}

              {formData.frequency === 'monthly' && (
                <TextField
                  label="Day of Month"
                  type="number"
                  value={formData.day_of_month || 1}
                  onChange={(e) => setFormData({ ...formData, day_of_month: Number(e.target.value) })}
                  inputProps={{ min: 1, max: 31 }}
                  fullWidth
                  required
                />
              )}

              <Box display="flex" gap={2}>
                <TextField
                  label="Hour (0-23)"
                  type="number"
                  value={formData.hour}
                  onChange={(e) => setFormData({ ...formData, hour: Number(e.target.value) })}
                  inputProps={{ min: 0, max: 23 }}
                  fullWidth
                  required
                />
                <TextField
                  label="Minute (0-59)"
                  type="number"
                  value={formData.minute}
                  onChange={(e) => setFormData({ ...formData, minute: Number(e.target.value) })}
                  inputProps={{ min: 0, max: 59 }}
                  fullWidth
                />
              </Box>

              <FormControlLabel
                control={
                  <Switch
                    checked={formData.is_enabled}
                    onChange={(e) => setFormData({ ...formData, is_enabled: e.target.checked })}
                  />
                }
                label="Enabled"
              />

              {formData.task_type === 'newsletter' && formData.profile_id && (
                <Accordion>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography>Advanced Configuration</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Box display="flex" flexDirection="column" gap={2}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={formData.config?.use_profile_recipients || false}
                            onChange={(e) => setFormData({
                              ...formData,
                              config: { ...formData.config, use_profile_recipients: e.target.checked }
                            })}
                          />
                        }
                        label="Use profile email recipients"
                      />
                      {!formData.config?.use_profile_recipients && (
                        <TextField
                          label="Email Recipients"
                          placeholder="email1@example.com, email2@example.com"
                          value={formData.config?.emailRecipients?.join(', ') || ''}
                          onChange={(e) => setFormData({
                            ...formData,
                            config: {
                              ...formData.config,
                              emailRecipients: e.target.value.split(',').map(email => email.trim()).filter(Boolean)
                            }
                          })}
                          fullWidth
                          multiline
                          rows={2}
                          helperText="Comma-separated email addresses"
                        />
                      )}
                    </Box>
                  </AccordionDetails>
                </Accordion>
              )}
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleSubmit}
              variant="contained"
              disabled={createTaskMutation.isPending || updateTaskMutation.isPending}
            >
              {editingTask ? 'Update' : 'Create'}
            </Button>
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>
  );
};