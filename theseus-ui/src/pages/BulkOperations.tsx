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
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import {
  PlayArrow as PlayIcon,
} from '@mui/icons-material';

import {
  profileApi,
  type BulkJudgeRunRequest,
  type ProfileAwareIngestRequest,
} from '../services/api';
import { useMutation } from '@tanstack/react-query';
import ProfileSelector from '../components/ProfileSelector';

interface BulkOperationsProps {}

const BulkOperations: React.FC<BulkOperationsProps> = () => {
  const [activeTab, setActiveTab] = useState(0);
  
  // Judge Run State
  const [selectedJudgeProfiles, setSelectedJudgeProfiles] = useState<number[]>([]);
  const [selectedJudgeTags, setSelectedJudgeTags] = useState<string[]>([]);
  const [judgeStartDate, setJudgeStartDate] = useState<Date | null>(null);
  const [judgeEndDate, setJudgeEndDate] = useState<Date | null>(null);
  const [cosineThreshold, setCosineThreshold] = useState<number>(0.7);
  const [overwriteExisting] = useState(false);
  const [batchSize, setBatchSize] = useState<number>(100);
  
  // Ingestion State
  const [selectedIngestProfiles, setSelectedIngestProfiles] = useState<number[]>([]);
  const [selectedIngestTags, setSelectedIngestTags] = useState<string[]>([]);
  const [ingestStartDate, setIngestStartDate] = useState<Date | null>(null);
  const [ingestEndDate, setIngestEndDate] = useState<Date | null>(null);
  const [scoreAllProfiles] = useState(false);
  const [overwriteExistingIngest] = useState(false);
  const [cosineThresholdIngest, setCosineThresholdIngest] = useState<number>(0.7);
  const [batchSizeIngest, setBatchSizeIngest] = useState<number>(100);

  // Mutations
  const bulkJudgeMutation = useMutation({
    mutationFn: (request: BulkJudgeRunRequest) => profileApi.runBulkJudge(request),
    onSuccess: (response) => {
      console.log('Bulk judge run started:', response.data);
    },
    onError: (error) => {
      console.error('Failed to start bulk judge run:', error);
    },
  });

  const ingestionMutation = useMutation({
    mutationFn: (request: ProfileAwareIngestRequest) => profileApi.runProfileAwareIngest(request),
    onSuccess: (response) => {
      console.log('Profile-aware ingestion started:', response.data);
    },
    onError: (error) => {
      console.error('Failed to start profile-aware ingestion:', error);
    },
  });

  // Judge Run Handlers
  const handleJudgeRun = () => {
    const request: BulkJudgeRunRequest = {
      profile_ids: selectedJudgeProfiles.length > 0 ? selectedJudgeProfiles : undefined,
      profile_tags: selectedJudgeTags.length > 0 ? selectedJudgeTags : undefined,
      start_date: judgeStartDate?.toISOString().split('T')[0],
      end_date: judgeEndDate?.toISOString().split('T')[0],
      overwrite_existing: overwriteExisting,
      cosine_threshold: cosineThreshold,
      batch_size: batchSize,
    };
    bulkJudgeMutation.mutate(request);
  };

  const canRunJudge = selectedJudgeProfiles.length > 0 || selectedJudgeTags.length > 0;

  // Ingestion Handlers
  const handleIngestionRun = () => {
    const request: ProfileAwareIngestRequest = {
      profile_ids: selectedIngestProfiles.length > 0 ? selectedIngestProfiles : undefined,
      profile_tags: selectedIngestTags.length > 0 ? selectedIngestTags : undefined,
      start_date: ingestStartDate?.toISOString().split('T')[0],
      end_date: ingestEndDate?.toISOString().split('T')[0],
      score_all_profiles: scoreAllProfiles,
      overwrite_existing: overwriteExistingIngest,
      cosine_threshold: cosineThresholdIngest,
      batch_size: batchSizeIngest,
    };
    ingestionMutation.mutate(request);
  };

  const canRunIngest = selectedIngestProfiles.length > 0 || selectedIngestTags.length > 0;

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ p: 3 }}>
        <Typography variant="h4" gutterBottom>
          Bulk Operations
        </Typography>
        
        <Typography variant="body1" color="text.secondary" paragraph>
          Execute bulk operations across multiple profiles. Select profiles directly or use tags to target groups of profiles.
        </Typography>

        <Tabs value={activeTab} onChange={handleTabChange} sx={{ mb: 3 }}>
          <Tab label="Bulk Judge Run" />
          <Tab label="Profile-Aware Ingestion" />
        </Tabs>

        {activeTab === 0 && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Bulk Judge Run
              </Typography>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                Run LLM judge scoring across multiple profiles for a specified date range.
              </Typography>

                             <Grid container spacing={3}>
                 <Grid size={{ xs: 12 }}>
                   <ProfileSelector
                     onProfileChange={setSelectedJudgeProfiles}
                     onTagChange={setSelectedJudgeTags}
                     allowMultiple={true}
                     showTags={true}
                     label="Select Profiles for Judge Run"
                   />
                 </Grid>

                 <Grid size={{ xs: 12, md: 6 }}>
                   <DatePicker
                     label="Start Date"
                     value={judgeStartDate}
                     onChange={(newValue) => setJudgeStartDate(newValue)}
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
                     value={judgeEndDate}
                     onChange={(newValue) => setJudgeEndDate(newValue)}
                     slotProps={{
                       textField: {
                         fullWidth: true,
                       },
                     }}
                   />
                 </Grid>

                 <Grid size={{ xs: 12, md: 6 }}>
                   <TextField
                     label="Cosine Threshold"
                     type="number"
                     value={cosineThreshold}
                     onChange={(e) => setCosineThreshold(parseFloat(e.target.value))}
                     inputProps={{ min: 0, max: 1, step: 0.1 }}
                     fullWidth
                   />
                   <TextField
                     label="Batch Size"
                     type="number"
                     value={batchSize}
                     onChange={(e) => setBatchSize(parseInt(e.target.value))}
                     inputProps={{ min: 1, max: 1000 }}
                     fullWidth
                     sx={{ mt: 2 }}
                   />
                 </Grid>

                 <Grid size={{ xs: 12, md: 6 }}>
                   <Alert severity="info">
                     <Typography variant="body2">
                       Selected profiles: {selectedJudgeProfiles.length}
                       <br />
                       Selected tags: {selectedJudgeTags.length}
                     </Typography>
                   </Alert>
                 </Grid>

                 <Grid size={{ xs: 12 }}>
                   <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
                     {selectedJudgeTags.map((tag) => (
                       <Chip key={tag} label={tag} variant="outlined" />
                     ))}
                   </Box>
                 </Grid>
               </Grid>
            </CardContent>
            
            <CardActions>
              <Button
                variant="contained"
                color="primary"
                onClick={handleJudgeRun}
                disabled={!canRunJudge || bulkJudgeMutation.isPending}
                startIcon={bulkJudgeMutation.isPending ? <CircularProgress size={20} /> : <PlayIcon />}
              >
                {bulkJudgeMutation.isPending ? 'Starting...' : 'Start Bulk Judge'}
              </Button>
            </CardActions>
          </Card>
        )}

        {activeTab === 1 && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Profile-Aware Ingestion
              </Typography>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                Ingest papers and run profile-aware scoring across multiple profiles.
              </Typography>

              <Grid container spacing={3}>
                <Grid size={{ xs: 12 }}>
                  <ProfileSelector
                    onProfileChange={setSelectedIngestProfiles}
                    onTagChange={setSelectedIngestTags}
                    allowMultiple={true}
                    showTags={true}
                    label="Select Profiles for Ingestion"
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

                <Grid size={{ xs: 12, md: 6 }}>
                  <TextField
                    label="Cosine Threshold"
                    type="number"
                    value={cosineThresholdIngest}
                    onChange={(e) => setCosineThresholdIngest(parseFloat(e.target.value))}
                    inputProps={{ min: 0, max: 1, step: 0.1 }}
                    fullWidth
                  />
                  <TextField
                    label="Batch Size"
                    type="number"
                    value={batchSizeIngest}
                    onChange={(e) => setBatchSizeIngest(parseInt(e.target.value))}
                    inputProps={{ min: 1, max: 1000 }}
                    fullWidth
                    sx={{ mt: 2 }}
                  />
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                  <Alert severity="info">
                    <Typography variant="body2">
                      Selected profiles: {selectedIngestProfiles.length}
                      <br />
                      Selected tags: {selectedIngestTags.length}
                    </Typography>
                  </Alert>
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
                    {selectedIngestTags.map((tag) => (
                      <Chip key={tag} label={tag} variant="outlined" />
                    ))}
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
            
            <CardActions>
              <Button
                variant="contained"
                color="primary"
                onClick={handleIngestionRun}
                disabled={!canRunIngest || ingestionMutation.isPending}
                startIcon={ingestionMutation.isPending ? <CircularProgress size={20} /> : <PlayIcon />}
              >
                {ingestionMutation.isPending ? 'Starting...' : 'Start Ingestion'}
              </Button>
            </CardActions>
          </Card>
        )}
      </Box>
    </LocalizationProvider>
  );
};

export default BulkOperations;