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
  AutoFixHigh as AutoFixHighIcon,
} from '@mui/icons-material';
import {
  trendsApi,
  profileApi,
  researchInterestsApi,
  type TimelineDataResponse,
  type ProfileInterestResponse,
} from '../services/api';
import { useTheme } from '../contexts/ThemeContext';
import { useLayout } from '../contexts/LayoutContext';
import { useProfile } from '../contexts/ProfileContext';
import TimelineCanvas from '../components/timeline/TimelineCanvas';
import TimelineLegend from '../components/timeline/TimelineLegend';

type ZoomLevel = 'year' | 'quarter' | 'month' | 'week';

// Extended type for profile interests with id for selection
interface SelectableInterest {
  id: number;
  interest_text: string;
  profile_id?: number;
  profile_name?: string;
}

const ResearchTimeline: React.FC = () => {
  const navigate = useNavigate();
  const { isDarkMode } = useTheme();
  const { headerHeight } = useLayout();
  const { selectedProfileIds, getSelectedProfiles } = useProfile();

  // State
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timelineData, setTimelineData] = useState<TimelineDataResponse | null>(null);
  const [availableInterests, setAvailableInterests] = useState<SelectableInterest[]>([]);
  const [selectedInterestIds, setSelectedInterestIds] = useState<number[]>([]);
  const [zoomLevel, setZoomLevel] = useState<ZoomLevel>('month');
  const [topicsLimit, setTopicsLimit] = useState(5);
  const [isComputing, setIsComputing] = useState(false);
  const [computeMessage, setComputeMessage] = useState<string | null>(null);
  const [isGeneratingLabels, setIsGeneratingLabels] = useState(false);

  // Fetch research interests from selected profiles
  useEffect(() => {
    const fetchProfileInterests = async () => {
      if (selectedProfileIds.length === 0) {
        setAvailableInterests([]);
        return;
      }

      try {
        const selectedProfiles = getSelectedProfiles();
        const allInterests: SelectableInterest[] = [];

        // Fetch interests for each selected profile
        for (const profile of selectedProfiles) {
          try {
            const response = await profileApi.getProfileInterests(profile.id);
            const profileInterests = response.data.map((interest: ProfileInterestResponse) => ({
              id: interest.id,
              interest_text: interest.interest_text,
              profile_id: profile.id,
              profile_name: profile.name,
            }));
            allInterests.push(...profileInterests);
          } catch (err) {
            console.error(`Failed to fetch interests for profile ${profile.id}:`, err);
          }
        }

        setAvailableInterests(allInterests);
      } catch (err) {
        console.error('Failed to fetch profile interests:', err);
      }
    };

    fetchProfileInterests();
  }, [selectedProfileIds, getSelectedProfiles]);

  // Fetch timeline data
  const fetchTimelineData = useCallback(async () => {
    // Don't fetch if no profiles are selected
    if (selectedProfileIds.length === 0) {
      setTimelineData(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await trendsApi.getTimelineData({
        topic_ids: selectedInterestIds.length > 0 ? selectedInterestIds.join(',') : undefined,
        profile_ids: selectedProfileIds.join(','),
        period_type: zoomLevel === 'year' ? 'quarter' : zoomLevel,
        include_key_papers: true,
        key_papers_limit: 3,
        limit: topicsLimit,
        source: 'profile_interests', // Use profile-specific interests
      });

      setTimelineData(response.data);
    } catch (err) {
      console.error('Failed to fetch timeline data:', err);
      setError('Failed to load timeline data. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [selectedInterestIds, selectedProfileIds, zoomLevel, topicsLimit]);

  useEffect(() => {
    fetchTimelineData();
  }, [fetchTimelineData]);

  // Handle zoom level change
  const handleZoomChange = (newZoom: ZoomLevel) => {
    setZoomLevel(newZoom);
  };

  // Handle interest selection
  const handleInterestSelect = (_event: React.SyntheticEvent, values: SelectableInterest[]) => {
    setSelectedInterestIds(values.map(t => t.id));
  };

  // Navigate to papers page with filters
  const handleViewPapers = (profileInterestId: number, startDate: string, endDate: string) => {
    console.log('handleViewPapers called:', profileInterestId, startDate, endDate);
    navigate(`/papers?profile_interest_id=${profileInterestId}&from_date=${startDate}&to_date=${endDate}`);
  };

  // Handle generate short labels
  const handleGenerateLabels = async () => {
    if (selectedProfileIds.length === 0) {
      setError('Please select a profile first');
      return;
    }

    setIsGeneratingLabels(true);
    setError(null);

    try {
      const response = await trendsApi.generateShortLabels({
        profile_ids: selectedProfileIds,
      });

      if (response.data.processed > 0) {
        setComputeMessage(`Generated ${response.data.processed} short labels. Refreshing...`);
        // Refresh timeline data to show new labels
        setTimeout(() => {
          fetchTimelineData();
          setComputeMessage(null);
        }, 1000);
      } else {
        setComputeMessage(response.data.message);
        setTimeout(() => setComputeMessage(null), 3000);
      }
    } catch (err) {
      console.error('Failed to generate labels:', err);
      setError('Failed to generate short labels. Please try again.');
    } finally {
      setIsGeneratingLabels(false);
    }
  };

  // Handle compute timeline data
  const handleComputeTimeline = async () => {
    if (selectedProfileIds.length === 0) {
      setError('Please select a profile first');
      return;
    }

    setIsComputing(true);
    setComputeMessage('Starting timeline computation...');
    setError(null);

    try {
      const response = await researchInterestsApi.recomputeProfileInterests({
        profile_ids: selectedProfileIds,
        lookback_months: 24,
        clear_existing: true,
      });

      setComputeMessage(`Task started: ${response.data.task_id}. This may take a few minutes. Refresh to check for results.`);

      // Auto-refresh after a delay
      setTimeout(() => {
        fetchTimelineData();
        setComputeMessage(null);
      }, 5000);
    } catch (err) {
      console.error('Failed to start timeline computation:', err);
      setError('Failed to start timeline computation. Please try again.');
      setComputeMessage(null);
    } finally {
      setIsComputing(false);
    }
  };

  return (
    <Box
      sx={{
        p: 3,
        pt: `${headerHeight + 16}px`,
        minHeight: `calc(100vh - ${headerHeight}px)`,
        bgcolor: 'background.default',
      }}
    >
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
        <Box sx={{ minWidth: 0 }}>
          <Box sx={{
            fontFamily: '"Geist Mono", monospace',
            fontSize: 10,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: 'primary.main',
            mb: 0.75,
          }}>
            Trends · 2024–2026
          </Box>
          <Typography
            component="div"
            sx={{
              fontFamily: '"Instrument Serif", Georgia, serif',
              fontSize: 32,
              letterSpacing: '-0.02em',
              lineHeight: 1.05,
            }}
          >
            Research timeline
          </Typography>
        </Box>

        <Stack direction="row" spacing={1}>
          <Button
            variant="outlined"
            size="small"
            startIcon={isGeneratingLabels ? <CircularProgress size={16} /> : <AutoFixHighIcon />}
            onClick={handleGenerateLabels}
            disabled={isGeneratingLabels || selectedProfileIds.length === 0}
            title="Generate short labels for research interests using AI"
          >
            {isGeneratingLabels ? 'Generating...' : 'Generate Labels'}
          </Button>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchTimelineData}
            disabled={loading}
          >
            Refresh
          </Button>
        </Stack>
      </Box>

      {/* Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems="center">
            {/* Research Interest Selection */}
            <Autocomplete
              multiple
              options={availableInterests}
              getOptionLabel={(option) => {
                // Truncate long interest text for display
                const text = option.interest_text || '';
                const profileSuffix = option.profile_name ? ` (${option.profile_name})` : '';
                const fullText = text + profileSuffix;
                return fullText.length > 60 ? fullText.substring(0, 60) + '...' : fullText;
              }}
              value={availableInterests.filter(t => selectedInterestIds.includes(t.id))}
              onChange={handleInterestSelect}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Select Research Interests"
                  placeholder={selectedProfileIds.length === 0
                    ? "Select a profile first..."
                    : "Choose interests to visualize..."}
                  size="small"
                />
              )}
              renderTags={(value, getTagProps) =>
                value.map((option, index) => {
                  // Show shorter version in chip
                  const text = option.interest_text || '';
                  const chipLabel = text.length > 30 ? text.substring(0, 30) + '...' : text;
                  return (
                    <Chip
                      {...getTagProps({ index })}
                      key={option.id}
                      label={chipLabel}
                      size="small"
                      color="primary"
                      variant="outlined"
                      title={`${text}${option.profile_name ? ` (${option.profile_name})` : ''}`}
                    />
                  );
                })
              }
              sx={{ minWidth: 300, flexGrow: 1 }}
              limitTags={3}
              disabled={selectedProfileIds.length === 0}
              noOptionsText={selectedProfileIds.length === 0
                ? "Select a profile to see interests"
                : "No research interests found for selected profile(s)"}
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
            {selectedInterestIds.length === 0 && (
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

      {/* Compute Progress Message */}
      {computeMessage && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {computeMessage}
        </Alert>
      )}

      {/* Empty State */}
      {!loading && !error && (!timelineData || timelineData.topics.length === 0) && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <ShowChartIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No Timeline Data Available
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            {selectedProfileIds.length === 0
              ? 'Select a profile from the header to see research interests.'
              : availableInterests.length === 0
                ? 'Configure research interests in Profile Management to see timeline data.'
                : 'Timeline visualization requires computing interest metrics from your papers.'}
          </Typography>
          {selectedProfileIds.length > 0 && availableInterests.length > 0 && (
            <Button
              variant="contained"
              onClick={handleComputeTimeline}
              disabled={isComputing}
              startIcon={isComputing ? <CircularProgress size={20} /> : <RefreshIcon />}
            >
              {isComputing ? 'Computing...' : 'Compute Timeline Data'}
            </Button>
          )}
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
                Showing {timelineData.total_topics} interest(s) • {zoomLevel}ly view
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default ResearchTimeline;
