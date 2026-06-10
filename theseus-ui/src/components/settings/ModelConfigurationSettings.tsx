import React, { useState } from 'react';
import {
  Autocomplete, Box, Button, Card, CardContent, CircularProgress,
  FormControl, IconButton, InputLabel, MenuItem, Select, Switch, FormControlLabel,
  Tab, Tabs, TextField, Tooltip, Typography,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { settingsApi } from '../../services/api';
import { useSnackbar } from '../../contexts/SnackbarContext';
import OllamaServersSettings from '../OllamaServersSettings';
import { TabPanel } from './TabPanel';
import { ModelNameAutocomplete } from './ModelNameAutocomplete';
import type { ModelCatalogOption } from './ModelNameAutocomplete';

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

interface ModelConfigurationSettingsProps {
  modelCatalogData?: any;
  modelProviders?: any[];
  getHostsByProvider: (provider: 'ollama' | 'lmstudio' | 'custom-oai') => string[];
}

/** Orchestration model configuration tabs (extracted from Settings.tsx
    in F3). One generic renderer drives all MODEL_TABS keys; the
    inference-servers tab embeds OllamaServersSettings. */
export const ModelConfigurationSettings: React.FC<ModelConfigurationSettingsProps> = ({
  modelCatalogData,
  modelProviders,
  getHostsByProvider,
}) => {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useSnackbar();
  const [tab, setTab] = useState(0);

  const { data: orchestrationConfig, isLoading: isLoadingOrchestration, isError: isErrorOrchestration } = useQuery({
    queryKey: ['orchestrationConfig'],
    queryFn: () => settingsApi.getOrchestrationConfig().then(res => res.data),
  });


  const updateOrchestrationMutation = useMutation({
    mutationFn: (newConfig: any) => settingsApi.updateOrchestrationConfig(newConfig),
    onSuccess: (data) => {
      queryClient.setQueryData(['orchestrationConfig'], data.data); // Assuming API returns the updated config
      queryClient.invalidateQueries({ queryKey: ['orchestrationConfig'] });
      showSuccess('Configuration updated successfully');
    },
    onError: (error: any) => showError(error.message || 'Failed to update configuration'),
  });


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

  if (isLoadingOrchestration) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }
  if (isErrorOrchestration) {
    showError('Failed to load orchestration config.');
  }

  return (
    <>
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

    </>
  );
};
