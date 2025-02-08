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

const defaultConfig: PodcastGenerationConfig = {
  text_model: {
    model_name: "gemini-2.0-flash",
    model_type: "gemini",
    max_new_tokens: 8192,
    temperature: 0.1,
    num_ctx: 131072
  },
  tts_provider: "openai",
  speaker_1_voice: "sage",
  speaker_1_speed: 1.0,
  speaker_2_voice: "ash",
  speaker_2_speed: 1.0,
  output_format: "mp3",
  visualizer: false,
  visualizer_config: {
    resolution: [1920, 1080],
    fps: 30,
    matrix_count: 200,
    matrix_head_color: "#00ff00",
    matrix_tail_color: "#004400",
    matrix_char_size: 24,
    head_step_time: 0.25,
    random_x_jitter: 2.0,
    fade_time: 1.5,
    head_glow_passes: 3,
    head_glow_alpha_decay: 50,
    head_spawn_delay_range: [1.0, 3.0],
    head_saw_period: 1.5,
    wave_color: "#ff00ff",
    trail_colors: ["#ff0088", "#8800ff", "#ff88ff"],
    glow_passes: 3,
    glow_alpha_decay: 40,
    line_width: 6,
    font_path: "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
  },
  fade_time: 3.0,
  head_saw_period: 1.5,
  font_path: ""
};

const PodcastGenerator: React.FC = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [files, setFiles] = useState<File[]>([]);
  const [urls, setUrls] = useState<string[]>([]);
  const [config, setConfig] = useState<PodcastGenerationConfig>(defaultConfig);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { mutate: generatePodcast, isLoading: isGenerating } = useGeneratePodcast();
  const { data: taskStatus } = usePodcastStatus(taskId || '');

  const handleNext = () => {
    if (activeStep === steps.length - 1) {
      // Start generation
      const formData = new FormData();
      
      // Add files to form data
      files.forEach((file) => {
        formData.append('files', file);
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