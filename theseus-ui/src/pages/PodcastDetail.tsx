import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { podcastHistoryApi } from '../services/api';
import type { PodcastDetailResponse, PodcastScriptItem } from '../services/api';
import {
  Container,
  Typography,
  CircularProgress,
  Alert,
  Card,
  CardContent,
  Box,
  Paper,
  Chip,
  TextField,
  IconButton,
  Snackbar,
  Button,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { format } from 'date-fns';

// Helper function to parse date strings correctly without timezone issues
const parseDate = (dateString: string): Date => {
  // Parse YYYY-MM-DD format manually to avoid timezone issues
  const [year, month, day] = dateString.split('-').map(Number);
  return new Date(year, month - 1, day); // month is 0-indexed in JavaScript
};

// Define speaker colors - easily extendable
const speakerColors: Record<string, { paper: string, chip: string, text: string }> = {
  'speaker-1': { paper: '#e3f2fd', chip: 'info', text: '#0d47a1' }, // Light Blue
  'speaker-2': { paper: '#e8f5e9', chip: 'success', text: '#1b5e20' }, // Light Green
  'speaker-3': { paper: '#fff3e0', chip: 'warning', text: '#e65100' }, // Light Orange
  'speaker-4': { paper: '#f3e5f5', chip: 'secondary', text: '#4a148c' }, // Light Purple
  'speaker-5': { paper: '#ffebee', chip: 'error', text: '#b71c1c' }, // Light Red
  default: { paper: '#f5f5f5', chip: 'default', text: '#424242' }, // Grey for others
};

const getSpeakerStyle = (speaker: string) => {
  return speakerColors[speaker] || speakerColors.default;
};

const PodcastDetail: React.FC = () => {
  const { podcastId } = useParams<{ podcastId: string }>();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  
  // State for editing title
  const [isEditingTitle, setIsEditingTitle] = React.useState(false);
  const [editedTitle, setEditedTitle] = React.useState('');
  const [snackbarMessage, setSnackbarMessage] = React.useState<string | null>(null);

  const { data: podcast, isLoading, error } = useQuery<PodcastDetailResponse, Error>({
    queryKey: ['podcastDetail', podcastId],
    queryFn: () => podcastHistoryApi.getPodcastDetail(podcastId!),
    enabled: !!podcastId, // Only run query if podcastId is available
  });

  // Update edited title when podcast data changes
  React.useEffect(() => {
    if (podcast) {
      setEditedTitle(podcast.title);
    }
  }, [podcast]);

  const updateTitleMutation = useMutation({
    mutationFn: (newTitle: string) => podcastHistoryApi.updatePodcastTitle(Number(podcastId), newTitle),
    onSuccess: () => {
      setSnackbarMessage('Podcast title updated successfully');
      setIsEditingTitle(false);
      // Invalidate queries to refresh the data
      queryClient.invalidateQueries({ queryKey: ['podcastDetail', podcastId] });
      queryClient.invalidateQueries({ queryKey: ['podcastHistoryList'] });
    },
    onError: () => {
      setSnackbarMessage('Error updating podcast title');
      setEditedTitle(podcast?.title || ''); // Reset to original title on error
    },
  });

  const handleStartEdit = () => {
    setIsEditingTitle(true);
  };

  const handleSaveTitle = () => {
    if (editedTitle.trim() && editedTitle !== podcast?.title) {
      updateTitleMutation.mutate(editedTitle.trim());
    } else {
      setIsEditingTitle(false);
    }
  };

  const handleCancelEdit = () => {
    setEditedTitle(podcast?.title || '');
    setIsEditingTitle(false);
  };

  const handleTitleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter') {
      handleSaveTitle();
    } else if (event.key === 'Escape') {
      handleCancelEdit();
    }
  };

  const handleBackToHistory = () => {
    navigate('/podcast-history');
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
        <Alert severity="error">Error fetching podcast details: {error.message}</Alert>
      </Container>
    );
  }

  if (!podcast) {
    return (
      <Container sx={{ mt: 4 }}>
        <Typography variant="h6" align="center">Podcast not found.</Typography>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Back Button */}
      <Box sx={{ mb: 2 }}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={handleBackToHistory}
          variant="outlined"
          sx={{ mb: 2 }}
        >
          Back to Podcast History
        </Button>
      </Box>

      <Card>
        <CardContent>
          {/* Editable Title Section */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
            {isEditingTitle ? (
              <>
                <TextField
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  onKeyDown={handleTitleKeyPress}
                  variant="outlined"
                  size="medium"
                  fullWidth
                  autoFocus
                  sx={{
                    '& .MuiOutlinedInput-root': {
                      fontSize: '2.125rem', // h4 font size
                      fontWeight: 400,
                    }
                  }}
                />
                <IconButton 
                  onClick={handleSaveTitle} 
                  color="primary"
                  disabled={updateTitleMutation.isPending}
                >
                  <SaveIcon />
                </IconButton>
                <IconButton 
                  onClick={handleCancelEdit} 
                  color="secondary"
                  disabled={updateTitleMutation.isPending}
                >
                  <CancelIcon />
                </IconButton>
              </>
            ) : (
              <>
                <Typography variant="h4" component="div" sx={{ flexGrow: 1 }}>
                  {podcast.title}
                </Typography>
                <IconButton onClick={handleStartEdit} color="primary">
                  <EditIcon />
                </IconButton>
              </>
            )}
          </Box>

          {/* Date - now displayed above description */}
          <Typography variant="subtitle1" color="text.secondary" gutterBottom sx={{ mb: 2 }}>
            Date: {format(parseDate(podcast.date), 'MMMM d, yyyy')}
          </Typography>

          {/* Description */}
          <Typography variant="body1" paragraph sx={{ mb: 3, whiteSpace: 'pre-line' }}>
            {podcast.description}
          </Typography>

          <Typography variant="h5" component="h2" gutterBottom sx={{ mt: 4, mb: 2, fontWeight: 500 }}>
            Podcast Transcript
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {podcast.script.map((item: PodcastScriptItem, index: number) => {
              const speakerStyle = getSpeakerStyle(item.speaker);
              return (
                <Paper 
                  key={index} 
                  elevation={2} 
                  sx={{
                    p: 2,
                    backgroundColor: speakerStyle.paper, 
                    borderLeft: `5px solid ${speakerStyle.text}` // Accent border
                  }}
                >
                  <Chip 
                    label={item.speaker.replace('-', ' ').toUpperCase()} // Format speaker label
                    size="small"
                    // @ts-ignore because chip color prop expects specific literal types, but we want dynamic assignment
                    color={speakerStyle.chip} 
                    sx={{ mb: 1, fontWeight: 'bold' }}
                  />
                  <Typography variant="body1" sx={{ color: speakerStyle.text, whiteSpace: 'pre-line'}}>
                    {item.text}
                  </Typography>
                  {item.segment_label && (
                    <Typography variant="caption" display="block" sx={{ mt: 1, color: 'text.secondary', fontStyle: 'italic' }}>
                      Segment: {item.segment_label}
                    </Typography>
                  )}
                </Paper>
              );
            })}
          </Box>
        </CardContent>
      </Card>

      <Snackbar
        open={snackbarMessage !== null}
        autoHideDuration={6000}
        onClose={() => setSnackbarMessage(null)}
        message={snackbarMessage}
      />
    </Container>
  );
};

export default PodcastDetail; 