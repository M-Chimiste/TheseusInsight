import React, { useState, useCallback, useEffect, useMemo } from 'react';
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
  Slider,
  Chip,
  TextField,
  Snackbar,
} from '@mui/material';
import {
  Close as CloseIcon,
  Fullscreen as FullscreenIcon,
  FullscreenExit as FullscreenExitIcon,
  FilterList as FilterListIcon,
  Refresh as RefreshIcon,
  Save as SaveIcon,
} from '@mui/icons-material';

import MindMapCanvas from './MindMapCanvas';
import { useMindMap } from '../hooks/useMindMap';
import { mindMapApi } from '../services/api';
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
  const [showFilters, setShowFilters] = useState(false);
  
  // Filter states
  const [dateRange, setDateRange] = useState<[number, number]>([1990, new Date().getFullYear()]);
  const [connectionThreshold, setConnectionThreshold] = useState<number>(0);

  // Calculate filtered count for display
  const filteredNodeCount = useMemo(() => {
    if (!state.data?.nodes) return 0;
    
    return state.data.nodes.filter(node => {
      // Date filter
      if (dateRange[0] !== 1990 || dateRange[1] !== new Date().getFullYear()) {
        const nodeYear = node.date ? new Date(node.date).getFullYear() : null;
        if (nodeYear && (nodeYear < dateRange[0] || nodeYear > dateRange[1])) {
          return false;
        }
      }
      
      // Connection threshold filter - we need to calculate this temporarily
      if (connectionThreshold > 0) {
        const connectionCount = state.data?.edges?.filter(edge => 
          String(edge.source_id) === String(node.id) || String(edge.target_id) === String(node.id)
        ).length || 0;
        if (connectionCount < connectionThreshold) {
          return false;
        }
      }
      
      return true;
    }).length;
  }, [state.data, dateRange, connectionThreshold]);
  


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
    // Set defaults based on initial options
    setExpandK(initialOptions?.k ?? 10);
    setExpandThreshold(initialOptions?.similarity_threshold ?? 0.3);
    setExpandDialogOpen(true);
  }, [initialOptions]);

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

  // Handle regenerate
  const handleRegenerate = useCallback(() => {
    if (seedPaper) {
      console.log('🔄 Regenerating mindmap');
      openMindMap(seedPaper, initialOptions);
    }
  }, [seedPaper, openMindMap, initialOptions]);

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
          ...initialOptions,
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
  }, [state.data, state.seedPaper, saveTitle, saveDescription, initialOptions, reportId]);

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
    } else if (seedPaper && !state.isLoading) {
      console.log('🎯 Initial dialog open with options:', initialOptions);
      openMindMap(seedPaper, initialOptions);
    }
  }, [open, initialData, seedPaper, state.isOpen, state.isLoading, openMindMap, initialOptions, loadSavedMap]);

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
              onClick={() => setShowFilters(!showFilters)}
              color={showFilters ? 'primary' : 'default'}
            >
              <FilterListIcon />
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

      {/* Filter Panel */}
      {showFilters && (
        <>
          <Divider />
          <Box sx={{ p: 2, bgcolor: 'background.default' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="subtitle2">
                Filter Papers
              </Typography>
              {state.data && (
                <Typography variant="caption" color="text.secondary">
                  Showing {filteredNodeCount} of {state.data.nodes?.length || 0} papers
                </Typography>
              )}
            </Box>
            <Box sx={{ display: 'flex', gap: 3, alignItems: 'center', flexWrap: 'wrap' }}>
              <Box sx={{ minWidth: 250 }}>
                <Typography variant="body2" gutterBottom>
                  Publication Year: {dateRange[0]} - {dateRange[1]}
                </Typography>
                <Slider
                  value={dateRange}
                  onChange={(_, value) => setDateRange(value as [number, number])}
                  min={1990}
                  max={new Date().getFullYear()}
                  step={1}
                  size="small"
                  marks={[
                    { value: 1990, label: '1990' },
                    { value: 2010, label: '2010' },
                    { value: new Date().getFullYear(), label: new Date().getFullYear().toString() },
                  ]}
                  valueLabelDisplay="auto"
                />
              </Box>

              <Box sx={{ minWidth: 250 }}>
                <Typography variant="body2" gutterBottom>
                  Min Connections: {connectionThreshold}
                </Typography>
                <Slider
                  value={connectionThreshold}
                  onChange={(_, value) => setConnectionThreshold(value as number)}
                  min={0}
                  max={20}
                  step={1}
                  size="small"
                  marks={[
                    { value: 0, label: '0' },
                    { value: 5, label: '5' },
                    { value: 10, label: '10' },
                    { value: 20, label: '20+' },
                  ]}
                  valueLabelDisplay="auto"
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
            dateRange={dateRange}
            connectionThreshold={connectionThreshold}
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
          {(dateRange[0] !== 1990 || dateRange[1] !== new Date().getFullYear() || connectionThreshold > 0) && (
            <> • Filters active: {dateRange[0] !== 1990 || dateRange[1] !== new Date().getFullYear() ? `${dateRange[0]}-${dateRange[1]}` : ''}{connectionThreshold > 0 ? ` ${connectionThreshold}+ connections` : ''}</>
          )}
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