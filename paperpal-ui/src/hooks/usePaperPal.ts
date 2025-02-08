import { useState } from 'react';
import { PaperPalConfig } from '../types/api';

interface PaperPalStatus {
  status: 'initializing' | 'running' | 'completed' | 'failed';
  progress: number;
  stage: string;
  message: string;
  error?: string;
}

export const usePaperPal = () => {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<PaperPalStatus | null>(null);

  const runPaperPal = async (
    config: PaperPalConfig,
    researchInterestsFile: File | null,
    orchestrationFile: File | null
  ) => {
    try {
      const formData = new FormData();
      
      console.log('Files being sent:', {
        researchInterests: researchInterestsFile,
        orchestration: orchestrationFile
      });
      
      if (researchInterestsFile) {
        formData.append('research_interests_file', researchInterestsFile);
        formData.append('research_interests_path', '');
      } else {
        formData.append('research_interests_path', config.researchInterestsPath);
      }

      if (orchestrationFile) {
        formData.append('orchestration_file', orchestrationFile);
        formData.append('orchestration_config_path', '');
      } else {
        formData.append('orchestration_config_path', config.orchestrationConfigPath);
      }
      
      // Convert dates to ISO strings for JSON serialization
      const configToSend = {
        ...config,
        startDate: config.startDate?.toISOString() || null,
        endDate: config.endDate?.toISOString() || null,
      };
      
      formData.append('config', JSON.stringify(configToSend));
      
      console.log('Config being sent:', configToSend);
      console.log('FormData entries:', Array.from(formData.entries()));

      // Use the full URL and include credentials
      const response = await fetch('http://localhost:8000/api/paperpal/run', {
        method: 'POST',
        body: formData,
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
        }
      });

      console.log('Response status:', response.status);
      console.log('Response headers:', response.headers);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Error response text:', errorText);
        const errorData = JSON.parse(errorText);
        console.error('Error response:', errorData);
        throw new Error(errorData?.detail || 'Failed to start PaperPal');
      }

      const data = await response.json();
      console.log('Response data:', data);
      
      setTaskId(data.task_id);
      return data.task_id;
    } catch (error) {
      console.error('Error in runPaperPal:', error);
      throw error;
    }
  };

  const checkStatus = async (taskId: string) => {
    try {
      const response = await fetch(`/api/paperpal/status/${taskId}`);
      if (!response.ok) {
        throw new Error('Failed to get status');
      }
      const status = await response.json();
      setStatus(status);
      return status;
    } catch (error) {
      throw error;
    }
  };

  return {
    taskId,
    status,
    runPaperPal,
    checkStatus,
  };
}; 