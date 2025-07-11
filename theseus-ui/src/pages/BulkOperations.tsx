import React, { useState } from 'react';
import {
  Box,
  Button,
  Typography,
  Card,
  CardContent,
  CardActions,
  Grid,
  Chip,
  TextField,
  CircularProgress,
  Alert,
  Tab,
  Tabs,
  List,
  ListItem,
  ListItemText,
  FormControlLabel,
  Checkbox,
  Autocomplete,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import {
  PlayArrow as PlayIcon,
  CloudDownload as DownloadIcon,
  CheckCircle as CheckIcon,
} from '@mui/icons-material';

import {
  profileApi,
  type ProfileAwareIngestRequest,
  type BulkEmbedRequest,
} from '../services/api';
import { useMutation, useQuery } from '@tanstack/react-query';
import ProfileSelector from '../components/ProfileSelector';
import { useLayout } from '../contexts/LayoutContext';

interface BulkOperationsProps {}

// Common ArXiv categories
const ARXIV_CATEGORIES = [
  { value: 'ALL', label: 'All Papers - No Filters' },
  { value: 'cs.AI', label: 'Artificial Intelligence' },
  { value: 'cs.CL', label: 'Computation and Language' },
  { value: 'cs.CV', label: 'Computer Vision and Pattern Recognition' },
  { value: 'cs.LG', label: 'Machine Learning' },
  { value: 'cs.IR', label: 'Information Retrieval' },
  { value: 'cs.MA', label: 'Multiagent Systems' },
  { value: 'cs.NE', label: 'Neural and Evolutionary Computing' },
  { value: 'cs.RO', label: 'Robotics' },
  { value: 'stat.ML', label: 'Machine Learning (Statistics)' },
  { value: 'math.OC', label: 'Optimization and Control' },
  { value: 'eess.AS', label: 'Audio and Speech Processing' },
  { value: 'eess.IV', label: 'Image and Video Processing' },
];

const BulkOperations: React.FC<BulkOperationsProps> = () => {
  const { headerHeight } = useLayout(); // Get dynamic header height
  const [activeTab, setActiveTab] = useState(0);
  
  // Profile-Aware Full Ingestion State
  const [selectedIngestProfiles, setSelectedIngestProfiles] = useState<number[]>([]);
  const [selectedIngestTags, setSelectedIngestTags] = useState<string[]>([]);
  const [ingestStartDate, setIngestStartDate] = useState<Date | null>(null);
  const [ingestEndDate, setIngestEndDate] = useState<Date | null>(null);
  const [cosineThresholdIngest, setCosineThresholdIngest] = useState<number>(0.7);
  const [batchSizeIngest, setBatchSizeIngest] = useState<number>(100);
  const [checkExistingData, setCheckExistingData] = useState<boolean>(true);
  
  // Bulk Embedding Only State
  const [embedStartDate, setEmbedStartDate] = useState<Date | null>(null);
  const [embedEndDate, setEmbedEndDate] = useState<Date | null>(null);
  const [embedBatchSize, setEmbedBatchSize] = useState<number>(100);
  const [skipExistingEmbeddings, setSkipExistingEmbeddings] = useState<boolean>(true);
  const [selectedArxivCategories, setSelectedArxivCategories] = useState<string[]>([]);
  const [useDefaultCategories, setUseDefaultCategories] = useState<boolean>(true);

  // Status State
  const [ingestionStatus, setIngestionStatus] = useState<string>('');
  const [embeddingStatus, setEmbeddingStatus] = useState<string>('');

  // Query to check existing data
  const existingDataQuery = useQuery({
    queryKey: ['existing-bulk-data', ingestStartDate, ingestEndDate],
    queryFn: async () => {
      if (!ingestStartDate || !ingestEndDate) return null;
      // This endpoint needs to be implemented in the backend
      const response = await profileApi.checkExistingBulkData({
        start_date: ingestStartDate.toISOString().split('T')[0],
        end_date: ingestEndDate.toISOString().split('T')[0],
      });
      return response.data;
    },
    enabled: checkExistingData && !!ingestStartDate && !!ingestEndDate,
  });

  // Mutations
  const fullIngestMutation = useMutation({
    mutationFn: async (request: ProfileAwareIngestRequest) => {
      setIngestionStatus('Starting profile-aware ingestion...');
      return profileApi.runProfileAwareIngest(request);
    },
    onSuccess: (response) => {
      setIngestionStatus(`Ingestion started successfully. Task ID: ${response.data.task_id}`);
      console.log('Profile-aware ingestion started:', response.data);
    },
    onError: (error) => {
      setIngestionStatus('Failed to start ingestion');
      console.error('Failed to start profile-aware ingestion:', error);
    },
  });

  const bulkEmbedMutation = useMutation({
    mutationFn: async (request: BulkEmbedRequest) => {
      setEmbeddingStatus('Starting bulk embedding...');
      return profileApi.runBulkEmbed(request);
    },
    onSuccess: (response) => {
      setEmbeddingStatus(`Embedding started successfully. Task ID: ${response.data.task_id}`);
      console.log('Bulk embedding started:', response.data);
    },
    onError: (error) => {
      setEmbeddingStatus('Failed to start embedding');
      console.error('Failed to start bulk embedding:', error);
    },
  });

  // Handlers
  const handleFullIngestionRun = () => {
    const request: ProfileAwareIngestRequest = {
      profile_ids: selectedIngestProfiles.length > 0 ? selectedIngestProfiles : undefined,
      profile_tags: selectedIngestTags.length > 0 ? selectedIngestTags : undefined,
      start_date: ingestStartDate?.toISOString().split('T')[0],
      end_date: ingestEndDate?.toISOString().split('T')[0],
      cosine_threshold: cosineThresholdIngest,
      batch_size: batchSizeIngest,
      score_all_profiles: false,
      overwrite_existing: !checkExistingData,
    };
    fullIngestMutation.mutate(request);
  };

  const handleBulkEmbedRun = () => {
    // Determine arxiv categories:
    // - If using defaults: undefined (backend will use default categories)  
    // - If "ALL" is selected: send ["ALL"] to explicitly request no filtering
    // - Otherwise: send the selected categories
    let arxivCategories: string[] | undefined;
    if (useDefaultCategories) {
      arxivCategories = undefined; // Use backend defaults
    } else if (selectedArxivCategories.includes('ALL')) {
      arxivCategories = ['ALL']; // Explicit flag for no filtering
    } else if (selectedArxivCategories.length > 0) {
      arxivCategories = selectedArxivCategories; // Use selected categories
    } else {
      arxivCategories = []; // Empty array - prompt user to select something
    }
    
    const request: BulkEmbedRequest = {
      start_date: embedStartDate?.toISOString().split('T')[0] || '',
      end_date: embedEndDate?.toISOString().split('T')[0] || '',
      batch_size: embedBatchSize,
      skip_existing: skipExistingEmbeddings,
      arxiv_categories: arxivCategories,
    };
    bulkEmbedMutation.mutate(request);
  };

  const canRunFullIngest = (selectedIngestProfiles.length > 0 || selectedIngestTags.length > 0) 
    && ingestStartDate && ingestEndDate;
  const canRunBulkEmbed = embedStartDate && embedEndDate;

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ pt: `${headerHeight + 24}px`, pb: 3, px: 3 }}>
        <Typography variant="h4" gutterBottom>
          Bulk Operations
        </Typography>
        
        <Typography variant="body1" color="text.secondary" paragraph>
          Manage bulk data ingestion and processing operations for your research profiles.
        </Typography>

        <Tabs value={activeTab} onChange={handleTabChange} sx={{ mb: 3 }}>
          <Tab label="Profile-Aware Full Ingestion" />
          <Tab label="Bulk Embedding Only" />
        </Tabs>

        {activeTab === 0 && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Profile-Aware Full Ingestion
              </Typography>
              
              <Alert severity="info" sx={{ mb: 3 }}>
                <Typography variant="body2">
                  This mode performs a complete ingestion workflow:
                  <List dense>
                    <ListItem>
                      <ListItemText primary="1. Downloads papers from Kaggle/ArXiv for the specified date range" />
                    </ListItem>
                    <ListItem>
                      <ListItemText primary="2. Filters papers based on profile configurations" />
                    </ListItem>
                    <ListItem>
                      <ListItemText primary="3. Embeds paper abstracts using the configured embedding model" />
                    </ListItem>
                    <ListItem>
                      <ListItemText primary="4. Stores embedded papers in the database" />
                    </ListItem>
                    <ListItem>
                      <ListItemText primary="5. Runs LLM judge scoring for selected profiles" />
                    </ListItem>
                    <ListItem>
                      <ListItemText primary="6. Updates paper scores and rankings for each profile" />
                    </ListItem>
                  </List>
                </Typography>
              </Alert>

              <Grid container spacing={3}>
                <Grid size={{ xs: 12 }}>
                  <ProfileSelector
                    onProfileChange={setSelectedIngestProfiles}
                    onTagChange={setSelectedIngestTags}
                    allowMultiple={true}
                    showTags={true}
                    label="Select Profiles for Full Ingestion"
                  />
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                  <DatePicker
                    label="Start Date"
                    value={ingestStartDate}
                    onChange={(newValue) => setIngestStartDate(newValue)}
                    slotProps={{
                      textField: {
                        fullWidth: true,
                      },
                    }}
                  />
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                  <DatePicker
                    label="End Date"
                    value={ingestEndDate}
                    onChange={(newValue) => setIngestEndDate(newValue)}
                    slotProps={{
                      textField: {
                        fullWidth: true,
                      },
                    }}
                  />
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={checkExistingData}
                        onChange={(e) => setCheckExistingData(e.target.checked)}
                      />
                    }
                    label="Check for existing data (skip downloading if already available)"
                  />
                </Grid>

                {existingDataQuery.data && checkExistingData && (
                  <Grid size={{ xs: 12 }}>
                    <Alert severity="success" icon={<CheckIcon />}>
                      <Typography variant="body2">
                        Found existing data: {existingDataQuery.data.paper_count} papers already available.
                        {existingDataQuery.data.embedded_count > 0 && 
                          ` (${existingDataQuery.data.embedded_count} already embedded)`
                        }
                      </Typography>
                    </Alert>
                  </Grid>
                )}

                <Grid size={{ xs: 12, md: 6 }}>
                  <TextField
                    label="Cosine Threshold"
                    type="number"
                    value={cosineThresholdIngest}
                    onChange={(e) => setCosineThresholdIngest(parseFloat(e.target.value))}
                    inputProps={{ min: 0, max: 1, step: 0.1 }}
                    fullWidth
                    helperText="Minimum similarity score for profile matching"
                  />
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                  <TextField
                    label="Batch Size"
                    type="number"
                    value={batchSizeIngest}
                    onChange={(e) => setBatchSizeIngest(parseInt(e.target.value))}
                    inputProps={{ min: 1, max: 1000 }}
                    fullWidth
                    helperText="Number of papers to process in each batch"
                  />
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <Alert severity="info">
                    <Typography variant="body2">
                      Selected profiles: {selectedIngestProfiles.length}
                      <br />
                      Selected tags: {selectedIngestTags.length}
                      {selectedIngestTags.length > 0 && (
                        <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                          {selectedIngestTags.map((tag) => (
                            <Chip key={tag} label={tag} size="small" variant="outlined" />
                          ))}
                        </Box>
                      )}
                    </Typography>
                  </Alert>
                </Grid>

                {ingestionStatus && (
                  <Grid size={{ xs: 12 }}>
                    <Alert severity={ingestionStatus.includes('Failed') ? 'error' : 'success'}>
                      {ingestionStatus}
                    </Alert>
                  </Grid>
                )}
              </Grid>
            </CardContent>
            
            <CardActions>
              <Button
                variant="contained"
                color="primary"
                onClick={handleFullIngestionRun}
                disabled={!canRunFullIngest || fullIngestMutation.isPending}
                startIcon={fullIngestMutation.isPending ? <CircularProgress size={20} /> : <PlayIcon />}
              >
                {fullIngestMutation.isPending ? 'Processing...' : 'Start Full Ingestion'}
              </Button>
            </CardActions>
          </Card>
        )}

        {activeTab === 1 && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Bulk Embedding Only
              </Typography>
              
              <Alert severity="info" sx={{ mb: 3 }}>
                <Typography variant="body2">
                  This mode performs embedding only:
                  <List dense>
                    <ListItem>
                      <ListItemText primary="1. Downloads papers from Kaggle/ArXiv for the specified date range" />
                    </ListItem>
                    <ListItem>
                      <ListItemText primary="2. Embeds all paper abstracts without filtering" />
                    </ListItem>
                    <ListItem>
                      <ListItemText primary="3. Stores embedded papers in the database" />
                    </ListItem>
                    <ListItem>
                      <ListItemText primary="4. Papers are ready for later profile-specific judging" />
                    </ListItem>
                  </List>
                  <Typography variant="body2" sx={{ mt: 1, fontWeight: 'bold' }}>
                    Use this mode to pre-process papers for multiple profiles or future analysis.
                  </Typography>
                </Typography>
              </Alert>

              <Grid container spacing={3}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <DatePicker
                    label="Start Date"
                    value={embedStartDate}
                    onChange={(newValue) => setEmbedStartDate(newValue)}
                    slotProps={{
                      textField: {
                        fullWidth: true,
                      },
                    }}
                  />
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                  <DatePicker
                    label="End Date"
                    value={embedEndDate}
                    onChange={(newValue) => setEmbedEndDate(newValue)}
                    slotProps={{
                      textField: {
                        fullWidth: true,
                      },
                    }}
                  />
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={skipExistingEmbeddings}
                        onChange={(e) => setSkipExistingEmbeddings(e.target.checked)}
                      />
                    }
                    label="Skip papers that already have embeddings"
                  />
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={useDefaultCategories}
                        onChange={(e) => setUseDefaultCategories(e.target.checked)}
                      />
                    }
                    label="Use default ArXiv categories (AI, CL, LG, IR, MA, CV)"
                  />
                </Grid>

                {!useDefaultCategories && (
                  <Grid size={{ xs: 12 }}>
                    <Autocomplete
                      multiple
                      options={ARXIV_CATEGORIES}
                      getOptionLabel={(option) => `${option.value} - ${option.label}`}
                      value={ARXIV_CATEGORIES.filter(cat => selectedArxivCategories.includes(cat.value))}
                      onChange={(_, newValue) => {
                        // If "ALL" is selected, clear other selections
                        const hasAll = newValue.some(cat => cat.value === 'ALL');
                        if (hasAll) {
                          setSelectedArxivCategories(['ALL']);
                        } else {
                          setSelectedArxivCategories(newValue.map(cat => cat.value));
                        }
                      }}
                      renderInput={(params) => (
                        <TextField
                          {...params}
                          label="Select ArXiv Categories"
                          placeholder="Choose categories to download"
                          helperText={selectedArxivCategories.includes('ALL') 
                            ? "All papers from ALL categories will be downloaded (no filtering)" 
                            : "Select specific ArXiv categories or choose 'All Papers - No Filters'"}
                        />
                      )}
                      renderTags={(value, getTagProps) =>
                        value.map((option, index) => (
                          <Chip
                            variant={option.value === 'ALL' ? 'filled' : 'outlined'}
                            color={option.value === 'ALL' ? 'primary' : 'default'}
                            label={option.label}
                            {...getTagProps({ index })}
                            key={option.value}
                          />
                        ))
                      }
                    />
                  </Grid>
                )}

                <Grid size={{ xs: 12, md: 6 }}>
                  <TextField
                    label="Batch Size"
                    type="number"
                    value={embedBatchSize}
                    onChange={(e) => setEmbedBatchSize(parseInt(e.target.value))}
                    inputProps={{ min: 1, max: 1000 }}
                    fullWidth
                    helperText="Number of papers to embed in each batch"
                  />
                </Grid>

                {embeddingStatus && (
                  <Grid size={{ xs: 12 }}>
                    <Alert severity={embeddingStatus.includes('Failed') ? 'error' : 'success'}>
                      {embeddingStatus}
                    </Alert>
                  </Grid>
                )}
              </Grid>
            </CardContent>
            
            <CardActions>
              <Button
                variant="contained"
                color="primary"
                onClick={handleBulkEmbedRun}
                disabled={!canRunBulkEmbed || bulkEmbedMutation.isPending}
                startIcon={bulkEmbedMutation.isPending ? <CircularProgress size={20} /> : <DownloadIcon />}
              >
                {bulkEmbedMutation.isPending ? 'Processing...' : 'Start Bulk Embedding'}
              </Button>
            </CardActions>
          </Card>
        )}
      </Box>
    </LocalizationProvider>
  );
};

export default BulkOperations;