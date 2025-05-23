import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Grid,
  Button,
  ToggleButton,
  ToggleButtonGroup,
  Collapse,
  Card,
  CardContent,
  TextField,
  Slider,
  Chip,
  Stack,
  IconButton,
  Tooltip,
} from '@mui/material';
import { LocalizationProvider, DatePicker } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import ViewModuleIcon from '@mui/icons-material/ViewModule'; // For Grid view
import ViewListIcon from '@mui/icons-material/ViewList'; // For List/Row view
import FilterListIcon from '@mui/icons-material/FilterList';
import ClearIcon from '@mui/icons-material/Clear';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
// import type { SelectChangeEvent } from '@mui/material'; // Commented out as unused
import { papersApi } from '../services/api';
import type { PaperApiResponse, PaginatedPapersResponse } from '../services/api';
import PaperCard from './PaperCard'; // Assuming PaperCard.tsx is in the same directory
import PaperRowCard from './PaperRowCard'; // Import the new PaperRowCard

const DEFAULT_PAGE_SIZE = 9; // 3 cards per row, 3 rows for grid view

type ViewMode = 'grid' | 'list';

interface FilterState {
  minScore: number;
  maxScore: number;
  fromDate: Date | null;
  toDate: Date | null;
  search: string;
}

const Papers: React.FC = () => {
  // Keep track of all fetched papers for infinite scroll
  const [allPapers, setAllPapers] = useState<PaperApiResponse[]>([]); 
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(DEFAULT_PAGE_SIZE);
  const [hasNextPage, setHasNextPage] = useState<boolean>(true); // Track if more pages are available
  const [initialLoadComplete, setInitialLoadComplete] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<ViewMode>('grid'); // New state for view mode
  
  // Filter state
  const [filters, setFilters] = useState<FilterState>({
    minScore: 0,
    maxScore: 10,
    fromDate: null,
    toDate: null,
    search: ''
  });
  const [showFilters, setShowFilters] = useState<boolean>(false);
  const [appliedFilters, setAppliedFilters] = useState<FilterState>({
    minScore: 0,
    maxScore: 10,
    fromDate: null,
    toDate: null,
    search: ''
  });

  const loader = useRef<HTMLDivElement>(null); // For Intersection Observer

  const fetchPapers = useCallback(async (page: number, size: number, isInitialLoad: boolean = false) => {
    if (!hasNextPage && !isInitialLoad) return; // Don't fetch if no more pages, unless it's the very first load
    setLoading(true);
    setError(null);
    try {
      const data = await papersApi.getPapers(
        page, 
        size, 
        'score', 
        'desc',
        appliedFilters.minScore > 0 ? appliedFilters.minScore : undefined,
        appliedFilters.fromDate ? appliedFilters.fromDate.toISOString().split('T')[0] : undefined,
        appliedFilters.toDate ? appliedFilters.toDate.toISOString().split('T')[0] : undefined,
        appliedFilters.search || undefined
      );
      setAllPapers(prevPapers => isInitialLoad ? data.items : [...prevPapers, ...data.items]);
      setCurrentPage(data.current_page + 1); // Prepare for the next page
      setHasNextPage(data.nextPage !== null);
      if (!initialLoadComplete) setInitialLoadComplete(true);
    } catch (err) {
      console.error("Error fetching papers:", err);
      setError('Failed to fetch papers. Please try again.');
    }
    setLoading(false);
  }, [hasNextPage, initialLoadComplete, appliedFilters]);

  // Reset papers when filters change
  const resetAndFetch = useCallback(() => {
    setAllPapers([]);
    setCurrentPage(1);
    setHasNextPage(true);
    setInitialLoadComplete(false);
  }, []);

  // Initial fetch
  useEffect(() => {
    resetAndFetch();
  }, [pageSize, appliedFilters, resetAndFetch]);

  useEffect(() => {
    if(!initialLoadComplete) {
        fetchPapers(1, pageSize, true);
    }
  }, [pageSize, fetchPapers, initialLoadComplete]);

  // Intersection Observer for infinite scrolling
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && !loading && hasNextPage && initialLoadComplete) {
          fetchPapers(currentPage, pageSize);
        }
      },
      { threshold: 1.0 }
    );

    const currentLoader = loader.current;
    if (currentLoader) {
      observer.observe(currentLoader);
    }

    return () => {
      if (currentLoader) {
        observer.unobserve(currentLoader);
      }
    };
  }, [loading, hasNextPage, currentPage, pageSize, fetchPapers, initialLoadComplete]);

  const sortedPapers = useMemo(() => {
    // Papers are already sorted by the API, no need to re-sort
    // But we can do client-side filtering for maxScore since API only supports minScore
    return allPapers.filter(paper => paper.score <= appliedFilters.maxScore);
  }, [allPapers, appliedFilters.maxScore]);

  const handleViewModeChange = (
    _event: React.MouseEvent<HTMLElement>,
    newViewMode: ViewMode | null, 
  ) => {
    if (newViewMode !== null) {
      setViewMode(newViewMode);
    }
  };

  const handleApplyFilters = () => {
    setAppliedFilters({ ...filters });
  };

  const handleResetFilters = () => {
    const resetFilters = {
      minScore: 0,
      maxScore: 10,
      fromDate: null,
      toDate: null,
      search: ''
    };
    setFilters(resetFilters);
    setAppliedFilters(resetFilters);
  };

  const hasActiveFilters = useMemo(() => {
    return appliedFilters.minScore > 0 || 
           appliedFilters.maxScore < 10 || 
           appliedFilters.fromDate !== null || 
           appliedFilters.toDate !== null || 
           appliedFilters.search !== '';
  }, [appliedFilters]);

  const getActiveFilterChips = () => {
    const chips = [];
    if (appliedFilters.minScore > 0) {
      chips.push(`Min Score: ${appliedFilters.minScore}`);
    }
    if (appliedFilters.maxScore < 10) {
      chips.push(`Max Score: ${appliedFilters.maxScore}`);
    }
    if (appliedFilters.fromDate) {
      chips.push(`From: ${appliedFilters.fromDate.toLocaleDateString()}`);
    }
    if (appliedFilters.toDate) {
      chips.push(`To: ${appliedFilters.toDate.toLocaleDateString()}`);
    }
    if (appliedFilters.search) {
      chips.push(`Search: "${appliedFilters.search}"`);
    }
    return chips;
  };
  
  if (loading && allPapers.length === 0) { // Show full page loader only on initial load
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error && allPapers.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>
        <Button onClick={() => fetchPapers(1, pageSize, true)} sx={{ mt: 2 }}>Retry Initial Load</Button>
      </Box>
    );
  }

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2}}>
          <Typography variant="h4" gutterBottom component="div">
            Historical Papers
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Button
              variant="outlined"
              startIcon={<FilterListIcon />}
              endIcon={showFilters ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              onClick={() => setShowFilters(!showFilters)}
              color={hasActiveFilters ? "primary" : "inherit"}
            >
              Filters {hasActiveFilters && `(${getActiveFilterChips().length})`}
            </Button>
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

        {/* Filter Panel */}
        <Collapse in={showFilters}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Filter Papers
              </Typography>
              
              <Grid container spacing={3}>
                {/* Search */}
                <Grid size={{ xs: 12 }}>
                  <TextField
                    fullWidth
                    label="Search in title and abstract"
                    value={filters.search}
                    onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                    placeholder="Enter keywords..."
                  />
                </Grid>

                {/* Score Range */}
                <Grid size={{ xs: 12, md: 6 }}>
                  <Typography gutterBottom>Score Range: {filters.minScore} - {filters.maxScore}</Typography>
                  <Slider
                    value={[filters.minScore, filters.maxScore]}
                    onChange={(_, newValue) => {
                      const [min, max] = newValue as number[];
                      setFilters(prev => ({ ...prev, minScore: min, maxScore: max }));
                    }}
                    valueLabelDisplay="auto"
                    min={0}
                    max={10}
                    step={0.1}
                    marks={[
                      { value: 0, label: '0' },
                      { value: 5, label: '5' },
                      { value: 10, label: '10' }
                    ]}
                  />
                </Grid>

                {/* Date Range */}
                <Grid size={{ xs: 12, md: 3 }}>
                  <DatePicker
                    label="From Date"
                    value={filters.fromDate}
                    onChange={(newValue) => setFilters(prev => ({ ...prev, fromDate: newValue }))}
                    slotProps={{ textField: { fullWidth: true } }}
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 3 }}>
                  <DatePicker
                    label="To Date"
                    value={filters.toDate}
                    onChange={(newValue) => setFilters(prev => ({ ...prev, toDate: newValue }))}
                    slotProps={{ textField: { fullWidth: true } }}
                    minDate={filters.fromDate || undefined}
                  />
                </Grid>
              </Grid>

              {/* Filter Actions */}
              <Box sx={{ mt: 3, display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
                <Button variant="outlined" onClick={handleResetFilters} startIcon={<ClearIcon />}>
                  Reset
                </Button>
                <Button variant="contained" onClick={handleApplyFilters}>
                  Apply Filters
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Collapse>

        {/* Active Filter Chips */}
        {hasActiveFilters && (
          <Box sx={{ mb: 2 }}>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              <Typography variant="body2" sx={{ alignSelf: 'center', mr: 1 }}>
                Active filters:
              </Typography>
              {getActiveFilterChips().map((chipLabel, index) => (
                <Chip
                  key={index}
                  label={chipLabel}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
              ))}
              <Tooltip title="Clear all filters">
                <IconButton size="small" onClick={handleResetFilters}>
                  <ClearIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Stack>
          </Box>
        )}
        
        {/* Conditional Rendering based on viewMode */} 
        {viewMode === 'grid' ? (
          <Grid container spacing={3} sx={{ mb: 3 }}>
            {sortedPapers.map((paper) => (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={paper.id + "_" + paper.date_run + "_grid"}>
                <PaperCard paper={paper} />
              </Grid>
            ))}
          </Grid>
        ) : (
          <Box sx={{ mb: 3 }}>
            {sortedPapers.map((paper) => (
              <PaperRowCard key={paper.id + "_" + paper.date_run + "_list"} paper={paper} />
            ))}
          </Box>
        )}

        {/* Loader for infinite scroll */} 
        <div ref={loader} style={{ height: '50px', margin: '20px 0' }}>
          {loading && initialLoadComplete && <CircularProgress sx={{ display: 'block', margin: 'auto' }}/>}
        </div>

        {!loading && !hasNextPage && initialLoadComplete && allPapers.length > 0 && (
          <Typography textAlign="center" sx={{ my: 2 }}>
            You've reached the end of the list.
          </Typography>
        )}

        {!loading && !hasNextPage && initialLoadComplete && allPapers.length === 0 && (
           <Alert severity="info" sx={{mt: 2}}>No papers found for the current criteria.</Alert>
        )}
      </Box>
    </LocalizationProvider>
  );
};

export default Papers; 