import React from 'react';
import {
  Box,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Slider,
  Grid,
} from '@mui/material';
import { ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import { PodcastGenerationConfig, VisualizerConfig } from '../../types/api';

interface ConfigurationPanelProps {
  config: PodcastGenerationConfig;
  onChange: (config: PodcastGenerationConfig) => void;
}

const fontOptions = [
  { label: 'System Default', value: '' },
  { label: 'Hiragino Kaku Gothic W3', value: '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc' },
];

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

const ConfigurationPanel: React.FC<ConfigurationPanelProps> = ({
  config,
  onChange,
}) => {
  const handleChange = (field: keyof PodcastGenerationConfig, value: any) => {
    const newConfig = { ...config, [field]: value };
    
    // Reset voices when changing TTS provider
    if (field === 'tts_provider') {
      if (value === 'openai') {
        newConfig.speaker_1_voice = 'sage';
        newConfig.speaker_2_voice = 'ash';
      } else {
        newConfig.speaker_1_voice = 'af_heart';
        newConfig.speaker_2_voice = 'am_adam';
      }
    }
    
    onChange(newConfig);
  };

  const handleTextModelChange = (
    field: keyof typeof config.text_model,
    value: any
  ) => {
    onChange({
      ...config,
      text_model: {
        ...config.text_model,
        [field]: value,
      },
    });
  };

  const handleVisualizerConfigChange = <K extends keyof VisualizerConfig>(
    field: K,
    value: VisualizerConfig[K]
  ) => {
    onChange({
      ...config,
      visualizer_config: {
        ...config.visualizer_config,
        [field]: value
      }
    });
  };

  const currentVoices = config.tts_provider === 'openai' ? OPENAI_VOICES : KOKORO_VOICES;

  return (
    <Box>
      <Accordion defaultExpanded>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6">Text Model Settings</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              fullWidth
              label="Model Name"
              value={config.text_model.model_name}
              onChange={(e) =>
                handleTextModelChange('model_name', e.target.value)
              }
              helperText="Enter the name of the model to use"
            />

            <FormControl fullWidth>
              <InputLabel>Model Type</InputLabel>
              <Select
                value={config.text_model.model_type}
                label="Model Type"
                onChange={(e) =>
                  handleTextModelChange('model_type', e.target.value)
                }
              >
                <MenuItem value="anthropic">Anthropic</MenuItem>
                <MenuItem value="openai">OpenAI</MenuItem>
                <MenuItem value="ollama">Ollama</MenuItem>
                <MenuItem value="gemini">Gemini</MenuItem>
              </Select>
            </FormControl>

            <Box>
              <Typography gutterBottom>Temperature</Typography>
              <Slider
                value={config.text_model.temperature}
                min={0}
                max={1}
                step={0.1}
                onChange={(_, value) =>
                  handleTextModelChange('temperature', value)
                }
                valueLabelDisplay="auto"
              />
            </Box>

            <TextField
              fullWidth
              type="number"
              label="Max New Tokens"
              value={config.text_model.max_new_tokens}
              onChange={(e) =>
                handleTextModelChange(
                  'max_new_tokens',
                  parseInt(e.target.value)
                )
              }
            />

            <TextField
              fullWidth
              type="number"
              label="Context Length"
              value={config.text_model.num_ctx}
              onChange={(e) =>
                handleTextModelChange(
                  'num_ctx',
                  parseInt(e.target.value)
                )
              }
              helperText="Maximum context length (important for Ollama models)"
            />
          </Box>
        </AccordionDetails>
      </Accordion>

      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6">TTS Settings</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FormControl fullWidth>
              <InputLabel>TTS Provider</InputLabel>
              <Select
                value={config.tts_provider}
                label="TTS Provider"
                onChange={(e) => handleChange('tts_provider', e.target.value)}
              >
                {TTS_PROVIDERS.map((provider) => (
                  <MenuItem key={provider.value} value={provider.value}>
                    {provider.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth>
              <InputLabel>Speaker 1 Voice</InputLabel>
              <Select
                value={config.speaker_1_voice}
                label="Speaker 1 Voice"
                onChange={(e) => handleChange('speaker_1_voice', e.target.value)}
              >
                {currentVoices.map((voice) => (
                  <MenuItem key={voice.value} value={voice.value}>
                    {voice.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box>
              <Typography gutterBottom>Speaker 1 Speed</Typography>
              <Slider
                value={config.speaker_1_speed}
                min={0.5}
                max={2}
                step={0.05}
                onChange={(_, value) =>
                  handleChange('speaker_1_speed', value)
                }
                valueLabelDisplay="auto"
              />
            </Box>

            <FormControl fullWidth>
              <InputLabel>Speaker 2 Voice</InputLabel>
              <Select
                value={config.speaker_2_voice}
                label="Speaker 2 Voice"
                onChange={(e) => handleChange('speaker_2_voice', e.target.value)}
              >
                {currentVoices.map((voice) => (
                  <MenuItem key={voice.value} value={voice.value}>
                    {voice.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box>
              <Typography gutterBottom>Speaker 2 Speed</Typography>
              <Slider
                value={config.speaker_2_speed}
                min={0.5}
                max={2}
                step={0.05}
                onChange={(_, value) =>
                  handleChange('speaker_2_speed', value)
                }
                valueLabelDisplay="auto"
              />
            </Box>
          </Box>
        </AccordionDetails>
      </Accordion>

      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6">Output Settings</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FormControl fullWidth>
              <InputLabel>Output Format</InputLabel>
              <Select
                value={config.output_format}
                label="Output Format"
                onChange={(e) =>
                  handleChange('output_format', e.target.value)
                }
              >
                <MenuItem value="mp3">MP3</MenuItem>
                <MenuItem value="wav">WAV</MenuItem>
              </Select>
            </FormControl>

            <FormControlLabel
              control={
                <Switch
                  checked={config.visualizer}
                  onChange={(e) =>
                    handleChange('visualizer', e.target.checked)
                  }
                />
              }
              label="Generate Visualizer"
            />

            {config.visualizer && (
              <>
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <TextField
                    fullWidth
                    label="Width"
                    type="number"
                    value={config.visualizer_config.resolution[0]}
                    onChange={(e) => {
                      const newResolution: [number, number] = [
                        parseInt(e.target.value),
                        config.visualizer_config.resolution[1]
                      ];
                      handleVisualizerConfigChange('resolution', newResolution);
                    }}
                  />
                  <TextField
                    fullWidth
                    label="Height"
                    type="number"
                    value={config.visualizer_config.resolution[1]}
                    onChange={(e) => {
                      const newResolution: [number, number] = [
                        config.visualizer_config.resolution[0],
                        parseInt(e.target.value)
                      ];
                      handleVisualizerConfigChange('resolution', newResolution);
                    }}
                  />
                </Box>

                <TextField
                  fullWidth
                  type="number"
                  label="FPS"
                  value={config.visualizer_config.fps}
                  onChange={(e) => handleVisualizerConfigChange('fps', parseInt(e.target.value))}
                />

                <TextField
                  fullWidth
                  type="number"
                  label="Matrix Count"
                  value={config.visualizer_config.matrix_count}
                  onChange={(e) => handleVisualizerConfigChange('matrix_count', parseInt(e.target.value))}
                  inputProps={{ min: 50, max: 500 }}
                />

                <Typography gutterBottom>Fade Time (seconds)</Typography>
                <Slider
                  value={config.fade_time || 3.0}
                  onChange={(_, value) => handleChange('fade_time', value)}
                  min={1}
                  max={10}
                  step={0.5}
                  marks={[
                    { value: 1, label: '1s' },
                    { value: 5, label: '5s' },
                    { value: 10, label: '10s' },
                  ]}
                  valueLabelDisplay="auto"
                />

                <Typography gutterBottom>Head Saw Period (seconds)</Typography>
                <Slider
                  value={config.head_saw_period || 1.5}
                  onChange={(_, value) => handleChange('head_saw_period', value)}
                  min={0.1}
                  max={3.0}
                  step={0.1}
                  marks={[
                    { value: 0.5, label: '0.5s' },
                    { value: 1.5, label: '1.5s' },
                    { value: 3.0, label: '3.0s' },
                  ]}
                  valueLabelDisplay="auto"
                />

                <FormControl fullWidth>
                  <InputLabel>Font</InputLabel>
                  <Select
                    value={config.font_path || ''}
                    onChange={(e) => handleChange('font_path', e.target.value)}
                    label="Font"
                  >
                    {fontOptions.map((font) => (
                      <MenuItem key={font.label} value={font.value}>
                        {font.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </>
            )}
          </Box>
        </AccordionDetails>
      </Accordion>

      <Accordion 
        expanded={config.visualizer} 
        disabled={!config.visualizer}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography>Visualizer Settings</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Matrix Head Color"
                type="color"
                value={config.visualizer_config.matrix_head_color.startsWith('#') ? 
                  config.visualizer_config.matrix_head_color : 
                  '#' + config.visualizer_config.matrix_head_color.substring(2)}
                onChange={(e) => handleVisualizerConfigChange('matrix_head_color', e.target.value)}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Matrix Tail Color"
                type="color"
                value={config.visualizer_config.matrix_tail_color.startsWith('#') ? 
                  config.visualizer_config.matrix_tail_color : 
                  '#' + config.visualizer_config.matrix_tail_color.substring(2)}
                onChange={(e) => handleVisualizerConfigChange('matrix_tail_color', e.target.value)}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Wave Color"
                type="color"
                value={config.visualizer_config.wave_color}
                onChange={(e) => handleVisualizerConfigChange('wave_color', e.target.value)}
              />
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle1" gutterBottom>
                Trail Colors
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {config.visualizer_config.trail_colors.map((color: string, index: number) => (
                  <TextField
                    key={index}
                    label={`Trail Color ${index + 1}`}
                    type="color"
                    value={color}
                    onChange={(e) => {
                      const newColors = [...config.visualizer_config.trail_colors];
                      newColors[index] = e.target.value;
                      handleVisualizerConfigChange('trail_colors', newColors);
                    }}
                    sx={{ width: '150px' }}
                  />
                ))}
              </Box>
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Line Width"
                value={config.visualizer_config.line_width}
                onChange={(e) => handleVisualizerConfigChange('line_width', parseInt(e.target.value))}
                InputProps={{ inputProps: { min: 1, max: 10 } }}
              />
            </Grid>
          </Grid>
        </AccordionDetails>
      </Accordion>
    </Box>
  );
};

export default ConfigurationPanel; 