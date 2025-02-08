import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  FormControlLabel,
  Switch,
  Alert,
  IconButton,
  Tooltip,
} from '@mui/material';
import DatePicker from 'react-datepicker';
import "react-datepicker/dist/react-datepicker.css";
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Upload as UploadIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { VisualizerConfig } from '../types/api';
import { usePaperPal } from '../hooks/usePaperPal';
import GenerationProgress from '../components/PaperPal/GenerationProgress';
import FilePreview from '../components/PaperPal/FilePreview';

interface PaperPalConfig {
  researchInterestsPath: string;
  orchestrationConfigPath: string;
  nDays: number;
  topN: number;
  startDate: Date | null;
  endDate: Date | null;
  emails: string[];
  similarityThreshold: number;
  publishToYoutube: boolean;
  introMusicPath: string;
  ttsProvider: 'openai' | 'kokoro';
  speaker1Voice: string;
  speaker1Speed: number;
  speaker2Voice: string;
  speaker2Speed: number;
  visualizerConfig: VisualizerConfig;
}

const defaultConfig: PaperPalConfig = {
  researchInterestsPath: "../config/research_interests.txt",
  orchestrationConfigPath: "../config/orchestration.json",
  nDays: 7,
  topN: 5,
  startDate: null,
  endDate: null,
  emails: [],
  similarityThreshold: 0.7,
  publishToYoutube: false,
  introMusicPath: '',
  ttsProvider: 'openai',
  speaker1Voice: 'ash',
  speaker1Speed: 1.0,
  speaker2Voice: 'sage',
  speaker2Speed: 1.0,
  visualizerConfig: {
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
  }
};

const TTS_PROVIDERS = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Kokoro', value: 'kokoro' }
] as const;

const OPENAI_VOICES = [
  { label: 'Sage', value: 'sage' },
  { label: 'Ash', value: 'ash' },
  { label: 'Alloy', value: 'alloy' },
  { label: 'Echo', value: 'echo' },
  { label: 'Fable', value: 'fable' },
  { label: 'Onyx', value: 'onyx' },
  { label: 'Nova', value: 'nova' },
  { label: 'Shimmer', value: 'shimmer' }
] as const;

const KOKORO_VOICES = [
  { label: 'Heart', value: 'af_heart' },
  { label: 'Alloy', value: 'af_alloy' },
  { label: 'Aoede', value: 'af_aoede' },
  { label: 'Bella', value: 'af_bella' },
  { label: 'Adam', value: 'am_adam' },
  { label: 'Echo', value: 'am_echo' },
  { label: 'Eric', value: 'am_eric' },
  { label: 'Michael', value: 'am_michael' },
  { label: 'Fenrir', value: 'am_fenrir'},
  { label: 'Sky', value: 'am_sky' }
] as const;


const RESOLUTION_PRESETS = [
  { label: '1080p', value: [1920, 1080] },
  { label: '720p', value: [1280, 720] },
  { label: '480p', value: [854, 480] },
] as const;

const fontOptions = [
  { label: 'Hiragino Kaku Gothic W3', value: '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc', default: true },
  { label: 'System Default', value: '' },
];

const PaperPal: React.FC = () => {
  const [config, setConfig] = useState<PaperPalConfig>(defaultConfig);
  const [newEmail, setNewEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [researchInterestsFile, setResearchInterestsFile] = useState<File | null>(null);
  const [orchestrationFile, setOrchestrationFile] = useState<File | null>(null);
  const { taskId, runPaperPal, checkStatus } = usePaperPal();
  const [previewFile, setPreviewFile] = useState<{
    file: File | null;
    type: 'json' | 'text';
  } | null>(null);
  const [introMusicFile, setIntroMusicFile] = useState<File | null>(null);

  const handleConfigChange = (field: keyof PaperPalConfig, value: any) => {
    setConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleVisualizerConfigChange = (field: keyof VisualizerConfig, value: any) => {
    setConfig(prev => ({
      ...prev,
      visualizerConfig: {
        ...prev.visualizerConfig,
        [field]: value
      }
    }));
  };

  const handleAddEmail = () => {
    if (newEmail && !config.emails.includes(newEmail)) {
      handleConfigChange('emails', [...config.emails, newEmail]);
      setNewEmail('');
    }
  };

  const handleRemoveEmail = (email: string) => {
    handleConfigChange('emails', config.emails.filter(e => e !== email));
  };

  const handleResearchInterestsUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setResearchInterestsFile(file);
      handleConfigChange('researchInterestsPath', file.name);
    }
  };

  const handleOrchestrationUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setOrchestrationFile(file);
      handleConfigChange('orchestrationConfigPath', file.name);
    }
  };

  const handleDateChange = (field: 'startDate' | 'endDate', date: Date | null) => {
    handleConfigChange(field, date);
  };

  const handleIntroMusicUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setIntroMusicFile(file);
      handleConfigChange('introMusicPath', file.name);
    }
  };

  const validateFiles = () => {
    const errors: string[] = [];

    if (!researchInterestsFile && !config.researchInterestsPath.includes('config/research_interests.txt')) {
      errors.push('Research interests file is required');
    }

    if (!orchestrationFile && !config.orchestrationConfigPath.includes('config/orchestration.json')) {
      errors.push('Orchestration config file is required');
    }

    if (config.emails.length === 0) {
      errors.push('At least one email recipient is required');
    }

    if (config.emails.some(email => !email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/))) {
      errors.push('Invalid email format detected');
    }

    if (config.nDays < 1) {
      errors.push('Number of days must be at least 1');
    }

    if (config.topN < 1) {
      errors.push('Top N papers must be at least 1');
    }

    if (config.startDate && config.endDate) {
      if (config.startDate > config.endDate) {
        errors.push('Start date must be before end date');
      }
    }

    return errors;
  };

  const handleSubmit = async () => {
    const errors = validateFiles();
    if (errors.length > 0) {
      setError(errors.join('\n'));
      return;
    }

    try {
      console.log('Submitting with config paths:', {
        researchInterestsPath: config.researchInterestsPath,
        orchestrationConfigPath: config.orchestrationConfigPath
      });
      
      await runPaperPal(
        config,
        researchInterestsFile,
        orchestrationFile
      );
    } catch (err) {
      console.error('Submit error:', err);
      setError(err instanceof Error ? err.message : 'An error occurred');
    }
  };

  const handlePreview = (file: File, type: 'json' | 'text') => {
    setPreviewFile({ file, type });
  };

  return (
    <Box sx={{ 
      maxWidth: '1200px', 
      margin: '0 auto',
      backgroundColor: 'background.paper',
      minHeight: '100vh'
    }}>
      <Typography variant="h2" gutterBottom>
        Run PaperPal
      </Typography>

      {taskId ? (
        <GenerationProgress
          taskId={taskId}
          onCheckStatus={checkStatus}
        />
      ) : (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Grid container spacing={3}>
            {/* File Upload Section */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Configuration Files
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <TextField
                  fullWidth
                  label="Research Interests Path"
                  value={config.researchInterestsPath}
                  onChange={(e) => handleConfigChange('researchInterestsPath', e.target.value)}
                  error={!researchInterestsFile && !config.researchInterestsPath}
                  helperText={!researchInterestsFile && !config.researchInterestsPath ? 
                    'Required' : ''}
                />
                <input
                  type="file"
                  accept=".txt"
                  id="research-interests-upload"
                  hidden
                  onChange={handleResearchInterestsUpload}
                />
                <Tooltip title="Upload research interests file">
                  <IconButton
                    component="label"
                    htmlFor="research-interests-upload"
                  >
                    <UploadIcon />
                  </IconButton>
                </Tooltip>
                {researchInterestsFile && (
                  <Tooltip title="Preview file">
                    <IconButton
                      onClick={() => handlePreview(researchInterestsFile, 'text')}
                    >
                      <InfoIcon />
                    </IconButton>
                  </Tooltip>
                )}
              </Box>
            </Grid>

            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <TextField
                  fullWidth
                  label="Orchestration Config Path"
                  value={config.orchestrationConfigPath}
                  onChange={(e) => handleConfigChange('orchestrationConfigPath', e.target.value)}
                  error={!orchestrationFile && !config.orchestrationConfigPath}
                  helperText={!orchestrationFile && !config.orchestrationConfigPath ? 
                    'Required' : ''}
                />
                <input
                  type="file"
                  accept=".json"
                  id="orchestration-upload"
                  hidden
                  onChange={handleOrchestrationUpload}
                />
                <Tooltip title="Upload orchestration config file">
                  <IconButton
                    component="label"
                    htmlFor="orchestration-upload"
                  >
                    <UploadIcon />
                  </IconButton>
                </Tooltip>
                {orchestrationFile && (
                  <Tooltip title="Preview file">
                    <IconButton
                      onClick={() => handlePreview(orchestrationFile, 'json')}
                    >
                      <InfoIcon />
                    </IconButton>
                  </Tooltip>
                )}
              </Box>
            </Grid>

            {/* Basic Settings */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Basic Settings
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Number of Days"
                value={config.nDays}
                onChange={(e) => handleConfigChange('nDays', parseInt(e.target.value))}
                InputProps={{ inputProps: { min: 1 } }}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Top N Papers"
                value={config.topN}
                onChange={(e) => handleConfigChange('topN', parseInt(e.target.value))}
                InputProps={{ inputProps: { min: 1 } }}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <DatePicker
                selected={config.startDate}
                onChange={(date: Date | null) => handleDateChange('startDate', date)}
                customInput={
                  <TextField
                    fullWidth
                    label="Start Date"
                  />
                }
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <DatePicker
                selected={config.endDate}
                onChange={(date: Date | null) => handleDateChange('endDate', date)}
                customInput={
                  <TextField
                    fullWidth
                    label="End Date"
                  />
                }
              />
            </Grid>

            {/* Email Recipients */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Email Recipients
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                <TextField
                  fullWidth
                  label="Add Email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                />
                <Button
                  variant="contained"
                  onClick={handleAddEmail}
                  startIcon={<AddIcon />}
                >
                  Add
                </Button>
              </Box>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {config.emails.map((email) => (
                  <Chip
                    key={email}
                    label={email}
                    onDelete={() => handleRemoveEmail(email)}
                  />
                ))}
              </Box>
            </Grid>

            {/* Audio Settings */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Audio Settings
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>TTS Provider</InputLabel>
                <Select
                  value={config.ttsProvider}
                  label="TTS Provider"
                  onChange={(e) => handleConfigChange('ttsProvider', e.target.value)}
                >
                  {TTS_PROVIDERS.map((provider) => (
                    <MenuItem key={provider.value} value={provider.value}>
                      {provider.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Speaker 1 Voice</InputLabel>
                <Select
                  value={config.speaker1Voice}
                  label="Speaker 1 Voice"
                  onChange={(e) => handleConfigChange('speaker1Voice', e.target.value)}
                >
                  {(config.ttsProvider === 'openai' ? OPENAI_VOICES : KOKORO_VOICES).map((voice) => (
                    <MenuItem key={voice.value} value={voice.value}>
                      {voice.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Speaker 1 Speed"
                value={config.speaker1Speed}
                onChange={(e) => handleConfigChange('speaker1Speed', parseFloat(e.target.value))}
                inputProps={{ step: 0.1, min: 0.5, max: 2.0 }}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Speaker 2 Voice</InputLabel>
                <Select
                  value={config.speaker2Voice}
                  label="Speaker 2 Voice"
                  onChange={(e) => handleConfigChange('speaker2Voice', e.target.value)}
                >
                  {(config.ttsProvider === 'openai' ? OPENAI_VOICES : KOKORO_VOICES).map((voice) => (
                    <MenuItem key={voice.value} value={voice.value}>
                      {voice.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Speaker 2 Speed"
                value={config.speaker2Speed}
                onChange={(e) => handleConfigChange('speaker2Speed', parseFloat(e.target.value))}
                inputProps={{ step: 0.1, min: 0.5, max: 2.0 }}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <TextField
                  fullWidth
                  label="Intro Music Path"
                  value={config.introMusicPath}
                  onChange={(e) => handleConfigChange('introMusicPath', e.target.value)}
                />
                <input
                  type="file"
                  accept="audio/*"
                  id="intro-music-upload"
                  hidden
                  onChange={handleIntroMusicUpload}
                />
                <Tooltip title="Upload intro music">
                  <IconButton
                    component="label"
                    htmlFor="intro-music-upload"
                  >
                    <UploadIcon />
                  </IconButton>
                </Tooltip>
              </Box>
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Similarity Threshold"
                value={config.similarityThreshold}
                onChange={(e) => handleConfigChange('similarityThreshold', parseFloat(e.target.value))}
                inputProps={{ step: 0.1, min: 0, max: 1 }}
              />
            </Grid>

            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={config.publishToYoutube}
                    onChange={(e) => handleConfigChange('publishToYoutube', e.target.checked)}
                  />
                }
                label="Publish to YouTube"
              />
            </Grid>

            {/* Visualizer Settings */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Visualizer Settings
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Resolution</InputLabel>
                <Select
                  value={config.visualizerConfig.resolution.join('x')}
                  label="Resolution"
                  onChange={(e) => {
                    const [width, height] = e.target.value.split('x').map(Number);
                    handleVisualizerConfigChange('resolution', [width, height]);
                  }}
                >
                  {RESOLUTION_PRESETS.map((preset) => (
                    <MenuItem key={preset.label} value={preset.value.join('x')}>
                      {preset.label} ({preset.value.join('x')})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Font</InputLabel>
                <Select
                  value={config.visualizerConfig.font_path}
                  label="Font"
                  onChange={(e) => handleVisualizerConfigChange('font_path', e.target.value)}
                >
                  {fontOptions.map((font) => (
                    <MenuItem key={font.value} value={font.value}>
                      {font.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Character Size"
                value={config.visualizerConfig.matrix_char_size}
                onChange={(e) => handleVisualizerConfigChange('matrix_char_size', parseInt(e.target.value))}
                InputProps={{ inputProps: { min: 12, max: 48 } }}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Line Width"
                value={config.visualizerConfig.line_width}
                onChange={(e) => handleVisualizerConfigChange('line_width', parseInt(e.target.value))}
                InputProps={{ inputProps: { min: 1, max: 10 } }}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Matrix Head Color"
                type="color"
                value={config.visualizerConfig.matrix_head_color.startsWith('#') ? 
                  config.visualizerConfig.matrix_head_color : 
                  '#' + config.visualizerConfig.matrix_head_color.substring(2)}
                onChange={(e) => handleVisualizerConfigChange('matrix_head_color', e.target.value)}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Matrix Tail Color"
                type="color"
                value={config.visualizerConfig.matrix_tail_color.startsWith('#') ? 
                  config.visualizerConfig.matrix_tail_color : 
                  '#' + config.visualizerConfig.matrix_tail_color.substring(2)}
                onChange={(e) => handleVisualizerConfigChange('matrix_tail_color', e.target.value)}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Wave Color"
                type="color"
                value={config.visualizerConfig.wave_color}
                onChange={(e) => handleVisualizerConfigChange('wave_color', e.target.value)}
              />
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle1" gutterBottom>
                Trail Colors
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {config.visualizerConfig.trail_colors.map((color, index) => (
                  <TextField
                    key={index}
                    label={`Trail Color ${index + 1}`}
                    type="color"
                    value={color}
                    onChange={(e) => {
                      const newColors = [...config.visualizerConfig.trail_colors];
                      newColors[index] = e.target.value;
                      handleVisualizerConfigChange('trail_colors', newColors);
                    }}
                    sx={{ width: '150px' }}
                  />
                ))}
              </Box>
            </Grid>

            {/* Submit Button */}
            <Grid item xs={12}>
              <Button
                variant="contained"
                color="primary"
                size="large"
                onClick={handleSubmit}
                sx={{ mt: 2 }}
              >
                Run PaperPal
              </Button>
            </Grid>
          </Grid>
        </Paper>
      )}

      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <FilePreview
        file={previewFile?.file || null}
        type={previewFile?.type || 'text'}
        isOpen={!!previewFile}
        onClose={() => setPreviewFile(null)}
      />
    </Box>
  );
};

export default PaperPal; 