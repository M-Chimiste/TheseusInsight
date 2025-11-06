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
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Switch,
  FormControlLabel,
  Chip,
  Tooltip,
  Alert,
  CircularProgress,
  Snackbar,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Grid,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  PlayArrow as TestIcon,
  Power as PowerIcon,
  PowerOff as PowerOffIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ollamaServersApi } from '../services/api';
import type {
  OllamaServer,
  OllamaServerCreate,
  OllamaServerUpdate,
  ServerTestResult,
  GlobalDefaults,
} from '../services/api';

const OllamaServersSettings: React.FC = () => {
  const queryClient = useQueryClient();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedServer, setSelectedServer] = useState<OllamaServer | null>(null);
  const [serverToDelete, setServerToDelete] = useState<OllamaServer | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'warning' | 'info' }>({
    open: false,
    message: '',
    severity: 'success'
  });

  // Form states
  const [formData, setFormData] = useState<OllamaServerCreate>({
    name: '',
    url: '',
    provider: 'ollama',
    config_json: {},
    notes: ''
  });

  const [editFormData, setEditFormData] = useState<OllamaServerUpdate>({
    name: '',
    url: '',
    provider: 'ollama',
    enabled: true,
    config_json: {},
    notes: ''
  });

  const [globalDefaults, setGlobalDefaults] = useState<GlobalDefaults>({
    request_timeout_sec: 30,
    max_retries: 3,
    circuit_breaker_threshold: 5
  });

  // Queries
  const { data: servers = [], isLoading: serversLoading } = useQuery({
    queryKey: ['ollamaServers'],
    queryFn: () => ollamaServersApi.getAllServers().then((res: { data: any; }) => res.data),
  });

  const { data: globalDefaultsData } = useQuery({
    queryKey: ['ollamaGlobalDefaults'],
    queryFn: () => ollamaServersApi.getGlobalDefaults().then((res: { data: any; }) => res.data),
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: (server: OllamaServerCreate) => ollamaServersApi.createServer(server).then((res: { data: any; }) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ollamaServers'] });
      queryClient.invalidateQueries({ queryKey: ['inferenceServersForSettings'] });
      setCreateDialogOpen(false);
      setFormData({ name: '', url: '', provider: 'ollama', config_json: {}, model_name: undefined, model_config: {}, notes: '' });
      showSnackbar('Server created successfully', 'success');
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      showSnackbar(`Failed to create server: ${errorMessage}`, 'error');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, server }: { id: number; server: OllamaServerUpdate }) =>
      ollamaServersApi.updateServer(id, server).then((res: { data: any; }) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ollamaServers'] });
      queryClient.invalidateQueries({ queryKey: ['inferenceServersForSettings'] });
      setEditDialogOpen(false);
      setSelectedServer(null);
      showSnackbar('Server updated successfully', 'success');
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      showSnackbar(`Failed to update server: ${errorMessage}`, 'error');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => ollamaServersApi.deleteServer(id).then((res: { data: any; }) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ollamaServers'] });
      queryClient.invalidateQueries({ queryKey: ['inferenceServersForSettings'] });
      showSnackbar('Server deleted successfully', 'success');
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      showSnackbar(`Failed to delete server: ${errorMessage}`, 'error');
    },
  });

  const testMutation = useMutation({
    mutationFn: (id: number) => ollamaServersApi.testServer(id).then((res: { data: any; }) => res.data),
    onSuccess: (data: ServerTestResult) => {
      queryClient.invalidateQueries({ queryKey: ['ollamaServers'] });
      queryClient.invalidateQueries({ queryKey: ['inferenceServersForSettings'] });
      if (data.success) {
        showSnackbar(`Server test successful (${data.latency_ms}ms)`, 'success');
      } else {
        showSnackbar(`Server test failed: ${data.error}`, 'error');
      }
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      showSnackbar(`Server test failed: ${errorMessage}`, 'error');
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (id: number) => ollamaServersApi.toggleServer(id).then((res: { data: any; }) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ollamaServers'] });
      queryClient.invalidateQueries({ queryKey: ['inferenceServersForSettings'] });
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      showSnackbar(`Failed to toggle server: ${errorMessage}`, 'error');
    },
  });

  const updateDefaultsMutation = useMutation({
    mutationFn: (defaults: GlobalDefaults) => ollamaServersApi.updateGlobalDefaults(defaults).then((res: { data: any; }) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ollamaGlobalDefaults'] });
      showSnackbar('Global defaults updated successfully', 'success');
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      showSnackbar(`Failed to update defaults: ${errorMessage}`, 'error');
    },
  });

  // Effects
  useEffect(() => {
    if (globalDefaultsData) {
      setGlobalDefaults(globalDefaultsData);
    }
  }, [globalDefaultsData]);

  // Helper functions
  const showSnackbar = (message: string, severity: 'success' | 'error' | 'warning' | 'info') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  const handleCreateDialogOpen = () => {
    setCreateDialogOpen(true);
  };

  const handleCreateDialogClose = () => {
    setCreateDialogOpen(false);
    setFormData({ name: '', url: '', provider: 'ollama', config_json: {}, model_name: undefined, model_config: {}, notes: '' });
  };

  const handleEditDialogOpen = (server: OllamaServer) => {
    setSelectedServer(server);
    setEditFormData({
      name: server.name,
      url: server.url,
      provider: server.provider,
      enabled: server.enabled,
      config_json: server.config_json || {},
      model_name: server.model_name,
      model_config: server.model_config || {},
      notes: server.notes || ''
    });
    setEditDialogOpen(true);
  };

  const handleEditDialogClose = () => {
    setEditDialogOpen(false);
    setSelectedServer(null);
    setEditFormData({ name: '', url: '', provider: 'ollama', enabled: true, config_json: {}, model_name: undefined, model_config: {}, notes: '' });
  };

  const handleCreateSubmit = () => {
    if (!formData.name.trim() || !formData.url.trim()) {
      showSnackbar('Name and URL are required', 'error');
      return;
    }
    createMutation.mutate(formData);
  };

  const handleEditSubmit = () => {
    if (!selectedServer) return;
    if (!editFormData.name.trim() || !editFormData.url.trim()) {
      showSnackbar('Name and URL are required', 'error');
      return;
    }
    updateMutation.mutate({ id: selectedServer.id, server: editFormData });
  };

  const handleDeleteClick = (server: OllamaServer) => {
    setServerToDelete(server);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (serverToDelete) {
      deleteMutation.mutate(serverToDelete.id);
    }
    setDeleteDialogOpen(false);
    setServerToDelete(null);
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setServerToDelete(null);
  };

  const handleTest = (server: OllamaServer) => {
    testMutation.mutate(server.id);
  };

  const handleToggle = (server: OllamaServer) => {
    toggleMutation.mutate(server.id);
  };

  const handleGlobalDefaultsChange = (field: keyof GlobalDefaults, value: number) => {
    setGlobalDefaults(prev => ({ ...prev, [field]: value }));
  };

  const handleGlobalDefaultsSubmit = () => {
    updateDefaultsMutation.mutate(globalDefaults);
  };

  const getStatusIcon = (server: OllamaServer) => {
    if (!server.enabled) {
      return <PowerOffIcon color="disabled" />;
    }

    if (server.last_test_ok === null) {
      return <InfoIcon color="action" />;
    }

    return server.last_test_ok ? (
      <CheckCircleIcon color="success" />
    ) : (
      <ErrorIcon color="error" />
    );
  };

  const getStatusText = (server: OllamaServer) => {
    if (!server.enabled) {
      return 'Disabled';
    }

    if (server.last_test_ok === null) {
      return 'Not tested';
    }

    return server.last_test_ok ? 'Healthy' : 'Unhealthy';
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6" fontWeight={600} sx={{ flex: 1 }}>
          Inference Servers
        </Typography>
        <Tooltip title="Configure multiple Ollama and LM Studio servers for distributed bulk processing">
          <InfoIcon color="action" sx={{ mr: 2 }} />
        </Tooltip>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleCreateDialogOpen}
          disabled={serversLoading}
        >
          Add Server
        </Button>
      </Box>

      {/* Global Defaults Section */}
      <Accordion sx={{ mb: 3 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6" fontWeight={600}>
            Global Configuration
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={3}>
            <Grid size={{ xs: 12, md: 4 }}>
              <TextField
                fullWidth
                label="Request Timeout (seconds)"
                type="number"
                value={globalDefaults.request_timeout_sec}
                onChange={(e) => handleGlobalDefaultsChange('request_timeout_sec', parseInt(e.target.value) || 30)}
                inputProps={{ min: 5, max: 300 }}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <TextField
                fullWidth
                label="Max Retries"
                type="number"
                value={globalDefaults.max_retries}
                onChange={(e) => handleGlobalDefaultsChange('max_retries', parseInt(e.target.value) || 3)}
                inputProps={{ min: 0, max: 10 }}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <TextField
                fullWidth
                label="Circuit Breaker Threshold"
                type="number"
                value={globalDefaults.circuit_breaker_threshold}
                onChange={(e) => handleGlobalDefaultsChange('circuit_breaker_threshold', parseInt(e.target.value) || 5)}
                inputProps={{ min: 1, max: 20 }}
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <Button
                variant="contained"
                onClick={handleGlobalDefaultsSubmit}
                disabled={updateDefaultsMutation.isPending}
              >
                {updateDefaultsMutation.isPending ? <CircularProgress size={20} /> : 'Update Defaults'}
              </Button>
            </Grid>
          </Grid>
        </AccordionDetails>
      </Accordion>

      {/* Servers Table */}
      <Card>
        <CardContent>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Provider</TableCell>
                  <TableCell>URL</TableCell>
                  <TableCell>Model</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Last Test</TableCell>
                  <TableCell>Latency</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {serversLoading ? (
                  <TableRow>
                    <TableCell colSpan={8} align="center">
                      <CircularProgress size={24} />
                    </TableCell>
                  </TableRow>
                ) : servers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} align="center">
                      <Typography color="textSecondary">
                        No inference servers configured. Click "Add Server" to get started.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  servers.map((server: OllamaServer) => (
                    <TableRow key={server.id}>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {server.name}
                          {server.notes && (
                            <Tooltip title={server.notes}>
                              <InfoIcon fontSize="small" color="action" />
                            </Tooltip>
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={server.provider === 'ollama' ? 'Ollama' : 'LM Studio'}
                          size="small"
                          color={server.provider === 'ollama' ? 'primary' : 'secondary'}
                        />
                      </TableCell>
                      <TableCell>{server.url}</TableCell>
                      <TableCell>
                        {server.model_name ? (
                          <Tooltip title="Custom model configured for this server">
                            <Chip label={server.model_name} size="small" variant="outlined" />
                          </Tooltip>
                        ) : (
                          <Typography variant="body2" color="textSecondary">
                            Default
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {getStatusIcon(server)}
                          <Typography variant="body2">
                            {getStatusText(server)}
                          </Typography>
                          <Chip
                            size="small"
                            label={server.enabled ? 'Enabled' : 'Disabled'}
                            color={server.enabled ? 'success' : 'default'}
                          />
                        </Box>
                      </TableCell>
                      <TableCell>
                        {server.last_tested_at ? (
                          <Tooltip title={new Date(server.last_tested_at).toLocaleString()}>
                            <Typography variant="body2">
                              {new Date(server.last_tested_at).toLocaleDateString()}
                            </Typography>
                          </Tooltip>
                        ) : (
                          <Typography variant="body2" color="textSecondary">
                            Never
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        {server.last_test_latency_ms !== null ? (
                          <Typography variant="body2">
                            {server.last_test_latency_ms}ms
                          </Typography>
                        ) : (
                          <Typography variant="body2" color="textSecondary">
                            -
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Tooltip title="Test connection">
                          <IconButton
                            size="small"
                            onClick={() => handleTest(server)}
                            disabled={testMutation.isPending}
                          >
                            {testMutation.isPending ? <CircularProgress size={16} /> : <TestIcon />}
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Edit server">
                          <IconButton size="small" onClick={() => handleEditDialogOpen(server)}>
                            <EditIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={server.enabled ? 'Disable server' : 'Enable server'}>
                          <IconButton size="small" onClick={() => handleToggle(server)}>
                            {server.enabled ? <PowerIcon /> : <PowerOffIcon />}
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete server">
                          <IconButton size="small" onClick={() => handleDeleteClick(server)}>
                            <DeleteIcon />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Create Server Dialog */}
      <Dialog open={createDialogOpen} onClose={handleCreateDialogClose} maxWidth="sm" fullWidth>
        <DialogTitle>Add Inference Server</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FormControl fullWidth required>
              <InputLabel>Provider</InputLabel>
              <Select
                value={formData.provider}
                label="Provider"
                onChange={(e) => setFormData({ ...formData, provider: e.target.value as 'ollama' | 'lmstudio', config_json: {} })}
              >
                <MenuItem value="ollama">Ollama</MenuItem>
                <MenuItem value="lmstudio">LM Studio</MenuItem>
              </Select>
            </FormControl>
            <TextField
              fullWidth
              label="Server Name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
            <TextField
              fullWidth
              label="Server URL"
              value={formData.url}
              onChange={(e) => setFormData({ ...formData, url: e.target.value })}
              placeholder={formData.provider === 'ollama' ? 'http://localhost:11434' : 'http://localhost:1234'}
              required
              helperText={formData.provider === 'ollama'
                ? 'Include protocol and port (e.g., http://server:11434)'
                : 'Include protocol and port (e.g., http://server:1234)'}
            />
            {formData.provider === 'lmstudio' && (
              <>
                <TextField
                  fullWidth
                  label="Context Length"
                  type="number"
                  value={formData.config_json?.context_length || ''}
                  onChange={(e) => setFormData({
                    ...formData,
                    config_json: { ...formData.config_json, context_length: parseInt(e.target.value) || undefined }
                  })}
                  placeholder="32768"
                  helperText="Maximum context window size (optional)"
                />
                <TextField
                  fullWidth
                  label="GPU Offload"
                  value={formData.config_json?.gpu_offload || ''}
                  onChange={(e) => setFormData({
                    ...formData,
                    config_json: { ...formData.config_json, gpu_offload: e.target.value || undefined }
                  })}
                  placeholder="max"
                  helperText="GPU offload setting (e.g., 'max', '0', '32') (optional)"
                />
              </>
            )}
            <TextField
              fullWidth
              label="Model Name (optional)"
              value={formData.model_name || ''}
              onChange={(e) => setFormData({ ...formData, model_name: e.target.value || undefined })}
              placeholder={formData.provider === 'ollama' ? 'phi4:latest' : 'phi4-mlx'}
              helperText="Override the default model name for this server (leave empty to use global default)"
            />
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle2">Model Configuration Overrides (Optional)</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <TextField
                    fullWidth
                    label="Temperature"
                    type="number"
                    value={formData.model_config?.temperature ?? ''}
                    onChange={(e) => setFormData({
                      ...formData,
                      model_config: { ...formData.model_config, temperature: e.target.value ? parseFloat(e.target.value) : undefined }
                    })}
                    placeholder="0.7"
                    inputProps={{ step: 0.1, min: 0, max: 2 }}
                    helperText="Override temperature for this server"
                  />
                  <TextField
                    fullWidth
                    label="Max New Tokens"
                    type="number"
                    value={formData.model_config?.max_new_tokens ?? ''}
                    onChange={(e) => setFormData({
                      ...formData,
                      model_config: { ...formData.model_config, max_new_tokens: e.target.value ? parseInt(e.target.value) : undefined }
                    })}
                    placeholder="2048"
                    helperText="Override max_new_tokens for this server"
                  />
                  {formData.provider === 'ollama' && (
                    <TextField
                      fullWidth
                      label="Context Window (num_ctx)"
                      type="number"
                      value={formData.model_config?.num_ctx ?? ''}
                      onChange={(e) => setFormData({
                        ...formData,
                        model_config: { ...formData.model_config, num_ctx: e.target.value ? parseInt(e.target.value) : undefined }
                      })}
                      placeholder="131072"
                      helperText="Override Ollama context window size"
                    />
                  )}
                </Box>
              </AccordionDetails>
            </Accordion>
            <TextField
              fullWidth
              label="Notes (optional)"
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              multiline
              rows={2}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCreateDialogClose}>Cancel</Button>
          <Button
            onClick={handleCreateSubmit}
            variant="contained"
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? <CircularProgress size={20} /> : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit Server Dialog */}
      <Dialog open={editDialogOpen} onClose={handleEditDialogClose} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Inference Server</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FormControl fullWidth required>
              <InputLabel>Provider</InputLabel>
              <Select
                value={editFormData.provider}
                label="Provider"
                onChange={(e) => setEditFormData({ ...editFormData, provider: e.target.value as 'ollama' | 'lmstudio', config_json: {} })}
              >
                <MenuItem value="ollama">Ollama</MenuItem>
                <MenuItem value="lmstudio">LM Studio</MenuItem>
              </Select>
            </FormControl>
            <TextField
              fullWidth
              label="Server Name"
              value={editFormData.name}
              onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
              required
            />
            <TextField
              fullWidth
              label="Server URL"
              value={editFormData.url}
              onChange={(e) => setEditFormData({ ...editFormData, url: e.target.value })}
              placeholder={editFormData.provider === 'ollama' ? 'http://localhost:11434' : 'http://localhost:1234'}
              required
              helperText={editFormData.provider === 'ollama'
                ? 'Include protocol and port (e.g., http://server:11434)'
                : 'Include protocol and port (e.g., http://server:1234)'}
            />
            {editFormData.provider === 'lmstudio' && (
              <>
                <TextField
                  fullWidth
                  label="Context Length"
                  type="number"
                  value={editFormData.config_json?.context_length || ''}
                  onChange={(e) => setEditFormData({
                    ...editFormData,
                    config_json: { ...editFormData.config_json, context_length: parseInt(e.target.value) || undefined }
                  })}
                  placeholder="32768"
                  helperText="Maximum context window size (optional)"
                />
                <TextField
                  fullWidth
                  label="GPU Offload"
                  value={editFormData.config_json?.gpu_offload || ''}
                  onChange={(e) => setEditFormData({
                    ...editFormData,
                    config_json: { ...editFormData.config_json, gpu_offload: e.target.value || undefined }
                  })}
                  placeholder="max"
                  helperText="GPU offload setting (e.g., 'max', '0', '32') (optional)"
                />
              </>
            )}
            <TextField
              fullWidth
              label="Model Name (optional)"
              value={editFormData.model_name || ''}
              onChange={(e) => setEditFormData({ ...editFormData, model_name: e.target.value || undefined })}
              placeholder={editFormData.provider === 'ollama' ? 'phi4:latest' : 'phi4-mlx'}
              helperText="Override the default model name for this server (leave empty to use global default)"
            />
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle2">Model Configuration Overrides (Optional)</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <TextField
                    fullWidth
                    label="Temperature"
                    type="number"
                    value={editFormData.model_config?.temperature ?? ''}
                    onChange={(e) => setEditFormData({
                      ...editFormData,
                      model_config: { ...editFormData.model_config, temperature: e.target.value ? parseFloat(e.target.value) : undefined }
                    })}
                    placeholder="0.7"
                    inputProps={{ step: 0.1, min: 0, max: 2 }}
                    helperText="Override temperature for this server"
                  />
                  <TextField
                    fullWidth
                    label="Max New Tokens"
                    type="number"
                    value={editFormData.model_config?.max_new_tokens ?? ''}
                    onChange={(e) => setEditFormData({
                      ...editFormData,
                      model_config: { ...editFormData.model_config, max_new_tokens: e.target.value ? parseInt(e.target.value) : undefined }
                    })}
                    placeholder="2048"
                    helperText="Override max_new_tokens for this server"
                  />
                  {editFormData.provider === 'ollama' && (
                    <TextField
                      fullWidth
                      label="Context Window (num_ctx)"
                      type="number"
                      value={editFormData.model_config?.num_ctx ?? ''}
                      onChange={(e) => setEditFormData({
                        ...editFormData,
                        model_config: { ...editFormData.model_config, num_ctx: e.target.value ? parseInt(e.target.value) : undefined }
                      })}
                      placeholder="131072"
                      helperText="Override Ollama context window size"
                    />
                  )}
                </Box>
              </AccordionDetails>
            </Accordion>
            <TextField
              fullWidth
              label="Notes (optional)"
              value={editFormData.notes}
              onChange={(e) => setEditFormData({ ...editFormData, notes: e.target.value })}
              multiline
              rows={2}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={editFormData.enabled}
                  onChange={(e) => setEditFormData({ ...editFormData, enabled: e.target.checked })}
                />
              }
              label="Enabled"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleEditDialogClose}>Cancel</Button>
          <Button
            onClick={handleEditSubmit}
            variant="contained"
            disabled={updateMutation.isPending}
          >
            {updateMutation.isPending ? <CircularProgress size={20} /> : 'Update'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
        <DialogTitle>Delete Inference Server</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete the server "{serverToDelete?.name}"?
            This action cannot be undone.
          </Typography>
          {serverToDelete && (
            <>
              <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
                Provider: {serverToDelete.provider}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Server URL: {serverToDelete.url}
              </Typography>
            </>
          )}
          <Typography variant="body2" color="warning.main" sx={{ mt: 2 }}>
            Warning: Any bulk judge jobs using this server will be affected.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel}>Cancel</Button>
          <Button
            onClick={handleDeleteConfirm}
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? <CircularProgress size={20} /> : 'Delete Server'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default OllamaServersSettings;
