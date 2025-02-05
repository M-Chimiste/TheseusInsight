import React from 'react';
import {
  Box,
  Typography,
  LinearProgress,
  Button,
  Alert,
} from '@mui/material';
import { TaskStatus } from '../../types/api';
import { Download as DownloadIcon } from '@mui/icons-material';
import { API_BASE_URL } from '../../hooks/useAPI';

interface GenerationProgressProps {
  taskStatus?: TaskStatus;
  isGenerating: boolean;
}

const GenerationProgress: React.FC<GenerationProgressProps> = ({
  taskStatus,
  isGenerating,
}) => {
  const handleDownload = () => {
    if (taskStatus?.output_url) {
      const fullUrl = `${API_BASE_URL}${taskStatus.output_url}`;
      const link = document.createElement('a');
      link.href = fullUrl;
      link.download = '';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  if (!taskStatus && !isGenerating) {
    return (
      <Box>
        <Alert severity="info">
          Click the Generate button to start creating your visualization
        </Alert>
      </Box>
    );
  }

  if (isGenerating && !taskStatus) {
    return (
      <Box>
        <Typography variant="body1" gutterBottom>
          Initializing generation...
        </Typography>
        <LinearProgress />
      </Box>
    );
  }

  return (
    <Box>
      {taskStatus?.status === 'failed' ? (
        <Alert severity="error">
          {taskStatus.error || 'An error occurred during generation'}
        </Alert>
      ) : (
        <>
          <Typography variant="body1" gutterBottom>
            {taskStatus?.current_step || 'Processing...'}
          </Typography>

          <LinearProgress
            variant="determinate"
            value={taskStatus?.progress || 0}
            sx={{ mb: 2 }}
          />

          {taskStatus?.steps?.map((step, index) => (
            <Box key={index} sx={{ mb: 1 }}>
              <Typography variant="body2" color="textSecondary">
                {step.name}: {step.status}
                {step.progress !== undefined && ` (${step.progress}%)`}
              </Typography>
            </Box>
          ))}

          {taskStatus?.status === 'completed' && taskStatus.output_url && (
            <Box sx={{ mt: 2 }}>
              <Button
                variant="contained"
                startIcon={<DownloadIcon />}
                onClick={handleDownload}
              >
                Download Visualization
              </Button>
            </Box>
          )}
        </>
      )}
    </Box>
  );
};

export default GenerationProgress; 