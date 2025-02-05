import React from 'react';
import {
  Box,
  Typography,
  LinearProgress,
  Paper,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Button,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Pending as PendingIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';
import { TaskStatus } from '../../types/api';
import { API_BASE_URL } from '../../hooks/useAPI';

interface GenerationProgressProps {
  taskStatus?: TaskStatus;
  isGenerating: boolean;
}

const GenerationProgress: React.FC<GenerationProgressProps> = ({
  taskStatus,
  isGenerating,
}) => {
  const getStatusIcon = (stepIndex: number, currentStepIndex: number, taskStatus: TaskStatus) => {
    if (taskStatus.status === 'completed') {
      return <CheckCircleIcon color="success" />;
    }
    if (taskStatus.status === 'failed') {
      return <ErrorIcon color="error" />;
    }
    if (stepIndex < currentStepIndex) {
      return <CheckCircleIcon color="success" />;
    }
    if (stepIndex === currentStepIndex) {
      return <PendingIcon color="primary" />;
    }
    return <PendingIcon color="disabled" />;
  };

  const handleDownload = () => {
    if (taskStatus?.output_url) {
      window.open(`${API_BASE_URL}${taskStatus.output_url}`, '_blank');
    }
  };

  const steps = [
    'Processing PDFs',
    'Generating podcast description',
    'Generating dialogue',
    'Converting text to speech',
    'Combining audio segments',
    'Finalizing output'
  ];

  const currentStepIndex = taskStatus?.current_step
    ? steps.findIndex((step) => step === taskStatus.current_step)
    : -1;

  return (
    <Box>
      {isGenerating && !taskStatus && (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="h6" gutterBottom>
            Starting podcast generation...
          </Typography>
          <LinearProgress />
        </Box>
      )}

      {taskStatus && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Generation Progress
          </Typography>

          <Box sx={{ mb: 3 }}>
            <LinearProgress
              variant="determinate"
              value={taskStatus.progress || 0}
            />
          </Box>

          <List>
            {steps.map((step, index) => (
              <ListItem key={step}>
                <ListItemIcon>
                  {getStatusIcon(index, currentStepIndex, taskStatus)}
                </ListItemIcon>
                <ListItemText
                  primary={step}
                  secondary={
                    index === currentStepIndex && taskStatus.status === 'processing'
                      ? `${taskStatus.progress}%`
                      : ''
                  }
                />
              </ListItem>
            ))}
          </List>

          {taskStatus.status === 'completed' && taskStatus.output_url && (
            <Box sx={{ mt: 3, textAlign: 'center' }}>
              <Button
                variant="contained"
                color="primary"
                startIcon={<DownloadIcon />}
                onClick={handleDownload}
              >
                Download Podcast
              </Button>
            </Box>
          )}

          {taskStatus.status === 'failed' && taskStatus.error && (
            <Box sx={{ mt: 3 }}>
              <Typography color="error" variant="body1">
                Error: {taskStatus.error}
              </Typography>
            </Box>
          )}
        </Paper>
      )}
    </Box>
  );
};

export default GenerationProgress; 