import React, { useState, useCallback, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  CircularProgress,
  Alert,
  IconButton,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Chip,
  TextField,
  Snackbar,
} from '@mui/material';
import {
  Close as CloseIcon,
  Fullscreen as FullscreenIcon,
  FullscreenExit as FullscreenExitIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
  Save as SaveIcon,
} from '@mui/icons-material';
import type { SelectChangeEvent } from '@mui/material';
import MindMapCanvas from './MindMapCanvas';
import { useMindMap } from '../hooks/useMindMap';
import { mindMapApi, settingsApi } from '../services/api';
import type { PaperApiResponse, MindMapExpandRequest, MindMapReportSaveRequest } from '../services/api';
import type { MindMapData } from '../services/api';

interface MindMapExplorerProps {
  open: boolean;
  onClose: () => void;
  seedPaper: PaperApiResponse | null;
  initialOptions?: Partial<MindMapExpandRequest>;
  initialData?: MindMapData; // pre-saved mind map to display directly
  reportId?: number; // if editing an existing saved report
}

const MindMapExplorer: React.FC<MindMapExplorerProps> = ({
  open,
  onClose,
  seedPaper,
  initialOptions,
  initialData,
  reportId,
}) => {
  const { state, openMindMap, closeMindMap, expandNode, clearError, loadSavedMap } = useMindMap();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  
  // Local generation settings.  We start undefined so that we can pull the
  // true defaults from the global orchestration configuration on first open.
  const [settings, setSettings] = useState<Partial<MindMapExpandRequest>>({
    k: initialOptions?.k,
    similarity_threshold: initialOptions?.similarity_threshold,
    layout_algorithm: initialOptions?.layout_algorithm,
    expansion_order: initialOptions?.expansion_order,
    max_nodes_per_order: initialOptions?.max_nodes_per_order,
  });

  // Flag so we only fetch defaults once per dialog open
  const [defaultsLoaded, setDefaultsLoaded] = useState(false);

  // Pull default Mind-Map parameters from the orchestration settings the first
  // time the dialog opens.
  useEffect(() => {
    if (!open || defaultsLoaded) return;

    (async () => {
      try {
        const resp = await settingsApi.getOrchestrationConfig();
        const cfg = resp.data?.mind_map_config ?? {};
        setSettings(prev => ({
          k: prev.k ?? cfg.k ?? 15,
          similarity_threshold: prev.similarity_threshold ?? cfg.similarity_threshold ?? 0.3,
          layout_algorithm: prev.layout_algorithm ?? (cfg.layout_algorithm as any) ?? 'force',
          expansion_order: prev.expansion_order ?? cfg.expansion_order ?? 1,
          max_nodes_per_order: prev.max_nodes_per_order ?? cfg.max_nodes_per_order ?? 20,
        }));
      } catch (e) {
        /* fallback to hard-coded defaults if request fails */
        setSettings(prev => ({
          k: prev.k ?? 15,
          similarity_threshold: prev.similarity_threshold ?? 0.3,
          layout_algorithm: prev.layout_algorithm ?? 'force',
          expansion_order: prev.expansion_order ?? 1,
          max_nodes_per_order: prev.max_nodes_per_order ?? 20,
        }));
      } finally {
        setDefaultsLoaded(true);
      }
    })();
  }, [open, defaultsLoaded]);

  // Save dialog state
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveTitle, setSaveTitle] = useState('');
  const [saveDescription, setSaveDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState('');

  // Expansion dialog state
  const [expandDialogOpen, setExpandDialogOpen] = useState(false);
  const [expandTargetNodeId, setExpandTargetNodeId] = useState<string | null>(null);
  const [expandK, setExpandK] = useState<number>(10);
  const [expandThreshold, setExpandThreshold] = useState<number>(0.3);

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
    setExpandTargetNodeId(nodeId);
    // Set defaults based on current settings
    setExpandK(settings.k ?? 10);
    setExpandThreshold(settings.similarity_threshold ?? 0.3);
    setExpandDialogOpen(true);
  }, [settings]);

  const handleConfirmExpand = useCallback(() => {
    if (expandTargetNodeId) {
      expandNode(
        expandTargetNodeId,
        {
          k: expandK,
          similarity_threshold: expandThreshold,
        },
        true // merge mode
      );
    }
    setExpandDialogOpen(false);
  }, [expandTargetNodeId, expandK, expandThreshold, expandNode]);

  const handleCancelExpand = useCallback(() => {
    setExpandDialogOpen(false);
  }, []);

  // Handle settings change
  const handleSettingsChange = useCallback((newSettings: typeof settings) => {
    console.log('🔧 Settings changed:', { old: settings, new: newSettings });
    setSettings(newSettings);
    if (seedPaper) {
      console.log('🚀 Calling openMindMap with NEW settings:', newSettings);
      openMindMap(seedPaper, newSettings);
    }
  }, [seedPaper, openMindMap]);

  // Handle regenerate
  const handleRegenerate = useCallback(() => {
    if (seedPaper) {
      console.log('🔄 Regenerating with current settings:', settings);
      openMindMap(seedPaper, settings);
    }
  }, [seedPaper, openMindMap, settings]);

  // Handle save dialog
  const handleOpenSaveDialog = useCallback(() => {
    if (state.seedPaper) {
      setSaveTitle(`Mind-Map: ${state.seedPaper.title.substring(0, 100)}${state.seedPaper.title.length > 100 ? '...' : ''}`);
      setSaveDescription('');
      setSaveDialogOpen(true);
    }
  }, [state.seedPaper]);

  const handleSave = useCallback(async () => {
    if (!state.data || !state.seedPaper || !saveTitle.trim()) return;

    setSaving(true);
    try {
      const nodeCount = state.data.nodes?.length || 0;
      const edgeCount = state.data.edges?.length || 0;

      const baseRequest = {
        title: saveTitle.trim(),
        description: saveDescription.trim() || undefined,
        mindmap_data: state.data,
        parameters: {
          ...settings,
          seed_paper_id: state.seedPaper.id,
          seed_paper_title: state.seedPaper.title,
        },
      } as MindMapReportSaveRequest & { statistics?: any };

      if (reportId) {
        baseRequest.statistics = {
          nodes_count: nodeCount,
          edges_count: edgeCount,
          updated_at: new Date().toISOString(),
        };
      }

      if (reportId) {
        // Update existing report
        await mindMapApi.updateReport(reportId, baseRequest);
        setSaveSuccess('Mind-map updated');
      } else {
        // Save new report
        const response = await mindMapApi.saveReport(baseRequest);
        setSaveSuccess(`Mind-map saved as "${response.title}"`);
      }

      setSaveDialogOpen(false);
      setSaveTitle('');
      setSaveDescription('');
    } catch (error) {
      console.error('Error saving mind-map:', error);
      // Handle error (you could add an error state if needed)
    } finally {
      setSaving(false);
    }
  }, [state.data, state.seedPaper, saveTitle, saveDescription, settings, reportId]);

  const handleCloseSaveDialog = useCallback(() => {
    setSaveDialogOpen(false);
    setSaveTitle('');
    setSaveDescription('');
  }, []);

  // Handle first open depending on whether we have pre-saved data
  useEffect(() => {
    if (!open || state.isOpen) return;

    if (initialData) {
      loadSavedMap(initialData, seedPaper ?? null);
    } else if (seedPaper && defaultsLoaded && !state.isLoading) {
      console.log('🎯 Initial dialog open with settings (defaults):', settings);
      openMindMap(seedPaper, settings);
    }
  }, [open, initialData, seedPaper, defaultsLoaded, state.isOpen, state.isLoading, openMindMap, settings, loadSavedMap]);

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
              onClick={handleOpenSaveDialog}
              disabled={!state.data || state.isLoading}
              color="primary"
            >
              <SaveIcon />
            </IconButton>
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

        {/* Simple spinner while loading */}
        {state.isLoading && (
          <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
            <CircularProgress size={16} />
            <Typography variant="body2" color="text.secondary">
              {state.currentStep || 'Working...'}
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
                  Papers: {settings.k ?? 15}
                </Typography>
                <Slider
                  value={settings.k ?? 15}
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
                  Similarity Threshold: {((settings.similarity_threshold ?? 0.3) * 100).toFixed(0)}%
                </Typography>
                <Slider
                  value={settings.similarity_threshold ?? 0.3}
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

              <Box sx={{ minWidth: 200 }}>
                <Typography variant="body2" gutterBottom>
                  Expansion Order: {settings.expansion_order ?? 1}
                </Typography>
                <Slider
                  value={settings.expansion_order ?? 1}
                  onChange={(_, value) => 
                    handleSettingsChange({ 
                      ...settings, 
                      expansion_order: value as number 
                    })
                  }
                  min={1}
                  max={5}
                  step={1}
                  size="small"
                  marks={[
                    { value: 1, label: '1' },
                    { value: 3, label: '3' },
                    { value: 5, label: '5' },
                  ]}
                />
              </Box>

              <Box sx={{ minWidth: 200 }}>
                <Typography variant="body2" gutterBottom>
                  Max Nodes per Order: {settings.max_nodes_per_order ?? 20}
                </Typography>
                <Slider
                  value={settings.max_nodes_per_order ?? 20}
                  onChange={(_, value) => 
                    handleSettingsChange({ 
                      ...settings, 
                      max_nodes_per_order: value as number 
                    })
                  }
                  min={5}
                  max={50}
                  step={5}
                  size="small"
                  marks={[
                    { value: 5, label: '5' },
                    { value: 20, label: '20' },
                    { value: 50, label: '50' },
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

      {/* Save Dialog */}
      <Dialog open={saveDialogOpen} onClose={handleCloseSaveDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Save Mind-Map Report</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              fullWidth
              label="Title"
              value={saveTitle}
              onChange={(e) => setSaveTitle(e.target.value)}
              required
              error={!saveTitle.trim()}
              helperText={!saveTitle.trim() ? "Title is required" : ""}
              disabled={saving}
            />
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Description (Optional)"
              value={saveDescription}
              onChange={(e) => setSaveDescription(e.target.value)}
              disabled={saving}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseSaveDialog} disabled={saving}>
            Cancel
          </Button>
          <Button 
            onClick={handleSave} 
            variant="contained" 
            disabled={!saveTitle.trim() || saving}
            startIcon={saving ? <CircularProgress size={16} /> : <SaveIcon />}
          >
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Success Snackbar */}
      <Snackbar
        open={Boolean(saveSuccess)}
        autoHideDuration={4000}
        onClose={() => setSaveSuccess('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setSaveSuccess('')} severity="success" sx={{ width: '100%' }}>
          {saveSuccess}
        </Alert>
      </Snackbar>

      {/* Expansion Dialog */}
      <Dialog
        open={expandDialogOpen}
        onClose={handleCancelExpand}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Expand Node</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              fullWidth
              label="K"
              type="number"
              value={expandK}
              onChange={(e) => setExpandK(Number(e.target.value))}
              required
              error={!expandK.toString().trim()}
              helperText={!expandK.toString().trim() ? "K is required" : ""}
            />
            <TextField
              fullWidth
              label="Similarity Threshold"
              type="number"
              value={expandThreshold}
              onChange={(e) => setExpandThreshold(Number(e.target.value))}
              required
              error={!expandThreshold.toString().trim()}
              helperText={!expandThreshold.toString().trim() ? "Similarity Threshold is required" : ""}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelExpand}>Cancel</Button>
          <Button onClick={handleConfirmExpand}>Expand</Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  );
};

export default MindMapExplorer; 