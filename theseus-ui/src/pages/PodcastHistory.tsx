import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { podcastHistoryApi } from '../services/api';
import type { PodcastListItemResponse } from '../services/api';
import { Link as RouterLink } from 'react-router-dom';
import {
  Container,
  Typography,
  CircularProgress,
  Alert,
  Card,
  CardContent,
  CardActionArea,
  Grid,
  Box,
  ToggleButton,
  ToggleButtonGroup,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  Snackbar,
} from '@mui/material';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ViewListIcon from '@mui/icons-material/ViewList';
import DeleteIcon from '@mui/icons-material/Delete';
import HistoryIcon from '@mui/icons-material/History';
import RefreshIcon from '@mui/icons-material/Refresh';
import { format } from 'date-fns';

type ViewMode = 'grid' | 'list';

// Helper function to parse date strings correctly without timezone issues
const parseDate = (dateString: string): Date => {
  // Parse YYYY-MM-DD format manually to avoid timezone issues
  const [year, month, day] = dateString.split('-').map(Number);
  return new Date(year, month - 1, day); // month is 0-indexed in JavaScript
};

const PodcastHistory: React.FC = () => {
  const [viewMode, setViewMode] = React.useState<ViewMode>('grid');
  const [openDeleteDialog, setOpenDeleteDialog] = React.useState(false);
  const [selectedPodcastId, setSelectedPodcastId] = React.useState<number | null>(null);
  const [snackbarMessage, setSnackbarMessage] = React.useState<string | null>(null);

  const queryClient = useQueryClient();

  const { data: podcasts, isLoading, error, refetch } = useQuery<PodcastListItemResponse[], Error>({
    queryKey: ['podcastHistoryList'],
    queryFn: podcastHistoryApi.getPodcastHistoryList,
  });

  const deleteMutation = useMutation({
    mutationFn: (podcastId: number) => podcastHistoryApi.deletePodcast(podcastId),
    onSuccess: () => {
      setSnackbarMessage('Podcast deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['podcastHistoryList'] });
    },
    onError: () => {
      setSnackbarMessage('Error deleting podcast');
    },
  });

  const handleViewModeChange = (
    _event: React.MouseEvent<HTMLElement>,
    newViewMode: ViewMode | null,
  ) => {
    if (newViewMode !== null) {
      setViewMode(newViewMode);
    }
  };

  const handleDeleteClick = (podcastId: number, event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setSelectedPodcastId(podcastId);
    setOpenDeleteDialog(true);
  };

  const handleDeleteConfirm = () => {
    if (selectedPodcastId) {
      deleteMutation.mutate(selectedPodcastId);
    }
    setOpenDeleteDialog(false);
    setSelectedPodcastId(null);
  };

  const handleRefresh = () => {
    refetch();
    setSnackbarMessage('Podcast history refreshed');
  };

  if (isLoading) {
    return (
      <Container sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Container>
    );
  }

  if (error) {
    return (
      <Container sx={{ mt: 4 }}>
        <Alert severity="error">Error fetching podcast history: {error.message}</Alert>
      </Container>
    );
  }

  if (!podcasts || podcasts.length === 0) {
    return (
      <Container sx={{ mt: 4 }}>
        <Typography variant="h6" align="center">No podcast history found.</Typography>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="div">
          Podcast History
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <IconButton
            onClick={handleRefresh}
            color="primary"
            size="small"
            title="Refresh podcast history"
          >
            <RefreshIcon />
          </IconButton>
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={handleViewModeChange}
            aria-label="view mode"
            size="small"
          >
            <ToggleButton value="grid" aria-label="grid view">
              <ViewModuleIcon />
            </ToggleButton>
            <ToggleButton value="list" aria-label="list view">
              <ViewListIcon />
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>

      {viewMode === 'grid' ? (
        <Grid container spacing={3}>
          {podcasts.map((podcast) => (
            <Grid size={{ xs: 12, sm: 6, md: 4 }} key={podcast.id}>
              <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
                <IconButton
                  sx={{
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    zIndex: 1,
                    backgroundColor: 'rgba(255, 255, 255, 0.8)',
                    '&:hover': {
                      backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    },
                  }}
                  onClick={(e) => handleDeleteClick(podcast.id, e)}
                  color="error"
                  size="small"
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
                <CardActionArea component={RouterLink} to={`/podcast-history/${podcast.id}`} sx={{ flexGrow: 1 }}>
                  <CardContent sx={{ flexGrow: 1 }}>
                    <Typography variant="h6" component="div" gutterBottom>
                      {podcast.title}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Date: {format(parseDate(podcast.date), 'MMMM d, yyyy')}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ 
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      display: '-webkit-box',
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical',
                    }}>
                      {podcast.description_snippet}
                    </Typography>
                  </CardContent>
                </CardActionArea>
              </Card>
            </Grid>
          ))}
        </Grid>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {podcasts.map((podcast) => (
            <Card key={podcast.id} variant="outlined">
              <CardActionArea component={RouterLink} to={`/podcast-history/${podcast.id}`}>
                <CardContent sx={{ py: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="h6" sx={{ mb: 0.5 }}>
                        {podcast.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        Date: {format(parseDate(podcast.date), 'MMMM d, yyyy')}
                      </Typography>
                      <Typography variant="body2">
                        {podcast.description_snippet}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 2 }}>
                      <IconButton
                        onClick={(e) => handleDeleteClick(podcast.id, e)}
                        color="error"
                        size="small"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                      <Chip
                        icon={<HistoryIcon />}
                        label="View Details"
                        size="small"
                        variant="outlined"
                      />
                    </Box>
                  </Box>
                </CardContent>
              </CardActionArea>
            </Card>
          ))}
        </Box>
      )}

      <Dialog
        open={openDeleteDialog}
        onClose={() => setOpenDeleteDialog(false)}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle id="alert-dialog-title">{"Confirm Delete"}</DialogTitle>
        <DialogContent>
          <DialogContentText id="alert-dialog-description">
            Are you sure you want to delete this podcast history?
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDeleteDialog(false)} color="primary">
            Cancel
          </Button>
          <Button onClick={handleDeleteConfirm} color="primary" autoFocus>
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbarMessage !== null}
        autoHideDuration={6000}
        onClose={() => setSnackbarMessage(null)}
        message={snackbarMessage}
      />
    </Container>
  );
};

export default PodcastHistory; 