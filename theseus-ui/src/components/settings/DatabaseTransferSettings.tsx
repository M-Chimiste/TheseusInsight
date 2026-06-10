import React, { useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Card,
  CardContent, CircularProgress, FormControl, FormControlLabel, InputLabel,
  LinearProgress, MenuItem, Select, Slider, Switch, TextField, Tooltip,
  Typography,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { settingsApi } from '../../services/api';
import { useDatabaseTaskState } from '../../hooks/useDatabaseTaskState';
import { useSnackbar } from '../../contexts/SnackbarContext';

/** Database export/import (extracted from Settings.tsx in F3).

    Owns the full transfer UI: full/incremental/profile-scoped export with
    WebSocket progress + file download, and archive import with profile
    mapping. The useDatabaseTaskState hook lives here now (it must only be
    mounted once); F4 replaces it with the unified useTask hook. */
export const DatabaseTransferSettings: React.FC = () => {
  const queryClient = useQueryClient();
  const { showSuccess } = useSnackbar();
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
    clearImportTask
  } = useDatabaseTaskState();

  const { data: researchProfiles } = useQuery({
    queryKey: ['researchProfilesForExport'],
    queryFn: async () => {
      const response = await fetch('/api/profiles');
      if (!response.ok) throw new Error('Failed to fetch profiles');
      return response.json();
    }
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
                showSuccess(`Database exported successfully (${(blob.size / 1024 / 1024).toFixed(1)} MB)`);
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
          showSuccess('Database imported successfully. Please restart the application.');
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

  return (
    <>
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
                          onChange={(_: Event, value: number | number[]) => setExportOptions({...exportOptions, max_workers: value as number})}
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
    </>
  );
};
