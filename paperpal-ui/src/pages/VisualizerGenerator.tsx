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
import { useGenerateVisualizer, useVisualizerStatus } from '../hooks/useVisualizer';
import { VisualizerConfig } from '../types/api';
import AudioUpload from '../components/VisualizerGenerator/AudioUpload';
import VisualizerSettings from '../components/VisualizerGenerator/VisualizerSettings';
import GenerationProgress from '../components/VisualizerGenerator/GenerationProgress';

const steps = ['Upload Audio', 'Configure Visualizer', 'Generate Video'];

const defaultConfig: VisualizerConfig = {
  resolution: [1920, 1080],
  fps: 30,
  matrix_count: 200,
  matrix_head_color: "#e0ffe7",
  matrix_tail_color: "0x00b000",
  matrix_char_size: 24,
  head_step_time: 0.25,
  random_x_jitter: 2.0,
  fade_time: 3.0,
  head_glow_passes: 3,
  head_glow_alpha_decay: 50,
  head_spawn_delay_range: [1.0, 3.0],
  head_saw_period: 1.5,
  wave_color: "#d703fc",
  trail_colors: ["#fc03b6", "#ba03fc", "#ce6bf2"],
  glow_passes: 3,
  glow_alpha_decay: 40,
  line_width: 6,
  font_path: ""
};

const VisualizerGenerator: React.FC = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [config, setConfig] = useState<VisualizerConfig>(defaultConfig);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { mutate: generateVisualizer, isLoading: isGenerating } = useGenerateVisualizer();
  const { data: taskStatus } = useVisualizerStatus(taskId || '');

  const handleNext = () => {
    if (activeStep === steps.length - 1) {
      // Start generation
      if (!audioFile) return;

      generateVisualizer(
        { file: audioFile, config },
        {
          onSuccess: (response) => {
            if (response.status === 'processing') {
              setTaskId(response.task_id);
            }
          },
          onError: (error) => {
            setError(error.message);
          },
        }
      );
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
        return !!audioFile;
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
        Visualizer Generator
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
            <AudioUpload
              file={audioFile}
              onFileChange={setAudioFile}
            />
          )}
          {activeStep === 1 && (
            <VisualizerSettings
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

export default VisualizerGenerator; 