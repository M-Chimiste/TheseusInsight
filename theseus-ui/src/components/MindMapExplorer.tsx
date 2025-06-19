import React, { useState, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  LinearProgress,
  Alert,
  IconButton,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Chip,
} from '@mui/material';
import {
  Close as CloseIcon,
  Fullscreen as FullscreenIcon,
  FullscreenExit as FullscreenExitIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import type { SelectChangeEvent } from '@mui/material';
import MindMapCanvas from './MindMapCanvas';
import { useMindMap } from '../hooks/useMindMap';
import type { PaperApiResponse, MindMapExpandRequest } from '../services/api';

interface MindMapExplorerProps {
  open: boolean;
  onClose: () => void;
  seedPaper: PaperApiResponse | null;
  initialOptions?: Partial<MindMapExpandRequest>;
}

const MindMapExplorer: React.FC<MindMapExplorerProps> = ({
  open,
  onClose,
  seedPaper,
  initialOptions,
}) => {
  const { state, openMindMap, closeMindMap, expandNode, clearError } = useMindMap();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  
  // Mind-map generation settings
  const [settings, setSettings] = useState({
    k: initialOptions?.k || 15,
    similarity_threshold: initialOptions?.similarity_threshold || 0.3,
    layout_algorithm: initialOptions?.layout_algorithm || 'force',
  });

  // Handle dialog close
  const handleClose = () => {
    onClose();
    closeMindMap();
  };

  // Handle fullscreen toggle
  const toggleFullscreen = useCallback(() => {
    setIsFullscreen(!isFullscreen);
  }, [isFullscreen]);

  // Handle node expansion
  const handleNodeExpand = useCallback((nodeId: string) => {
    expandNode(nodeId, settings);
  }, [expandNode, settings]);

  // Handle settings change
  const handleSettingsChange = useCallback((newSettings: typeof settings) => {
    setSettings(newSettings);
    if (seedPaper) {
      openMindMap(seedPaper, newSettings);
    }
  }, [seedPaper, openMindMap]);

  // Handle regenerate
  const handleRegenerate = useCallback(() => {
    if (seedPaper) {
      openMindMap(seedPaper, settings);
    }
  }, [seedPaper, openMindMap, settings]);

  // Start mind-map generation when dialog opens
  React.useEffect(() => {
    if (open && seedPaper && !state.isOpen) {
      openMindMap(seedPaper, settings);
    }
  }, [open, seedPaper, state.isOpen, openMindMap, settings]);

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth={false}
      fullScreen={isFullscreen}
      sx={{
        '& .MuiDialog-paper': {
          width: isFullscreen ? '100vw' : '90vw',
          height: isFullscreen ? '100vh' : '80vh',
          maxWidth: 'none',
          maxHeight: 'none',
        },
      }}
    >
      {/* Dialog Header */}
      <DialogTitle sx={{ p: 2, pb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="h6" component="div">
              Mind-Map Explorer
            </Typography>
            {state.seedPaper && (
              <Chip
                label={`Seed: ${state.seedPaper.title.substring(0, 50)}...`}
                size="small"
                color="primary"
                variant="outlined"
              />
            )}
          </Box>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton
              size="small"
              onClick={() => setShowSettings(!showSettings)}
              color={showSettings ? 'primary' : 'default'}
            >
              <SettingsIcon />
            </IconButton>
            <IconButton size="small" onClick={handleRegenerate} disabled={state.isLoading}>
              <RefreshIcon />
            </IconButton>
            <IconButton size="small" onClick={toggleFullscreen}>
              {isFullscreen ? <FullscreenExitIcon /> : <FullscreenIcon />}
            </IconButton>
            <IconButton size="small" onClick={handleClose}>
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>

        {/* Progress Bar */}
        {state.isLoading && (
          <Box sx={{ mt: 1 }}>
            <LinearProgress variant="determinate" value={state.progress} />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {state.currentStep} ({state.progress.toFixed(0)}%)
            </Typography>
          </Box>
        )}

        {/* Error Display */}
        {state.error && (
          <Alert 
            severity="error" 
            sx={{ mt: 1 }}
            action={
              <Button color="inherit" size="small" onClick={clearError}>
                Dismiss
              </Button>
            }
          >
            {state.error}
          </Alert>
        )}
      </DialogTitle>

      {/* Settings Panel */}
      {showSettings && (
        <>
          <Divider />
          <Box sx={{ p: 2, bgcolor: 'background.default' }}>
            <Typography variant="subtitle2" gutterBottom>
              Generation Settings
            </Typography>
            <Box sx={{ display: 'flex', gap: 3, alignItems: 'center', flexWrap: 'wrap' }}>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel>Layout</InputLabel>
                <Select
                  value={settings.layout_algorithm}
                  label="Layout"
                  onChange={(e: SelectChangeEvent) => 
                    handleSettingsChange({ 
                      ...settings, 
                      layout_algorithm: e.target.value as any 
                    })
                  }
                >
                  <MenuItem value="force">Force-directed</MenuItem>
                </Select>
              </FormControl>

              <Box sx={{ minWidth: 200 }}>
                <Typography variant="body2" gutterBottom>
                  Papers: {settings.k}
                </Typography>
                <Slider
                  value={settings.k}
                  onChange={(_, value) => 
                    handleSettingsChange({ 
                      ...settings, 
                      k: value as number 
                    })
                  }
                  min={5}
                  max={30}
                  step={1}
                  size="small"
                  marks={[
                    { value: 5, label: '5' },
                    { value: 15, label: '15' },
                    { value: 30, label: '30' },
                  ]}
                />
              </Box>

              <Box sx={{ minWidth: 200 }}>
                <Typography variant="body2" gutterBottom>
                  Similarity Threshold: {(settings.similarity_threshold * 100).toFixed(0)}%
                </Typography>
                <Slider
                  value={settings.similarity_threshold}
                  onChange={(_, value) => 
                    handleSettingsChange({ 
                      ...settings, 
                      similarity_threshold: value as number 
                    })
                  }
                  min={0.1}
                  max={0.8}
                  step={0.05}
                  size="small"
                  marks={[
                    { value: 0.1, label: '10%' },
                    { value: 0.3, label: '30%' },
                    { value: 0.8, label: '80%' },
                  ]}
                />
              </Box>
            </Box>
          </Box>
        </>
      )}

      {/* Main Content */}
      <DialogContent sx={{ p: 0, flex: 1, overflow: 'hidden' }}>
        {state.error ? (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              p: 3,
              gap: 2,
            }}
          >
            <Alert severity="error" sx={{ width: '100%' }}>
              {state.error}
            </Alert>
            <Button variant="outlined" onClick={clearError}>
              Try Again
            </Button>
          </Box>
        ) : state.data ? (
          <MindMapCanvas
            data={state.data}
            onNodeExpand={handleNodeExpand}
            isLoading={state.isLoading}
          />
        ) : state.isLoading ? (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              gap: 2,
            }}
          >
            <Typography variant="h6" color="text.secondary">
              Generating Mind-Map...
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {state.currentStep}
            </Typography>
          </Box>
        ) : (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              gap: 2,
            }}
          >
            <Typography variant="h6" color="text.secondary">
              No mind-map data available
            </Typography>
            <Button variant="contained" onClick={handleRegenerate}>
              Generate Mind-Map
            </Button>
          </Box>
        )}
      </DialogContent>

      {/* Dialog Actions */}
      <DialogActions sx={{ p: 2, pt: 1 }}>
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
          Double-click nodes to expand • Right-click for options
        </Typography>
        <Button onClick={handleClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default MindMapExplorer; 