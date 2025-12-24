import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  Chip,
  Stack,
  Button,
  Paper,
  Autocomplete,
  TextField,
} from '@mui/material';
import {
  ShowChart as ShowChartIcon,
  ZoomIn as ZoomInIcon,
  ZoomOut as ZoomOutIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import {
  trendsApi,
  type TimelineDataResponse,
  type TopicApiResponse,
} from '../services/api';
import { useTheme } from '../contexts/ThemeContext';
import { useLayout } from '../contexts/LayoutContext';
import TimelineCanvas from '../components/timeline/TimelineCanvas';
import TimelineLegend from '../components/timeline/TimelineLegend';

type ZoomLevel = 'year' | 'quarter' | 'month' | 'week';

const ResearchTimeline: React.FC = () => {
  const navigate = useNavigate();
  const { isDarkMode } = useTheme();
  const { headerHeight } = useLayout();

  // State
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timelineData, setTimelineData] = useState<TimelineDataResponse | null>(null);
  const [availableTopics, setAvailableTopics] = useState<TopicApiResponse[]>([]);
  const [selectedTopicIds, setSelectedTopicIds] = useState<number[]>([]);
  const [zoomLevel, setZoomLevel] = useState<ZoomLevel>('month');
  const [topicsLimit, setTopicsLimit] = useState(5);

  // Fetch available topics for selection
  useEffect(() => {
    const fetchTopics = async () => {
      try {
        const response = await trendsApi.getTrendingTopics({
          limit: 50,
          period_type: 'month',
          min_doc_count: 1,
        });
        setAvailableTopics(response.data.topics || []);
      } catch (err) {
        console.error('Failed to fetch topics:', err);
      }
    };
    fetchTopics();
  }, []);

  // Fetch timeline data
  const fetchTimelineData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await trendsApi.getTimelineData({
        topic_ids: selectedTopicIds.length > 0 ? selectedTopicIds.join(',') : undefined,
        period_type: zoomLevel === 'year' ? 'quarter' : zoomLevel,
        include_key_papers: true,
        key_papers_limit: 3,
        limit: topicsLimit,
      });

      setTimelineData(response.data);
    } catch (err) {
      console.error('Failed to fetch timeline data:', err);
      setError('Failed to load timeline data. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [selectedTopicIds, zoomLevel, topicsLimit]);

  useEffect(() => {
    fetchTimelineData();
  }, [fetchTimelineData]);

  // Handle zoom level change
  const handleZoomChange = (newZoom: ZoomLevel) => {
    setZoomLevel(newZoom);
  };

  // Handle topic selection
  const handleTopicSelect = (_event: React.SyntheticEvent, values: TopicApiResponse[]) => {
    setSelectedTopicIds(values.map(t => t.id));
  };

  // Navigate to papers page with filters
  const handleViewPapers = (topicId: number, startDate: string, endDate: string) => {
    navigate(`/papers?topic_id=${topicId}&from_date=${startDate}&to_date=${endDate}`);
  };

  return (
    <Box
      sx={{
        p: 3,
        minHeight: `calc(100vh - ${headerHeight}px)`,
        bgcolor: 'background.default',
      }}
    >
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <ShowChartIcon sx={{ fontSize: 32, color: 'primary.main' }} />
          <Typography variant="h4" fontWeight="bold">
            Research Timeline
          </Typography>
        </Box>

        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={fetchTimelineData}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {/* Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems="center">
            {/* Topic Selection */}
            <Autocomplete
              multiple
              options={availableTopics}
              getOptionLabel={(option) => option.label}
              value={availableTopics.filter(t => selectedTopicIds.includes(t.id))}
              onChange={handleTopicSelect}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Select Topics"
                  placeholder="Choose topics to visualize..."
                  size="small"
                />
              )}
              renderTags={(value, getTagProps) =>
                value.map((option, index) => (
                  <Chip
                    {...getTagProps({ index })}
                    key={option.id}
                    label={option.label}
                    size="small"
                    color="primary"
                    variant="outlined"
                  />
                ))
              }
              sx={{ minWidth: 300, flexGrow: 1 }}
              limitTags={3}
            />

            {/* Zoom Level */}
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Zoom Level</InputLabel>
              <Select
                value={zoomLevel}
                label="Zoom Level"
                onChange={(e) => handleZoomChange(e.target.value as ZoomLevel)}
              >
                <MenuItem value="year">Years</MenuItem>
                <MenuItem value="quarter">Quarters</MenuItem>
                <MenuItem value="month">Months</MenuItem>
                <MenuItem value="week">Weeks</MenuItem>
              </Select>
            </FormControl>

            {/* Topics Limit (when no selection) */}
            {selectedTopicIds.length === 0 && (
              <FormControl size="small" sx={{ minWidth: 100 }}>
                <InputLabel>Show</InputLabel>
                <Select
                  value={topicsLimit}
                  label="Show"
                  onChange={(e) => setTopicsLimit(Number(e.target.value))}
                >
                  <MenuItem value={3}>Top 3</MenuItem>
                  <MenuItem value={5}>Top 5</MenuItem>
                  <MenuItem value={10}>Top 10</MenuItem>
                </Select>
              </FormControl>
            )}

            {/* Zoom Buttons */}
            <Stack direction="row" spacing={1}>
              <Button
                size="small"
                variant="outlined"
                onClick={() => {
                  const levels: ZoomLevel[] = ['year', 'quarter', 'month', 'week'];
                  const currentIndex = levels.indexOf(zoomLevel);
                  if (currentIndex > 0) {
                    handleZoomChange(levels[currentIndex - 1]);
                  }
                }}
                disabled={zoomLevel === 'year'}
                startIcon={<ZoomOutIcon />}
              >
                Zoom Out
              </Button>
              <Button
                size="small"
                variant="outlined"
                onClick={() => {
                  const levels: ZoomLevel[] = ['year', 'quarter', 'month', 'week'];
                  const currentIndex = levels.indexOf(zoomLevel);
                  if (currentIndex < levels.length - 1) {
                    handleZoomChange(levels[currentIndex + 1]);
                  }
                }}
                disabled={zoomLevel === 'week'}
                startIcon={<ZoomInIcon />}
              >
                Zoom In
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Loading State */}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Empty State */}
      {!loading && !error && (!timelineData || timelineData.topics.length === 0) && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <ShowChartIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No Timeline Data Available
          </Typography>
          <Typography color="text.secondary">
            Select topics above or wait for trend analysis to complete.
          </Typography>
        </Paper>
      )}

      {/* Timeline Visualization */}
      {!loading && !error && timelineData && timelineData.topics.length > 0 && (
        <Card>
          <CardContent>
            {/* Legend */}
            <TimelineLegend />

            {/* Timeline Canvas */}
            <TimelineCanvas
              data={timelineData}
              zoomLevel={zoomLevel}
              isDarkMode={isDarkMode}
              onPeriodClick={(topicId, periodStart, periodEnd) =>
                handleViewPapers(topicId, periodStart, periodEnd)
              }
            />

            {/* Date Range Info */}
            <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="caption" color="text.secondary">
                Date Range: {timelineData.date_range.start} to {timelineData.date_range.end}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Showing {timelineData.total_topics} topic(s) • {zoomLevel}ly view
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default ResearchTimeline;
