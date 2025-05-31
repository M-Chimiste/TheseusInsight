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
import { settingsApi } from '../services/api';
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
];

const MODEL_TABS = [
  { key: 'embedding_model', label: 'Embedding Model', tooltip: 'Used for vector search and similarity.' },
  { key: 'judge_model', label: 'Judge Model', tooltip: 'Used for ranking and scoring papers.' },
  { key: 'content_extraction_model', label: 'Content Extraction Model', tooltip: 'Extracts content from papers.' },
  { key: 'newsletter_sections_model', label: 'Newsletter Sections Model', tooltip: 'Generates newsletter sections.' },
  { key: 'newsletter_intro_model', label: 'Newsletter Intro Model', tooltip: 'Generates newsletter introduction.' },
  { key: 'podcast_model', label: 'Podcast Model', tooltip: 'Used for podcast generation.' },
  { key: 'tts_model', label: 'TTS Model', tooltip: 'Text-to-speech for podcast.' },
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
    if (!orchestrationConfig) return;
    const newOrchestrationConfig = JSON.parse(JSON.stringify(orchestrationConfig)); // Deep copy
    
    if (!newOrchestrationConfig[modelKey]) {
      newOrchestrationConfig[modelKey] = {};
    }
    newOrchestrationConfig[modelKey][field] = value;
    
    // Optimistically update local state for UI responsiveness
    queryClient.setQueryData(['orchestrationConfig'], newOrchestrationConfig);
    // Debounce or handle mutation trigger carefully if needed, for now direct mutation
    // updateOrchestrationMutation.mutate(newOrchestrationConfig); // This will be triggered by Save button
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

  if (isLoadingOrchestration || isLoadingArxiv || isLoadingResearch || isLoadingEmail || isLoadingProviders || isCheckingDbTasks) {
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
          <TextField
            fullWidth
            label="TTS Model Name"
            value={currentConfig.tts_model_name || ''}
            onChange={e => handleModelConfigChange(modelKey, 'tts_model_name', e.target.value)}
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
          <TextField
            fullWidth
            label="Model Name"
            value={currentConfig.model_name || ''}
            onChange={e => handleModelConfigChange(modelKey, 'model_name', e.target.value)}
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
          {typeof currentConfig.trust_remote_code === 'boolean' && (
            <FormControlLabel
              control={
                <Switch
                  checked={currentConfig.trust_remote_code}
                  onChange={e => handleModelConfigChange(modelKey, 'trust_remote_code', e.target.checked)}
                />
              }
              label={
                <Box display="flex" alignItems="center" gap={0.5}>
                  Trust Remote Code
                  <Tooltip title="Allow loading remote code for this model. (Typically for embedding models)">
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
                  {orchestrationConfig && orchestrationConfig[tabDef.key] ?
                    renderModelConfigFields(tabDef.key, orchestrationConfig[tabDef.key])
                    : <Typography>Loading configuration for {tabDef.label}...</Typography>
                  }
                  <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
                    <Button
                      variant="contained"
                      onClick={() => {
                        if (orchestrationConfig) {
                           // Create a payload with only the specific model config that was changed
                           const payload = {
                            ...orchestrationConfig, // Send the whole config, backend expects OrchestrationConfig
                           };
                          updateOrchestrationMutation.mutate(payload);
                        }
                      }}
                      disabled={updateOrchestrationMutation.isPending || !orchestrationConfig || !orchestrationConfig[tabDef.key]}
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
                type={key === 'OLLAMA_URL' ? 'text' : (showCreds[key] ? 'text' : 'password')}
                value={credValues[key] || ''}
                onChange={e => setCredValues({ ...credValues, [key]: e.target.value })}
                InputProps={{
                  endAdornment:
                    key === 'OLLAMA_URL' ? null : (
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
