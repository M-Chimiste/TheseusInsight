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
  ToggleButton,
  ToggleButtonGroup,
  Chip,
} from '@mui/material';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ViewListIcon from '@mui/icons-material/ViewList';
import HistoryIcon from '@mui/icons-material/History';
import { format } from 'date-fns';

type ViewMode = 'grid' | 'list';

const PodcastHistory: React.FC = () => {
  const [viewMode, setViewMode] = React.useState<ViewMode>('grid');

  const { data: podcasts, isLoading, error } = useQuery<PodcastListItemResponse[], Error>({
    queryKey: ['podcastHistoryList'],
    queryFn: podcastHistoryApi.getPodcastHistoryList,
  });

  const handleViewModeChange = (
    _event: React.MouseEvent<HTMLElement>,
    newViewMode: ViewMode | null,
  ) => {
    if (newViewMode !== null) {
      setViewMode(newViewMode);
    }
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

      {viewMode === 'grid' ? (
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
                        Date: {format(new Date(podcast.date), 'MMMM d, yyyy')}
                      </Typography>
                      <Typography variant="body2">
                        {podcast.description_snippet}
                      </Typography>
                    </Box>
                    <Chip
                      icon={<HistoryIcon />}
                      label="View Details"
                      size="small"
                      variant="outlined"
                      sx={{ ml: 2 }}
                    />
                  </Box>
                </CardContent>
              </CardActionArea>
            </Card>
          ))}
        </Box>
      )}
    </Container>
  );
};

export default PodcastHistory; 