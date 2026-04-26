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
  Chip,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi, modelCatalogApi, performanceApi, researchAgentApi, ollamaServersApi } from '../services/api';
import type { PerformanceConfig, SystemInfo } from '../services/api';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import SettingsIcon from '@mui/icons-material/Settings';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import SpeedIcon from '@mui/icons-material/Speed';
import MemoryIcon from '@mui/icons-material/Memory';
import DeveloperModeIcon from '@mui/icons-material/DeveloperMode';
import PaletteIcon from '@mui/icons-material/Palette';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import GroupWorkIcon from '@mui/icons-material/GroupWork';
import { useDatabaseTaskState } from '../hooks/useDatabaseTaskState';
import DisplayTweaks from '../components/observatory/DisplayTweaks';
import { useLayout } from '../contexts/LayoutContext';
import { ScheduledTasksSettings } from '../components/ScheduledTasksSettings';
import OllamaServersSettings from '../components/OllamaServersSettings';

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
  { key: 'mind_map_config', label: 'Mind-Map Explorer', tooltip: 'Configuration for mind-map visualization and paper relationship exploration.' },
  { key: 'inference_servers', label: 'Inference Servers', tooltip: 'Configure multiple Ollama and LMStudio servers for distributed bulk processing.' },
];

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
      // User selected from catalog - update the input field immediately and call batch update
      onChange(newValue.model_string);
      if (onModelSelected) {
        onModelSelected(newValue);
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
  const { headerHeight } = useLayout(); // Get dynamic header height
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [tab, setTab] = useState(0);
  const [researchAgentTab, setResearchAgentTab] = useState(0);

  const [selectedImportFile, setSelectedImportFile] = useState<File | null>(null);
  const [importMode, setImportMode] = useState<'merge' | 'overwrite'>('merge');

  // Profile mapping options for import
  const [importMappingStrategy, setImportMappingStrategy] = useState<'auto' | 'create_new' | 'merge_to' | 'match_by_name'>('auto');
  const [importMergeToProfileId, setImportMergeToProfileId] = useState<number | null>(null);
  const [importNewProfileName, setImportNewProfileName] = useState<string>('');
  
  // Incremental export state
  const [exportMode, setExportMode] = useState<'full' | 'incremental' | 'profile'>('full');
  const [incrementalSince, setIncrementalSince] = useState<string>('');
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [exportOptions, setExportOptions] = useState({
    streaming: false,
    parallel: false,
    batch_size: 1000,
    max_workers: 4
  });

  // Profile-scoped export state
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [profileExportOptions, setProfileExportOptions] = useState({
    include_fulltext: true,
    include_topics: false,
    include_newsletters: false,
    include_podcasts: false,
    include_lit_reviews: false,
    include_research_runs: false,
    include_mindmap_reports: false,
    include_model_catalog: false
  });

  // Research Agent Configuration State
  const [singleAgentConfig, setSingleAgentConfig] = useState<any>({});
  const [multiAgentConfig, setMultiAgentConfig] = useState<any>({});
  
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

  // Research Agent Configuration Queries
  const { data: researchModes, isLoading: isLoadingResearchModes } = useQuery({
    queryKey: ['researchModes'],
    queryFn: () => researchAgentApi.getModes().then(res => res.data),
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
  const { data: researchProfiles } = useQuery({
    queryKey: ['researchProfilesForExport'],
    queryFn: async () => {
      const response = await fetch('/api/profiles');
      if (!response.ok) throw new Error('Failed to fetch profiles');
      return response.json();
    }
  });
  
  const updateOrchestrationMutation = useMutation({
    mutationFn: (newConfig: any) => settingsApi.updateOrchestrationConfig(newConfig),
    onSuccess: (data) => {
      queryClient.setQueryData(['orchestrationConfig'], data.data); // Assuming API returns the updated config
      queryClient.invalidateQueries({ queryKey: ['orchestrationConfig'] });
      setSuccess('Configuration updated successfully');
    },
    onError: (error: any) => setError(error.message || 'Failed to update configuration'),
  });

  // Research Agent Configuration Mutations
  const setResearchModeMutation = useMutation({
    mutationFn: (mode: 'single' | 'multi') => researchAgentApi.setMode(mode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['researchModes'] });
      setSuccess('Research agent mode updated successfully');
    },
    onError: (error: any) => setError(error.message || 'Failed to update research agent mode'),
  });

  const updateSingleAgentConfigMutation = useMutation({
    mutationFn: (config: any) => researchAgentApi.setModeConfig('single', config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['researchModes'] });
      setSuccess('Single-agent configuration updated successfully');
    },
    onError: (error: any) => setError(error.message || 'Failed to update single-agent configuration'),
  });

  const updateMultiAgentConfigMutation = useMutation({
    mutationFn: (config: any) => researchAgentApi.setModeConfig('multi', config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['researchModes'] });
      setSuccess('Multi-agent configuration updated successfully');
    },
    onError: (error: any) => setError(error.message || 'Failed to update multi-agent configuration'),
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
    mutationFn: () => {
      const options: any = {};

      if (exportMode === 'profile') {
        // Profile-scoped export
        if (!selectedProfileId) {
          throw new Error('Please select a profile for profile-scoped export');
        }
        options.profile_id = selectedProfileId;
        options.include_fulltext = profileExportOptions.include_fulltext;
        options.include_topics = profileExportOptions.include_topics;
        options.include_newsletters = profileExportOptions.include_newsletters;
        options.include_podcasts = profileExportOptions.include_podcasts;
        options.include_lit_reviews = profileExportOptions.include_lit_reviews;
        options.include_research_runs = profileExportOptions.include_research_runs;
        options.include_mindmap_reports = profileExportOptions.include_mindmap_reports;
        options.include_model_catalog = profileExportOptions.include_model_catalog;
        options.streaming = exportOptions.streaming;
      } else if (exportMode === 'incremental') {
        options.incremental = true;
        if (incrementalSince) {
          // Convert date to ISO format with timezone
          const date = new Date(incrementalSince);
          options.since_timestamp = date.toISOString();
        }
        if (selectedTables.length > 0) {
          options.tables = selectedTables;
        }
        // Add performance options for incremental
        options.streaming = exportOptions.streaming;
        options.parallel = exportOptions.parallel;
        options.batch_size = exportOptions.batch_size;
        options.max_workers = exportOptions.max_workers;
      } else {
        // Full export - add performance options
        options.streaming = exportOptions.streaming;
        options.parallel = exportOptions.parallel;
        options.batch_size = exportOptions.batch_size;
        options.max_workers = exportOptions.max_workers;
      }

      return settingsApi.startExportDatabase(options);
    },
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
    mutationFn: ({ file, mode, mappingStrategy, mergeToProfileId, newProfileName }: {
      file: File;
      mode: 'merge' | 'overwrite';
      mappingStrategy?: string;
      mergeToProfileId?: number | null;
      newProfileName?: string;
    }) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('mode', mode);

      if (mappingStrategy) {
        formData.append('mapping_strategy', mappingStrategy);
      }
      if (mergeToProfileId) {
        formData.append('merge_to_profile_id', mergeToProfileId.toString());
      }
      if (newProfileName) {
        formData.append('new_profile_name', newProfileName);
      }

      return settingsApi.importDatabase(file, mode);
    },
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

  // Initialize research agent configurations
  useEffect(() => {
    if (researchModes) {
      setSingleAgentConfig(researchModes.single_agent_config || {});
      setMultiAgentConfig(researchModes.multi_agent_config || {});
    }
  }, [researchModes]);

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

  const handleDatabaseImportFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    setSelectedImportFile(file || null);
  };

  const handleDatabaseImport = () => {
    if (selectedImportFile) {
      importDatabaseMutation.mutate({
        file: selectedImportFile,
        mode: importMode,
        mappingStrategy: importMappingStrategy,
        mergeToProfileId: importMergeToProfileId,
        newProfileName: importNewProfileName
      });
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

  if (isLoadingOrchestration || isLoadingProviders || isCheckingDbTasks || isLoadingResearchModes) {
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

      {/* Display / Observatory tweaks */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5" fontWeight={600} sx={{ flex: 1 }}>
              <PaletteIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              Display
            </Typography>
            <Tooltip title="Tune the Observatory visual system: accent color, density, and card surface style.">
              <InfoOutlinedIcon color="action" />
            </Tooltip>
          </Box>
          <Typography variant="body2" sx={{ mb: 3 }} color="text.secondary">
            Tune the Observatory visual system live across every page.
          </Typography>

          <DisplayTweaks />
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
                Create a backup of your database as a compressed archive.
              </Typography>
              
              {/* Export Mode Selection */}
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Export Mode</InputLabel>
                <Select
                  value={exportMode}
                  label="Export Mode"
                  onChange={(e) => setExportMode(e.target.value as 'full' | 'incremental' | 'profile')}
                >
                  <MenuItem value="full">
                    <Box>
                      <Typography variant="body2" fontWeight={500}>Full Export</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Export all data in the database
                      </Typography>
                    </Box>
                  </MenuItem>
                  <MenuItem value="incremental">
                    <Box>
                      <Typography variant="body2" fontWeight={500}>Incremental Export</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Export only changes since a specific date
                      </Typography>
                    </Box>
                  </MenuItem>
                  <MenuItem value="profile">
                    <Box>
                      <Typography variant="body2" fontWeight={500}>Profile-Scoped Export</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Export a specific research profile with its papers
                      </Typography>
                    </Box>
                  </MenuItem>
                </Select>
              </FormControl>
              
              {/* Incremental Options */}
              {exportMode === 'incremental' && (
                <Box sx={{ mb: 2, pl: 4 }}>
                  <TextField
                    label="Export changes since"
                    type="datetime-local"
                    value={incrementalSince}
                    onChange={(e) => setIncrementalSince(e.target.value)}
                    InputLabelProps={{ shrink: true }}
                    helperText="Leave empty to auto-detect from last export"
                    sx={{ mb: 2, width: '100%', maxWidth: 300 }}
                  />

                  <FormControl sx={{ mb: 2, width: '100%', maxWidth: 400 }}>
                    <InputLabel>Tables to export (optional)</InputLabel>
                    <Select
                      multiple
                      value={selectedTables}
                      onChange={(e) => setSelectedTables(e.target.value as string[])}
                      renderValue={(selected) => selected.join(', ')}
                    >
                      {['papers', 'research_runs', 'mindmap_reports', 'research_agent_state',
                        'paper_fulltext', 'topics', 'research_profiles', 'podcasts', 'newsletters'].map((table) => (
                        <MenuItem key={table} value={table}>
                          {table}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Box>
              )}

              {/* Profile-Scoped Export Options */}
              {exportMode === 'profile' && (
                <Box sx={{ mb: 2, pl: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                  <Typography variant="body2" fontWeight={500} gutterBottom>
                    Profile-Scoped Export Settings
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
                    Export a single research profile with all its related data (papers, scores, interests)
                  </Typography>

                  <FormControl fullWidth sx={{ mb: 2 }}>
                    <InputLabel>Select Research Profile</InputLabel>
                    <Select
                      value={selectedProfileId || ''}
                      label="Select Research Profile"
                      onChange={(e) => setSelectedProfileId(e.target.value as number)}
                    >
                      {researchProfiles?.map((profile: any) => (
                        <MenuItem key={profile.id} value={profile.id}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Box
                              sx={{
                                width: 12,
                                height: 12,
                                borderRadius: '50%',
                                bgcolor: profile.color || '#888'
                              }}
                            />
                            <Typography>{profile.name}</Typography>
                          </Box>
                        </MenuItem>
                      )) || []}
                    </Select>
                  </FormControl>

                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={profileExportOptions.include_fulltext}
                          onChange={(e) => setProfileExportOptions({
                            ...profileExportOptions,
                            include_fulltext: e.target.checked
                          })}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">Include Full-text Content</Typography>
                          <Typography variant="caption" color="text.secondary">
                            Export full-text content for papers (if available)
                          </Typography>
                        </Box>
                      }
                    />

                    <FormControlLabel
                      control={
                        <Switch
                          checked={profileExportOptions.include_topics}
                          onChange={(e) => setProfileExportOptions({
                            ...profileExportOptions,
                            include_topics: e.target.checked
                          })}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">Include Topic Relationships</Typography>
                          <Typography variant="caption" color="text.secondary">
                            Export topic classifications and relationships
                          </Typography>
                        </Box>
                      }
                    />

                    <FormControlLabel
                      control={
                        <Switch
                          checked={profileExportOptions.include_newsletters}
                          onChange={(e) => setProfileExportOptions({
                            ...profileExportOptions,
                            include_newsletters: e.target.checked
                          })}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">Include Newsletters</Typography>
                          <Typography variant="caption" color="text.secondary">
                            Export all newsletters
                          </Typography>
                        </Box>
                      }
                    />

                    <FormControlLabel
                      control={
                        <Switch
                          checked={profileExportOptions.include_podcasts}
                          onChange={(e) => setProfileExportOptions({
                            ...profileExportOptions,
                            include_podcasts: e.target.checked
                          })}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">Include Podcasts</Typography>
                          <Typography variant="caption" color="text.secondary">
                            Export all podcast episodes
                          </Typography>
                        </Box>
                      }
                    />

                    <FormControlLabel
                      control={
                        <Switch
                          checked={profileExportOptions.include_lit_reviews}
                          onChange={(e) => setProfileExportOptions({
                            ...profileExportOptions,
                            include_lit_reviews: e.target.checked
                          })}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">Include Literature Reviews</Typography>
                          <Typography variant="caption" color="text.secondary">
                            Export all literature reviews
                          </Typography>
                        </Box>
                      }
                    />

                    <FormControlLabel
                      control={
                        <Switch
                          checked={profileExportOptions.include_research_runs}
                          onChange={(e) => setProfileExportOptions({
                            ...profileExportOptions,
                            include_research_runs: e.target.checked
                          })}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">Include Research Runs</Typography>
                          <Typography variant="caption" color="text.secondary">
                            Export research agent runs
                          </Typography>
                        </Box>
                      }
                    />

                    <FormControlLabel
                      control={
                        <Switch
                          checked={profileExportOptions.include_mindmap_reports}
                          onChange={(e) => setProfileExportOptions({
                            ...profileExportOptions,
                            include_mindmap_reports: e.target.checked
                          })}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">Include Mindmap Reports</Typography>
                          <Typography variant="caption" color="text.secondary">
                            Export mindmap reports
                          </Typography>
                        </Box>
                      }
                    />

                    <FormControlLabel
                      control={
                        <Switch
                          checked={profileExportOptions.include_model_catalog}
                          onChange={(e) => setProfileExportOptions({
                            ...profileExportOptions,
                            include_model_catalog: e.target.checked
                          })}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">Include Model Catalog</Typography>
                          <Typography variant="caption" color="text.secondary">
                            Export model catalog configuration
                          </Typography>
                        </Box>
                      }
                    />
                  </Box>

                  {selectedProfileId && (
                    <Alert severity="info" sx={{ mt: 2 }}>
                      This will export only the selected profile and papers scored by that profile.
                      Use this to share or migrate specific research areas.
                    </Alert>
                  )}
                </Box>
              )}
              
              {/* Advanced Options */}
              <Accordion sx={{ mb: 2 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="body2">Advanced Export Options</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={exportOptions.streaming}
                          onChange={(e) => setExportOptions({...exportOptions, streaming: e.target.checked})}
                        />
                      }
                      label="Enable streaming (for large datasets)"
                    />
                    <FormControlLabel
                      control={
                        <Switch
                          checked={exportOptions.parallel}
                          onChange={(e) => setExportOptions({...exportOptions, parallel: e.target.checked})}
                        />
                      }
                      label="Enable parallel processing"
                    />
                    {exportOptions.parallel && (
                      <Box sx={{ pl: 3 }}>
                        <Typography variant="body2" gutterBottom>
                          Max Workers: {exportOptions.max_workers}
                        </Typography>
                        <Slider
                          value={exportOptions.max_workers}
                          onChange={(_, value) => setExportOptions({...exportOptions, max_workers: value as number})}
                          min={1}
                          max={8}
                          marks
                          sx={{ maxWidth: 200 }}
                        />
                      </Box>
                    )}
                  </Box>
                </AccordionDetails>
              </Accordion>
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

              {/* Profile Mapping Options for Merge Mode */}
              {importMode === 'merge' && (
                <Accordion sx={{ mb: 2 }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="body2">Profile Mapping Options (for profile-scoped imports)</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <Typography variant="caption" color="text.secondary">
                        Configure how imported profiles should be mapped to existing profiles
                      </Typography>

                      <FormControl fullWidth>
                        <InputLabel>Mapping Strategy</InputLabel>
                        <Select
                          value={importMappingStrategy}
                          label="Mapping Strategy"
                          onChange={(e) => setImportMappingStrategy(e.target.value as any)}
                        >
                          <MenuItem value="auto">
                            <Box>
                              <Typography variant="body2">Auto (Recommended)</Typography>
                              <Typography variant="caption" color="text.secondary">
                                Match by name, create if not exists
                              </Typography>
                            </Box>
                          </MenuItem>
                          <MenuItem value="create_new">
                            <Box>
                              <Typography variant="body2">Create New Profile</Typography>
                              <Typography variant="caption" color="text.secondary">
                                Always create a new profile
                              </Typography>
                            </Box>
                          </MenuItem>
                          <MenuItem value="merge_to">
                            <Box>
                              <Typography variant="body2">Merge To Existing</Typography>
                              <Typography variant="caption" color="text.secondary">
                                Merge into a specific profile
                              </Typography>
                            </Box>
                          </MenuItem>
                          <MenuItem value="match_by_name">
                            <Box>
                              <Typography variant="body2">Match By Name</Typography>
                              <Typography variant="caption" color="text.secondary">
                                Must match existing profile name
                              </Typography>
                            </Box>
                          </MenuItem>
                        </Select>
                      </FormControl>

                      {importMappingStrategy === 'merge_to' && (
                        <FormControl fullWidth>
                          <InputLabel>Target Profile</InputLabel>
                          <Select
                            value={importMergeToProfileId || ''}
                            label="Target Profile"
                            onChange={(e) => setImportMergeToProfileId(e.target.value as number)}
                          >
                            {researchProfiles?.map((profile: any) => (
                              <MenuItem key={profile.id} value={profile.id}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <Box
                                    sx={{
                                      width: 12,
                                      height: 12,
                                      borderRadius: '50%',
                                      bgcolor: profile.color || '#888'
                                    }}
                                  />
                                  <Typography>{profile.name}</Typography>
                                </Box>
                              </MenuItem>
                            )) || []}
                          </Select>
                        </FormControl>
                      )}

                      {importMappingStrategy === 'create_new' && (
                        <TextField
                          fullWidth
                          label="New Profile Name (optional)"
                          value={importNewProfileName}
                          onChange={(e) => setImportNewProfileName(e.target.value)}
                          helperText="Leave empty to use original name with '(Imported)' suffix"
                        />
                      )}
                    </Box>
                  </AccordionDetails>
                </Accordion>
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
