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
  CircularProgress
} from '@mui/material';
import { LocalizationProvider, DatePicker } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import { settingsApi } from '../services/api';
import { useTaskState } from '../hooks/useTaskState';

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

// Interfaces for form data

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
  
  // Use the new task state hook
  const { taskState, setTaskId, isCheckingForActiveTasks } = useTaskState('newsletter');

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
      .split(/[,\n\s]+/)
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
    setEmailRecipientsInput(updatedEmails.join('\\n'));
  };

  // Update status messages when task state changes
  useEffect(() => {
    if (taskState.taskId && taskState.message) {
      const logMessage = `[${taskState.stage.toUpperCase()}] ${new Date().toLocaleTimeString()}: ${taskState.message}`;
      setStatusMessages(prev => [...prev, logMessage]);
    }
  }, [taskState.message, taskState.stage, taskState.taskId]);

  const handleGenerateNewsletter = async () => {
    if (!researchInterests.trim()) {
      // Show error in status messages
      setStatusMessages(prev => [...prev, `[ERROR] ${new Date().toLocaleTimeString()}: Research Interests cannot be empty.`]);
      return;
    }

    setStatusMessages([]);

    try {
      const params = {
        start_date: startDate ? startDate.toISOString().split('T')[0] : '',
        end_date: endDate ? endDate.toISOString().split('T')[0] : '',
        email_recipients: emailRecipients,
        research_interests: researchInterests,
      };
      const response = await settingsApi.runNewsletterPipeline(params);
      setTaskId(response.data.task_id);
    } catch (err: any) {
      console.error("Failed to start newsletter pipeline:", err);
      const errorMessage = err.response?.data?.detail || err.message || "An unknown error occurred.";
      setStatusMessages(prev => [...prev, `[ERROR] ${new Date().toLocaleTimeString()}: ${errorMessage}`]);
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
              helperText="Enter emails separated by commas, spaces, or line breaks. Valid emails will appear as tags below in real-time."
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
          startIcon={isCheckingForActiveTasks ? <CircularProgress size={20} color="inherit" /> : <RocketLaunchIcon />}
          onClick={handleGenerateNewsletter}
          disabled={taskState.isRunning || isCheckingForActiveTasks}
          sx={{ py: 1.5, mb: 3, fontSize: '1.1rem' }}
        >
          {isCheckingForActiveTasks ? 'Checking for active tasks...' :
           taskState.isRunning ? `Generating... (${taskState.stage} ${taskState.progress.toFixed(0)}%)` : 
           '🚀 Generate Newsletter'}
        </Button>

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
                <Typography variant="body1" gutterBottom>{taskState.stage} - {taskState.message}</Typography>
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