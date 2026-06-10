import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Switch,
  FormControlLabel,
  Button,
  Alert,
  Snackbar,
  CircularProgress,
  Container,
  Tabs,
  Tab,
  Tooltip,
  IconButton,
  Autocomplete,
  Slider,
  Paper,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi, modelCatalogApi, performanceApi, ollamaServersApi } from '../services/api';
import type { PerformanceConfig, SystemInfo } from '../services/api';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import SettingsIcon from '@mui/icons-material/Settings';
import SpeedIcon from '@mui/icons-material/Speed';
import MemoryIcon from '@mui/icons-material/Memory';
import DeveloperModeIcon from '@mui/icons-material/DeveloperMode';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import PaletteIcon from '@mui/icons-material/Palette';
import { useTheme as useCustomTheme } from '../contexts/ThemeContext';
import { useLayout } from '../contexts/LayoutContext';
import { ScheduledTasksSettings } from '../components/ScheduledTasksSettings';
import OllamaServersSettings from '../components/OllamaServersSettings';
import { TabPanel } from '../components/settings/TabPanel';
import { ModelNameAutocomplete } from '../components/settings/ModelNameAutocomplete';
import { CredentialsSettings } from '../components/settings/CredentialsSettings';
import { DatabaseTransferSettings } from '../components/settings/DatabaseTransferSettings';
import { ResearchAgentSettings } from '../components/settings/ResearchAgentSettings';
import type { ModelCatalogOption } from '../components/settings/ModelNameAutocomplete';


const MODEL_TABS = [
  { key: 'embedding_model', label: 'Embedding Model', tooltip: 'Used for vector search and similarity.' },
  { key: 'judge_model', label: 'Judge Model', tooltip: 'Used for ranking and scoring papers.' },
  { key: 'content_extraction_model', label: 'Content Extraction Model', tooltip: 'Extracts content from papers.' },
  { key: 'newsletter_sections_model', label: 'Newsletter Sections Model', tooltip: 'Generates newsletter sections.' },
  { key: 'newsletter_intro_model', label: 'Newsletter Intro Model', tooltip: 'Generates newsletter introduction.' },
  { key: 'podcast_model', label: 'Podcast Model', tooltip: 'Used for podcast generation.' },
  { key: 'tts_model', label: 'TTS Model', tooltip: 'Text-to-speech for podcast.' },
  { key: 'mind_map_config', label: 'Mind-Map Explorer', tooltip: 'Configuration for mind-map visualization and paper relationship exploration.' },
  { key: 'inference_servers', label: 'Inference Servers', tooltip: 'Configure multiple Ollama and LMStudio servers for distributed bulk processing.' },
];


const Settings: React.FC = () => {
  const queryClient = useQueryClient();
  const { isDarkMode, toggleTheme } = useCustomTheme();
  const { headerHeight } = useLayout(); // Get dynamic header height
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [tab, setTab] = useState(0);

  
  const { data: orchestrationConfig, isLoading: isLoadingOrchestration, isError: isErrorOrchestration } = useQuery({
    queryKey: ['orchestrationConfig'],
    queryFn: () => settingsApi.getOrchestrationConfig().then(res => res.data),
  });

  const { data: modelProviders, isLoading: isLoadingProviders, isError: isErrorProviders } = useQuery<any[], Error>({
    queryKey: ['modelProviders'],
    queryFn: () => settingsApi.getModelProviders().then(res => res.data || []),
  });

  // Query for model catalog to enable autocomplete
  const { data: modelCatalogData } = useQuery({
    queryKey: ['modelCatalogForSettings'],
    queryFn: () => modelCatalogApi.searchModels({
      page: 1,
      page_size: 100  // Maximum allowed by backend validation
    }).then(res => res.data),
  });

  // Query for inference servers to provide host autocomplete
  const { data: inferenceServers } = useQuery({
    queryKey: ['inferenceServersForSettings'],
    queryFn: () => ollamaServersApi.getAllServers().then((res: any) => res.data)
  });

  // Helper function to get hosts filtered by provider
  const getHostsByProvider = React.useCallback((provider: 'ollama' | 'lmstudio' | 'custom-oai') => {
    if (!inferenceServers || !Array.isArray(inferenceServers)) return [];

    // For custom-oai, we could show all hosts or none - let's show all
    if (provider === 'custom-oai') {
      const hosts = inferenceServers.map((server: any) => server.url);
      return Array.from(new Set(hosts)).sort();
    }

    // Filter by provider and extract URLs
    const hosts = inferenceServers
      .filter((server: any) => server.provider === provider)
      .map((server: any) => server.url);
    return Array.from(new Set(hosts)).sort();
  }, [inferenceServers]);

  // Query for research profiles (for profile-scoped export)
  const updateOrchestrationMutation = useMutation({
    mutationFn: (newConfig: any) => settingsApi.updateOrchestrationConfig(newConfig),
    onSuccess: (data) => {
      queryClient.setQueryData(['orchestrationConfig'], data.data); // Assuming API returns the updated config
      queryClient.invalidateQueries({ queryKey: ['orchestrationConfig'] });
      setSuccess('Configuration updated successfully');
    },
    onError: (error: any) => setError(error.message || 'Failed to update configuration'),
  });

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
      setSuccess('Performance configuration updated successfully');
    },
    onError: (error: any) => setError(error.message || 'Failed to update performance configuration'),
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

  const handleModelConfigChange = (modelKey: string, field: string, value: any) => {
    // Handle regular orchestration config
    if (!orchestrationConfig) {
      return;
    }
    const newOrchestrationConfig = JSON.parse(JSON.stringify(orchestrationConfig)); // Deep copy
    
    if (!newOrchestrationConfig[modelKey]) {
      newOrchestrationConfig[modelKey] = {};
    }
    
    // Handle nested paths like "boss_model.model_name" or "worker_models.summary.temperature"
    if (field.includes('.')) {
      const fieldParts = field.split('.');
      let currentObj = newOrchestrationConfig[modelKey];
      
      // Navigate to the parent object
      for (let i = 0; i < fieldParts.length - 1; i++) {
        if (!currentObj[fieldParts[i]]) {
          currentObj[fieldParts[i]] = {};
        }
        currentObj = currentObj[fieldParts[i]];
      }
      
      // Set the final value
      currentObj[fieldParts[fieldParts.length - 1]] = value;
    } else {
      newOrchestrationConfig[modelKey][field] = value;
    }
    
    // Optimistically update local state for UI responsiveness
    queryClient.setQueryData(['orchestrationConfig'], newOrchestrationConfig);
  };

  // Handle when a model is selected from the catalog - auto-populate other fields
  const handleModelSelectedFromCatalog = (modelKey: string, selectedOption: ModelCatalogOption, prefix?: string) => {
    // Find the full catalog entry to get all the metadata
    const fullCatalogEntry = modelCatalogData?.models?.find((model: any) => 
      model.id === selectedOption.id
    );

    if (!fullCatalogEntry) {
      return;
    }

    // Build model data object with all fields to update
    const modelData: any = {};

    // Always include the model_name when selecting from catalog
    modelData.model_name = fullCatalogEntry.model_string;

    // model_type should match provider names from the modelProviders query
    if (fullCatalogEntry.provider_name) {
      modelData.model_type = fullCatalogEntry.provider_name;
    }

    // Populate other fields from catalog if they exist
    if (fullCatalogEntry.max_new_tokens !== null && fullCatalogEntry.max_new_tokens !== undefined) {
      modelData.max_new_tokens = fullCatalogEntry.max_new_tokens;
    }

    if (fullCatalogEntry.temperature !== null && fullCatalogEntry.temperature !== undefined) {
      modelData.temperature = fullCatalogEntry.temperature;
    }

    if (fullCatalogEntry.num_ctx !== null && fullCatalogEntry.num_ctx !== undefined) {
      modelData.num_ctx = fullCatalogEntry.num_ctx;
    }

    // Only include trust_remote_code for sentence-transformers models
    if (fullCatalogEntry.provider_name === 'sentence-transformers') {
      modelData.trust_remote_code = fullCatalogEntry.trust_remote_code !== null ? fullCatalogEntry.trust_remote_code : false;
    }

    // Apply all fields in a single batch update to avoid race conditions
    if (Object.keys(modelData).length > 0) {
      if (!orchestrationConfig) {
        return;
      }
      const newOrchestrationConfig = JSON.parse(JSON.stringify(orchestrationConfig)); // Deep copy
      
      if (!newOrchestrationConfig[modelKey]) {
        newOrchestrationConfig[modelKey] = {};
      }
      
      // Apply all fields to the config
      Object.entries(modelData).forEach(([field, value]) => {
        const fieldPath = prefix ? `${prefix}.${field}` : field;
        
        if (fieldPath.includes('.')) {
          const fieldParts = fieldPath.split('.');
          let currentObj = newOrchestrationConfig[modelKey];
          
          for (let i = 0; i < fieldParts.length - 1; i++) {
            if (!currentObj[fieldParts[i]]) {
              currentObj[fieldParts[i]] = {};
            }
            currentObj = currentObj[fieldParts[i]];
          }
          
          currentObj[fieldParts[fieldParts.length - 1]] = value;
        } else {
          newOrchestrationConfig[modelKey][fieldPath] = value;
        }
      });
      
      queryClient.setQueryData(['orchestrationConfig'], newOrchestrationConfig);
    }
  };

  const renderModelConfigFields = (modelKey: string, config: any) => {
    if (!config) return <Typography>Configuration not available for {modelKey}.</Typography>;

    const currentConfig = orchestrationConfig?.[modelKey] || {};

    // TTS model is a special case (single column)
    if (modelKey === 'tts_model') {
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <FormControl fullWidth>
            <InputLabel>TTS Provider</InputLabel>
            <Select
              value={currentConfig.tts_provider || ''}
              label="TTS Provider"
              onChange={e => handleModelConfigChange(modelKey, 'tts_provider', e.target.value)}
            >
              {(modelProviders || []).map((provider: any) => (
                <MenuItem key={provider.name} value={provider.name}>
                  {provider.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <ModelNameAutocomplete
            label="TTS Model Name"
            value={currentConfig.tts_model_name || ''}
            onChange={value => handleModelConfigChange(modelKey, 'tts_model_name', value)}
            onModelSelected={selectedModel => handleModelSelectedFromCatalog(modelKey, selectedModel)}
            modelCatalogData={modelCatalogData}
          />
          <TextField
            fullWidth
            label="Speaker 1 Voice"
            value={currentConfig.speaker_1_voice || ''}
            onChange={e => handleModelConfigChange(modelKey, 'speaker_1_voice', e.target.value)}
          />
           <TextField
            fullWidth
            label="Speaker 1 Speed"
            type="number"
            inputProps={{ step: "0.1" }}
            value={currentConfig.speaker_1_speed || 1.0}
            onChange={e => handleModelConfigChange(modelKey, 'speaker_1_speed', parseFloat(e.target.value))}
          />
          <TextField
            fullWidth
            label="Speaker 2 Voice"
            value={currentConfig.speaker_2_voice || ''}
            onChange={e => handleModelConfigChange(modelKey, 'speaker_2_voice', e.target.value)}
          />
          <TextField
            fullWidth
            label="Speaker 2 Speed"
            type="number"
            inputProps={{ step: "0.1" }}
            value={currentConfig.speaker_2_speed || 1.0}
            onChange={e => handleModelConfigChange(modelKey, 'speaker_2_speed', parseFloat(e.target.value))}
          />
        </Box>
      );
    }

    // Mind-Map configuration is a special case (parameters + model)
    if (modelKey === 'mind_map_config') {
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Mind-Map Parameters */}
          <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1, backgroundColor: 'background.default' }}>
            <Typography variant="h6" gutterBottom>
              Mind-Map Parameters
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, alignItems: 'flex-start' }}>
              <TextField
                label="Number of Neighbors"
                type="number"
                value={currentConfig.k || 15}
                onChange={(e) => handleModelConfigChange(modelKey, 'k', Number(e.target.value))}
                inputProps={{ min: 5, max: 50, step: 1 }}
                helperText="Number of similar papers to retrieve (5-50)"
                sx={{ minWidth: 200, flex: '1 1 200px' }}
              />
              <TextField
                label="Similarity Threshold"
                type="number"
                value={currentConfig.similarity_threshold || 0.3}
                onChange={(e) => handleModelConfigChange(modelKey, 'similarity_threshold', parseFloat(e.target.value))}
                inputProps={{ min: 0.1, max: 0.95, step: 0.05 }}
                helperText="Minimum similarity threshold (0.1-0.95)"
                sx={{ minWidth: 200, flex: '1 1 200px' }}
              />
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, minWidth: 200, flex: '1 1 200px' }}>
                <Box sx={{ flex: 1 }}>
                  <FormControl fullWidth>
                    <InputLabel>Layout Algorithm</InputLabel>
                    <Select
                      value={currentConfig.layout_algorithm || 'force'}
                      label="Layout Algorithm"
                      onChange={(e) => handleModelConfigChange(modelKey, 'layout_algorithm', e.target.value)}
                    >
                      <MenuItem value="force">
                         <Tooltip title="Physics-based layout that simulates forces between nodes, creating natural clustering and spacing. Best for exploring relationships organically." placement="right">
                           <span>Force-Directed</span>
                         </Tooltip>
                       </MenuItem>
                    </Select>
                  </FormControl>
                  <Box sx={{ mt: 0.5, fontSize: '0.75rem', color: 'text.secondary', minHeight: '1.5em' }}>
                    Choose layout algorithm for node arrangement
                  </Box>
                </Box>
                <Tooltip title="Choose how papers are visually arranged in the mind-map. Each algorithm reveals different relationship patterns." placement="top">
                  <IconButton size="small" sx={{ mt: 1 }}>
                    <InfoOutlinedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>
            
            {/* Multi-Order Expansion Settings */}
            <Typography variant="body2" color="primary" sx={{ mt: 2, mb: 1, fontWeight: 'medium' }}>
              Multi-Order Expansion
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, alignItems: 'flex-start' }}>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, minWidth: 200, flex: '1 1 200px' }}>
                <Box sx={{ flex: 1 }}>
                  <TextField
                    label="Expansion Order"
                    type="number"
                    value={currentConfig.expansion_order || 1}
                    onChange={(e) => handleModelConfigChange(modelKey, 'expansion_order', Number(e.target.value))}
                    inputProps={{ min: 1, max: 5, step: 1 }}
                    helperText="Number of expansion orders (1-5)"
                    fullWidth
                  />
                  <Box sx={{ mt: 0.5, fontSize: '0.75rem', color: 'text.secondary', minHeight: '1.5em' }}>
                    1st order = direct neighbors, 2nd order = neighbors of neighbors, etc.
                  </Box>
                </Box>
                <Tooltip title="Higher orders exponentially expand the graph by finding papers similar to each retrieved paper. Order 1 finds papers similar to the seed. Order 2 finds papers similar to each Order 1 paper, and so on." placement="top">
                  <IconButton size="small" sx={{ mt: 1 }}>
                    <InfoOutlinedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
              
              <TextField
                label="Max Nodes per Order"
                type="number"
                value={currentConfig.max_nodes_per_order || 20}
                onChange={(e) => handleModelConfigChange(modelKey, 'max_nodes_per_order', Number(e.target.value))}
                inputProps={{ min: 5, max: 50, step: 1 }}
                helperText="Maximum nodes to expand from each paper in multi-order expansion (5-50)"
                sx={{ minWidth: 200, flex: '1 1 200px' }}
              />
            </Box>
          </Box>

          {/* Summarization Model */}
          <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1, backgroundColor: 'background.default' }}>
            <Typography variant="h6" gutterBottom>
              Summarization Model
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Model used to generate paper summaries for the mind-map nodes.
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                <ModelNameAutocomplete
                  label="Model Name"
                  value={currentConfig.summarization_model?.model_name || ''}
                  onChange={value => handleModelConfigChange(modelKey, 'summarization_model.model_name', value)}
                  onModelSelected={selectedModel => handleModelSelectedFromCatalog(modelKey, selectedModel, 'summarization_model')}
                  modelCatalogData={modelCatalogData}
                />
                <FormControl fullWidth>
                  <InputLabel>Model Type (Provider)</InputLabel>
                  <Select
                    value={currentConfig.summarization_model?.model_type || ''}
                    label="Model Type (Provider)"
                    onChange={e => handleModelConfigChange(modelKey, 'summarization_model.model_type', e.target.value)}
                  >
                    {(modelProviders || []).map((provider: any) => (
                      <MenuItem key={provider.id} value={provider.name}>
                        {provider.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>
              <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField
                  fullWidth
                  label="Max New Tokens"
                  type="number"
                  value={currentConfig.summarization_model?.max_new_tokens || 1024}
                  onChange={e => handleModelConfigChange(modelKey, 'summarization_model.max_new_tokens', Number(e.target.value))}
                />
                <TextField
                  fullWidth
                  label="Temperature"
                  type="number"
                  inputProps={{ step: '0.1' }}
                  value={currentConfig.summarization_model?.temperature || 0.3}
                  onChange={e => handleModelConfigChange(modelKey, 'summarization_model.temperature', parseFloat(e.target.value))}
                />
                {(currentConfig.summarization_model?.model_type === 'ollama' || currentConfig.summarization_model?.model_type === 'llamacpp' || currentConfig.summarization_model?.model_type === 'lmstudio') && (
                  <TextField
                    fullWidth
                    label="Context Window (num_ctx)"
                    type="number"
                    value={currentConfig.summarization_model?.num_ctx || 4096}
                    onChange={e => handleModelConfigChange(modelKey, 'summarization_model.num_ctx', Number(e.target.value))}
                  />
                )}
                {(currentConfig.summarization_model?.model_type === 'ollama' || currentConfig.summarization_model?.model_type === 'lmstudio' || currentConfig.summarization_model?.model_type === 'custom-oai') && (
                  <Autocomplete
                    fullWidth
                    freeSolo
                    options={getHostsByProvider(currentConfig.summarization_model?.model_type as 'ollama' | 'lmstudio' | 'custom-oai')}
                    value={currentConfig.summarization_model?.host || ''}
                    onInputChange={(_, newInputValue) => {
                      handleModelConfigChange(modelKey, 'summarization_model.host', newInputValue || undefined);
                    }}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Host (Optional)"
                        placeholder={
                          currentConfig.summarization_model?.model_type === 'ollama' ? 'athena.local:11434' :
                          currentConfig.summarization_model?.model_type === 'lmstudio' ? 'localhost:1234' :
                          'http://custom-server:8000'
                        }
                        helperText="Custom host for this model (leave empty to use environment default)"
                      />
                    )}
                  />
                )}
              </Box>
            </Box>
          </Box>
        </Box>
      );
    }

    // General model config (two-column layout using Box)
    return (
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          <ModelNameAutocomplete
            label="Model Name"
            value={currentConfig.model_name || ''}
            onChange={value => handleModelConfigChange(modelKey, 'model_name', value)}
            onModelSelected={selectedModel => handleModelSelectedFromCatalog(modelKey, selectedModel)}
            modelCatalogData={modelCatalogData}
          />
          <FormControl fullWidth>
            <InputLabel>Model Type (Provider)</InputLabel>
            <Select
              value={currentConfig.model_type || ''}
              label="Model Type (Provider)"
              onChange={e => handleModelConfigChange(modelKey, 'model_type', e.target.value)}
            >
              {(modelProviders || []).map((provider: any) => (
                <MenuItem key={provider.id} value={provider.name}>
                  {provider.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
        <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {typeof currentConfig.max_new_tokens === 'number' && (
            <TextField
              fullWidth
              label="Max New Tokens"
              type="number"
              value={currentConfig.max_new_tokens}
              onChange={e => handleModelConfigChange(modelKey, 'max_new_tokens', Number(e.target.value))}
            />
          )}
          {typeof currentConfig.temperature === 'number' && (
            <TextField
              fullWidth
              label="Temperature"
              type="number"
              inputProps={{ step: '0.1' }}
              value={currentConfig.temperature}
              onChange={e => handleModelConfigChange(modelKey, 'temperature', parseFloat(e.target.value))}
            />
          )}
          {typeof currentConfig.num_ctx === 'number' && ( // Only show for certain providers
             (currentConfig.model_type === 'ollama' || currentConfig.model_type === 'llamacpp' || currentConfig.model_type === 'lmstudio')
          ) && (
            <TextField
              fullWidth
              label="Context Window (num_ctx)"
              type="number"
              value={currentConfig.num_ctx}
              onChange={e => handleModelConfigChange(modelKey, 'num_ctx', Number(e.target.value))}
            />
          )}
          {(currentConfig.model_type === 'ollama' || currentConfig.model_type === 'lmstudio' || currentConfig.model_type === 'custom-oai') && (
            <Autocomplete
              fullWidth
              freeSolo
              options={getHostsByProvider(currentConfig.model_type as 'ollama' | 'lmstudio' | 'custom-oai')}
              value={currentConfig.host || ''}
              onInputChange={(_, newInputValue) => {
                handleModelConfigChange(modelKey, 'host', newInputValue || undefined);
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Host (Optional)"
                  placeholder={
                    currentConfig.model_type === 'ollama' ? 'athena.local:11434' :
                    currentConfig.model_type === 'lmstudio' ? 'localhost:1234' :
                    'http://custom-server:8000'
                  }
                  helperText="Custom host for this model (leave empty to use environment default)"
                />
              )}
            />
          )}
          {currentConfig.model_type === 'sentence-transformers' && (
            <FormControlLabel
              control={
                <Switch
                  checked={currentConfig.trust_remote_code || false}
                  onChange={e => handleModelConfigChange(modelKey, 'trust_remote_code', e.target.checked)}
                />
              }
              label={
                <Box display="flex" alignItems="center" gap={0.5}>
                  Trust Remote Code
                  <Tooltip title="Allow loading remote code for this model. Required for some sentence-transformers models.">
                    <IconButton size="small">
                      <InfoOutlinedIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              }
            />
          )}
        </Box>
      </Box>
    );
  };

  if (isLoadingOrchestration || isLoadingProviders) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh" sx={{ pt: `${headerHeight + 24}px` }}>
        <CircularProgress />
      </Box>
    );
  }
  
  if (isErrorOrchestration) setError('Failed to load orchestration config.');
  if (isErrorProviders) setError('Failed to load model providers.');

  return (
    <Container maxWidth="lg" sx={{ pt: `${headerHeight + 32}px`, pb: 4 }}>
      <Snackbar
        open={Boolean(error)}
        autoHideDuration={4000}
        onClose={() => setError(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert onClose={() => setError(null)} severity="error" sx={{ width: '100%' }}>
          {error}
        </Alert>
      </Snackbar>

      <Snackbar
        open={Boolean(success)}
        autoHideDuration={4000}
        onClose={() => setSuccess(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert onClose={() => setSuccess(null)} severity="success" sx={{ width: '100%' }}>
          {success}
        </Alert>
      </Snackbar>

      <Typography variant="h4" gutterBottom component="div" sx={{ mb: 3 }}>
        <SettingsIcon sx={{ mr: 1, verticalAlign: 'middle' }}/> Settings
      </Typography>

      {/* Model Configuration Section */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5" fontWeight={600} sx={{ flex: 1 }}>
              Model Configuration
            </Typography>
            <Tooltip title="Configure the models used for different aspects of newsletter and podcast generation.">
              <InfoOutlinedIcon color="action" />
            </Tooltip>
          </Box>
          <Tabs
            value={tab}
            onChange={(_, newValue) => setTab(newValue)}
            variant="scrollable"
            scrollButtons="auto"
            aria-label="Model Configuration Tabs"
            sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}
          >
            {MODEL_TABS.map((tabDef, idx) => (
              <Tab
                key={tabDef.key}
                label={
                  <Box display="flex" alignItems="center" gap={1}>
                    {tabDef.label}
                    <Tooltip title={tabDef.tooltip}>
                      <InfoOutlinedIcon fontSize="small" />
                    </Tooltip>
                  </Box>
                }
                id={`model-tab-${idx}`}
                aria-controls={`model-tabpanel-${idx}`}
              />
            ))}
          </Tabs>
          {MODEL_TABS.map((tabDef, idx) => (
            <TabPanel value={tab} index={idx} key={tabDef.key}>
              <Card variant="outlined"> {/* Card for each model's settings */}
                <CardContent>
                  <Typography variant="h6" gutterBottom component="div">
                    {tabDef.label} Settings
                  </Typography>

                  {/* Special handling for Inference servers (Ollama & LMStudio) */}
                  {tabDef.key === 'inference_servers' ? (
                    <OllamaServersSettings />
                  ) : orchestrationConfig && orchestrationConfig[tabDef.key] ? (
                    renderModelConfigFields(tabDef.key, orchestrationConfig[tabDef.key])
                  ) : (
                    <Typography>Loading configuration for {tabDef.label}...</Typography>
                  )}

                  {/* Only show save button for non-Inference servers tabs */}
                  {tabDef.key !== 'inference_servers' && (
                    <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
                      <Button
                        variant="contained"
                        onClick={() => {
                          if (!orchestrationConfig) return;

                          // Create a mutable copy of the config to be sent
                          const configToUpdate = JSON.parse(JSON.stringify(orchestrationConfig));
                          updateOrchestrationMutation.mutate(configToUpdate);
                        }}
                        disabled={updateOrchestrationMutation.isPending}
                      >
                        Save {tabDef.label} Settings
                      </Button>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </TabPanel>
          ))}
        </CardContent>
      </Card>

      {/* Research Agent Configuration Section */}
      <ResearchAgentSettings
        modelCatalogData={modelCatalogData}
        modelProviders={modelProviders}
        getHostsByProvider={getHostsByProvider}
      />

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

      {/* Theme Preferences Section */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5" fontWeight={600} sx={{ flex: 1 }}>
              <PaletteIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              Theme Preferences
            </Typography>
            <Tooltip title="Choose between dark and light theme for the application interface.">
              <InfoOutlinedIcon color="action" />
            </Tooltip>
          </Box>
          <Typography variant="body2" sx={{ mb: 3 }}>
            Customize the appearance of Theseus Insight to match your preferences.
          </Typography>

          <Box sx={{ 
            p: 3,
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
            maxWidth: 400
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {isDarkMode ? (
                  <Brightness4Icon sx={{ color: 'warning.main' }} />
                ) : (
                  <Brightness7Icon sx={{ color: 'orange' }} />
                )}
                <Typography variant="h6">
                  {isDarkMode ? 'Dark Mode' : 'Light Mode'}
                </Typography>
              </Box>
              <Box sx={{ flex: 1 }} />
              <FormControlLabel
                control={
                  <Switch
                    checked={isDarkMode}
                    onChange={toggleTheme}
                    color="primary"
                  />
                }
                label=""
                sx={{ m: 0 }}
              />
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {isDarkMode 
                ? 'Switch to light mode for a brighter interface'
                : 'Switch to dark mode for easier viewing in low-light environments'
              }
            </Typography>
          </Box>
        </CardContent>
      </Card>

      {/* Scheduled Tasks Section */}
      <Box sx={{ mb: 4 }}>
        <ScheduledTasksSettings 
          onStatusChange={(message, severity) => {
            if (severity === 'success') {
              setSuccess(message);
            } else if (severity === 'error') {
              setError(message);
            }
          }}
        />
      </Box>

      {/* API Credentials Section */}
      <CredentialsSettings />

      {/* Database Management Section */}
      <DatabaseTransferSettings />


    </Container>
  );
};

export default Settings;
