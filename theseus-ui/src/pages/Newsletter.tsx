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
  Chip
} from '@mui/material';
import { LocalizationProvider, DatePicker } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import { settingsApi } from '../services/api'; // Assuming API service is correctly set up
import { useWebSocket } from '../hooks/useWebSocket'; // Assuming WebSocket hook is available

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

// Frontend state for the pipeline
interface PipelineStatus {
  isRunning: boolean;
  stage: string;
  progress: number;
  message: string;
  error: string | null;
  taskId: string | null;
}

// Interfaces to represent the WebSocket JSON payload from the backend (RunStatus model)
interface NodeStatusPayload {
  nodeId: string;
  name?: string;
  status: string; // e.g., TaskStatus enum from backend
  message?: string;
  progress?: number; // Percentage 0-100 from backend
  timestamp?: string;
  error?: string;
  // inputs & outputs are omitted as they are not primarily used for live status display here
}

interface RunStatusPayload {
  taskId: string;
  pipelineType?: string;
  nodes: NodeStatusPayload[];
  overallStatus: string; // e.g., TaskStatus enum from backend
  current_step?: string; // Not consistently sent by backend tasks.py for progress
  progress?: number;     // Not consistently sent by backend tasks.py for progress
  message?: string;      // Not consistently sent by backend tasks.py for progress
  error?: string | null; // Overall error for the run (allow null)
  result?: Record<string, any>;
  start_time?: string;
  end_time?: string;
}

const Newsletter = () => {
  const today = new Date();
  const sevenDaysAgo = getDateByOffset(-6); // -6 because we add 1 in getDaysDifference for an inclusive 7 days

  const [startDate, setStartDate] = useState<Date | null>(sevenDaysAgo);
  const [endDate, setEndDate] = useState<Date | null>(today);
  const [days, setDays] = useState<number>(7);

  const [emailRecipientsInput, setEmailRecipientsInput] = useState<string>('');
  const [emailRecipients, setEmailRecipients] = useState<string[]>([]);
  const [researchInterests, setResearchInterests] = useState<string>('');
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus>({
    isRunning: false,
    stage: '',
    progress: 0,
    message: "No active newsletter generation task. Configure and click 'Generate Newsletter' to start.",
    error: null,
    taskId: null,
  });

  // Fetch default settings
  useEffect(() => {
    settingsApi.getEmailRecipients()
      .then(response => {
        setEmailRecipients(response.data.recipients || []);
        setEmailRecipientsInput((response.data.recipients || []).join('\\n'));
      })
      .catch(err => console.error("Failed to load email recipients:", err));

    settingsApi.getResearchInterests()
      .then(response => setResearchInterests(response.data.interests || ''))
      .catch(err => console.error("Failed to load research interests:", err));
  }, []);
  
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
    const parsed = input
      .split(/[,\\n\\s]+/)
      .map(email => email.trim())
      .filter(email => email && /^[^\s@]+@[^\s@]+\\.[^\s@]+$/.test(email)); // Basic email validation
    setEmailRecipients(Array.from(new Set(parsed))); // Remove duplicates
  };

  const handleEmailInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEmailRecipientsInput(event.target.value);
  };
  
  const handleEmailInputBlur = () => {
    parseAndSetEmails(emailRecipientsInput);
  };

  const handleDeleteEmail = (emailToDelete: string) => {
    const updatedEmails = emailRecipients.filter(email => email !== emailToDelete);
    setEmailRecipients(updatedEmails);
    setEmailRecipientsInput(updatedEmails.join('\\n'));
  };

  // Processes the parsed RunStatus payload from WebSocket to update UI state
  const handleParsedRunStatus = (payload: RunStatusPayload) => {
    const mainNode = payload.nodes && payload.nodes.length > 0 ? payload.nodes[0] : null;

    // Update live log messages
    const logMessage = `[${payload.overallStatus.toUpperCase()}] ${new Date().toLocaleTimeString()}: ${mainNode?.message || payload.error || 'Status update'}`;
    setStatusMessages(prev => [...prev, logMessage]);

    // Update pipeline status for progress bar and summary text
    setPipelineStatus(prev => ({
      ...prev,
      // Use mainNode.message for stage, fallback to overall status or previous stage
      stage: mainNode?.message || (payload.overallStatus === 'FAILED' ? 'Failed' : prev.stage),
      // Progress comes from the mainNode
      progress: mainNode?.progress ?? (payload.overallStatus === 'COMPLETED' ? 100 : (payload.overallStatus === 'FAILED' ? 0 : prev.progress)),
      // Display mainNode message, or overall error if present, or fallback
      message: mainNode?.message || payload.error || (payload.overallStatus === 'COMPLETED' ? 'Completed successfully' : 'Processing...'),
      // Prioritize overall error, then node error
      error: payload.error || mainNode?.error || null,
      isRunning: payload.overallStatus !== 'COMPLETED' && payload.overallStatus !== 'FAILED',
      // Ensure taskId from payload is used if it's the first time or changes (though unlikely for an ongoing task)
      taskId: payload.taskId || prev.taskId, 
    }));

    // If task is fully completed or failed, you might want to do additional cleanup or state changes here
    // For instance, if you want useWebSocket to disconnect or stop trying for this specific task ID:
    // if (payload.overallStatus === 'COMPLETED' || payload.overallStatus === 'FAILED') {
    //   setPipelineStatus(prev => ({ ...prev, taskId: null })); // This would make currentTaskId null
    // }
  };

  const currentTaskId = pipelineStatus.taskId;
  // const placeholderTaskId = 'dummy-task-id'; // No longer needed for the hook call

  // Pass currentTaskId directly (can be null). The hook should handle null taskId gracefully.
  const hookState = useWebSocket(currentTaskId, "newsletter");

  useEffect(() => {
    // Only process messages if we have a REAL taskId and a new message
    if (currentTaskId && hookState.lastMessage) {
      console.log("[Newsletter.tsx] WebSocket lastMessage received:", hookState.lastMessage); // DEBUG LOG
      handleParsedRunStatus(hookState.lastMessage);
    }

    // Handle WebSocket errors for real tasks
    if (currentTaskId && hookState.error) {
      console.log(`[Newsletter.tsx] WebSocket error for task ${currentTaskId}:`, hookState.error); // DEBUG LOG
      const errorMessage = hookState.error?.toString() || 'WebSocket connection error';
      // if (currentTaskId !== placeholderTaskId) { // This check is redundant if currentTaskId is string | null
      setPipelineStatus(prev => ({
        ...prev,
        isRunning: false,
        error: errorMessage,
        message: `WebSocket Error: ${errorMessage}`,
      }));
      setStatusMessages(prev => [...prev, `[ERROR] ${new Date().toLocaleTimeString()} for task ${currentTaskId}: ${errorMessage}`]);
      // }
    }
  }, [currentTaskId, hookState.lastMessage, hookState.error]);

  const handleGenerateNewsletter = async () => {
    if (!researchInterests.trim()) {
      setPipelineStatus(prev => ({ ...prev, error: "Research Interests cannot be empty." }));
      return;
    }

    setStatusMessages([]);
    setPipelineStatus({
      isRunning: true,
      stage: 'Initiating...',
      progress: 5,
      message: 'Preparing to generate newsletter...',
      error: null,
      taskId: null, // Will be set by API response
    });

    try {
      const params = {
        start_date: startDate ? startDate.toISOString().split('T')[0] : '',
        end_date: endDate ? endDate.toISOString().split('T')[0] : '',
        email_recipients: emailRecipients,
        research_interests: researchInterests,
      };
      const response = await settingsApi.runNewsletterPipeline(params);
      setPipelineStatus(prev => ({ ...prev, taskId: response.data.task_id, message: `Task ${response.data.task_id} started.` }));
    } catch (err: any) {
      console.error("Failed to start newsletter pipeline:", err);
      const errorMessage = err.response?.data?.detail || err.message || "An unknown error occurred.";
      setPipelineStatus({
        isRunning: false,
        stage: 'Failed to Start',
        progress: 0,
        message: `Error: ${errorMessage}`,
        error: errorMessage,
        taskId: null,
      });
    }
  };
  

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          <RocketLaunchIcon sx={{ mr: 1, verticalAlign: 'middle' }}/> New Theseus Insight Newsletter Run
        </Typography>

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

        {/* Targeting and Content Focus Section */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" fontWeight={600} sx={{ flexGrow: 1 }}>
                🎯 Targeting and Content Focus
                </Typography>
                <Tooltip title="Define your target audience and the specific research areas for this newsletter.">
                    <InfoOutlinedIcon color="action" />
                </Tooltip>
            </Box>
            <TextField
              fullWidth
              label="Email Recipients (for this run)"
              value={emailRecipientsInput}
              onChange={handleEmailInputChange}
              onBlur={handleEmailInputBlur}
              multiline
              rows={3}
              helperText="Enter emails separated by commas, spaces, or newlines. Validated emails will appear as tags below."
              sx={{ mb: 1 }}
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
              label="Research Interests (for this run)"
              value={researchInterests}
              onChange={(e) => setResearchInterests(e.target.value)}
              multiline
              rows={5}
              helperText="Provide a detailed description of your research interests."
              sx={{ mb: 2 }}
            />
          </CardContent>
        </Card>
        
        {/* Action Button */}
        <Button
          variant="contained"
          color="primary"
          fullWidth
          size="large"
          startIcon={<RocketLaunchIcon />}
          onClick={handleGenerateNewsletter}
          disabled={pipelineStatus.isRunning}
          sx={{ py: 1.5, mb: 3, fontSize: '1.1rem' }}
        >
          {pipelineStatus.isRunning ? `Generating... (${pipelineStatus.stage} ${pipelineStatus.progress.toFixed(0)}%)` : '🚀 Generate Newsletter'}
        </Button>

        {/* Pipeline Status Section */}
        <Card>
          <CardContent>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Pipeline Status
            </Typography>
            {pipelineStatus.error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {pipelineStatus.error}
              </Alert>
            )}
            {pipelineStatus.isRunning && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="body1" gutterBottom>{pipelineStatus.stage} - {pipelineStatus.message}</Typography>
                <LinearProgress variant="determinate" value={pipelineStatus.progress} />
              </Box>
            )}
            {!pipelineStatus.isRunning && !pipelineStatus.error && pipelineStatus.taskId && (
                 <Alert severity="success" sx={{ mb: 2 }}>
                    Task {pipelineStatus.taskId} completed successfully.
                 </Alert>
            )}
             {!pipelineStatus.isRunning && !pipelineStatus.taskId && (
                 <Typography variant="body1" color="text.secondary">{pipelineStatus.message}</Typography>
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