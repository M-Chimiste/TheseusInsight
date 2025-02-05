import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Stepper,
  Step,
  StepLabel,
  Button,
  Alert,
  Snackbar,
} from '@mui/material';
import { useGeneratePodcast, usePodcastStatus } from '../hooks/usePodcast';
import { PodcastGenerationConfig } from '../types/api';
import FileUpload from '../components/PodcastGenerator/FileUpload';
import ConfigurationPanel from '../components/PodcastGenerator/ConfigurationPanel';
import GenerationProgress from '../components/PodcastGenerator/GenerationProgress';

const steps = ['Upload Files', 'Configure Settings', 'Generate Podcast'];

const PodcastGenerator: React.FC = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [files, setFiles] = useState<File[]>([]);
  const [urls, setUrls] = useState<string[]>([]);
  const [config, setConfig] = useState<PodcastGenerationConfig>({
    text_model: {
      model_name: "claude-3-5-sonnet-20240620",
      model_type: "anthropic",
      max_new_tokens: 8192,
      temperature: 0.1,
      num_ctx: 131072
    },
    tts_provider: "kokoro",
    speaker_1_voice: "af_bella",
    speaker_1_speed: 1.15,
    speaker_2_voice: "am_adam",
    speaker_2_speed: 1.15,
    output_format: "mp3",
    visualizer: false,
    resolution: [1920, 1080],
    fps: 30,
    matrix_count: 200,
    fade_time: 3.0,
    head_saw_period: 1.5,
    font_path: ""
  });
  const [taskId, setTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { mutate: generatePodcast, isLoading: isGenerating } = useGeneratePodcast();
  const { data: taskStatus } = usePodcastStatus(taskId || '');

  const handleNext = () => {
    if (activeStep === steps.length - 1) {
      // Start generation
      const formData = new FormData();
      
      // Add files to form data
      files.forEach((file, index) => {
        formData.append(`file_${index}`, file);
      });
      
      // Add URLs as a JSON string
      formData.append('urls', JSON.stringify(urls));
      
      // Add config as JSON string
      formData.append('config', JSON.stringify(config));
      
      generatePodcast(formData, {
        onSuccess: (response) => {
          if (response.status === 'processing') {
            setTaskId(response.task_id);
          }
        },
        onError: (error) => {
          setError(error.message);
        }
      });
    } else {
      setActiveStep((prevStep) => prevStep + 1);
    }
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  const canProceed = () => {
    switch (activeStep) {
      case 0:
        return files.length > 0 || urls.length > 0;
      case 1:
        return true; // Configuration is optional
      case 2:
        return !isGenerating;
      default:
        return false;
    }
  };

  return (
    <Box>
      <Typography variant="h2" gutterBottom>
        New Podcast Generator
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        <Box sx={{ mt: 2, mb: 2 }}>
          {activeStep === 0 && (
            <FileUpload
              files={files}
              urls={urls}
              onFilesChange={setFiles}
              onUrlsChange={setUrls}
            />
          )}
          {activeStep === 1 && (
            <ConfigurationPanel
              config={config}
              onChange={setConfig}
            />
          )}
          {activeStep === 2 && (
            <GenerationProgress
              taskStatus={taskStatus}
              isGenerating={isGenerating}
            />
          )}
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
          <Button
            disabled={activeStep === 0}
            onClick={handleBack}
          >
            Back
          </Button>
          <Button
            variant="contained"
            onClick={handleNext}
            disabled={!canProceed()}
          >
            {activeStep === steps.length - 1 ? 'Generate' : 'Next'}
          </Button>
        </Box>
      </Paper>

      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={() => setError(null)}
      >
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default PodcastGenerator; 