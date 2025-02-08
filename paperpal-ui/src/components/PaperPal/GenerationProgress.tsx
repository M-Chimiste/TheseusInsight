import React, { useEffect, useCallback, useState } from 'react';
import {
  Box,
  Typography,
  LinearProgress,
  Paper,
  Alert,
} from '@mui/material';
import { PaperPalStatus } from '../../types/api';

interface GenerationProgressProps {
  taskId: string;
  onCheckStatus: (taskId: string) => Promise<PaperPalStatus>;
}

const GenerationProgress: React.FC<GenerationProgressProps> = ({
  taskId,
  onCheckStatus,
}) => {
  const [currentStatus, setCurrentStatus] = useState<PaperPalStatus | null>(null);

  const checkStatus = useCallback(async () => {
    try {
      const status = await onCheckStatus(taskId);
      setCurrentStatus(status);
      if (status.status !== 'completed' && status.status !== 'failed') {
        setTimeout(() => checkStatus(), 2000); // Poll every 2 seconds
      }
    } catch (error) {
      console.error('Failed to check status:', error);
    }
  }, [taskId, onCheckStatus]);

  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Generation Progress
      </Typography>

      <Box sx={{ mt: 2 }}>
        <Typography variant="body1" gutterBottom>
          Current Stage: {currentStatus?.stage || 'Initializing'}
        </Typography>
        <LinearProgress
          variant="determinate"
          value={currentStatus?.progress || 0}
          sx={{ my: 2 }}
        />
        <Typography variant="body2" color="textSecondary">
          {currentStatus?.message || 'Starting PaperPal...'}
        </Typography>
      </Box>

      {currentStatus?.error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {currentStatus.error}
        </Alert>
      )}
    </Paper>
  );
};

export default GenerationProgress; 