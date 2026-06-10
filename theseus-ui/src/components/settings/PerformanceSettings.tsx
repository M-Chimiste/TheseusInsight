import React, { useEffect, useState } from 'react';
import {
  Box, Button, Card, CardContent, CircularProgress, FormControlLabel,
  Paper, Slider, Switch, TextField, Tooltip, Typography,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import SpeedIcon from '@mui/icons-material/Speed';
import MemoryIcon from '@mui/icons-material/Memory';
import DeveloperModeIcon from '@mui/icons-material/DeveloperMode';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { performanceApi } from '../../services/api';
import type { PerformanceConfig, SystemInfo } from '../../services/api';
import { useSnackbar } from '../../contexts/SnackbarContext';

/** Hardware/performance tuning (extracted from Settings.tsx in F3). */
export const PerformanceSettings: React.FC = () => {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useSnackbar();

  // Performance Configuration State
  const [performanceConfig, setPerformanceConfig] = useState<PerformanceConfig | null>(null);

  // Performance Configuration Queries
  const { data: systemInfo, isLoading: isLoadingSystemInfo } = useQuery<SystemInfo>({
    queryKey: ['systemInfo'],
    queryFn: () => performanceApi.getSystemInfo(),
  });


  const { data: currentPerformanceConfig, isLoading: isLoadingPerformanceConfig } = useQuery<PerformanceConfig>({
    queryKey: ['performanceConfig'],
    queryFn: () => performanceApi.getPerformanceConfig(),
  });


  const updatePerformanceConfigMutation = useMutation({
    mutationFn: (config: PerformanceConfig) => performanceApi.updatePerformanceConfig(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['performanceConfig'] });
      showSuccess('Performance configuration updated successfully');
    },
    onError: (error: any) => showError(error.message || 'Failed to update performance configuration'),
  });


  // Initialize performance config when loaded
  useEffect(() => {
    if (currentPerformanceConfig && !performanceConfig) {
      setPerformanceConfig(currentPerformanceConfig);
    }
  }, [currentPerformanceConfig, performanceConfig]);


  // Helper functions for performance configuration
  const handlePerformanceConfigChange = (field: keyof PerformanceConfig, value: any) => {
    if (performanceConfig) {
      setPerformanceConfig({
        ...performanceConfig,
        [field]: value,
      });
    }
  };

  const applyRecommendedConfig = () => {
    if (systemInfo?.recommended_config) {
      setPerformanceConfig(systemInfo.recommended_config);
    }
  };

  const savePerformanceConfig = () => {
    if (performanceConfig) {
      updatePerformanceConfigMutation.mutate(performanceConfig);
    }
  };


  return (
    <>
      {/* Performance Configuration Section */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5" fontWeight={600} sx={{ flex: 1 }}>
              <SpeedIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              Performance Configuration
            </Typography>
            <Tooltip title="Optimize performance for your hardware. Configure CPU cores, memory usage, and processing parameters for maximum efficiency.">
              <InfoOutlinedIcon color="action" />
            </Tooltip>
          </Box>
          <Typography variant="body2" sx={{ mb: 3 }}>
            Optimize Theseus Insight for your hardware resources. Configure parallelization, memory usage, and processing parameters to maximize performance.
          </Typography>

          {/* System Information */}
          {systemInfo && (
            <Paper sx={{ 
              p: 3, 
              mb: 3, 
              bgcolor: 'background.default',
              border: '1px solid',
              borderColor: 'divider'
            }}>
              <Typography variant="h6" gutterBottom>
                <MemoryIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                System Information
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <Box sx={{ minWidth: 200 }}>
                  <Typography variant="body2" color="text.secondary">CPU Cores</Typography>
                  <Typography variant="h6">{systemInfo.cpu_count_logical} ({systemInfo.cpu_count_physical} physical)</Typography>
                </Box>
                <Box sx={{ minWidth: 200 }}>
                  <Typography variant="body2" color="text.secondary">Memory</Typography>
                  <Typography variant="h6">{systemInfo.memory_total_gb.toFixed(1)} GB</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {systemInfo.memory_available_gb.toFixed(1)} GB available
                  </Typography>
                </Box>
                <Box sx={{ minWidth: 200 }}>
                  <Typography variant="body2" color="text.secondary">GPU</Typography>
                  <Typography variant="h6">{systemInfo.gpu_available ? '✅ Available' : '❌ None'}</Typography>
                  {systemInfo.gpu_name && (
                    <Typography variant="caption" color="text.secondary">{systemInfo.gpu_name}</Typography>
                  )}
                </Box>
                <Box sx={{ minWidth: 200, display: 'flex', alignItems: 'flex-end' }}>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={applyRecommendedConfig}
                    disabled={!systemInfo.recommended_config}
                  >
                    Apply Recommended
                  </Button>
                </Box>
              </Box>
            </Paper>
          )}

          {/* Performance Configuration Controls */}
          {performanceConfig && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              
              {/* Hardware Resources */}
              <Box>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                  <SpeedIcon sx={{ mr: 1 }} />
                  Hardware Resources
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                  <Box sx={{ flex: '1 1 300px' }}>
                    <Typography gutterBottom>
                      Max CPU Cores: {performanceConfig.max_cores}
                    </Typography>
                    <Slider
                      value={performanceConfig.max_cores}
                      onChange={(_, value) => handlePerformanceConfigChange('max_cores', value)}
                      min={1}
                      max={systemInfo?.cpu_count_logical || 32}
                      step={1}
                      marks
                      valueLabelDisplay="auto"
                    />
                  </Box>
                  <Box sx={{ flex: '1 1 300px' }}>
                    <Typography gutterBottom>
                      Max Memory: {performanceConfig.max_memory_gb} GB
                    </Typography>
                    <Slider
                      value={performanceConfig.max_memory_gb}
                      onChange={(_, value) => handlePerformanceConfigChange('max_memory_gb', value)}
                      min={4}
                      max={systemInfo?.memory_total_gb || 64}
                      step={1}
                      marks
                      valueLabelDisplay="auto"
                    />
                  </Box>
                </Box>
              </Box>

              {/* Clustering Optimization */}
              <Box>
                <Typography variant="h6" gutterBottom>
                  🧠 Clustering & Topic Extraction
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                  <Box sx={{ flex: '1 1 300px' }}>
                    <TextField
                      fullWidth
                      label="HDBSCAN Parallel Jobs"
                      type="number"
                      value={performanceConfig.hdbscan_n_jobs}
                      onChange={(e) => handlePerformanceConfigChange('hdbscan_n_jobs', parseInt(e.target.value))}
                      helperText="-1 = use all cores, 1 = single threaded"
                      inputProps={{ min: -1, max: 128 }}
                    />
                  </Box>
                  <Box sx={{ flex: '1 1 300px' }}>
                    <TextField
                      fullWidth
                      label="Clustering Batch Size"
                      type="number"
                      value={performanceConfig.clustering_batch_size}
                      onChange={(e) => handlePerformanceConfigChange('clustering_batch_size', parseInt(e.target.value))}
                      helperText="Papers processed per batch"
                      inputProps={{ min: 1000, max: 1000000 }}
                    />
                  </Box>
                </Box>
              </Box>

              {/* Vector Processing */}
              <Box>
                <Typography variant="h6" gutterBottom>
                  🔢 Vector & Embedding Processing
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                  <Box sx={{ flex: '1 1 300px' }}>
                    <TextField
                      fullWidth
                      label="Embedding Batch Size"
                      type="number"
                      value={performanceConfig.embedding_batch_size}
                      onChange={(e) => handlePerformanceConfigChange('embedding_batch_size', parseInt(e.target.value))}
                      helperText={performanceConfig.auto_tune_batch_size ? "Auto-tuned on first run" : "Embeddings computed per batch"}
                      inputProps={{ min: 32, max: 2048 }}
                      disabled={performanceConfig.auto_tune_batch_size}
                    />
                    <FormControlLabel
                      control={
                        <Switch
                          checked={performanceConfig.auto_tune_batch_size !== false}
                          onChange={(e) => handlePerformanceConfigChange('auto_tune_batch_size', e.target.checked)}
                        />
                      }
                      label={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          Auto-tune Batch Size
                          <Tooltip title="Automatically optimizes batch size for your hardware on first run. Recommended for best performance.">
                            <InfoOutlinedIcon fontSize="small" />
                          </Tooltip>
                        </Box>
                      }
                    />
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                      Auto-tuning tests 256, 512, 1024, and 2048 batch sizes to find optimal throughput for your GPU
                    </Typography>
                  </Box>
                  <Box sx={{ flex: '1 1 300px' }}>
                    <TextField
                      fullWidth
                      label="Vector Processing Workers"
                      type="number"
                      value={performanceConfig.vector_processing_workers}
                      onChange={(e) => handlePerformanceConfigChange('vector_processing_workers', parseInt(e.target.value))}
                      helperText="Parallel workers for vector operations"
                      inputProps={{ min: 1, max: 64 }}
                    />
                  </Box>
                </Box>
              </Box>

              {/* Memory Management */}
              <Box>
                <Typography variant="h6" gutterBottom>
                  💾 Memory Management
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                  <Box sx={{ flex: '1 1 300px' }}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={performanceConfig.enable_memory_mapping}
                          onChange={(e) => handlePerformanceConfigChange('enable_memory_mapping', e.target.checked)}
                        />
                      }
                      label="Memory Mapping"
                    />
                    <Typography variant="caption" color="text.secondary" display="block">
                      Use memory-mapped files for large datasets
                    </Typography>
                  </Box>
                  <Box sx={{ flex: '1 1 300px' }}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={performanceConfig.cache_embeddings}
                          onChange={(e) => handlePerformanceConfigChange('cache_embeddings', e.target.checked)}
                        />
                      }
                      label="Cache Embeddings"
                    />
                    <Typography variant="caption" color="text.secondary" display="block">
                      Keep embeddings in memory for faster access
                    </Typography>
                  </Box>
                  <Box sx={{ flex: '1 1 300px' }}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={performanceConfig.aggressive_garbage_collection}
                          onChange={(e) => handlePerformanceConfigChange('aggressive_garbage_collection', e.target.checked)}
                        />
                      }
                      label="Aggressive GC"
                    />
                    <Typography variant="caption" color="text.secondary" display="block">
                      Force garbage collection between stages
                    </Typography>
                  </Box>
                </Box>
              </Box>

              {/* Development Mode */}
              <Box>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                  <DeveloperModeIcon sx={{ mr: 1 }} />
                  Development Mode
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                  <Box sx={{ flex: '1 1 300px' }}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={performanceConfig.development_mode}
                          onChange={(e) => handlePerformanceConfigChange('development_mode', e.target.checked)}
                        />
                      }
                      label="Enable Development Mode"
                    />
                    <Typography variant="caption" color="text.secondary" display="block">
                      Limit dataset size for faster iteration during development
                    </Typography>
                  </Box>
                  {performanceConfig.development_mode && (
                    <Box sx={{ flex: '1 1 300px' }}>
                      <TextField
                        fullWidth
                        label="Max Papers (Dev Mode)"
                        type="number"
                        value={performanceConfig.development_max_papers}
                        onChange={(e) => handlePerformanceConfigChange('development_max_papers', parseInt(e.target.value))}
                        helperText="Maximum papers processed in development mode"
                        inputProps={{ min: 100, max: 50000 }}
                      />
                    </Box>
                  )}
                </Box>
              </Box>

              {/* Save Button */}
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, mt: 3 }}>
                <Button
                  variant="outlined"
                  onClick={applyRecommendedConfig}
                  disabled={!systemInfo?.recommended_config}
                >
                  Reset to Recommended
                </Button>
                <Button
                  variant="contained"
                  onClick={savePerformanceConfig}
                  disabled={updatePerformanceConfigMutation.isPending}
                  startIcon={updatePerformanceConfigMutation.isPending ? <CircularProgress size={20} /> : undefined}
                >
                  Save Performance Settings
                </Button>
              </Box>
            </Box>
          )}

          {/* Loading States */}
          {(isLoadingSystemInfo || isLoadingPerformanceConfig) && (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
              <Typography sx={{ ml: 2 }}>Loading performance configuration...</Typography>
            </Box>
          )}
        </CardContent>
      </Card>

    </>
  );
};
