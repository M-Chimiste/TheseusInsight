import React, { useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  IconButton,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  Snackbar,
  Chip,
  Menu,
  MenuItem,
  CircularProgress,
  Grid,
} from '@mui/material';
import {
  PlayArrow as PlayArrowIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  MoreVert as MoreVertIcon,
  Map as MapIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { mindMapApi } from '../services/api';
import type { MindMapReport } from '../services/api';
import MindMapExplorer from '../components/MindMapExplorer';
import { useLayout } from '../contexts/LayoutContext';

const MindMapReports: React.FC = () => {
  const { headerHeight } = useLayout(); // Get dynamic header height
  const [selectedReport, setSelectedReport] = useState<MindMapReport | null>(null);
  const [mindMapOpen, setMindMapOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingReport, setEditingReport] = useState<MindMapReport | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [reportToDelete, setReportToDelete] = useState<MindMapReport | null>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [menuReport, setMenuReport] = useState<MindMapReport | null>(null);
  const [editDescription, setEditDescription] = useState('');
  
  // Snackbar states
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const queryClient = useQueryClient();

  // Fetch mind-map reports
  const { data: reportsData, isLoading, error } = useQuery({
    queryKey: ['mindMapReports'],
    queryFn: mindMapApi.getReports,
  });

  // Update title mutation
  const updateReportMutation = useMutation({
    mutationFn: ({ reportId, title }: { reportId: number; title: string }) =>
      mindMapApi.updateReportTitle(reportId, title),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['mindMapReports'] });
      setSuccessMessage(`Title updated to "${data.title}"`);
      setEditDialogOpen(false);
      setEditingReport(null);
      setEditTitle('');
      setEditDescription('');
    },
    onError: () => {
      setErrorMessage('Failed to update title');
    },
  });

  const updateDescriptionMutation = useMutation({
    mutationFn: ({ reportId, description }: { reportId: number; description: string }) =>
      mindMapApi.updateReportDescription(reportId, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mindMapReports'] });
      setSuccessMessage('Description updated');
      setEditDialogOpen(false);
      setEditingReport(null);
      setEditTitle('');
      setEditDescription('');
    },
    onError: () => {
      setErrorMessage('Failed to update description');
    },
  });

  // Delete report mutation
  const deleteReportMutation = useMutation({
    mutationFn: (reportId: number) => mindMapApi.deleteReport(reportId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mindMapReports'] });
      setSuccessMessage('Mind-map report deleted successfully');
      setDeleteDialogOpen(false);
      setReportToDelete(null);
    },
    onError: () => {
      setErrorMessage('Failed to delete mind-map report');
    },
  });

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, report: MindMapReport) => {
    setAnchorEl(event.currentTarget);
    setMenuReport(report);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setMenuReport(null);
  };

  const handleViewMindMap = async (report: MindMapReport) => {
    try {
      const full = await mindMapApi.getReport(report.id);
      setSelectedReport(full);
      setMindMapOpen(true);
    } catch (err) {
      console.error('Failed to fetch full report', err);
      setErrorMessage('Failed to load mind-map');
    } finally {
      handleMenuClose();
    }
  };

  const handleCloseMindMap = () => {
    setMindMapOpen(false);
    setSelectedReport(null);
  };

  const handleEditTitle = (report: MindMapReport) => {
    setEditingReport(report);
    setEditTitle(report.title);
    setEditDescription(report.description || '');
    setEditDialogOpen(true);
    handleMenuClose();
  };

  const handleSaveTitle = () => {
    if (!editingReport) return;

    const promises: Promise<any>[] = [];

    if (editTitle.trim() !== editingReport.title) {
      promises.push(updateReportMutation.mutateAsync({ reportId: editingReport.id, title: editTitle.trim() } as any));
    }

    if (editDescription.trim() !== (editingReport.description || '')) {
      promises.push(updateDescriptionMutation.mutateAsync({ reportId: editingReport.id, description: editDescription.trim() }));
    }

    if (promises.length === 0) {
      setEditDialogOpen(false);
      setEditingReport(null);
      return;
    }
  };

  const handleDeleteReport = (report: MindMapReport) => {
    setReportToDelete(report);
    setDeleteDialogOpen(true);
    handleMenuClose();
  };

  const confirmDelete = () => {
    if (reportToDelete) {
      deleteReportMutation.mutate(reportToDelete.id);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh', pt: `${headerHeight + 24}px` }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ pt: `${headerHeight + 24}px`, pb: 3, px: 3 }}>
        <Alert severity="error">Failed to load mind-map reports</Alert>
      </Box>
    );
  }

  const reports = reportsData?.reports || [];

  return (
    <Box sx={{ pt: `${headerHeight + 24}px`, pb: 3, px: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Box sx={{
          fontFamily: '"Geist Mono", monospace',
          fontSize: 10,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: 'primary.main',
          mb: 0.75,
        }}>
          Atlas
        </Box>
        <Typography
          component="div"
          sx={{
            fontFamily: '"Instrument Serif", Georgia, serif',
            fontSize: 32,
            letterSpacing: '-0.02em',
            lineHeight: 1.05,
            mb: 1,
          }}
        >
          Mind-map reports
        </Typography>
        <Typography variant="body2" color="text.secondary">
          View and manage your saved mind-map reports. Click on a report to explore the visualization.
        </Typography>
      </Box>

      {reports.length === 0 ? (
        <Card>
          <CardContent sx={{ textAlign: 'center', py: 6 }}>
            <MapIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No Mind-Map Reports Found
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Generate a mind-map and save it as a report to see it here.
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {reports.map((report) => (
            <Grid size={{ xs: 12, sm: 6, md: 4 }} key={report.id}>
              <Card 
                sx={{ 
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  '&:hover': {
                    boxShadow: 4,
                  },
                }}
              >
                <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                    <Typography 
                      variant="h6" 
                      sx={{ 
                        fontSize: '1rem',
                        fontWeight: 'medium',
                        lineHeight: 1.3,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        flex: 1,
                        mr: 1,
                      }}
                    >
                      {report.title}
                    </Typography>
                    <IconButton
                      size="small"
                      onClick={(e) => handleMenuOpen(e, report)}
                    >
                      <MoreVertIcon />
                    </IconButton>
                  </Box>

                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2, fontWeight: 'medium' }}>
                    Seed: {report.seed_paper_title}
                  </Typography>

                  {report.description && (
                    <Typography 
                      variant="body2" 
                      color="text.secondary" 
                      sx={{ 
                        mb: 2,
                        display: '-webkit-box',
                        WebkitLineClamp: 3,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      {report.description}
                    </Typography>
                  )}

                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                    <Chip 
                      label={`${report.statistics.nodes_count || report.statistics.nodes_created || 0} nodes`} 
                      size="small" 
                      variant="outlined" 
                    />
                    <Chip 
                      label={`${report.statistics.edges_count || report.statistics.edges_created || 0} edges`} 
                      size="small" 
                      variant="outlined" 
                    />
                    {report.parameters.expansion_order > 1 && (
                      <Chip 
                        label={`${report.parameters.expansion_order} orders`} 
                        size="small" 
                        variant="outlined"
                        color="primary"
                      />
                    )}
                  </Box>

                  <Box sx={{ mt: 'auto' }}>
                    <Typography variant="caption" color="text.secondary">
                      Created: {formatDate(report.created_at)}
                    </Typography>
                  </Box>
                </CardContent>

                <Box sx={{ p: 2, pt: 0 }}>
                  <Button
                    fullWidth
                    variant="contained"
                    startIcon={<PlayArrowIcon />}
                    onClick={() => handleViewMindMap(report)}
                  >
                    Open Mind-Map
                  </Button>
                </Box>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Context Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={() => menuReport && handleViewMindMap(menuReport)}>
          <PlayArrowIcon sx={{ mr: 1 }} />
          Open Mind-Map
        </MenuItem>
        <MenuItem onClick={() => menuReport && handleEditTitle(menuReport)}>
          <EditIcon sx={{ mr: 1 }} />
          Edit Details
        </MenuItem>
        <MenuItem 
          onClick={() => menuReport && handleDeleteReport(menuReport)}
          sx={{ color: 'error.main' }}
        >
          <DeleteIcon sx={{ mr: 1 }} />
          Delete
        </MenuItem>
      </Menu>

      {/* Mind-Map Explorer */}
      {selectedReport && (
        <MindMapExplorer
          open={mindMapOpen}
          onClose={handleCloseMindMap}
          seedPaper={{
            id: selectedReport.seed_paper_id,
            title: selectedReport.seed_paper_title,
            abstract: '',
            date: '',
            date_run: '',
            score: 0,
            rationale: '',
            related: false,
            cosine_similarity: 0,
            url: '',
            embedding_model: '',
          }}
          initialData={selectedReport.mindmap_data as any}
          reportId={selectedReport.id}
          initialOptions={{
            k: selectedReport.parameters.k || 15,
            similarity_threshold: selectedReport.parameters.similarity_threshold || 0.3,
            layout_algorithm: selectedReport.parameters.layout_algorithm || 'force',
            expansion_order: selectedReport.parameters.expansion_order || 1,
            max_nodes_per_order: selectedReport.parameters.max_nodes_per_order || 20,
          }}
        />
      )}

      {/* Edit Details Dialog */}
      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Report Details</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Title"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            margin="normal"
            disabled={updateReportMutation.isPending || updateDescriptionMutation.isPending}
          />
          <TextField
            fullWidth
            multiline
            rows={3}
            label="Description"
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
            margin="normal"
            disabled={updateReportMutation.isPending || updateDescriptionMutation.isPending}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)} disabled={updateReportMutation.isPending || updateDescriptionMutation.isPending}>
            Cancel
          </Button>
          <Button 
            onClick={handleSaveTitle} 
            variant="contained"
            disabled={(editTitle.trim() === editingReport?.title && editDescription.trim() === (editingReport?.description || '')) || updateReportMutation.isPending || updateDescriptionMutation.isPending}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete Mind-Map Report</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete the report "{reportToDelete?.title}"? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} disabled={deleteReportMutation.isPending}>
            Cancel
          </Button>
          <Button 
            onClick={confirmDelete} 
            color="error" 
            variant="contained"
            disabled={deleteReportMutation.isPending}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Success Snackbar */}
      <Snackbar
        open={Boolean(successMessage)}
        autoHideDuration={4000}
        onClose={() => setSuccessMessage('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setSuccessMessage('')} severity="success" sx={{ width: '100%' }}>
          {successMessage}
        </Alert>
      </Snackbar>

      {/* Error Snackbar */}
      <Snackbar
        open={Boolean(errorMessage)}
        autoHideDuration={4000}
        onClose={() => setErrorMessage('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setErrorMessage('')} severity="error" sx={{ width: '100%' }}>
          {errorMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default MindMapReports; 