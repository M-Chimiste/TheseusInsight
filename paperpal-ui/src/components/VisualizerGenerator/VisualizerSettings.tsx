import React, { useCallback, useEffect } from 'react';
import {
  Box,
  Grid,
  TextField,
  Typography,
  Slider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { VisualizerConfig } from '../../types/api';

interface VisualizerSettingsProps {
  config: VisualizerConfig;
  onChange: (config: VisualizerConfig) => void;
}

const resolutionPresets = [
  { label: '1080p', value: [1920, 1080] },
  { label: '720p', value: [1280, 720] },
  { label: '480p', value: [854, 480] },
];

const fontOptions = [
  { label: 'Hiragino Kaku Gothic W3', value: '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc', default: true },
  { label: 'System Default', value: '' },
];

const VisualizerSettings: React.FC<VisualizerSettingsProps> = ({
  config,
  onChange,
}) => {
  // Define handleChange with useCallback before using it
  const handleChange = useCallback((field: keyof VisualizerConfig, value: any) => {
    onChange({
      ...config,
      [field]: value,
    });
  }, [onChange, config]);

  // Now use handleChange in useEffect
  useEffect(() => {
    if (!config.font_path) {
      handleChange('font_path', fontOptions[0].value);
    }
  }, [config.font_path, handleChange]);

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Video Settings
      </Typography>
      <Grid container spacing={3}>
        <Grid item xs={12} sm={6}>
          <FormControl fullWidth>
            <InputLabel>Resolution</InputLabel>
            <Select
              value={config.resolution.join('x')}
              onChange={(e) => {
                const [width, height] = e.target.value.split('x').map(Number);
                handleChange('resolution', [width, height]);
              }}
              label="Resolution"
            >
              {resolutionPresets.map((preset) => (
                <MenuItem
                  key={preset.label}
                  value={preset.value.join('x')}
                >
                  {preset.label} ({preset.value.join('x')})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>
        <Grid item xs={12} sm={6}>
          <Typography gutterBottom>FPS</Typography>
          <Slider
            value={config.fps}
            onChange={(_, value) => handleChange('fps', value)}
            min={24}
            max={60}
            step={1}
            marks={[
              { value: 24, label: '24' },
              { value: 30, label: '30' },
              { value: 60, label: '60' },
            ]}
            valueLabelDisplay="auto"
          />
        </Grid>

        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            Matrix Effect
          </Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Matrix Count"
            type="number"
            value={config.matrix_count}
            onChange={(e) =>
              handleChange('matrix_count', parseInt(e.target.value))
            }
            inputProps={{ min: 50, max: 500 }}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Matrix Character Size"
            type="number"
            value={config.matrix_char_size}
            onChange={(e) =>
              handleChange('matrix_char_size', parseInt(e.target.value))
            }
            inputProps={{ min: 12, max: 48 }}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Matrix Head Color"
            type="color"
            value={config.matrix_head_color}
            onChange={(e) => handleChange('matrix_head_color', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Matrix Tail Color"
            type="color"
            value={config.matrix_tail_color}
            onChange={(e) => handleChange('matrix_tail_color', e.target.value)}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Typography gutterBottom>Fade Time (seconds)</Typography>
          <Slider
            value={config.fade_time}
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
        </Grid>

        <Grid item xs={12} sm={6}>
          <Typography gutterBottom>Head Saw Period (seconds)</Typography>
          <Slider
            value={config.head_saw_period}
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
        </Grid>

        <Grid item xs={12} sm={6}>
          <FormControl fullWidth>
            <InputLabel>Font</InputLabel>
            <Select
              value={config.font_path}
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
        </Grid>

        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            Wave Effect
          </Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Wave Color"
            type="color"
            value={config.wave_color}
            onChange={(e) => handleChange('wave_color', e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Line Width"
            type="number"
            value={config.line_width}
            onChange={(e) =>
              handleChange('line_width', parseInt(e.target.value))
            }
            inputProps={{ min: 1, max: 12 }}
          />
        </Grid>

        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            Trail Colors
          </Typography>
        </Grid>

        {config.trail_colors.map((color, index) => (
          <Grid item xs={12} sm={4} key={index}>
            <TextField
              fullWidth
              label={`Trail Color ${index + 1}`}
              type="color"
              value={color}
              onChange={(e) => {
                const newColors = [...config.trail_colors];
                newColors[index] = e.target.value;
                handleChange('trail_colors', newColors);
              }}
            />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default VisualizerSettings; 