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
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  LinearProgress,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi, researchAgentApi, modelCatalogApi } from '../services/api';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import SettingsIcon from '@mui/icons-material/Settings';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import taxonomy from '../arxiv_taxonomy.json';
import { useDatabaseTaskState } from '../hooks/useDatabaseTaskState';


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
  // Alias taxonomy as any to allow dynamic indexing
  const taxonomyAny = taxonomy as any;
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [tab, setTab] = useState(0);
  const [selectedArxivMain, setSelectedArxivMain] = useState<string>('');
  const [selectedArxivSubs, setSelectedArxivSubs] = useState<string[]>([]);
  const [researchInterestsInput, setResearchInterestsInput] = useState<string>('');
  const [emailRecipientsInput, setEmailRecipientsInput] = useState<string>('');
  const [selectedImportFile, setSelectedImportFile] = useState<File | null>(null);
  const [importMode, setImportMode] = useState<'merge' | 'overwrite'>('merge');
  
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

  const { data: arxivCategories, isLoading: isLoadingArxiv } = useQuery({
    queryKey: ['arxivCategories'],
    queryFn: () => settingsApi.getArxivCategories().then(res => res.data),
  });

  const { data: researchInterests, isLoading: isLoadingResearch } = useQuery({
    queryKey: ['researchInterests'],
    queryFn: () => settingsApi.getResearchInterests().then(res => res.data),
  });

  const { data: emailRecipients, isLoading: isLoadingEmail } = useQuery({
    queryKey: ['emailRecipients'],
    queryFn: () => settingsApi.getEmailRecipients().then(res => res.data),
  });

  const { data: modelProviders, isLoading: isLoadingProviders, isError: isErrorProviders } = useQuery<any[], Error>({
    queryKey: ['modelProviders'],
    queryFn: () => settingsApi.getModelProviders().then(res => res.data || []),
  });

  const { data: researchAgentModelConfig, isLoading: isLoadingResearchAgent } = useQuery({
    queryKey: ['researchAgentModelConfig'],
    queryFn: () => researchAgentApi.getModelConfig().then((res: any) => res.data),
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

  const updateArxivCategoriesMutation = useMutation({
    mutationFn: (config: any) => settingsApi.updateArxivCategories(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['arxivCategories'] });
      setSuccess('ArXiv categories updated successfully');
    },
    onError: (error: any) => setError(error.message),
  });

  const updateResearchInterestsMutation = useMutation({
    mutationFn: (data: any) => settingsApi.updateResearchInterests(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['researchInterests'] });
      setSuccess('Research interests updated successfully');
    },
    onError: (error: any) => setError(error.message),
  });

  const updateEmailRecipientsMutation = useMutation({
    mutationFn: (data: any) => settingsApi.updateEmailRecipients(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emailRecipients'] });
      setSuccess('Email recipients updated successfully');
    },
    onError: (error: any) => setError(error.message),
  });

  const [appPasswordFailed, setAppPasswordFailed] = useState(false);

  const sendTestEmailMutation = useMutation({
    mutationFn: () => settingsApi.sendTestEmail(),
    onSuccess: () => setSuccess('Test email sent successfully'),
    onError: (error: any) => {
      const message = error?.response?.data?.detail || error.message;
      if (message && /application\-specific|authentication/i.test(message)) {
        setAppPasswordFailed(true);
      }
      setError(message);
    },
  });

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

  const updateResearchAgentModelConfigMutation = useMutation({
    mutationFn: (config: any) => researchAgentApi.updateModelConfig(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['researchAgentModelConfig'] });
      setSuccess('Research agent model configuration updated successfully');
    },
    onError: (error: any) => setError(error.message || 'Failed to update research agent model config'),
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

  const [showCreds, setShowCreds] = useState<Record<string, boolean>>({});
  const [credValues, setCredValues] = useState<Record<string, string>>({});

  useEffect(() => {
    if (credentials) {
      setCredValues(credentials);
    }
  }, [credentials]);

  const handleModelConfigChange = (modelKey: string, field: string, value: any) => {
    // Handle research agent model config separately
    if (modelKey === 'research_agent_model_config') {
      if (!researchAgentModelConfig) {
        return;
      }
      const newResearchAgentConfig = JSON.parse(JSON.stringify(researchAgentModelConfig)); // Deep copy
      
      // Handle nested paths like "boss_model.model_name" or "worker_models.summary.temperature"
      if (field.includes('.')) {
        const fieldParts = field.split('.');
        let currentObj = newResearchAgentConfig;
        
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
        newResearchAgentConfig[field] = value;
      }
      
      // Optimistically update local state for UI responsiveness
      queryClient.setQueryData(['researchAgentModelConfig'], newResearchAgentConfig);
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
        if (!researchAgentModelConfig) {
          return;
        }
        const newResearchAgentConfig = JSON.parse(JSON.stringify(researchAgentModelConfig)); // Deep copy
        
        // Apply all fields to the config
        Object.entries(modelData).forEach(([field, value]) => {
          const fieldPath = prefix ? `${prefix}.${field}` : field;
          
          if (fieldPath.includes('.')) {
            const fieldParts = fieldPath.split('.');
            let currentObj = newResearchAgentConfig;
            
            for (let i = 0; i < fieldParts.length - 1; i++) {
              if (!currentObj[fieldParts[i]]) {
                currentObj[fieldParts[i]] = {};
              }
              currentObj = currentObj[fieldParts[i]];
            }
            
            currentObj[fieldParts[fieldParts.length - 1]] = value;
          } else {
            newResearchAgentConfig[fieldPath] = value;
          }
        });
        
        queryClient.setQueryData(['researchAgentModelConfig'], newResearchAgentConfig);
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

  useEffect(() => {
    if (arxivCategories) {
      const mainCat = arxivCategories.main_category || '';
      setSelectedArxivMain(mainCat);
      // Map DB subcategories (lowercase) to taxonomy keys (uppercase)
      const subs = (arxivCategories.filter_categories || [])
        .map((code: string) => {
          const parts = code.split('.');
          if (parts.length !== 2) return null;
          const [mc, sc] = parts;
          const upper = sc.toUpperCase();
          if (taxonomyAny[mc] && taxonomyAny[mc][upper]) {
            return `${mc}.${upper}`;
          }
          return null;
        })
        .filter((v: string | null): v is string => !!v);
      setSelectedArxivSubs(subs);
    }
  }, [arxivCategories]);

  useEffect(() => {
    if (researchInterests) {
      setResearchInterestsInput(researchInterests.interests || '');
    }
  }, [researchInterests]);

  useEffect(() => {
    if (emailRecipients) {
      setEmailRecipientsInput(emailRecipients.recipients?.join('\n') || '');
    }
  }, [emailRecipients]);

  const handleDatabaseImportFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedImportFile(file);
    }
  };

  const handleDatabaseImport = () => {
    if (selectedImportFile) {
      importDatabaseMutation.mutate({ file: selectedImportFile, mode: importMode });
    }
  };

  const renderResearchAgentModelConfig = (config: any) => {
    if (!config) return <Typography>Research Agent configuration not available.</Typography>;

    // For the new LangGraph implementation, we focus on the main reasoning model
    // and search/retrieval configuration rather than boss/worker patterns
    const reasoningModel = config.reasoning_model || config.boss_model || {};
    const searchConfig = config.search_config || {};
    const maxResearchLoops = config.max_research_loops || 10;
    const initialSearchQueryCount = config.initial_search_query_count || 3;
    const localSearchLimit = config.local_search_limit || 10;
    const externalSearchLimit = config.external_search_limit || 5;
    const maxContextTokens = config.max_context_tokens || 30000;

    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Alert severity="info" sx={{ mb: 2 }}>
          <Typography variant="body2">
            <strong>LangGraph Research Agent:</strong> This agent uses a declarative workflow with parallel search operations, 
            reflection loops, and intelligent source combination. The reasoning model coordinates all research activities 
            through structured query generation, local/external search, and iterative refinement.
          </Typography>
        </Alert>

        {/* Main Reasoning Model */}
        <Card variant="outlined" sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Main Reasoning Model
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Primary model responsible for query generation, reflection, and final answer synthesis.
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                <ModelNameAutocomplete
                  label="Reasoning Model Name"
                  value={reasoningModel.model_name || ''}
                  onChange={value => handleModelConfigChange('research_agent_model_config', 'reasoning_model.model_name', value)}
                  onModelSelected={selectedModel => handleModelSelectedFromCatalog('research_agent_model_config', selectedModel, 'reasoning_model')}
                  modelCatalogData={modelCatalogData}
                />
                <FormControl fullWidth>
                  <InputLabel>Model Type (Provider)</InputLabel>
                  <Select
                    value={reasoningModel.model_type || ''}
                    label="Model Type (Provider)"
                    onChange={e => handleModelConfigChange('research_agent_model_config', 'reasoning_model.model_type', e.target.value)}
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
                  value={reasoningModel.max_new_tokens || 4096}
                  onChange={e => handleModelConfigChange('research_agent_model_config', 'reasoning_model.max_new_tokens', Number(e.target.value))}
                />
                <TextField
                  fullWidth
                  label="Temperature"
                  type="number"
                  inputProps={{ step: '0.1' }}
                  value={reasoningModel.temperature || 0.1}
                  onChange={e => handleModelConfigChange('research_agent_model_config', 'reasoning_model.temperature', parseFloat(e.target.value))}
                />
                {(reasoningModel.model_type === 'ollama' || reasoningModel.model_type === 'llamacpp') && (
                  <TextField
                    fullWidth
                    label="Context Window (num_ctx)"
                    type="number"
                    value={reasoningModel.num_ctx || 131072}
                    onChange={e => handleModelConfigChange('research_agent_model_config', 'reasoning_model.num_ctx', Number(e.target.value))}
                  />
                )}
              </Box>
            </Box>
          </CardContent>
        </Card>
        
        {/* Advanced Model Configuration */}
        <Card variant="outlined" sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Advanced Model Configuration
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Configure individual models for specific LangGraph nodes. Leave empty to use the main reasoning model.
            </Typography>
            
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {/* Query Generator Model */}
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle1">
                    Query Generator Model {config.query_generator_model ? '(Configured)' : '(Using Reasoning Model)'}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Specialized model for generating initial and follow-up search queries.
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                    <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <ModelNameAutocomplete
                        label="Query Generator Model Name"
                        value={config.query_generator_model?.model_name || ''}
                        onChange={value => {
                          if (!config.query_generator_model) {
                            // Initialize with reasoning model defaults if not set
                            handleModelConfigChange('research_agent_model_config', 'query_generator_model', {
                              model_name: value,
                              model_type: reasoningModel.model_type || 'gemini',
                              max_new_tokens: reasoningModel.max_new_tokens || 4096,
                              temperature: reasoningModel.temperature || 0.1,
                              num_ctx: reasoningModel.num_ctx || 131072
                            });
                          } else {
                            handleModelConfigChange('research_agent_model_config', 'query_generator_model.model_name', value);
                          }
                        }}
                        onModelSelected={selectedModel => handleModelSelectedFromCatalog('research_agent_model_config', selectedModel, 'query_generator_model')}
                        modelCatalogData={modelCatalogData}
                      />
                      <FormControl fullWidth>
                        <InputLabel>Model Type (Provider)</InputLabel>
                        <Select
                          value={config.query_generator_model?.model_type || ''}
                          label="Model Type (Provider)"
                          onChange={e => {
                            if (!config.query_generator_model) {
                              // Initialize with reasoning model defaults if not set
                              handleModelConfigChange('research_agent_model_config', 'query_generator_model', {
                                model_name: reasoningModel.model_name || 'gemini-2.0-flash',
                                model_type: e.target.value,
                                max_new_tokens: reasoningModel.max_new_tokens || 4096,
                                temperature: reasoningModel.temperature || 0.1,
                                num_ctx: reasoningModel.num_ctx || 131072
                              });
                            } else {
                              handleModelConfigChange('research_agent_model_config', 'query_generator_model.model_type', e.target.value);
                            }
                          }}
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
                        value={config.query_generator_model?.max_new_tokens || ''}
                        onChange={e => {
                          const value = Number(e.target.value);
                          if (!config.query_generator_model) {
                            // Initialize with reasoning model defaults if not set
                            handleModelConfigChange('research_agent_model_config', 'query_generator_model', {
                              model_name: reasoningModel.model_name || 'gemini-2.0-flash',
                              model_type: reasoningModel.model_type || 'gemini',
                              max_new_tokens: value,
                              temperature: reasoningModel.temperature || 0.1,
                              num_ctx: reasoningModel.num_ctx || 131072
                            });
                          } else {
                            handleModelConfigChange('research_agent_model_config', 'query_generator_model.max_new_tokens', value);
                          }
                        }}
                      />
                      <TextField
                        fullWidth
                        label="Temperature"
                        type="number"
                        inputProps={{ step: '0.1' }}
                        value={config.query_generator_model?.temperature || ''}
                        onChange={e => {
                          const value = parseFloat(e.target.value);
                          if (!config.query_generator_model) {
                            // Initialize with reasoning model defaults if not set
                            handleModelConfigChange('research_agent_model_config', 'query_generator_model', {
                              model_name: reasoningModel.model_name || 'gemini-2.0-flash',
                              model_type: reasoningModel.model_type || 'gemini',
                              max_new_tokens: reasoningModel.max_new_tokens || 4096,
                              temperature: value,
                              num_ctx: reasoningModel.num_ctx || 131072
                            });
                          } else {
                            handleModelConfigChange('research_agent_model_config', 'query_generator_model.temperature', value);
                          }
                        }}
                      />
                    </Box>
                  </Box>
                  <Button
                    variant="outlined"
                    color="secondary"
                    sx={{ mt: 2 }}
                    onClick={() => handleModelConfigChange('research_agent_model_config', 'query_generator_model', null)}
                  >
                    Clear (Use Reasoning Model)
                  </Button>
                </AccordionDetails>
              </Accordion>

              {/* Reflection Model */}
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle1">
                    Reflection Model {config.reflection_model ? '(Configured)' : '(Using Reasoning Model)'}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Specialized model for analyzing research progress and determining if more information is needed.
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                    <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <ModelNameAutocomplete
                        label="Reflection Model Name"
                        value={config.reflection_model?.model_name || ''}
                        onChange={value => {
                          if (!config.reflection_model) {
                            handleModelConfigChange('research_agent_model_config', 'reflection_model', {
                              model_name: value,
                              model_type: reasoningModel.model_type || 'gemini',
                              max_new_tokens: reasoningModel.max_new_tokens || 4096,
                              temperature: reasoningModel.temperature || 0.1,
                              num_ctx: reasoningModel.num_ctx || 131072
                            });
                          } else {
                            handleModelConfigChange('research_agent_model_config', 'reflection_model.model_name', value);
                          }
                        }}
                        onModelSelected={selectedModel => handleModelSelectedFromCatalog('research_agent_model_config', selectedModel, 'reflection_model')}
                        modelCatalogData={modelCatalogData}
                      />
                      <FormControl fullWidth>
                        <InputLabel>Model Type (Provider)</InputLabel>
                        <Select
                          value={config.reflection_model?.model_type || ''}
                          label="Model Type (Provider)"
                          onChange={e => {
                            if (!config.reflection_model) {
                              handleModelConfigChange('research_agent_model_config', 'reflection_model', {
                                model_name: reasoningModel.model_name || 'gemini-2.0-flash',
                                model_type: e.target.value,
                                max_new_tokens: reasoningModel.max_new_tokens || 4096,
                                temperature: reasoningModel.temperature || 0.1,
                                num_ctx: reasoningModel.num_ctx || 131072
                              });
                            } else {
                              handleModelConfigChange('research_agent_model_config', 'reflection_model.model_type', e.target.value);
                            }
                          }}
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
                        value={config.reflection_model?.max_new_tokens || ''}
                        onChange={e => {
                          const value = Number(e.target.value);
                          if (!config.reflection_model) {
                            handleModelConfigChange('research_agent_model_config', 'reflection_model', {
                              model_name: reasoningModel.model_name || 'gemini-2.0-flash',
                              model_type: reasoningModel.model_type || 'gemini',
                              max_new_tokens: value,
                              temperature: reasoningModel.temperature || 0.1,
                              num_ctx: reasoningModel.num_ctx || 131072
                            });
                          } else {
                            handleModelConfigChange('research_agent_model_config', 'reflection_model.max_new_tokens', value);
                          }
                        }}
                      />
                      <TextField
                        fullWidth
                        label="Temperature"
                        type="number"
                        inputProps={{ step: '0.1' }}
                        value={config.reflection_model?.temperature || ''}
                        onChange={e => {
                          const value = parseFloat(e.target.value);
                          if (!config.reflection_model) {
                            handleModelConfigChange('research_agent_model_config', 'reflection_model', {
                              model_name: reasoningModel.model_name || 'gemini-2.0-flash',
                              model_type: reasoningModel.model_type || 'gemini',
                              max_new_tokens: reasoningModel.max_new_tokens || 4096,
                              temperature: value,
                              num_ctx: reasoningModel.num_ctx || 131072
                            });
                          } else {
                            handleModelConfigChange('research_agent_model_config', 'reflection_model.temperature', value);
                          }
                        }}
                      />
                    </Box>
                  </Box>
                  <Button
                    variant="outlined"
                    color="secondary"
                    sx={{ mt: 2 }}
                    onClick={() => handleModelConfigChange('research_agent_model_config', 'reflection_model', null)}
                  >
                    Clear (Use Reasoning Model)
                  </Button>
                </AccordionDetails>
              </Accordion>

              {/* Judge Model */}
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle1">
                    Judge Model {config.judge_model ? '(Configured)' : '(Using Reasoning Model)'}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Specialized model for judging paper relevance before PDF download to save time on irrelevant papers.
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                    <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <ModelNameAutocomplete
                        label="Judge Model Name"
                        value={config.judge_model?.model_name || ''}
                        onChange={value => {
                          if (!config.judge_model) {
                            handleModelConfigChange('research_agent_model_config', 'judge_model', {
                              model_name: value,
                              model_type: reasoningModel.model_type || 'gemini',
                              max_new_tokens: reasoningModel.max_new_tokens || 4096,
                              temperature: reasoningModel.temperature || 0.1,
                              num_ctx: reasoningModel.num_ctx || 131072
                            });
                          } else {
                            handleModelConfigChange('research_agent_model_config', 'judge_model.model_name', value);
                          }
                        }}
                        onModelSelected={selectedModel => handleModelSelectedFromCatalog('research_agent_model_config', selectedModel, 'judge_model')}
                        modelCatalogData={modelCatalogData}
                      />
                      <FormControl fullWidth>
                        <InputLabel>Model Type (Provider)</InputLabel>
                        <Select
                          value={config.judge_model?.model_type || ''}
                          label="Model Type (Provider)"
                          onChange={e => {
                            if (!config.judge_model) {
                              handleModelConfigChange('research_agent_model_config', 'judge_model', {
                                model_name: reasoningModel.model_name || 'gemini-2.0-flash',
                                model_type: e.target.value,
                                max_new_tokens: reasoningModel.max_new_tokens || 4096,
                                temperature: reasoningModel.temperature || 0.1,
                                num_ctx: reasoningModel.num_ctx || 131072
                              });
                            } else {
                              handleModelConfigChange('research_agent_model_config', 'judge_model.model_type', e.target.value);
                            }
                          }}
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
                        value={config.judge_model?.max_new_tokens || ''}
                        onChange={e => {
                          const value = Number(e.target.value);
                          if (!config.judge_model) {
                            handleModelConfigChange('research_agent_model_config', 'judge_model', {
                              model_name: reasoningModel.model_name || 'gemini-2.0-flash',
                              model_type: reasoningModel.model_type || 'gemini',
                              max_new_tokens: value,
                              temperature: reasoningModel.temperature || 0.1,
                              num_ctx: reasoningModel.num_ctx || 131072
                            });
                          } else {
                            handleModelConfigChange('research_agent_model_config', 'judge_model.max_new_tokens', value);
                          }
                        }}
                      />
                      <TextField
                        fullWidth
                        label="Temperature"
                        type="number"
                        inputProps={{ step: '0.1' }}
                        value={config.judge_model?.temperature || ''}
                        onChange={e => {
                          const value = parseFloat(e.target.value);
                          if (!config.judge_model) {
                            handleModelConfigChange('research_agent_model_config', 'judge_model', {
                              model_name: reasoningModel.model_name || 'gemini-2.0-flash',
                              model_type: reasoningModel.model_type || 'gemini',
                              max_new_tokens: reasoningModel.max_new_tokens || 4096,
                              temperature: value,
                              num_ctx: reasoningModel.num_ctx || 131072
                            });
                          } else {
                            handleModelConfigChange('research_agent_model_config', 'judge_model.temperature', value);
                          }
                        }}
                      />
                    </Box>
                  </Box>
                  <Button
                    variant="outlined"
                    color="secondary"
                    sx={{ mt: 2 }}
                    onClick={() => handleModelConfigChange('research_agent_model_config', 'judge_model', null)}
                  >
                    Clear (Use Reasoning Model)
                  </Button>
                </AccordionDetails>
              </Accordion>

              {/* Answer Model */}
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle1">
                    Answer Model {config.answer_model ? '(Configured)' : '(Using Reasoning Model)'}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Specialized model for generating the final research summary and answer.
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                    <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <ModelNameAutocomplete
                        label="Answer Model Name"
                        value={config.answer_model?.model_name || ''}
                        onChange={value => {
                          if (!config.answer_model) {
                            handleModelConfigChange('research_agent_model_config', 'answer_model', {
                              model_name: value,
                              model_type: reasoningModel.model_type || 'gemini',
                              max_new_tokens: reasoningModel.max_new_tokens || 4096,
                              temperature: reasoningModel.temperature || 0.1,
                              num_ctx: reasoningModel.num_ctx || 131072
                            });
                          } else {
                            handleModelConfigChange('research_agent_model_config', 'answer_model.model_name', value);
                          }
                        }}
                        onModelSelected={selectedModel => handleModelSelectedFromCatalog('research_agent_model_config', selectedModel, 'answer_model')}
                        modelCatalogData={modelCatalogData}
                      />
                      <FormControl fullWidth>
                        <InputLabel>Model Type (Provider)</InputLabel>
                        <Select
                          value={config.answer_model?.model_type || ''}
                          label="Model Type (Provider)"
                          onChange={e => {
                            if (!config.answer_model) {
                              handleModelConfigChange('research_agent_model_config', 'answer_model', {
                                model_name: reasoningModel.model_name || 'gemini-2.0-flash',
                                model_type: e.target.value,
                                max_new_tokens: reasoningModel.max_new_tokens || 4096,
                                temperature: reasoningModel.temperature || 0.1,
                                num_ctx: reasoningModel.num_ctx || 131072
                              });
                            } else {
                              handleModelConfigChange('research_agent_model_config', 'answer_model.model_type', e.target.value);
                            }
                          }}
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
                        value={config.answer_model?.max_new_tokens || ''}
                        onChange={e => {
                          const value = Number(e.target.value);
                          if (!config.answer_model) {
                            handleModelConfigChange('research_agent_model_config', 'answer_model', {
                              model_name: reasoningModel.model_name || 'gemini-2.0-flash',
                              model_type: reasoningModel.model_type || 'gemini',
                              max_new_tokens: value,
                              temperature: reasoningModel.temperature || 0.1,
                              num_ctx: reasoningModel.num_ctx || 131072
                            });
                          } else {
                            handleModelConfigChange('research_agent_model_config', 'answer_model.max_new_tokens', value);
                          }
                        }}
                      />
                      <TextField
                        fullWidth
                        label="Temperature"
                        type="number"
                        inputProps={{ step: '0.1' }}
                        value={config.answer_model?.temperature || ''}
                        onChange={e => {
                          const value = parseFloat(e.target.value);
                          if (!config.answer_model) {
                            handleModelConfigChange('research_agent_model_config', 'answer_model', {
                              model_name: reasoningModel.model_name || 'gemini-2.0-flash',
                              model_type: reasoningModel.model_type || 'gemini',
                              max_new_tokens: reasoningModel.max_new_tokens || 4096,
                              temperature: value,
                              num_ctx: reasoningModel.num_ctx || 131072
                            });
                          } else {
                            handleModelConfigChange('research_agent_model_config', 'answer_model.temperature', value);
                          }
                        }}
                      />
                    </Box>
                  </Box>
                  <Button
                    variant="outlined"
                    color="secondary"
                    sx={{ mt: 2 }}
                    onClick={() => handleModelConfigChange('research_agent_model_config', 'answer_model', null)}
                  >
                    Clear (Use Reasoning Model)
                  </Button>
                </AccordionDetails>
              </Accordion>
            </Box>
          </CardContent>
        </Card>
        
        {/* Research Configuration */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>Research Workflow Configuration</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Controls the behavior of the LangGraph research workflow including search limits and iteration bounds.
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 3 }}>
              <TextField
                label="Max Research Loops"
                type="number"
                value={maxResearchLoops}
                onChange={e => handleModelConfigChange('research_agent_model_config', 'max_research_loops', Number(e.target.value))}
                helperText="Maximum research iterations"
                inputProps={{ min: 1, max: 50 }}
              />
              <TextField
                label="Initial Query Count"
                type="number"
                value={initialSearchQueryCount}
                onChange={e => handleModelConfigChange('research_agent_model_config', 'initial_search_query_count', Number(e.target.value))}
                helperText="Number of initial search queries"
                inputProps={{ min: 1, max: 10 }}
              />
              <TextField
                label="Local Search Limit"
                type="number"
                value={localSearchLimit}
                onChange={e => handleModelConfigChange('research_agent_model_config', 'local_search_limit', Number(e.target.value))}
                helperText="Papers per local search"
                inputProps={{ min: 1, max: 50 }}
              />
              <TextField
                label="External Search Limit"
                type="number"
                value={externalSearchLimit}
                onChange={e => handleModelConfigChange('research_agent_model_config', 'external_search_limit', Number(e.target.value))}
                helperText="Papers per external search"
                inputProps={{ min: 1, max: 20 }}
              />
              <TextField
                label="Max Context Tokens"
                type="number"
                value={maxContextTokens}
                onChange={e => handleModelConfigChange('research_agent_model_config', 'max_context_tokens', Number(e.target.value))}
                helperText="Token limit for research context"
                inputProps={{ min: 1000, max: 200000 }}
              />
            </Box>
          </CardContent>
        </Card>

        {/* Search Strategy Configuration */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>Search Strategy</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Configure the hybrid search strategy for local paper database queries.
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 3 }}>
              <TextField
                label="Semantic Weight"
                type="number"
                inputProps={{ step: '0.1', min: 0, max: 1 }}
                value={searchConfig.semantic_weight || 0.6}
                onChange={e => handleModelConfigChange('research_agent_model_config', 'search_config.semantic_weight', parseFloat(e.target.value))}
                helperText="Weight for semantic similarity"
              />
              <TextField
                label="Keyword Weight"
                type="number"
                inputProps={{ step: '0.1', min: 0, max: 1 }}
                value={searchConfig.keyword_weight || 0.4}
                onChange={e => handleModelConfigChange('research_agent_model_config', 'search_config.keyword_weight', parseFloat(e.target.value))}
                helperText="Weight for keyword matching"
              />
              <TextField
                label="Similarity Threshold"
                type="number"
                inputProps={{ step: '0.05', min: 0, max: 1 }}
                value={searchConfig.similarity_threshold || 0.3}
                onChange={e => handleModelConfigChange('research_agent_model_config', 'search_config.similarity_threshold', parseFloat(e.target.value))}
                helperText="Minimum similarity score"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={searchConfig.enable_pdf_download !== false}
                    onChange={e => handleModelConfigChange('research_agent_model_config', 'search_config.enable_pdf_download', e.target.checked)}
                  />
                }
                label={
                  <Box display="flex" alignItems="center" gap={0.5}>
                    Enable PDF Download
                    <Tooltip title="Automatically download and process PDFs for full-text analysis">
                      <IconButton size="small">
                        <InfoOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                }
              />
            </Box>
          </CardContent>
        </Card>

        {/* Legacy Configuration Support */}
        {(config.boss_model || config.worker_models) && (
                                <Card variant="outlined" sx={{ borderColor: 'warning.main', backgroundColor: 'warning.light' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <InfoOutlinedIcon color="warning" />
                <Typography variant="h6" color="warning.main">
                  Legacy Configuration Detected
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                This configuration uses the old boss/worker model structure. Consider migrating to the new 
                LangGraph configuration above for improved performance and capabilities.
              </Typography>
              <Button 
                variant="outlined" 
                color="warning" 
                size="small"
                onClick={() => {
                  // Convert legacy config to new format
                  const newConfig = {
                    reasoning_model: config.boss_model || {},
                    max_research_loops: 10,
                    initial_search_query_count: 3,
                    local_search_limit: 10,
                    external_search_limit: 5,
                    search_config: {
                      semantic_weight: 0.6,
                      keyword_weight: 0.4,
                      similarity_threshold: 0.3,
                      enable_pdf_download: true
                    }
                  };
                  handleModelConfigChange('research_agent_model_config', '', newConfig);
                }}
              >
                Migrate to New Format
              </Button>
            </CardContent>
          </Card>
        )}
      </Box>
    );
  };

  if (isLoadingOrchestration || isLoadingArxiv || isLoadingResearch || isLoadingEmail || isLoadingProviders || isLoadingResearchAgent || isCheckingDbTasks) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
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

    // Research Agent model is a special case (boss + worker models)
    if (modelKey === 'research_agent_model_config') {
      return renderResearchAgentModelConfig(config);
    }

    const currentConfig = config;

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
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
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
                    researchAgentModelConfig ?
                      renderModelConfigFields(tabDef.key, researchAgentModelConfig)
                      : <Typography>Loading configuration for {tabDef.label}...</Typography>
                  ) : (
                    orchestrationConfig && orchestrationConfig[tabDef.key] ?
                      renderModelConfigFields(tabDef.key, orchestrationConfig[tabDef.key])
                      : <Typography>Loading configuration for {tabDef.label}...</Typography>
                  )}
                  <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-start' }}>
                    <Button
                      variant="contained"
                      onClick={() => {
                        if (tabDef.key === 'research_agent_model_config') {
                          if (researchAgentModelConfig) {
                            updateResearchAgentModelConfigMutation.mutate(researchAgentModelConfig);
                          }
                        } else {
                          if (orchestrationConfig) {
                             // Create a payload with only the specific model config that was changed
                             const payload = {
                              ...orchestrationConfig, // Send the whole config, backend expects OrchestrationConfig
                             };
                            updateOrchestrationMutation.mutate(payload);
                          }
                        }
                      }}
                      disabled={
                        tabDef.key === 'research_agent_model_config' 
                          ? updateResearchAgentModelConfigMutation.isPending || !researchAgentModelConfig
                          : updateOrchestrationMutation.isPending || !orchestrationConfig || !orchestrationConfig[tabDef.key]
                      }
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

      {/* ArXiv Categories Section */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5" fontWeight={600} sx={{ flex: 1 }}>
              ArXiv Settings
            </Typography>
            <Tooltip title="Configure the ArXiv categories to use for paper selection.">
              <InfoOutlinedIcon color="action" />
            </Tooltip>
          </Box>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Configure the ArXiv categories to use for paper selection.
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 700 }}>
            {/* Main Category Selector */}
            <Autocomplete
              options={Object.entries(taxonomyAny.main_categories).map(([value, label]) => ({ value: value as string, label: label as string }))}
              getOptionLabel={(option) => option.label as string}
              value={taxonomyAny.main_categories[selectedArxivMain] ? { value: selectedArxivMain, label: `${selectedArxivMain} - ${taxonomyAny.main_categories[selectedArxivMain]}` } : null}
              onChange={(_, newValue) => {
                setSelectedArxivMain(newValue?.value || '');
                setSelectedArxivSubs([]);
              }}
              renderInput={(params) => <TextField {...params} label="Main Category" fullWidth />}
            />
            {/* Subcategories Multi-Select */}
            <Autocomplete
              multiple
              filterSelectedOptions
              isOptionEqualToValue={(option, value) => option.value === value.value}
              options={Object.entries(taxonomyAny[selectedArxivMain] || {}).map(([sub, desc]) => ({ value: `${selectedArxivMain}.${sub}`, label: `${selectedArxivMain}.${sub} - ${desc}` }))}
              getOptionLabel={(option) => option.label as string}
              value={Object.entries(taxonomyAny[selectedArxivMain] || {})
                .map(([sub, desc]) => ({ value: `${selectedArxivMain}.${sub}`, label: `${selectedArxivMain}.${sub} - ${desc}` }))
                .filter(opt => selectedArxivSubs.includes(opt.value))
              }
              onChange={(_, newValues) => setSelectedArxivSubs((newValues as any[]).map(opt => opt.value))}
              renderTags={(value, getTagProps) =>
                value.map((option, index) => {
                  const tagProps = getTagProps({ index });
                  const { key, ...otherProps } = tagProps;
                  return <Chip key={key} label={option.label as string} {...otherProps} />;
                })
              }
              renderInput={(params) => <TextField {...params} label="Subcategories" placeholder="Select subcategories" fullWidth />}
            />
            {/* Save Button */}
            <Box sx={{ mt: 2 }}>
              <Button
                variant="contained"
                onClick={() => {
                  const lowerSubs = selectedArxivSubs.map((v: string) => {
                    const parts = v.split('.');
                    return parts.length === 2 ? `${parts[0]}.${parts[1].toLowerCase()}` : v;
                  });
                  updateArxivCategoriesMutation.mutate({ main_category: selectedArxivMain, filter_categories: lowerSubs });
                }}
                disabled={updateArxivCategoriesMutation.isPending}
              >
                Save ArXiv Settings
              </Button>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* Research Interests Section */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5" fontWeight={600} sx={{ flex: 1 }}>
              Research Interests
            </Typography>
            <Tooltip title="Provide a detailed description of your research interests. This will be used to guide paper discovery and analysis.">
              <InfoOutlinedIcon color="action" />
            </Tooltip>
          </Box>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Provide a detailed description of your research interests. This will be used to guide paper discovery and analysis.
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 700 }}>
            <TextField
              fullWidth
              multiline
              rows={5}
              label="Your Research Interests"
              value={researchInterestsInput}
              onChange={(e) => setResearchInterestsInput(e.target.value)}
              helperText="Describe your research interests."
            />
            <Box sx={{ mt: 2 }}>
              <Button
                variant="contained"
                onClick={() => {
                  updateResearchInterestsMutation.mutate({ interests: researchInterestsInput });
                }}
                disabled={updateResearchInterestsMutation.isPending}
              >
                Save Research Interests
              </Button>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* Email Configuration Section */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5" fontWeight={600} sx={{ flex: 1 }}>
              Email Recipients
            </Typography>
            <Tooltip title="Enter email addresses below, one per line. These recipients will receive generated newsletters.">
              <InfoOutlinedIcon color="action" />
            </Tooltip>
          </Box>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Enter email addresses below, one per line. These recipients will receive generated newsletters.
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 700 }}>
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Email Recipients"
              value={emailRecipientsInput}
              onChange={(e) => setEmailRecipientsInput(e.target.value)}
              helperText="Enter one email address per line."
            />
            <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
              <Button
                variant="contained"
                onClick={() => {
                  updateEmailRecipientsMutation.mutate({ recipients: emailRecipientsInput.split('\n').map((s: string) => s.trim()).filter(Boolean) });
                }}
                disabled={updateEmailRecipientsMutation.isPending}
              >
                Save Email Recipients
              </Button>
              <Button
                variant="contained"
                color="primary"
                onClick={() => sendTestEmailMutation.mutate()}
                disabled={sendTestEmailMutation.isPending}
              >
                Send Test Email
              </Button>
            </Box>
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
