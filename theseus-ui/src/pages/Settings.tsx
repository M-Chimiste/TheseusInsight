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
  Accordion,
  AccordionSummary,
  AccordionDetails,
  LinearProgress,
  Slider,
  Paper,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi, modelCatalogApi, performanceApi } from '../services/api';
import type { PerformanceConfig, SystemInfo } from '../services/api';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import SettingsIcon from '@mui/icons-material/Settings';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import SpeedIcon from '@mui/icons-material/Speed';
import MemoryIcon from '@mui/icons-material/Memory';
import DeveloperModeIcon from '@mui/icons-material/DeveloperMode';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import PaletteIcon from '@mui/icons-material/Palette';
import { useDatabaseTaskState } from '../hooks/useDatabaseTaskState';
import { useTheme as useCustomTheme } from '../contexts/ThemeContext';
import { useLayout } from '../contexts/LayoutContext';

const CREDENTIAL_KEYS = [
  'GOOGLE_API_KEY',
  'ANTHROPIC_API_KEY',
  'OPENAI_API_KEY',
  'GMAIL_SENDER_ADDRESS',
  'GMAIL_APP_PASSWORD',
  'OLLAMA_URL',
  'CLIENT_ID',
  'PROJECT_ID',
  'CLIENT_SECRET',
  'CUSTOM_OAI_BASE_URL',
  'CUSTOM_OAI_API_KEY',
  'KAGGLE_USERNAME',
  'KAGGLE_KEY',
];

const MODEL_TABS = [
  { key: 'embedding_model', label: 'Embedding Model', tooltip: 'Used for vector search and similarity.' },
  { key: 'judge_model', label: 'Judge Model', tooltip: 'Used for ranking and scoring papers.' },
  { key: 'content_extraction_model', label: 'Content Extraction Model', tooltip: 'Extracts content from papers.' },
  { key: 'newsletter_sections_model', label: 'Newsletter Sections Model', tooltip: 'Generates newsletter sections.' },
  { key: 'newsletter_intro_model', label: 'Newsletter Intro Model', tooltip: 'Generates newsletter introduction.' },
  { key: 'podcast_model', label: 'Podcast Model', tooltip: 'Used for podcast generation.' },
  { key: 'tts_model', label: 'TTS Model', tooltip: 'Text-to-speech for podcast.' },
  { key: 'research_agent_model_config', label: 'Research Agent Models', tooltip: 'Boss and worker models for automated literature review.' },
  { key: 'mind_map_config', label: 'Mind-Map Explorer', tooltip: 'Configuration for mind-map visualization and paper relationship exploration.' },
];

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`model-tabpanel-${index}`}
      aria-labelledby={`model-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

// Interface for model catalog entries
interface ModelCatalogOption {
  id: number;
  alias: string;
  model_string: string;
  provider_name: string;
  model_type: string;
  display: string; // "Alias (model_string)"
}

// Component for model name autocomplete with catalog integration
interface ModelNameAutocompleteProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onModelSelected?: (model: any) => void; // Called when a catalog model is selected
  modelCatalogData?: any;
  fullWidth?: boolean;
}

const ModelNameAutocomplete: React.FC<ModelNameAutocompleteProps> = ({
  label,
  value,
  onChange,
  onModelSelected,
  modelCatalogData,
  fullWidth = true
}) => {
  // Transform model catalog data into options
  const catalogOptions: ModelCatalogOption[] = React.useMemo(() => {
    if (!modelCatalogData?.models) {
      return [];
    }
    
    const options = modelCatalogData.models.map((model: any) => ({
      id: model.id,
      alias: model.alias,
      model_string: model.model_string,
      provider_name: model.provider_name,
      model_type: model.model_type,
      display: `${model.alias} (${model.model_string})`
    }));
    
    return options;
  }, [modelCatalogData]);

  // Find the currently selected option based on model_string
  const selectedOption = catalogOptions.find(opt => opt.model_string === value) || null;

  const handleChange = (_: any, newValue: ModelCatalogOption | string | null) => {
    if (typeof newValue === 'string') {
      // User typed a custom value
      onChange(newValue);
    } else if (newValue) {
      // User selected from catalog - let batched update handle everything including model_name
      // This prevents race conditions between individual and batched updates
      if (onModelSelected) {
        onModelSelected(newValue);
      } else {
        // Fallback if no batched update callback - set model name directly
        onChange(newValue.model_string);
      }
    } else {
      // Cleared
      onChange('');
    }
  };

  return (
    <Autocomplete
      fullWidth={fullWidth}
      freeSolo
      options={catalogOptions}
      getOptionLabel={(option) => {
        if (typeof option === 'string') return option;
        return option.display;
      }}
      renderOption={(props, option) => (
        <li {...props} key={option.id}>
          <Box>
            <Typography variant="body2" fontWeight={500}>
              {option.alias}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {option.model_string} • {option.provider_name}
            </Typography>
          </Box>
        </li>
      )}
      value={selectedOption}
      onChange={handleChange}
      inputValue={selectedOption ? selectedOption.display : value}
      blurOnSelect={true}
      selectOnFocus={true}
      clearOnBlur={false}
      onInputChange={(_, newInputValue, reason) => {
        if (reason === 'clear') {
          onChange('');
        } else if (reason === 'input' && !selectedOption) {
          onChange(newInputValue);
        }
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          helperText={catalogOptions.length > 0 ? 
            `Search model catalog (${catalogOptions.length} models) or enter custom model name` : 
            "Model catalog not loaded - enter custom model name"
          }
        />
      )}
      filterOptions={(options, { inputValue }) => {
        if (!inputValue) return options.slice(0, 10); // Show first 10 when no input
        
        const filtered = options.filter(option =>
          option.alias.toLowerCase().includes(inputValue.toLowerCase()) ||
          option.model_string.toLowerCase().includes(inputValue.toLowerCase()) ||
          option.provider_name.toLowerCase().includes(inputValue.toLowerCase())
        );
        
        return filtered.slice(0, 20); // Limit to 20 results
      }}
    />
  );
};

const Settings: React.FC = () => {
  const queryClient = useQueryClient();
  const { isDarkMode, toggleTheme } = useCustomTheme();
  const { headerHeight } = useLayout(); // Get dynamic header height
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [tab, setTab] = useState(0);

  const [selectedImportFile, setSelectedImportFile] = useState<File | null>(null);
  const [importMode, setImportMode] = useState<'merge' | 'overwrite'>('merge');
  const [editedResearchAgentConfig, setEditedResearchAgentConfig] = useState<any | null>(null);
  
  // Use the database task state hook for persistent state management
  const {
    taskState: dbTaskState,
    setExportTaskId,
    setImportTaskId,
    updateExportProgress,
    updateImportProgress,
    setExportError,
    setImportError,
    clearExportTask,
    clearImportTask,
    isCheckingForActiveTasks: isCheckingDbTasks
  } = useDatabaseTaskState();

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
  
  const updateOrchestrationMutation = useMutation({
    mutationFn: (newConfig: any) => settingsApi.updateOrchestrationConfig(newConfig),
    onSuccess: (data) => {
      queryClient.setQueryData(['orchestrationConfig'], data.data); // Assuming API returns the updated config
      queryClient.invalidateQueries({ queryKey: ['orchestrationConfig'] });
      setSuccess('Orchestration configuration updated successfully');
    },
    onError: (error: any) => setError(error.message || 'Failed to update orchestration config'),
  });



  const [appPasswordFailed, setAppPasswordFailed] = useState(false);

  const { data: credentials } = useQuery({
    queryKey: ['credentials'],
    queryFn: () => settingsApi.getCredentials().then(res => res.data),
  });

  const updateCredentialsMutation = useMutation({
    mutationFn: (data: any) => settingsApi.updateCredentials(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credentials'] });
      setSuccess('Credentials updated');
    },
    onError: (error: any) => setError(error.message),
  });

  const exportDatabaseMutation = useMutation({
    mutationFn: () => settingsApi.startExportDatabase(),
    onMutate: () => {
      // Clear any previous errors
      setExportError(null);
    },
    onSuccess: (response) => {
      const taskId = response.data.task_id;
      setExportTaskId(taskId);

      const ws = new WebSocket(`ws://localhost:8000/ws/database-export/${taskId}`);

      ws.onmessage = (event) => {
        const status = JSON.parse(event.data);
        // Ensure export task progress stays in 0-90% range to leave room for download progress
        const taskProgress = Math.min(status.progress || 0, 90);
        updateExportProgress(taskProgress, status.message || 'Creating export archive...');

        if (status.overallStatus === 'completed') {
          ws.close();
          updateExportProgress(90, 'Downloading export file...');
          settingsApi
            .downloadExportDatabase(taskId, (downloadProgress) => {
              // Map download progress to 90-100% range to show download progress
              const mappedProgress = 90 + (downloadProgress * 0.1);
              updateExportProgress(Math.min(mappedProgress, 100), 'Downloading export file...');
            })
            .then((downloadResponse) => {
              try {
                updateExportProgress(100, 'Export completed successfully');
                const blob = new Blob([downloadResponse.data], {
                  type: downloadResponse.headers['content-type'] || 'application/gzip',
                });
                const url = window.URL.createObjectURL(blob);
                const contentDisposition = downloadResponse.headers['content-disposition'];
                let filename = `theseus_backup_${new Date().toISOString().split('T')[0]}.tar.gz`;
                if (contentDisposition) {
                  const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                  if (filenameMatch && filenameMatch[1]) {
                    filename = filenameMatch[1].replace(/['"]/g, '');
                  }
                }
                const link = document.createElement('a');
                link.href = url;
                link.download = filename;
                link.style.display = 'none';
                document.body.appendChild(link);
                link.click();
                setTimeout(() => {
                  document.body.removeChild(link);
                  window.URL.revokeObjectURL(url);
                }, 100);
                setSuccess(`Database exported successfully (${(blob.size / 1024 / 1024).toFixed(1)} MB)`);
                // Clear the export task after successful completion
                setTimeout(() => clearExportTask(), 3000);
              } catch (err) {
                console.error('Export download error:', err);
                setExportError(`Failed to download export file: ${err instanceof Error ? err.message : 'Unknown error'}`);
              }
            })
            .catch((err) => {
              setExportError(err.message || 'Failed to download export');
            });
        } else if (status.overallStatus === 'failed') {
          setExportError(status.error || 'Database export failed');
        }
      };

      ws.onerror = () => {
        setExportError('Connection error during export');
      };
    },
    onError: (error: any) => setExportError(error.message || 'Failed to start database export'),
  });

  const importDatabaseMutation = useMutation({
    mutationFn: ({ file, mode }: { file: File; mode: 'merge' | 'overwrite' }) => 
      settingsApi.importDatabase(file, mode),
    onMutate: () => {
      // Clear any previous errors
      setImportError(null);
    },
    onSuccess: (response) => {
      const taskId = response.data.task_id;
      setImportTaskId(taskId);
      
      // Connect to WebSocket for progress updates
      const ws = new WebSocket(`ws://localhost:8000/ws/database-import/${taskId}`);
      
      ws.onmessage = (event) => {
        const status = JSON.parse(event.data);
        updateImportProgress(status.progress || 0, status.message || 'Importing...');
        
        if (status.overallStatus === 'completed') {
          setSuccess('Database imported successfully. Please restart the application.');
          setSelectedImportFile(null);
          // Refresh all queries since database data has changed
          queryClient.invalidateQueries();
          // Clear the import task after successful completion
          setTimeout(() => clearImportTask(), 3000);
        } else if (status.overallStatus === 'failed') {
          setImportError(status.error || 'Database import failed');
        }
      };
      
      ws.onerror = () => {
        setImportError('Connection error during import');
      };
      
      ws.onclose = () => {
        if (dbTaskState.isImporting) {
          // Connection closed but import might still be running
          setTimeout(() => {
            // Only clear if still importing after 5 seconds
            if (dbTaskState.isImporting) {
              clearImportTask();
            }
          }, 5000);
        }
      };
    },
    onError: (error: any) => setImportError(error.message || 'Failed to start database import'),
  });

  const [credValues, setCredValues] = useState<Record<string, string>>({});
  const [showCreds, setShowCreds] = useState<Record<string, boolean>>({});

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

  useEffect(() => {
    if (credentials) {
      setCredValues(credentials);
    }
  }, [credentials]);

  useEffect(() => {
    if (orchestrationConfig?.research_agent_model_config) {
      // Deep clone the config and ensure all nested objects exist
      const clonedConfig = JSON.parse(JSON.stringify(orchestrationConfig.research_agent_model_config));
      
      // Ensure all required nested objects exist to prevent null access errors
      if (!clonedConfig.boss_model) clonedConfig.boss_model = {};
      if (!clonedConfig.worker_models) clonedConfig.worker_models = {};
      if (!clonedConfig.worker_models.summary) clonedConfig.worker_models.summary = {};
      if (!clonedConfig.worker_models.analysis) clonedConfig.worker_models.analysis = {};
      if (!clonedConfig.worker_models.search) clonedConfig.worker_models.search = {};
      if (!clonedConfig.query_planner_model) clonedConfig.query_planner_model = {};
      if (!clonedConfig.evidence_selector_model) clonedConfig.evidence_selector_model = {};
      if (!clonedConfig.compression_model) clonedConfig.compression_model = {};
      if (!clonedConfig.answer_generator_model) clonedConfig.answer_generator_model = {};
      
      setEditedResearchAgentConfig(clonedConfig);
    }
  }, [orchestrationConfig]);

  const handleModelConfigChange = (modelKey: string, field: string, value: any) => {
    // Handle research agent model config separately
    if (modelKey === 'research_agent_model_config') {
      const newConfig = JSON.parse(JSON.stringify(editedResearchAgentConfig || {}));
      
      // Handle nested paths like "boss_model.model_name" or "worker_models.summary.temperature"
      if (field.includes('.')) {
        const fieldParts = field.split('.');
        let currentObj = newConfig;
        
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
        newConfig[field] = value;
      }
      
      setEditedResearchAgentConfig(newConfig);
      // Optimistically update local state for UI responsiveness
      queryClient.setQueryData(['orchestrationConfig'], {
        ...orchestrationConfig,
        research_agent_model_config: newConfig
      });
      return;
    }
    
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
      if (modelKey === 'research_agent_model_config') {
        const newConfig = JSON.parse(JSON.stringify(editedResearchAgentConfig || {}));
        
        // Apply all fields to the config
        Object.entries(modelData).forEach(([field, value]) => {
          const fieldPath = prefix ? `${prefix}.${field}` : field;
          
          if (fieldPath.includes('.')) {
            const fieldParts = fieldPath.split('.');
            let currentObj = newConfig;
            
            for (let i = 0; i < fieldParts.length - 1; i++) {
              if (!currentObj[fieldParts[i]]) {
                currentObj[fieldParts[i]] = {};
              }
              currentObj = currentObj[fieldParts[i]];
            }
            
            currentObj[fieldParts[fieldParts.length - 1]] = value;
          } else {
            newConfig[fieldPath] = value;
          }
        });
        setEditedResearchAgentConfig(newConfig);
        queryClient.setQueryData(['orchestrationConfig'], {
          ...orchestrationConfig,
          research_agent_model_config: newConfig
        });
      } else {
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
    }
  };





  const handleDatabaseImportFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    setSelectedImportFile(file || null);
  };

  const handleDatabaseImport = () => {
    if (selectedImportFile) {
      importDatabaseMutation.mutate({ file: selectedImportFile, mode: importMode });
    }
  };

  const cleanResearchAgentConfig = (config: any): any => {
    if (!config) return null;

    // Deep copy to avoid mutating the original state
    const cleanedConfig = JSON.parse(JSON.stringify(config));

    // Helper to clean individual model objects
    const cleanModel = (model: any) => {
      if (!model) return null;
      // If it's not a valid model object, return null
      if (typeof model !== 'object' || !model.model_name || !model.model_type) {
        return null;
      }
      
      // Convert empty strings to null for numeric fields
      const numericFields = ['max_new_tokens', 'temperature', 'num_ctx'];
      numericFields.forEach(field => {
        if (model[field] === '' || model[field] === undefined) {
          model[field] = null;
        }
      });
      return model;
    };

    // Clean the main boss_model (must be valid)
    cleanedConfig.boss_model = cleanModel(cleanedConfig.boss_model);
    if (!cleanedConfig.boss_model) {
      setError("Research Agent's Boss Model must have a valid model name and type.");
      return null; // Stop processing if boss model is invalid
    }

    // Clean worker models, removing invalid ones
    if (cleanedConfig.worker_models) {
      const validWorkerModels: { [key: string]: any } = {};
      for (const key in cleanedConfig.worker_models) {
        const cleanedWorker = cleanModel(cleanedConfig.worker_models[key]);
        if (cleanedWorker) {
          validWorkerModels[key] = cleanedWorker;
        }
      }
      cleanedConfig.worker_models = validWorkerModels;
    }

    // Clean optional node-specific models
    const optionalModels = [
      'query_planner_model',
      'evidence_selector_model',
      'compression_model',
      'answer_generator_model'
    ];
    optionalModels.forEach(key => {
      cleanedConfig[key] = cleanModel(cleanedConfig[key]);
    });
    
    // Remove deprecated fields that are no longer used in the workflow
    delete cleanedConfig.timeout_seconds;
    delete cleanedConfig.external_search_timeout;
    delete cleanedConfig.default_worker;
    delete cleanedConfig.max_retries;

    // Ensure PDF processing fields have proper defaults
    if (cleanedConfig.enable_full_text === undefined) {
      cleanedConfig.enable_full_text = true;
    }
    if (cleanedConfig.full_text_top_n === undefined || cleanedConfig.full_text_top_n === '') {
      cleanedConfig.full_text_top_n = 20;
    }
    if (cleanedConfig.max_chunk_tokens === undefined || cleanedConfig.max_chunk_tokens === '') {
      cleanedConfig.max_chunk_tokens = 8000;
    }
    if (cleanedConfig.summary_target_tokens === undefined || cleanedConfig.summary_target_tokens === '') {
      cleanedConfig.summary_target_tokens = 1500;
    }

    return cleanedConfig;
  };

  const renderResearchAgentModelConfig = (config: any) => {
    if (!config) return <Typography>Research Agent configuration not available.</Typography>;

    const bossModel = config.boss_model || {};
    const workerModels = config.worker_models || {};

    const renderModelFields = (modelConfig: any, prefix: string, title: string) => (
      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>{title}</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
            <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
              <ModelNameAutocomplete
                label="Model Name"
                value={modelConfig.model_name || ''}
                onChange={value => handleModelConfigChange('research_agent_model_config', `${prefix}.model_name`, value)}
                onModelSelected={selectedModel => handleModelSelectedFromCatalog('research_agent_model_config', selectedModel, prefix)}
                modelCatalogData={modelCatalogData}
              />
              <FormControl fullWidth>
                <InputLabel>Model Type (Provider)</InputLabel>
                <Select
                  value={modelConfig.model_type || ''}
                  label="Model Type (Provider)"
                  onChange={e => handleModelConfigChange('research_agent_model_config', `${prefix}.model_type`, e.target.value)}
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
                value={modelConfig.max_new_tokens || 4096}
                onChange={e => handleModelConfigChange('research_agent_model_config', `${prefix}.max_new_tokens`, Number(e.target.value))}
              />
              <TextField
                fullWidth
                label="Temperature"
                type="number"
                inputProps={{ step: '0.1' }}
                value={modelConfig.temperature || 0.1}
                onChange={e => handleModelConfigChange('research_agent_model_config', `${prefix}.temperature`, parseFloat(e.target.value))}
              />
              {(modelConfig.model_type === 'ollama' || modelConfig.model_type === 'llamacpp') && (
                <TextField
                  fullWidth
                  label="Context Window (num_ctx)"
                  type="number"
                  value={modelConfig.num_ctx || 131072}
                  onChange={e => handleModelConfigChange('research_agent_model_config', `${prefix}.num_ctx`, Number(e.target.value))}
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
        <Card variant="outlined" sx={{ mb: 2 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <Typography variant="h6">Boss Model (Main Coordinator)</Typography>
              <Tooltip title="The primary model that orchestrates the entire research workflow, makes high-level decisions, and coordinates between different nodes. Reasoning models (o1) are highly recommended for complex research orchestration.">
                <IconButton size="small">
                  <InfoOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              <strong>Recommended:</strong> Reasoning models (o1-preview, o1-mini) for superior research coordination and decision-making
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                <ModelNameAutocomplete
                  label="Model Name"
                  value={bossModel.model_name || ''}
                  onChange={value => handleModelConfigChange('research_agent_model_config', `boss_model.model_name`, value)}
                  onModelSelected={selectedModel => handleModelSelectedFromCatalog('research_agent_model_config', selectedModel, 'boss_model')}
                  modelCatalogData={modelCatalogData}
                />
                <FormControl fullWidth>
                  <InputLabel>Model Type (Provider)</InputLabel>
                  <Select
                    value={bossModel.model_type || ''}
                    label="Model Type (Provider)"
                    onChange={e => handleModelConfigChange('research_agent_model_config', `boss_model.model_type`, e.target.value)}
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
                  value={bossModel.max_new_tokens || 4096}
                  onChange={e => handleModelConfigChange('research_agent_model_config', `boss_model.max_new_tokens`, Number(e.target.value))}
                />
                <TextField
                  fullWidth
                  label="Temperature"
                  type="number"
                  inputProps={{ step: '0.1' }}
                  value={bossModel.temperature || 0.1}
                  onChange={e => handleModelConfigChange('research_agent_model_config', `boss_model.temperature`, parseFloat(e.target.value))}
                />
                {(bossModel.model_type === 'ollama' || bossModel.model_type === 'llamacpp') && (
                  <TextField
                    fullWidth
                    label="Context Window (num_ctx)"
                    type="number"
                    value={bossModel.num_ctx || 131072}
                    onChange={e => handleModelConfigChange('research_agent_model_config', `boss_model.num_ctx`, Number(e.target.value))}
                  />
                )}
              </Box>
            </Box>
          </CardContent>
        </Card>
        
        {/* Worker Models */}
        <Box sx={{ mt: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <Typography variant="h6">Worker Models</Typography>
            <Tooltip title="Specialized models for specific tasks like summarization, analysis, and search processing. These handle the detailed work while the Boss Model coordinates the overall workflow.">
              <IconButton size="small">
                <InfoOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
          
          {/* Summary Worker */}
          <Card variant="outlined" sx={{ mb: 2 }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Typography variant="h6">Summary Worker</Typography>
                <Tooltip title="Processes and summarizes full-text content from PDFs and research papers. Instruct models are well-suited for this summarization task.">
                  <IconButton size="small">
                    <InfoOutlinedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                <strong>Recommended:</strong> Instruct models (GPT-4, Claude-3.5, Llama-3) excel at summarization tasks
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <ModelNameAutocomplete
                    label="Model Name"
                    value={workerModels.summary?.model_name || ''}
                    onChange={value => handleModelConfigChange('research_agent_model_config', `worker_models.summary.model_name`, value)}
                    onModelSelected={selectedModel => handleModelSelectedFromCatalog('research_agent_model_config', selectedModel, 'worker_models.summary')}
                    modelCatalogData={modelCatalogData}
                  />
                  <FormControl fullWidth>
                    <InputLabel>Model Type (Provider)</InputLabel>
                    <Select
                      value={workerModels.summary?.model_type || ''}
                      label="Model Type (Provider)"
                      onChange={e => handleModelConfigChange('research_agent_model_config', `worker_models.summary.model_type`, e.target.value)}
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
                    value={workerModels.summary?.max_new_tokens || 4096}
                    onChange={e => handleModelConfigChange('research_agent_model_config', `worker_models.summary.max_new_tokens`, Number(e.target.value))}
                  />
                  <TextField
                    fullWidth
                    label="Temperature"
                    type="number"
                    inputProps={{ step: '0.1' }}
                    value={workerModels.summary?.temperature || 0.1}
                    onChange={e => handleModelConfigChange('research_agent_model_config', `worker_models.summary.temperature`, parseFloat(e.target.value))}
                  />
                  {(workerModels.summary?.model_type === 'ollama' || workerModels.summary?.model_type === 'llamacpp') && (
                    <TextField
                      fullWidth
                      label="Context Window (num_ctx)"
                      type="number"
                      value={workerModels.summary?.num_ctx || 131072}
                      onChange={e => handleModelConfigChange('research_agent_model_config', `worker_models.summary.num_ctx`, Number(e.target.value))}
                    />
                  )}
                </Box>
              </Box>
            </CardContent>
          </Card>

          {/* Analysis Worker */}
          <Card variant="outlined" sx={{ mb: 2 }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Typography variant="h6">Analysis Worker</Typography>
                <Tooltip title="Analyzes research content for quality, relevance, and key insights. Reasoning models provide better analytical capabilities for complex research evaluation.">
                  <IconButton size="small">
                    <InfoOutlinedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                <strong>Recommended:</strong> Reasoning models (o1-preview, o1-mini) for deeper analysis, or strong instruct models (GPT-4, Claude-3.5)
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <ModelNameAutocomplete
                    label="Model Name"
                    value={workerModels.analysis?.model_name || ''}
                    onChange={value => handleModelConfigChange('research_agent_model_config', `worker_models.analysis.model_name`, value)}
                    onModelSelected={selectedModel => handleModelSelectedFromCatalog('research_agent_model_config', selectedModel, 'worker_models.analysis')}
                    modelCatalogData={modelCatalogData}
                  />
                  <FormControl fullWidth>
                    <InputLabel>Model Type (Provider)</InputLabel>
                    <Select
                      value={workerModels.analysis?.model_type || ''}
                      label="Model Type (Provider)"
                      onChange={e => handleModelConfigChange('research_agent_model_config', `worker_models.analysis.model_type`, e.target.value)}
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
                    value={workerModels.analysis?.max_new_tokens || 4096}
                    onChange={e => handleModelConfigChange('research_agent_model_config', `worker_models.analysis.max_new_tokens`, Number(e.target.value))}
                  />
                  <TextField
                    fullWidth
                    label="Temperature"
                    type="number"
                    inputProps={{ step: '0.1' }}
                    value={workerModels.analysis?.temperature || 0.1}
                    onChange={e => handleModelConfigChange('research_agent_model_config', `worker_models.analysis.temperature`, parseFloat(e.target.value))}
                  />
                  {(workerModels.analysis?.model_type === 'ollama' || workerModels.analysis?.model_type === 'llamacpp') && (
                    <TextField
                      fullWidth
                      label="Context Window (num_ctx)"
                      type="number"
                      value={workerModels.analysis?.num_ctx || 131072}
                      onChange={e => handleModelConfigChange('research_agent_model_config', `worker_models.analysis.num_ctx`, Number(e.target.value))}
                    />
                  )}
                </Box>
              </Box>
            </CardContent>
          </Card>

          {/* Search Worker */}
          <Card variant="outlined" sx={{ mb: 2 }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Typography variant="h6">Search Worker</Typography>
                <Tooltip title="Processes search results, filters relevant content, and helps refine search strategies. Instruct models are sufficient for search result processing and filtering.">
                  <IconButton size="small">
                    <InfoOutlinedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                <strong>Recommended:</strong> Instruct models (GPT-4, Claude-3.5, Llama-3) work well for search processing and filtering
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <ModelNameAutocomplete
                    label="Model Name"
                    value={workerModels.search?.model_name || ''}
                    onChange={value => handleModelConfigChange('research_agent_model_config', `worker_models.search.model_name`, value)}
                    onModelSelected={selectedModel => handleModelSelectedFromCatalog('research_agent_model_config', selectedModel, 'worker_models.search')}
                    modelCatalogData={modelCatalogData}
                  />
                  <FormControl fullWidth>
                    <InputLabel>Model Type (Provider)</InputLabel>
                    <Select
                      value={workerModels.search?.model_type || ''}
                      label="Model Type (Provider)"
                      onChange={e => handleModelConfigChange('research_agent_model_config', `worker_models.search.model_type`, e.target.value)}
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
                    value={workerModels.search?.max_new_tokens || 4096}
                    onChange={e => handleModelConfigChange('research_agent_model_config', `worker_models.search.max_new_tokens`, Number(e.target.value))}
                  />
                  <TextField
                    fullWidth
                    label="Temperature"
                    type="number"
                    inputProps={{ step: '0.1' }}
                    value={workerModels.search?.temperature || 0.1}
                    onChange={e => handleModelConfigChange('research_agent_model_config', `worker_models.search.temperature`, parseFloat(e.target.value))}
                  />
                  {(workerModels.search?.model_type === 'ollama' || workerModels.search?.model_type === 'llamacpp') && (
                    <TextField
                      fullWidth
                      label="Context Window (num_ctx)"
                      type="number"
                      value={workerModels.search?.num_ctx || 131072}
                      onChange={e => handleModelConfigChange('research_agent_model_config', `worker_models.search.num_ctx`, Number(e.target.value))}
                    />
                  )}
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Box>
        

        
        {/* Workflow Parameters */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>Workflow Parameters</Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {/* Core Parameters Row */}
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <TextField
                  label="Max Research Context Tokens"
                  type="number"
                  value={config.max_research_context_tokens || 15000}
                  onChange={e => handleModelConfigChange('research_agent_model_config', 'max_research_context_tokens', Number(e.target.value))}
                  sx={{ minWidth: 200 }}
                  inputProps={{ min: 1000, max: 100000 }}
                  helperText="Token budget before compression"
                />
                <TextField
                  label="Compress to Ratio"
                  type="number"
                  value={config.compress_to_ratio || 0.2}
                  onChange={e => handleModelConfigChange('research_agent_model_config', 'compress_to_ratio', parseFloat(e.target.value))}
                  sx={{ minWidth: 150 }}
                  inputProps={{ min: 0.1, max: 0.8, step: 0.1 }}
                  helperText="Target compression ratio"
                />
                <TextField
                  label="Max Research Loops"
                  type="number"
                  value={config.max_research_loops || 3}
                  onChange={e => handleModelConfigChange('research_agent_model_config', 'max_research_loops', Number(e.target.value))}
                  sx={{ minWidth: 150 }}
                  inputProps={{ min: 1, max: 10 }}
                  helperText="Max iteration loops"
                />
              </Box>

              {/* Search & Ranking Parameters Row */}
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <TextField
                  label="Initial Rerank Top K"
                  type="number"
                  value={config.initial_rerank_top_k || 40}
                  onChange={e => handleModelConfigChange('research_agent_model_config', 'initial_rerank_top_k', Number(e.target.value))}
                  sx={{ minWidth: 150 }}
                  inputProps={{ min: 5, max: 100 }}
                  helperText="Papers to re-rank"
                />
              </Box>

              {/* PDF Full Text Processing Section */}
              <Box sx={{ 
                p: 2, 
                border: '1px solid', 
                borderColor: 'divider', 
                borderRadius: 1,
                backgroundColor: 'background.default'
              }}>
                <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
                  PDF Full Text Processing
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Enable processing of full PDF content from top-ranked sources for enhanced evidence quality
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, alignItems: 'center' }}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={config.enable_full_text !== false} // Default to true if undefined
                        onChange={e => handleModelConfigChange('research_agent_model_config', 'enable_full_text', e.target.checked)}
                        color="primary"
                      />
                    }
                    label={
                      <Box>
                        <Typography variant="body2" fontWeight={500}>
                          Enable PDF Processing
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Extract full text from PDFs for better analysis
                        </Typography>
                      </Box>
                    }
                  />
                  <TextField
                    label="Max PDFs to Process"
                    type="number"
                    value={config.full_text_top_n || 20}
                    onChange={e => handleModelConfigChange('research_agent_model_config', 'full_text_top_n', Number(e.target.value))}
                    sx={{ minWidth: 180 }}
                    inputProps={{ min: 1, max: 50 }}
                    helperText="Number of top sources for full text"
                    disabled={config.enable_full_text === false}
                  />
                  <TextField
                    label="Chunk Size (Tokens)"
                    type="number"
                    value={config.max_chunk_tokens || 8000}
                    onChange={e => handleModelConfigChange('research_agent_model_config', 'max_chunk_tokens', Number(e.target.value))}
                    sx={{ minWidth: 180 }}
                    inputProps={{ min: 2000, max: 20000, step: 1000 }}
                    helperText="Max tokens per chunk for processing"
                    disabled={config.enable_full_text === false}
                  />
                  <TextField
                    label="Summary Target (Tokens)"
                    type="number"
                    value={config.summary_target_tokens || 1500}
                    onChange={e => handleModelConfigChange('research_agent_model_config', 'summary_target_tokens', Number(e.target.value))}
                    sx={{ minWidth: 180 }}
                    inputProps={{ min: 500, max: 4000, step: 250 }}
                    helperText="Target tokens for each summary"
                    disabled={config.enable_full_text === false}
                  />
                </Box>
              </Box>
            </Box>
          </CardContent>
        </Card>

        {/* External API Configuration */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>External API Configuration</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Configure rate limits and timeouts for external research APIs
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              <TextField
                label="ArXiv Rate Limit"
                type="number"
                value={config.arxiv_rate_limit || 3.0}
                onChange={e => handleModelConfigChange('research_agent_model_config', 'arxiv_rate_limit', parseFloat(e.target.value))}
                sx={{ minWidth: 180 }}
                inputProps={{ min: 0.5, max: 10.0, step: 0.5 }}
                helperText="Requests per second to ArXiv API"
              />
            </Box>
          </CardContent>
        </Card>

        {/* Node-Specific Models - Collapsible */}
        <Accordion sx={{ mt: 2 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="h6">Node-Specific Models (Optional)</Typography>
              <Tooltip title="Override default models for specific workflow nodes. Leave empty to use Boss/Worker models. These allow fine-tuning performance for specialized tasks.">
                <IconButton size="small">
                  <InfoOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {/* Query Planner Model */}
              <Card variant="outlined">
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <Typography variant="h6">Query Planner Model</Typography>
                    <Tooltip title="Breaks down your research question into focused sub-queries for targeted search. Reasoning models (like o1) excel at this complex decomposition task, but instruct models work fine for straightforward questions.">
                      <IconButton size="small">
                        <InfoOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    <strong>Recommended:</strong> Reasoning models (o1-preview, o1-mini) for complex question decomposition, or instruct models for simpler queries
                  </Typography>
                  {renderModelFields(config.query_planner_model || {}, 'query_planner_model', '')}
                </CardContent>
              </Card>

              {/* Evidence Selector Model */}
              <Card variant="outlined">
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <Typography variant="h6">Evidence Selector Model</Typography>
                    <Tooltip title="Evaluates source quality, relevance, and determines if gathered evidence is sufficient to answer the research question. Benefits from reasoning capabilities for quality assessment.">
                      <IconButton size="small">
                        <InfoOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    <strong>Recommended:</strong> Reasoning models (o1-preview, o1-mini) for better quality assessment, or strong instruct models (GPT-4, Claude-3.5)
                  </Typography>
                  {renderModelFields(config.evidence_selector_model || {}, 'evidence_selector_model', '')}
                </CardContent>
              </Card>

              {/* Compression Model */}
              <Card variant="outlined">
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <Typography variant="h6">Compression Model</Typography>
                    <Tooltip title="Compresses research evidence when token budget is exceeded, preserving the most important information while reducing length. Instruct models are sufficient for this summarization task.">
                      <IconButton size="small">
                        <InfoOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    <strong>Recommended:</strong> Instruct models (GPT-4, Claude-3.5, Llama-3) work well for summarization and compression
                  </Typography>
                  {renderModelFields(config.compression_model || {}, 'compression_model', '')}
                </CardContent>
              </Card>

              {/* Answer Generator Model */}
              <Card variant="outlined">
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <Typography variant="h6">Answer Generator Model</Typography>
                    <Tooltip title="Creates the final comprehensive research report by synthesizing all gathered evidence into a coherent, well-structured answer. Reasoning models provide better synthesis and analysis.">
                      <IconButton size="small">
                        <InfoOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    <strong>Recommended:</strong> Reasoning models (o1-preview, o1-mini) for superior synthesis and analysis, or high-quality instruct models
                  </Typography>
                  {renderModelFields(config.answer_generator_model || {}, 'answer_generator_model', '')}
                </CardContent>
              </Card>
            </Box>
          </AccordionDetails>
        </Accordion>
      </Box>
    );
  };

  if (isLoadingOrchestration || isLoadingProviders || isCheckingDbTasks) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh" sx={{ pt: `${headerHeight + 24}px` }}>
        <CircularProgress />
        {isCheckingDbTasks && (
          <Typography variant="body2" sx={{ ml: 2 }}>
            Checking for active database tasks...
          </Typography>
        )}
      </Box>
    );
  }
  
  if (isErrorOrchestration) setError('Failed to load orchestration config.');
  if (isErrorProviders) setError('Failed to load model providers.');


  const renderModelConfigFields = (modelKey: string, config: any) => {
    if (!config) return <Typography>Configuration not available for {modelKey}.</Typography>;

    const currentConfig = orchestrationConfig?.[modelKey] || {};

    // Research Agent model is a special case (boss + worker models)
    if (modelKey === 'research_agent_model_config') {
      // Use editedResearchAgentConfig for research agent to maintain local state
      return renderResearchAgentModelConfig(editedResearchAgentConfig || currentConfig);
    }

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
                {(currentConfig.summarization_model?.model_type === 'ollama' || currentConfig.summarization_model?.model_type === 'llamacpp') && (
                  <TextField
                    fullWidth
                    label="Context Window (num_ctx)"
                    type="number"
                    value={currentConfig.summarization_model?.num_ctx || 4096}
                    onChange={e => handleModelConfigChange(modelKey, 'summarization_model.num_ctx', Number(e.target.value))}
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
             (currentConfig.model_type === 'ollama' || currentConfig.model_type === 'llamacpp')
          ) && (
            <TextField
              fullWidth
              label="Context Window (num_ctx)"
              type="number"
              value={currentConfig.num_ctx}
              onChange={e => handleModelConfigChange(modelKey, 'num_ctx', Number(e.target.value))}
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

      {appPasswordFailed && (
        <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setAppPasswordFailed(false)}>
          Gmail authentication failed. Your application password didn't work. Please enter your credentials again.
        </Alert>
      )}

      {dbTaskState.exportError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setExportError(null)}>
          Export Error: {dbTaskState.exportError}
        </Alert>
      )}

      {dbTaskState.importError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setImportError(null)}>
          Import Error: {dbTaskState.importError}
        </Alert>
      )}

      <Typography variant="h4" gutterBottom component="div" sx={{ mb: 3 }}>
        <SettingsIcon sx={{ mr: 1, verticalAlign: 'middle' }}/> Settings
      </Typography>

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
                  {tabDef.key === 'research_agent_model_config' ? (
                    editedResearchAgentConfig ?
                      renderModelConfigFields(tabDef.key, editedResearchAgentConfig)
                      : <Typography>Loading configuration...</Typography>
                  ) : (
                    orchestrationConfig && orchestrationConfig[tabDef.key] ?
                      renderModelConfigFields(tabDef.key, orchestrationConfig[tabDef.key])
                      : <Typography>Loading configuration for {tabDef.label}...</Typography>
                  )}
                  <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
                    <Button
                      variant="contained"
                      onClick={() => {
                        if (!orchestrationConfig) return;
                        
                        // Create a mutable copy of the config to be sent
                        const configToUpdate = JSON.parse(JSON.stringify(orchestrationConfig));

                        // If we are saving the research agent, use the cleaned local state
                        if (tabDef.key === 'research_agent_model_config') {
                          const cleanedConfig = cleanResearchAgentConfig(editedResearchAgentConfig);
                          if (cleanedConfig) {
                            configToUpdate.research_agent_model_config = cleanedConfig;
                            updateOrchestrationMutation.mutate(configToUpdate);
                          }
                        } else {
                          // For other tabs, just save the entire orchestration config
                          updateOrchestrationMutation.mutate(configToUpdate);
                        }
                      }}
                      disabled={updateOrchestrationMutation.isPending}
                    >
                      Save {tabDef.label} Settings
                    </Button>
                  </Box>
                </CardContent>
              </Card>
            </TabPanel>
          ))}
        </CardContent>
      </Card>

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
                      helperText="Embeddings computed per batch"
                      inputProps={{ min: 32, max: 2048 }}
                    />
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

      {/* API Credentials Section */}
      <Accordion sx={{ mb: 4 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h5" fontWeight={600}>
            API Credentials
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 700 }}>
            {CREDENTIAL_KEYS.map((key) => (
              <TextField
                key={key}
                label={key}
                type={(key === 'OLLAMA_URL' || key === 'CUSTOM_OAI_BASE_URL') ? 'text' : (showCreds[key] ? 'text' : 'password')}
                value={credValues[key] || ''}
                onChange={e => setCredValues({ ...credValues, [key]: e.target.value })}
                InputProps={{
                  endAdornment:
                    (key === 'OLLAMA_URL' || key === 'CUSTOM_OAI_BASE_URL') ? null : (
                      <IconButton onClick={() => setShowCreds({ ...showCreds, [key]: !showCreds[key] })}>
                        {showCreds[key] ? <VisibilityOffIcon /> : <VisibilityIcon />}
                      </IconButton>
                    )
                }}
              />
            ))}
            <Box sx={{ mt: 2 }}>
              <Button
                variant="contained"
                onClick={() => updateCredentialsMutation.mutate(credValues)}
                disabled={updateCredentialsMutation.isPending}
              >
                Apply Credentials
              </Button>
            </Box>
          </Box>
        </AccordionDetails>
      </Accordion>

      {/* Database Management Section */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5" fontWeight={600} sx={{ flex: 1 }}>
              Database Management
            </Typography>
            <Tooltip title="Import and export your Theseus Insight database for backup and migration purposes.">
              <InfoOutlinedIcon color="action" />
            </Tooltip>
          </Box>
          <Typography variant="body2" sx={{ mb: 3 }}>
            Backup and restore your database, including papers, settings, and all application data.
          </Typography>
          
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, maxWidth: 700 }}>
            {/* Export Section */}
            <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
              <Typography variant="h6" gutterBottom>
                Export Database
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Create a backup of your entire database as a compressed archive.
              </Typography>
              <Button
                variant="contained"
                color="primary"
                onClick={() => exportDatabaseMutation.mutate()}
                disabled={dbTaskState.isExporting || exportDatabaseMutation.isPending}
                startIcon={dbTaskState.isExporting ? <CircularProgress size={20} /> : undefined}
                sx={{ mr: 2 }}
              >
                {dbTaskState.isExporting ? 'Exporting...' : 'Export Database'}
              </Button>
              {dbTaskState.isExporting && (
                <Button
                  variant="outlined"
                  color="secondary"
                  onClick={() => clearExportTask()}
                  sx={{ mr: 2 }}
                >
                  Clear Export Task
                </Button>
              )}
              {dbTaskState.isExporting && (

                <Box sx={{ mt: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Box sx={{ width: '100%' }}>
                      <LinearProgress
                        variant="determinate"
                        value={dbTaskState.exportProgress}
                        sx={{ height: 8, borderRadius: 4 }}
                      />
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      {Math.round(dbTaskState.exportProgress)}%
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    {dbTaskState.exportStatus || 'This may take a few minutes for large databases...'}
                  </Typography>
                </Box>
              )}
            </Box>

            {/* Import Section */}
            <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
              <Typography variant="h6" gutterBottom>
                Import Database
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Restore a database from a previously exported backup file (.tar.gz).
              </Typography>
              
              {/* Import Mode Selection */}
              <FormControlLabel
                control={
                  <Switch
                    checked={importMode === 'overwrite'}
                    onChange={(e) => setImportMode(e.target.checked ? 'overwrite' : 'merge')}
                    color="warning"
                  />
                }
                label={
                  <Box>
                    <Typography variant="body2" fontWeight={500}>
                      Complete Overwrite Mode
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {importMode === 'merge' 
                        ? 'Default: Merge mode - adds new records, preserves existing data'
                        : 'Destructive: Replaces ALL existing data with backup content'
                      }
                    </Typography>
                  </Box>
                }
                sx={{ mb: 2, display: 'block' }}
              />
              
              {importMode === 'overwrite' && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  <strong>Warning:</strong> Complete overwrite will permanently delete all current data and replace it with the backup. This action cannot be undone.
                </Alert>
              )}
              
              {importMode === 'merge' && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  <strong>Merge Mode:</strong> New records will be added to your database. Existing records will be preserved. Any conflicts will be skipped.
                </Alert>
              )}
              
              <input
                accept=".tar.gz,.tgz,application/gzip,application/x-gzip,application/x-tar"
                style={{ display: 'none' }}
                id="database-import-file"
                type="file"
                onChange={handleDatabaseImportFile}
              />
              <label htmlFor="database-import-file">
                <Button
                  variant="outlined"
                  component="span"
                  disabled={importDatabaseMutation.isPending}
                  sx={{ mr: 2 }}
                >
                  Select Backup File
                </Button>
              </label>
              {selectedImportFile && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    Selected file: {selectedImportFile.name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Import mode: <strong>{importMode === 'merge' ? 'Merge (Safe)' : 'Complete Overwrite (Destructive)'}</strong>
                  </Typography>
                  {!dbTaskState.isImporting ? (
                    <Button
                      variant="contained"
                      color={importMode === 'overwrite' ? 'error' : 'primary'}
                      onClick={handleDatabaseImport}
                      disabled={importDatabaseMutation.isPending}
                    >
                      {importDatabaseMutation.isPending 
                        ? 'Starting...' 
                        : `${importMode === 'merge' ? 'Merge' : 'Overwrite'} Database`
                      }
                    </Button>
                  ) : (
                    <Box sx={{ mb: 2 }}>
                      <Button
                        variant="outlined"
                        color="secondary"
                        onClick={() => clearImportTask()}
                        sx={{ mr: 2 }}
                      >
                        Clear Import Task
                      </Button>
                    </Box>
                  )}
                  {dbTaskState.isImporting && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="body2" sx={{ mb: 1 }}>
                        {dbTaskState.importStatus}
                      </Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box sx={{ width: '100%' }}>
                          <LinearProgress 
                            variant="determinate" 
                            value={dbTaskState.importProgress} 
                            sx={{ height: 8, borderRadius: 4 }}
                          />
                        </Box>
                        <Typography variant="body2" color="text.secondary">
                          {Math.round(dbTaskState.importProgress)}%
                        </Typography>
                      </Box>
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                        Please don't close this page while importing...
                      </Typography>
                    </Box>
                  )}
                </Box>
              )}
            </Box>
          </Box>
        </CardContent>
      </Card>

    </Container>
  );
};

export default Settings;
