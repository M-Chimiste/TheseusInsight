import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  LinearProgress,
  Alert,
  IconButton,
  Tooltip,
  Container,
  Chip,
  CircularProgress,
  Switch,
  FormControlLabel,
  FormGroup,
  Checkbox,
  Grid,
} from '@mui/material';
import { LocalizationProvider, DatePicker } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import StopIcon from '@mui/icons-material/Stop';
import { profileApi, settingsApi, inferenceServersApi } from '../services/api';
import type { InferenceServer, NewsletterRunParams } from '../services/api';
import { useTaskState } from '../hooks/useTaskState';
import { useProfile } from '../contexts/ProfileContext';
import ProfileSelector from '../components/ProfileSelector';
import { useQuery } from '@tanstack/react-query';
import { useLayout } from '../contexts/LayoutContext';

// Helper to get date N days ago or N days from now
const getDateByOffset = (days: number, fromDate: Date = new Date()): Date => {
  const newDate = new Date(fromDate);
  newDate.setDate(newDate.getDate() + days);
  return newDate;
};

// Calculate difference in days
const getDaysDifference = (date1: Date, date2: Date): number => {
  const diffTime = Math.abs(date2.getTime() - date1.getTime());
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1; // +1 to include both start and end day
};

const Newsletter = () => {
  const { headerHeight } = useLayout(); // Get dynamic header height
  const today = new Date();
  const sevenDaysAgo = getDateByOffset(-6); // -6 because we add 1 in getDaysDifference for an inclusive 7 days

  const [startDate, setStartDate] = useState<Date | null>(sevenDaysAgo);
  const [endDate, setEndDate] = useState<Date | null>(today);
  const [days, setDays] = useState<number>(7);

  const [emailRecipientsInput, setEmailRecipientsInput] = useState<string>('');
  const [emailRecipients, setEmailRecipients] = useState<string[]>([]);
  const [researchInterests, setResearchInterests] = useState<string>('');
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [isAborting, setIsAborting] = useState<boolean>(false);

  // Multi-server judge configuration state
  const [useMultiServerJudge, setUseMultiServerJudge] = useState<boolean>(false);
  const [selectedJudgeServers, setSelectedJudgeServers] = useState<number[]>([]);
  const [judgeRequestTimeout, setJudgeRequestTimeout] = useState<number>(60);
  const [judgeMaxRetries, setJudgeMaxRetries] = useState<number>(3);
  
  // Use profile context
  const { getSelectedProfiles, selectedProfileIds } = useProfile();
  const selectedProfiles = getSelectedProfiles();
  
  // Use the new task state hook
  const { taskState, setTaskId, isCheckingForActiveTasks } = useTaskState('newsletter');

  // Load profile interests for all selected profiles
  const { data: allProfileInterests } = useQuery({
    queryKey: ['all-profile-interests', selectedProfileIds.sort().join(',')],
    queryFn: async () => {
      if (selectedProfileIds.length === 0) return [];

      const currentProfiles = getSelectedProfiles();
      const interestsPromises = currentProfiles.map(async (profile) => {
        const response = await profileApi.getProfileInterests(profile.id);
        return response.data;
      });

      const allInterests = await Promise.all(interestsPromises);
      return allInterests.flat();
    },
    enabled: selectedProfileIds.length > 0,
  });

  // Load available inference servers
  const { data: availableServers = [] } = useQuery<InferenceServer[]>({
    queryKey: ['inference-servers'],
    queryFn: async () => {
      const response = await inferenceServersApi.getAllServers();
      return response.data.filter((s: InferenceServer) => s.enabled);
    },
  });

  // Auto-select all enabled servers when they load or when multi-server is enabled
  useEffect(() => {
    if (useMultiServerJudge && availableServers.length > 0) {
      const enabledIds = availableServers.map(s => s.id);
      setSelectedJudgeServers(enabledIds);
    }
  }, [availableServers, useMultiServerJudge]);

  // Update form data when profiles change
  useEffect(() => {
    if (selectedProfileIds.length > 0) {
      // Get current profiles inside effect to avoid dependency issues
      const currentProfiles = getSelectedProfiles();
      
      // Combine email recipients from all selected profiles (remove duplicates)
      const allRecipients = currentProfiles.flatMap(profile => {
        const recipients = profile.email_recipients || [];
        // Handle both array and string formats
        if (Array.isArray(recipients)) {
          return recipients;
        } else if (typeof (recipients as any) === 'string') {
          // If it's a string, split it by common delimiters
          return (recipients as string).split(/[,\n\s]+/).map((email: string) => email.trim()).filter((email: string) => email);
        }
        return [];
      });
      const uniqueRecipients = Array.from(new Set(allRecipients));
      setEmailRecipients(uniqueRecipients);
      setEmailRecipientsInput(uniqueRecipients.join('\n'));
      
      // Load research interests from all selected profiles
      if (allProfileInterests && allProfileInterests.length > 0) {
        const interestsText = allProfileInterests.map(interest => interest.interest_text).join('\n');
        setResearchInterests(interestsText);
      }
    } else {
      // Clear form if no profiles selected
      setEmailRecipients([]);
      setEmailRecipientsInput('');
      setResearchInterests('');
    }
  }, [selectedProfileIds, allProfileInterests]); // getSelectedProfiles is stable from context
  
  // Date logic handlers
  useEffect(() => {
    if (startDate && endDate) {
      const newDays = getDaysDifference(startDate, endDate);
      if (days !== newDays) setDays(newDays);
    }
  }, [startDate, endDate]);

  const handleDaysChange = (newDays: number) => {
    if (newDays < 1) newDays = 1;
    setDays(newDays);
    if (endDate) {
      setStartDate(getDateByOffset(-(newDays - 1), endDate));
    }
  };

  const handleStartDateChange = (newDate: Date | null) => {
    setStartDate(newDate);
    if (newDate && endDate && newDate > endDate) {
      setEndDate(newDate);
    }
  };

  const handleEndDateChange = (newDate: Date | null) => {
    setEndDate(newDate);
    if (newDate && startDate && newDate < startDate) {
      setStartDate(newDate);
    }
  };
  
  // Email parsing
  const parseAndSetEmails = (input: string) => {
    if (!input.trim()) {
      setEmailRecipients([]);
      return;
    }
    
    const parsed = input
      .split(/[,\n\s;]+/) // Split by comma, newline, space, or semicolon
      .map(email => email.trim())
      .filter(email => email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)); // Basic email validation
    
    setEmailRecipients(Array.from(new Set(parsed))); // Remove duplicates
  };

  const handleEmailInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = event.target.value;
    setEmailRecipientsInput(newValue);
    // Parse emails in real-time as user types
    parseAndSetEmails(newValue);
  };
  
  const handleEmailInputBlur = () => {
    // Also parse on blur to ensure consistency
    parseAndSetEmails(emailRecipientsInput);
  };

  const handleDeleteEmail = (emailToDelete: string) => {
    const updatedEmails = emailRecipients.filter(email => email !== emailToDelete);
    setEmailRecipients(updatedEmails);
    setEmailRecipientsInput(updatedEmails.join('\n'));
  };

  // Update status messages when task state changes
  useEffect(() => {
    if (taskState.taskId && taskState.message) {
      const logMessage = `[${taskState.stage.toUpperCase()}] ${new Date().toLocaleTimeString()}: ${taskState.message}`;
      setStatusMessages(prev => [...prev, logMessage]);
    }
  }, [taskState.message, taskState.stage, taskState.taskId]);

  const handleGenerateNewsletter = async () => {
    if (selectedProfiles.length === 0) {
      setStatusMessages(prev => [...prev, `[ERROR] ${new Date().toLocaleTimeString()}: Please select at least one profile first.`]);
      return;
    }

    if (!researchInterests.trim()) {
      setStatusMessages(prev => [...prev, `[ERROR] ${new Date().toLocaleTimeString()}: Research Interests cannot be empty.`]);
      return;
    }

    // Validate multi-server configuration
    if (useMultiServerJudge && selectedJudgeServers.length === 0) {
      setStatusMessages(prev => [...prev, `[ERROR] ${new Date().toLocaleTimeString()}: At least one server must be selected for multi-server mode.`]);
      return;
    }

    setStatusMessages([]);

    try {
      const params: NewsletterRunParams = {
        start_date: startDate ? startDate.toISOString().split('T')[0] : '',
        end_date: endDate ? endDate.toISOString().split('T')[0] : '',
        email_recipients: emailRecipients,
        research_interests: researchInterests,
        profile_ids: selectedProfileIds,
        // Multi-server judge configuration
        use_multi_server_judge: useMultiServerJudge,
        judge_server_ids: useMultiServerJudge ? selectedJudgeServers : undefined,
        judge_request_timeout_sec: useMultiServerJudge ? judgeRequestTimeout : undefined,
        judge_max_retries: useMultiServerJudge ? judgeMaxRetries : undefined,
      };

      // Use the general newsletter pipeline endpoint
      const response = await settingsApi.runNewsletterPipeline(params);
      setTaskId(response.data.task_id);
    } catch (err: any) {
      console.error("Failed to start newsletter pipeline:", err);
      const errorMessage = err.response?.data?.detail || err.message || "An unknown error occurred.";
      setStatusMessages(prev => [...prev, `[ERROR] ${new Date().toLocaleTimeString()}: ${errorMessage}`]);
    }
  };

  const handleAbortTask = async () => {
    if (!taskState.taskId) return;
    
    setIsAborting(true);
    try {
      await settingsApi.abortTask(taskState.taskId);
      setStatusMessages(prev => [...prev, `[ABORT] ${new Date().toLocaleTimeString()}: Task abort requested`]);
      // The task state will be updated via WebSocket when the task is actually terminated
    } catch (err: any) {
      console.error("Failed to abort task:", err);
      const errorMessage = err.response?.data?.detail || err.message || "Failed to abort task";
      setStatusMessages(prev => [...prev, `[ERROR] ${new Date().toLocaleTimeString()}: ${errorMessage}`]);
    } finally {
      setIsAborting(false);
    }
  };
  

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Container maxWidth="lg" sx={{ pt: `${headerHeight + 32}px`, pb: 4 }}>
        <Typography variant="h4" gutterBottom component="div" sx={{ mb: 3 }}>
          <RocketLaunchIcon sx={{ mr: 1, verticalAlign: 'middle' }}/> New Theseus Insight Newsletter Run
        </Typography>

        {/* Profile Selection */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" fontWeight={600} sx={{ flexGrow: 1 }}>
                👤 Profile Selection
              </Typography>
              <Tooltip title="Select which profile to use for this newsletter. The profile's email recipients and research interests will be loaded automatically.">
                <InfoOutlinedIcon color="action" />
              </Tooltip>
            </Box>
                         <ProfileSelector
               allowMultiple={true}
               showSmartBar={true}
               defaultExpanded={false}
               onProfileChange={(_profileIds) => {
                 // Newsletter can work with multiple profiles but we'll use the first one as primary
                 // The UI will show all selected profiles in the smart bar
               }}
             />
            {selectedProfiles.length === 0 && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                Please select at least one profile to continue. The newsletter will use the profile's email recipients and research interests.
              </Alert>
            )}
          </CardContent>
        </Card>

        {/* Date Range Section */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" fontWeight={600} sx={{ flexGrow: 1 }}>
                🗓️ Date Range for Paper Discovery
                </Typography>
                <Tooltip title="Select the date range for discovering relevant research papers.">
                    <InfoOutlinedIcon color="action" />
                </Tooltip>
            </Box>
            <Box display="flex" alignItems="center" gap={2} flexWrap="wrap">
              <Box display="flex" alignItems="center" gap={1} sx={{minWidth: '150px'}}>
                  <TextField
                    label="Days"
                    type="number"
                    value={days}
                    onChange={(e) => handleDaysChange(parseInt(e.target.value, 10))}
                    inputProps={{ min: 1 }}
                    sx={{ width: '100px' }}
                  />
                  <IconButton onClick={() => handleDaysChange(days - 1)} disabled={days <= 1} size="small"> <RemoveIcon /> </IconButton>
                  <IconButton onClick={() => handleDaysChange(days + 1)} size="small"> <AddIcon /> </IconButton>
              </Box>
              <DatePicker
                label="Start Date"
                value={startDate}
                onChange={handleStartDateChange}
                maxDate={today}
                
              />
              <DatePicker
                label="End Date"
                value={endDate}
                onChange={handleEndDateChange}
                maxDate={today}
                minDate={startDate || undefined}
              />
            </Box>
          </CardContent>
        </Card>

        {/* Multi-Server Judge Configuration Section */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" fontWeight={600} sx={{ flexGrow: 1 }}>
                🚀 LLM Judge Configuration
              </Typography>
              <Tooltip title="Configure how papers are scored for relevance to research interests. Multi-server mode distributes scoring across multiple inference servers for faster processing.">
                <InfoOutlinedIcon color="action" />
              </Tooltip>
            </Box>

            <FormControlLabel
              control={
                <Switch
                  checked={useMultiServerJudge}
                  onChange={(e) => setUseMultiServerJudge(e.target.checked)}
                />
              }
              label="Use Multi-Server Judge (faster for large paper sets)"
            />

            {useMultiServerJudge && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Available Inference Servers ({availableServers.length} enabled)
                </Typography>

                {availableServers.length === 0 ? (
                  <Alert severity="warning" sx={{ mt: 1 }}>
                    No enabled inference servers found. Please configure servers in Settings → Inference Servers.
                  </Alert>
                ) : (
                  <>
                    <FormGroup>
                      {availableServers.map((server) => (
                        <FormControlLabel
                          key={server.id}
                          control={
                            <Checkbox
                              checked={selectedJudgeServers.includes(server.id)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedJudgeServers([...selectedJudgeServers, server.id]);
                                } else {
                                  setSelectedJudgeServers(
                                    selectedJudgeServers.filter(id => id !== server.id)
                                  );
                                }
                              }}
                            />
                          }
                          label={
                            <Box>
                              <Typography variant="body2">
                                {server.name} ({server.provider})
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {server.url}
                                {server.model_name && ` - Model: ${server.model_name}`}
                              </Typography>
                            </Box>
                          }
                        />
                      ))}
                    </FormGroup>

                    {selectedJudgeServers.length === 0 && (
                      <Alert severity="warning" sx={{ mt: 1 }}>
                        At least one server must be selected for multi-server mode
                      </Alert>
                    )}

                    <Grid container spacing={2} sx={{ mt: 2 }}>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                          fullWidth
                          type="number"
                          label="Request Timeout (seconds)"
                          value={judgeRequestTimeout}
                          onChange={(e) => setJudgeRequestTimeout(Number(e.target.value))}
                          inputProps={{ min: 10, max: 300 }}
                          helperText="Max time to wait for each LLM request"
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                          fullWidth
                          type="number"
                          label="Max Retries"
                          value={judgeMaxRetries}
                          onChange={(e) => setJudgeMaxRetries(Number(e.target.value))}
                          inputProps={{ min: 0, max: 10 }}
                          helperText="Number of retry attempts for failed tasks"
                        />
                      </Grid>
                    </Grid>
                  </>
                )}
              </Box>
            )}
          </CardContent>
        </Card>

        {/* Targeting and Content Focus Section */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" fontWeight={600} sx={{ flexGrow: 1 }}>
                🎯 Targeting and Content Focus
                </Typography>
                <Tooltip title="Email recipients and research interests are loaded from the selected profile. You can modify them for this specific newsletter run.">
                    <InfoOutlinedIcon color="action" />
                </Tooltip>
            </Box>
            <TextField
              fullWidth
              label={`Email Recipients (${emailRecipients.length} total${selectedProfiles.length > 1 ? ' from all profiles' : ''})`}
              value={emailRecipientsInput}
              onChange={handleEmailInputChange}
              onBlur={handleEmailInputBlur}
              multiline
              rows={3}
              helperText={selectedProfiles.length > 1 ? 
                "Email recipients combined from all selected profiles. You can modify them for this run." :
                "Email recipients loaded from selected profile. You can modify them for this run."
              }
              sx={{ mb: 1 }}
              disabled={selectedProfiles.length === 0}
            />
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 2, minHeight: '30px' }}>
              {emailRecipients.map((email) => (
                <Chip
                  key={email}
                  label={email}
                  onDelete={() => handleDeleteEmail(email)}
                  color="primary"
                  size="small"
                />
              ))}
            </Box>
            <TextField
              fullWidth
              label={`Research Interests${selectedProfiles.length > 1 ? ' (from all profiles)' : ''}`}
              value={researchInterests}
              onChange={(e) => setResearchInterests(e.target.value)}
              multiline
              rows={5}
              helperText={selectedProfiles.length > 1 ? 
                "Research interests combined from all selected profiles. You can modify them for this run." :
                "Research interests loaded from selected profile. You can modify them for this run."
              }
              sx={{ mb: 2 }}
              disabled={selectedProfiles.length === 0}
            />
          </CardContent>
        </Card>
        
        {/* Action Buttons */}
        <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
          <Button
            variant="contained"
            color="primary"
            fullWidth
            size="large"
            startIcon={isCheckingForActiveTasks ? <CircularProgress size={20} color="inherit" /> : <RocketLaunchIcon />}
            onClick={handleGenerateNewsletter}
            disabled={taskState.isRunning || isCheckingForActiveTasks || selectedProfiles.length === 0}
            sx={{ py: 1.5, fontSize: '1.1rem' }}
          >
            {isCheckingForActiveTasks ? 'Checking for active tasks...' :
             taskState.isRunning ? `Generating... (${taskState.stage} ${taskState.progress.toFixed(0)}%)` : 
             selectedProfiles.length === 0 ? 'Select at least one profile to generate newsletter' :
             '🚀 Generate Newsletter'}
          </Button>
          
          {taskState.isRunning && (
            <Button
              variant="outlined"
              color="error"
              size="large"
              startIcon={isAborting ? <CircularProgress size={20} color="inherit" /> : <StopIcon />}
              onClick={handleAbortTask}
              disabled={isAborting}
              sx={{ py: 1.5, fontSize: '1.1rem', minWidth: '140px' }}
            >
              {isAborting ? 'Aborting...' : 'Abort'}
            </Button>
          )}
        </Box>

        {/* Pipeline Status Section */}
        <Card>
          <CardContent>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Pipeline Status
            </Typography>
            {taskState.error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {taskState.error}
              </Alert>
            )}
            {taskState.isRunning && (
              <Box sx={{ mb: 2 }}>
                {/* Show enhanced status for scoring phase */}
                {taskState.stage === 'rank' && useMultiServerJudge && (
                  <Alert severity="info" sx={{ mb: 2 }}>
                    🚀 Multi-Server Scoring in Progress
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      Using {selectedJudgeServers.length} inference server{selectedJudgeServers.length > 1 ? 's' : ''} to score papers in parallel.
                      {availableServers.length > 0 && (
                        <>
                          <br />
                          Servers: {availableServers
                            .filter(s => selectedJudgeServers.includes(s.id))
                            .map(s => s.name)
                            .join(', ')}
                        </>
                      )}
                    </Typography>
                  </Alert>
                )}
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body1" fontWeight={500}>
                    {taskState.stage.charAt(0).toUpperCase() + taskState.stage.slice(1)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {taskState.progress.toFixed(0)}%
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {taskState.message}
                </Typography>
                <LinearProgress variant="determinate" value={taskState.progress} />
              </Box>
            )}
            {!taskState.isRunning && !taskState.error && taskState.taskId && (
                 <Alert severity="success" sx={{ mb: 2 }}>
                    Task {taskState.taskId} completed successfully.
                 </Alert>
            )}
             {!taskState.isRunning && !taskState.taskId && !isCheckingForActiveTasks && (
                 <Typography variant="body1" color="text.secondary">{taskState.message}</Typography>
            )}
            {isCheckingForActiveTasks && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <CircularProgress size={20} />
                <Typography variant="body1" color="text.secondary">Checking for active tasks...</Typography>
              </Box>
            )}
            <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>Live Log:</Typography>
            <Box 
              sx={{ 
                height: 200, 
                overflowY: 'auto', 
                border: '1px solid',
                borderColor: 'divider', 
                p: 1, 
                borderRadius: 1,
                fontFamily: 'monospace',
                whiteSpace: 'pre-wrap',
                backgroundColor: 'action.hover'
              }}
            >
              {statusMessages.length > 0 ? statusMessages.map((msg, index) => (
                <div key={index}>{msg}</div>
              )) : "No log messages yet."}
            </Box>
          </CardContent>
        </Card>
      </Container>
    </LocalizationProvider>
  );
};

export default Newsletter; 