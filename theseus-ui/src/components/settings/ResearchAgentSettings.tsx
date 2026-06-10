import React, { useEffect, useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Autocomplete, Box,
  Button, Card, CardContent, Chip, FormControl, IconButton, InputLabel,
  MenuItem, Select, Tab, Tabs, TextField, Tooltip, Typography,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import GroupWorkIcon from '@mui/icons-material/GroupWork';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { researchAgentApi } from '../../services/api';
import { useSnackbar } from '../../contexts/SnackbarContext';
import { TabPanel } from './TabPanel';
import { ModelNameAutocomplete } from './ModelNameAutocomplete';
import type { ModelCatalogOption } from './ModelNameAutocomplete';

// Research Agent Configuration Tabs
const RESEARCH_AGENT_TABS = [
  { 
    key: 'single', 
    label: 'Single Agent', 
    tooltip: 'Sequential workflow with research loops for iterative deep analysis',
    icon: SmartToyIcon
  },
  { 
    key: 'multi', 
    label: 'Multi Agent', 
    tooltip: 'Parallel orchestration with specialized agents for comprehensive research',
    icon: GroupWorkIcon 
  },
];

interface ResearchAgentSettingsProps {
  modelCatalogData?: any;
  modelProviders?: any[];
  getHostsByProvider: (provider: 'ollama' | 'lmstudio' | 'custom-oai') => string[];
}

/** Research-agent single/multi mode configuration (extracted from
    Settings.tsx in F3). */
export const ResearchAgentSettings: React.FC<ResearchAgentSettingsProps> = ({
  modelCatalogData,
  modelProviders,
  getHostsByProvider,
}) => {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useSnackbar();
  const [researchAgentTab, setResearchAgentTab] = useState(0);
  // Research Agent Configuration State
  const [singleAgentConfig, setSingleAgentConfig] = useState<any>({});
  const [multiAgentConfig, setMultiAgentConfig] = useState<any>({});

  // Research Agent Configuration Queries
  const { data: researchModes, isLoading: isLoadingResearchModes } = useQuery({
    queryKey: ['researchModes'],
    queryFn: () => researchAgentApi.getModes().then(res => res.data),
  });


  // Research Agent Configuration Mutations
  const setResearchModeMutation = useMutation({
    mutationFn: (mode: 'single' | 'multi') => researchAgentApi.setMode(mode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['researchModes'] });
      showSuccess('Research agent mode updated successfully');
    },
    onError: (error: any) => showError(error.message || 'Failed to update research agent mode'),
  });

  const updateSingleAgentConfigMutation = useMutation({
    mutationFn: (config: any) => researchAgentApi.setModeConfig('single', config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['researchModes'] });
      showSuccess('Single-agent configuration updated successfully');
    },
    onError: (error: any) => showError(error.message || 'Failed to update single-agent configuration'),
  });

  const updateMultiAgentConfigMutation = useMutation({
    mutationFn: (config: any) => researchAgentApi.setModeConfig('multi', config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['researchModes'] });
      showSuccess('Multi-agent configuration updated successfully');
    },
    onError: (error: any) => showError(error.message || 'Failed to update multi-agent configuration'),
  });



  // Initialize research agent configurations
  useEffect(() => {
    if (researchModes) {
      setSingleAgentConfig(researchModes.single_agent_config || {});
      setMultiAgentConfig(researchModes.multi_agent_config || {});
    }
  }, [researchModes]);


  // Research Agent Configuration Helpers
  const handleSingleAgentConfigChange = (field: string, value: any) => {
    const newConfig = JSON.parse(JSON.stringify(singleAgentConfig));
    
    if (field.includes('.')) {
      const fieldParts = field.split('.');
      let currentObj = newConfig;
      
      for (let i = 0; i < fieldParts.length - 1; i++) {
        if (!currentObj[fieldParts[i]]) {
          currentObj[fieldParts[i]] = {};
        }
        currentObj = currentObj[fieldParts[i]];
      }
      
      currentObj[fieldParts[fieldParts.length - 1]] = value;
    } else {
      newConfig[field] = value;
    }
    
    setSingleAgentConfig(newConfig);
  };

  const handleMultiAgentConfigChange = (field: string, value: any) => {
    const newConfig = JSON.parse(JSON.stringify(multiAgentConfig));
    
    if (field.includes('.')) {
      const fieldParts = field.split('.');
      let currentObj = newConfig;
      
      for (let i = 0; i < fieldParts.length - 1; i++) {
        if (!currentObj[fieldParts[i]]) {
          currentObj[fieldParts[i]] = {};
        }
        currentObj = currentObj[fieldParts[i]];
      }
      
      currentObj[fieldParts[fieldParts.length - 1]] = value;
    } else {
      newConfig[field] = value;
    }
    
    setMultiAgentConfig(newConfig);
  };

  const handleResearchAgentModelSelected = (configType: 'single' | 'multi', selectedOption: ModelCatalogOption, modelPath: string) => {
    const fullCatalogEntry = modelCatalogData?.models?.find((model: any) => 
      model.id === selectedOption.id
    );

    if (!fullCatalogEntry) return;

    const modelData: any = {
      model_name: fullCatalogEntry.model_string,
      model_type: fullCatalogEntry.provider_name,
      temperature: fullCatalogEntry.temperature || 0.1,
      max_new_tokens: fullCatalogEntry.max_new_tokens || 4096,
    };

    if (fullCatalogEntry.num_ctx !== null && fullCatalogEntry.num_ctx !== undefined) {
      modelData.num_ctx = fullCatalogEntry.num_ctx;
    }

    // --- NEW IMPLEMENTATION: batch apply all fields in a single state update ---
    if (configType === 'single') {
      const newConfig = JSON.parse(JSON.stringify(singleAgentConfig));
      Object.entries(modelData).forEach(([field, value]) => {
        const fullPath = `${modelPath}.${field}`;
        const fieldParts = fullPath.split('.');
        let currentObj: any = newConfig;
        for (let i = 0; i < fieldParts.length - 1; i++) {
          if (!currentObj[fieldParts[i]]) {
            currentObj[fieldParts[i]] = {};
          }
          currentObj = currentObj[fieldParts[i]];
        }
        currentObj[fieldParts[fieldParts.length - 1]] = value;
      });
      setSingleAgentConfig(newConfig);
    } else {
      const newConfig = JSON.parse(JSON.stringify(multiAgentConfig));
      Object.entries(modelData).forEach(([field, value]) => {
        const fullPath = `${modelPath}.${field}`;
        const fieldParts = fullPath.split('.');
        let currentObj: any = newConfig;
        for (let i = 0; i < fieldParts.length - 1; i++) {
          if (!currentObj[fieldParts[i]]) {
            currentObj[fieldParts[i]] = {};
          }
          currentObj = currentObj[fieldParts[i]];
        }
        currentObj[fieldParts[fieldParts.length - 1]] = value;
      });
      setMultiAgentConfig(newConfig);
    }
  };


  // Render Single Agent Configuration
  const renderSingleAgentConfig = () => {
    const modelConfig = singleAgentConfig.model_config || {};
    const bossModel = modelConfig.boss_model || {};

    const renderModelFields = (modelObj: any, modelPath: string, title: string, description: string, isRequired: boolean = false) => (
      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="h6">{title}</Typography>
            {isRequired && <Chip label="Required" size="small" color="primary" />}
            <Tooltip title={description}>
              <IconButton size="small">
                <InfoOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {description}
          </Typography>
          
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
            <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
              <ModelNameAutocomplete
                label="Model Name"
                value={modelObj.model_name || ''}
                onChange={value => handleSingleAgentConfigChange(`${modelPath}.model_name`, value)}
                onModelSelected={selectedModel => handleResearchAgentModelSelected('single', selectedModel, modelPath)}
                modelCatalogData={modelCatalogData}
              />
              <FormControl fullWidth>
                <InputLabel>Model Type (Provider)</InputLabel>
                <Select
                  value={modelObj.model_type || ''}
                  label="Model Type (Provider)"
                  onChange={e => handleSingleAgentConfigChange(`${modelPath}.model_type`, e.target.value)}
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
                value={modelObj.max_new_tokens || 4096}
                onChange={e => handleSingleAgentConfigChange(`${modelPath}.max_new_tokens`, Number(e.target.value))}
              />
              <TextField
                fullWidth
                label="Temperature"
                type="number"
                inputProps={{ step: '0.1' }}
                value={modelObj.temperature || 0.1}
                onChange={e => handleSingleAgentConfigChange(`${modelPath}.temperature`, parseFloat(e.target.value))}
              />
              {(modelObj.model_type === 'ollama' || modelObj.model_type === 'llamacpp' || modelObj.model_type === 'lmstudio') && (
                <TextField
                  fullWidth
                  label="Context Window (num_ctx)"
                  type="number"
                  value={modelObj.num_ctx || 131072}
                  onChange={e => handleSingleAgentConfigChange(`${modelPath}.num_ctx`, Number(e.target.value))}
                />
              )}
              {(modelObj.model_type === 'ollama' || modelObj.model_type === 'lmstudio' || modelObj.model_type === 'custom-oai') && (
                <Autocomplete
                  fullWidth
                  freeSolo
                  options={getHostsByProvider(modelObj.model_type as 'ollama' | 'lmstudio' | 'custom-oai')}
                  value={modelObj.host || ''}
                  onInputChange={(_, newInputValue) => {
                    handleSingleAgentConfigChange(`${modelPath}.host`, newInputValue || undefined);
                  }}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Host (Optional)"
                      placeholder={
                        modelObj.model_type === 'ollama' ? 'athena.local:11434' :
                        modelObj.model_type === 'lmstudio' ? 'localhost:1234' :
                        'http://custom-server:8000'
                      }
                      helperText="Custom host for this model (leave empty to use environment default)"
                    />
                  )}
                />
              )}
            </Box>
          </Box>
        </CardContent>
      </Card>
    );

    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Boss Model */}
        {renderModelFields(
          bossModel, 
          'model_config.boss_model', 
          'Boss Model (Required)', 
          'The primary model that orchestrates the entire research workflow, makes high-level decisions, and coordinates between different nodes. This model drives the sequential research loop.', 
          true
        )}

        {/* Optional Node-Specific Models */}
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="h6">Node-Specific Models (Optional)</Typography>
              <Tooltip title="Override default models for specific workflow nodes. Leave empty to use Boss Model for all nodes.">
                <IconButton size="small">
                  <InfoOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {renderModelFields(
                modelConfig.query_planner_model || {}, 
                'model_config.query_planner_model', 
                'Query Planner Model', 
                'Breaks down your research question into focused sub-queries for targeted search. Reasoning models excel at this complex decomposition task.'
              )}
              {renderModelFields(
                modelConfig.evidence_selector_model || {}, 
                'model_config.evidence_selector_model', 
                'Evidence Selector Model', 
                'Evaluates source quality, relevance, and determines if gathered evidence is sufficient to answer the research question.'
              )}
              {renderModelFields(
                modelConfig.compression_model || {}, 
                'model_config.compression_model', 
                'Compression Model', 
                'Compresses research evidence when token budget is exceeded, preserving the most important information while reducing length.'
              )}
              {renderModelFields(
                modelConfig.answer_generator_model || {}, 
                'model_config.answer_generator_model', 
                'Answer Generator Model', 
                'Creates the final comprehensive research report by synthesizing all gathered evidence into a coherent, well-structured answer.'
              )}
            </Box>
          </AccordionDetails>
        </Accordion>

        {/* Workflow Parameters */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>Workflow Parameters</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              <TextField
                label="Max Research Loops"
                type="number"
                value={singleAgentConfig.max_research_loops || 3}
                onChange={e => handleSingleAgentConfigChange('max_research_loops', Number(e.target.value))}
                inputProps={{ min: 1, max: 10 }}
                helperText="Maximum research iteration loops"
                sx={{ minWidth: 200 }}
              />
              <TextField
                label="Max Research Context Tokens"
                type="number"
                value={singleAgentConfig.max_research_context_tokens || 15000}
                onChange={e => handleSingleAgentConfigChange('max_research_context_tokens', Number(e.target.value))}
                inputProps={{ min: 5000, max: 100000 }}
                helperText="Token budget before compression"
                sx={{ minWidth: 200 }}
              />
              <TextField
                label="Compress to Ratio"
                type="number"
                value={singleAgentConfig.compress_to_ratio || 0.2}
                onChange={e => handleSingleAgentConfigChange('compress_to_ratio', parseFloat(e.target.value))}
                inputProps={{ min: 0.1, max: 0.8, step: 0.1 }}
                helperText="Target compression ratio"
                sx={{ minWidth: 200 }}
              />
            </Box>
          </CardContent>
        </Card>

        {/* Search Configuration */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>Search Configuration</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              <TextField
                label="Local Search Limit"
                type="number"
                value={singleAgentConfig.search_config?.local_limit || 20}
                onChange={e => handleSingleAgentConfigChange('search_config.local_limit', Number(e.target.value))}
                inputProps={{ min: 5, max: 100 }}
                helperText="Max papers from local database"
                sx={{ minWidth: 200 }}
              />
              <TextField
                label="External Search Limit"
                type="number"
                value={singleAgentConfig.search_config?.external_limit || 15}
                onChange={e => handleSingleAgentConfigChange('search_config.external_limit', Number(e.target.value))}
                inputProps={{ min: 5, max: 50 }}
                helperText="Max papers from external APIs"
                sx={{ minWidth: 200 }}
              />
            </Box>
          </CardContent>
        </Card>
      </Box>
    );
  };

  // Render Multi Agent Configuration
  const renderMultiAgentConfig = () => {
    const bossModel = multiAgentConfig.boss_model || {};
    const specializedModels = multiAgentConfig.specialized_models || {};

    const renderModelFields = (modelObj: any, modelPath: string, title: string, description: string, isRequired: boolean = false) => (
      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="h6">{title}</Typography>
            {isRequired && <Chip label="Required" size="small" color="primary" />}
            <Tooltip title={description}>
              <IconButton size="small">
                <InfoOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {description}
          </Typography>
          
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
            <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
              <ModelNameAutocomplete
                label="Model Name"
                value={modelObj.model_name || ''}
                onChange={value => handleMultiAgentConfigChange(`${modelPath}.model_name`, value)}
                onModelSelected={selectedModel => handleResearchAgentModelSelected('multi', selectedModel, modelPath)}
                modelCatalogData={modelCatalogData}
              />
              <FormControl fullWidth>
                <InputLabel>Model Type (Provider)</InputLabel>
                <Select
                  value={modelObj.model_type || ''}
                  label="Model Type (Provider)"
                  onChange={e => handleMultiAgentConfigChange(`${modelPath}.model_type`, e.target.value)}
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
                value={modelObj.max_new_tokens || 4096}
                onChange={e => handleMultiAgentConfigChange(`${modelPath}.max_new_tokens`, Number(e.target.value))}
              />
              <TextField
                fullWidth
                label="Temperature"
                type="number"
                inputProps={{ step: '0.1' }}
                value={modelObj.temperature || 0.1}
                onChange={e => handleMultiAgentConfigChange(`${modelPath}.temperature`, parseFloat(e.target.value))}
              />
              {(modelObj.model_type === 'ollama' || modelObj.model_type === 'llamacpp' || modelObj.model_type === 'lmstudio') && (
                <TextField
                  fullWidth
                  label="Context Window (num_ctx)"
                  type="number"
                  value={modelObj.num_ctx || 131072}
                  onChange={e => handleMultiAgentConfigChange(`${modelPath}.num_ctx`, Number(e.target.value))}
                />
              )}
              {(modelObj.model_type === 'ollama' || modelObj.model_type === 'lmstudio' || modelObj.model_type === 'custom-oai') && (
                <Autocomplete
                  fullWidth
                  freeSolo
                  options={getHostsByProvider(modelObj.model_type as 'ollama' | 'lmstudio' | 'custom-oai')}
                  value={modelObj.host || ''}
                  onInputChange={(_, newInputValue) => {
                    handleMultiAgentConfigChange(`${modelPath}.host`, newInputValue || undefined);
                  }}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Host (Optional)"
                      placeholder={
                        modelObj.model_type === 'ollama' ? 'athena.local:11434' :
                        modelObj.model_type === 'lmstudio' ? 'localhost:1234' :
                        'http://custom-server:8000'
                      }
                      helperText="Custom host for this model (leave empty to use environment default)"
                    />
                  )}
                />
              )}
            </Box>
          </Box>
        </CardContent>
      </Card>
    );

    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Boss Model */}
        {renderModelFields(
          bossModel, 
          'boss_model', 
          'Boss Model (Required)', 
          'The primary orchestration model that coordinates the entire multi-agent workflow, decomposes questions, and synthesizes final answers from all agents.', 
          true
        )}

        {/* Specialized Agent Models */}
        <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Specialized Agent Models</Typography>
        
        {renderModelFields(
          specializedModels.question_generator || {}, 
          'specialized_models.question_generator', 
          'Question Generator Model', 
          'Decomposes the user\'s research question into specialized sub-questions tailored for different agent types. Reasoning models excel at this complex task.'
        )}
        
        {renderModelFields(
          specializedModels.research_agent || {}, 
          'specialized_models.research_agent', 
          'Research Agent Model', 
          'Conducts comprehensive information gathering and primary research. Focuses on breadth of coverage and foundational understanding.'
        )}
        
        {renderModelFields(
          specializedModels.analysis_agent || {}, 
          'specialized_models.analysis_agent', 
          'Analysis Agent Model', 
          'Provides deep analytical insights and pattern recognition. Analyzes trends, identifies contradictions, and evaluates methodological approaches.'
        )}
        
        {renderModelFields(
          specializedModels.verification_agent || {}, 
          'specialized_models.verification_agent', 
          'Verification Agent Model', 
          'Cross-validates findings against authoritative sources and checks for accuracy, consistency, and credibility of research evidence.'
        )}
        
        {renderModelFields(
          specializedModels.synthesis_agent || {}, 
          'specialized_models.synthesis_agent', 
          'Synthesis Agent Model', 
          'Combines and synthesizes results from all specialized agents into a coherent final answer, resolving conflicts and providing comprehensive conclusions.'
        )}

        {/* Orchestration Parameters */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>Orchestration Parameters</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              <TextField
                label="Parallel Agents"
                type="number"
                value={multiAgentConfig.parallel_agents || 4}
                onChange={e => handleMultiAgentConfigChange('parallel_agents', Number(e.target.value))}
                inputProps={{ min: 2, max: 6 }}
                helperText="Number of agents to run in parallel (2-6)"
                sx={{ minWidth: 200 }}
              />
              <TextField
                label="Task Timeout (seconds)"
                type="number"
                value={multiAgentConfig.task_timeout || 300}
                onChange={e => handleMultiAgentConfigChange('task_timeout', Number(e.target.value))}
                inputProps={{ min: 60, max: 1800 }}
                helperText="Maximum time per agent task"
                sx={{ minWidth: 200 }}
              />
            </Box>
          </CardContent>
        </Card>

        {/* Search Configuration */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>Search Configuration</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              <TextField
                label="Local Search Limit"
                type="number"
                value={multiAgentConfig.search_config?.local_limit || 25}
                onChange={e => handleMultiAgentConfigChange('search_config.local_limit', Number(e.target.value))}
                inputProps={{ min: 5, max: 100 }}
                helperText="Max papers from local database per agent"
                sx={{ minWidth: 200 }}
              />
              <TextField
                label="External Search Limit"
                type="number"
                value={multiAgentConfig.search_config?.external_limit || 20}
                onChange={e => handleMultiAgentConfigChange('search_config.external_limit', Number(e.target.value))}
                inputProps={{ min: 5, max: 50 }}
                helperText="Max papers from external APIs per agent"
                sx={{ minWidth: 200 }}
              />
            </Box>
          </CardContent>
        </Card>

        {/* Synthesis Configuration */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>Synthesis Configuration</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              <FormControl sx={{ minWidth: 250 }}>
                <InputLabel>Conflict Resolution</InputLabel>
                <Select
                  value={multiAgentConfig.synthesis_config?.conflict_resolution || 'weighted_consensus'}
                  label="Conflict Resolution"
                  onChange={e => handleMultiAgentConfigChange('synthesis_config.conflict_resolution', e.target.value)}
                >
                  <MenuItem value="weighted_consensus">Weighted Consensus</MenuItem>
                  <MenuItem value="evidence_based">Evidence Based</MenuItem>
                  <MenuItem value="majority_vote">Majority Vote</MenuItem>
                </Select>
              </FormControl>
              <FormControl sx={{ minWidth: 250 }}>
                <InputLabel>Citation Strategy</InputLabel>
                <Select
                  value={multiAgentConfig.synthesis_config?.citation_strategy || 'comprehensive'}
                  label="Citation Strategy"
                  onChange={e => handleMultiAgentConfigChange('synthesis_config.citation_strategy', e.target.value)}
                >
                  <MenuItem value="comprehensive">Comprehensive</MenuItem>
                  <MenuItem value="selective">Selective</MenuItem>
                  <MenuItem value="minimal">Minimal</MenuItem>
                </Select>
              </FormControl>
            </Box>
          </CardContent>
        </Card>
      </Box>
    );
  };


  if (isLoadingResearchModes) {
    return null;
  }

  return (
    <>
      {/* Research Agent Configuration Section (moved below Model Configuration Section) */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5" fontWeight={600} sx={{ flex: 1 }}>
              Research Agent Configuration
            </Typography>
            <Tooltip title="Configure the research agent models and parameters for both single-agent and multi-agent modes.">
              <InfoOutlinedIcon color="action" />
            </Tooltip>
          </Box>
          {/* Current Mode Display */}
          {researchModes && (
            <Box sx={{ mb: 3, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                <Typography variant="h6">Current Mode:</Typography>
                <Chip 
                  label={researchModes.current_mode === 'single' ? 'Single Agent' : 'Multi Agent'}
                  color={researchModes.current_mode === 'single' ? 'primary' : 'secondary'}
                  icon={researchModes.current_mode === 'single' ? <SmartToyIcon /> : <GroupWorkIcon />}
                />
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => {
                    const newMode = researchModes.current_mode === 'single' ? 'multi' : 'single';
                    setResearchModeMutation.mutate(newMode);
                  }}
                  disabled={setResearchModeMutation.isPending}
                >
                  Switch to {researchModes.current_mode === 'single' ? 'Multi' : 'Single'} Agent
                </Button>
              </Box>
              
              {researchModes.validation && !researchModes.validation.valid && (
                <Alert severity="warning" sx={{ mt: 1 }}>
                  Configuration Issues: {researchModes.validation.issues.join(', ')}
                </Alert>
              )}
            </Box>
          )}
          <Tabs
            value={researchAgentTab}
            onChange={(_, newValue) => setResearchAgentTab(newValue)}
            variant="fullWidth"
            sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}
          >
            {RESEARCH_AGENT_TABS.map((tabDef, idx) => {
              const Icon = tabDef.icon;
              return (
                <Tab
                  key={tabDef.key}
                  label={
                    <Box display="flex" alignItems="center" gap={1}>
                      <Icon />
                      {tabDef.label}
                      <Tooltip title={tabDef.tooltip}>
                        <InfoOutlinedIcon fontSize="small" />
                      </Tooltip>
                    </Box>
                  }
                  id={`research-tab-${idx}`}
                  aria-controls={`research-tabpanel-${idx}`}
                />
              );
            })}
          </Tabs>
          {/* Single Agent Tab */}
          <TabPanel value={researchAgentTab} index={0}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Single Agent Mode Configuration
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Sequential workflow with research loops for iterative deep analysis. One model coordinates the entire process through different workflow nodes.
                </Typography>
                {renderSingleAgentConfig()}
                <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
                  <Button
                    variant="contained"
                    onClick={() => updateSingleAgentConfigMutation.mutate(singleAgentConfig)}
                    disabled={updateSingleAgentConfigMutation.isPending}
                  >
                    Save Single Agent Configuration
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </TabPanel>
          {/* Multi Agent Tab */}
          <TabPanel value={researchAgentTab} index={1}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Multi Agent Mode Configuration
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Parallel orchestration with specialized agents for comprehensive research. Multiple agents work simultaneously on different aspects of the research question.
                </Typography>
                {renderMultiAgentConfig()}
                <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
                  <Button
                    variant="contained"
                    onClick={() => updateMultiAgentConfigMutation.mutate(multiAgentConfig)}
                    disabled={updateMultiAgentConfigMutation.isPending}
                  >
                    Save Multi Agent Configuration
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </TabPanel>
        </CardContent>
      </Card>

    </>
  );
};
