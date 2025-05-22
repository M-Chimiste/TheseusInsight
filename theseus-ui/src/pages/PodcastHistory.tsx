import React from 'react';
import { useQuery } from '@tanstack/react-query';
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
} from '@mui/material';
import { format } from 'date-fns';

const PodcastHistory: React.FC = () => {
  const { data: podcasts, isLoading, error } = useQuery<PodcastListItemResponse[], Error>({
    queryKey: ['podcastHistoryList'],
    queryFn: podcastHistoryApi.getPodcastHistoryList,
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
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        Podcast History
      </Typography>
      <Grid container spacing={3}>
        {podcasts.map((podcast) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={podcast.id}>
            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <CardActionArea component={RouterLink} to={`/podcast-history/${podcast.id}`} sx={{ flexGrow: 1 }}>
                <CardContent sx={{ flexGrow: 1 }}>
                  <Typography variant="h6" component="div" gutterBottom>
                    {podcast.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Date: {format(new Date(podcast.date), 'MMMM d, yyyy')}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {podcast.description_snippet}
                  </Typography>
                </CardContent>
              </CardActionArea>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Container>
  );
};

export default PodcastHistory; 