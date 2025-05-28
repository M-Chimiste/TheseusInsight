import React from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
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
} from '@mui/material';
import { format } from 'date-fns';

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

  const { data: podcast, isLoading, error } = useQuery<PodcastDetailResponse, Error>({
    queryKey: ['podcastDetail', podcastId],
    queryFn: () => podcastHistoryApi.getPodcastDetail(podcastId!),
    enabled: !!podcastId, // Only run query if podcastId is available
  });

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
      <Card>
        <CardContent>
          <Typography variant="h4" gutterBottom component="div" sx={{ mb: 3 }}>
            {podcast.title}
          </Typography>
          <Typography variant="subtitle1" color="text.secondary" gutterBottom>
            Date: {format(new Date(podcast.date), 'MMMM d, yyyy')}
          </Typography>
          <Typography variant="body1" paragraph sx={{ mt: 2, mb: 3, whiteSpace: 'pre-line' }}>
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
    </Container>
  );
};

export default PodcastDetail; 