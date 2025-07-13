import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
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
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { LocalizationProvider, DatePicker } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import ViewModuleIcon from '@mui/icons-material/ViewModule'; // For Grid view
import ViewListIcon from '@mui/icons-material/ViewList'; // For List/Row view
import FilterListIcon from '@mui/icons-material/FilterList';
import ClearIcon from '@mui/icons-material/Clear';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import SortIcon from '@mui/icons-material/Sort';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import DragHandleIcon from '@mui/icons-material/DragHandle';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import {
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
// import type { SelectChangeEvent } from '@mui/material'; // Commented out as unused
import { papersApi } from '../services/api';
import type { PaperApiResponse } from '../services/api';
import PaperCard from './PaperCard'; // Assuming PaperCard.tsx is in the same directory
import PaperRowCard from './PaperRowCard'; // Import the new PaperRowCard
import SimilarityView from './SimilarityView'; // Import the new SimilarityView
import MindMapExplorer from '../components/MindMapExplorer'; // Import the new MindMapExplorer
import { useLayout } from '../contexts/LayoutContext';
import { useProfile } from '../contexts/ProfileContext';

const DEFAULT_PAGE_SIZE = 18; // 6 cards per row, 3 rows for grid view - increased for smoother scrolling

type ViewMode = 'grid' | 'list' | 'similarity';

interface FilterState {
  minScore: number;
  maxScore: number;
  fromDate: Date | null;
  toDate: Date | null;
  search: string;
  topicId: number | null;
  // Profile-aware filters (only available when profiles are selected)
  minProfileScore: number;
  maxProfileScore: number;
  relevanceFilter: 'all' | 'relevant' | 'not_relevant';
}

// Multi-criteria sorting system
interface SortCriterion {
  id: string;
  field: 'score' | 'profile_score' | 'date';
  direction: 'asc' | 'desc';
}

const SORT_FIELD_LABELS = {
  score: 'Overall Score',
  profile_score: 'Profile Score',
  date: 'Date'
};

// Add helper just above the component to compute ordinal suffixes
const getOrdinalSuffix = (n: number): string => {
  const j = n % 10;
  const k = n % 100;
  if (j === 1 && k !== 11) return 'st';
  if (j === 2 && k !== 12) return 'nd';
  if (j === 3 && k !== 13) return 'rd';
  return 'th';
};

// Sortable item component for drag and drop
interface SortableItemProps {
  id: string;
  index: number;
  criterion: SortCriterion;
  selectedProfileIds: number[];
  sortCriteria: SortCriterion[];
  setSortCriteria: React.Dispatch<React.SetStateAction<SortCriterion[]>>;
}

const SortableItem: React.FC<SortableItemProps> = ({ 
  id, 
  index, 
  criterion, 
  selectedProfileIds, 
  sortCriteria, 
  setSortCriteria 
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <Paper 
      ref={setNodeRef} 
      style={style} 
      sx={{ 
        p: 2, 
        bgcolor: 'action.hover',
        cursor: isDragging ? 'grabbing' : 'grab'
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box 
          {...attributes} 
          {...listeners}
          sx={{ 
            cursor: 'grab',
            '&:active': { cursor: 'grabbing' },
            display: 'flex',
            alignItems: 'center'
          }}
        >
          <DragHandleIcon color="disabled" />
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ minWidth: 70 }}>
          {index === 0 ? 'Primary' : `${index + 1}${getOrdinalSuffix(index + 1)}`}
        </Typography>
        
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Field</InputLabel>
          <Select
            value={criterion.field}
            label="Field"
            onChange={(e) => {
              const newCriteria = [...sortCriteria];
              newCriteria[index] = { ...newCriteria[index], field: e.target.value as 'score' | 'profile_score' | 'date' };
              setSortCriteria(newCriteria);
            }}
          >
            <MenuItem value="score">Overall Score</MenuItem>
            <MenuItem value="profile_score" disabled={selectedProfileIds.length === 0}>
              Profile Score {selectedProfileIds.length === 0 && '(Select profiles first)'}
            </MenuItem>
            <MenuItem value="date">Date</MenuItem>
          </Select>
        </FormControl>
        
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Direction</InputLabel>
          <Select
            value={criterion.direction}
            label="Direction"
            onChange={(e) => {
              const newCriteria = [...sortCriteria];
              newCriteria[index] = { ...newCriteria[index], direction: e.target.value as 'asc' | 'desc' };
              setSortCriteria(newCriteria);
            }}
          >
            <MenuItem value="desc">High to Low</MenuItem>
            <MenuItem value="asc">Low to High</MenuItem>
          </Select>
        </FormControl>
        
        {sortCriteria.length > 1 && (
          <IconButton 
            color="error" 
            size="small"
            onClick={() => {
              const newCriteria = sortCriteria.filter((_, i) => i !== index);
              setSortCriteria(newCriteria);
            }}
          >
            <DeleteIcon />
          </IconButton>
        )}
      </Box>
    </Paper>
  );
};

const Papers: React.FC = () => {
  // Layout context for responsive sidebar
  const { currentDrawerWidth, headerHeight } = useLayout();
  
  // Profile context for filtering
  const { selectedProfileIds } = useProfile();
  
  // URL parameters for initial filtering
  const [searchParams] = useSearchParams();
  
  // Drag and drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Keep track of all fetched papers for infinite scroll
  const [allPapers, setAllPapers] = useState<PaperApiResponse[]>([]); 
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false); // Separate state for additional loads
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize] = useState<number>(DEFAULT_PAGE_SIZE);
  const [hasNextPage, setHasNextPage] = useState<boolean>(true); // Track if more pages are available
  const [initialLoadComplete, setInitialLoadComplete] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<ViewMode>('grid'); // Updated to include similarity
  
  // Multi-criteria sorting state
  const [sortCriteria, setSortCriteria] = useState<SortCriterion[]>([
    { id: 'primary', field: 'score', direction: 'desc' }
  ]);
  const [showSorting, setShowSorting] = useState<boolean>(false);
  
  // Similarity view state
  const [selectedPaper, setSelectedPaper] = useState<PaperApiResponse | null>(null);
  const [scrollPosition, setScrollPosition] = useState<number>(0);
  const [isScrolling, setIsScrolling] = useState<boolean>(false);
  
  // Mind-map state
  const [mindMapOpen, setMindMapOpen] = useState<boolean>(false);
  const [mindMapSeedPaper, setMindMapSeedPaper] = useState<PaperApiResponse | null>(null);
  
  // Initialize filters from URL parameters
  const getInitialFilters = useCallback((): FilterState => {
    const topicId = searchParams.get('topic_id');
    const search = searchParams.get('search');
    const minScore = searchParams.get('min_score');
    const maxScore = searchParams.get('max_score');
    const fromDate = searchParams.get('from_date');
    const toDate = searchParams.get('to_date');
    
    return {
      minScore: minScore ? parseFloat(minScore) : 0,
      maxScore: maxScore ? parseFloat(maxScore) : 10,
      fromDate: fromDate ? new Date(fromDate) : null,
      toDate: toDate ? new Date(toDate) : null,
      search: search || '',
      topicId: topicId ? parseInt(topicId) : null,
      // Profile-aware filters - defaults
      minProfileScore: 0,
      maxProfileScore: 10,
      relevanceFilter: 'all'
    };
  }, [searchParams]);

  // Filter state
  const [filters, setFilters] = useState<FilterState>(getInitialFilters);
  const [showFilters, setShowFilters] = useState<boolean>(false);
  const [appliedFilters, setAppliedFilters] = useState<FilterState>(getInitialFilters);
  
  // Hybrid search state
  const [useHybridSearch, setUseHybridSearch] = useState<boolean>(false);
  const [semanticWeight, setSemanticWeight] = useState<number>(0.6);
  const [keywordWeight, setKeywordWeight] = useState<number>(0.4);

  const loader = useRef<HTMLDivElement>(null); // For Intersection Observer

  // Show filters panel if URL parameters are present
  useEffect(() => {
    const hasUrlParams = searchParams.get('topic_id') || 
                        searchParams.get('search') || 
                        searchParams.get('min_score') || 
                        searchParams.get('max_score') || 
                        searchParams.get('from_date') || 
                        searchParams.get('to_date');
    
    if (hasUrlParams) {
      setShowFilters(true);
    }
  }, [searchParams]);

  const fetchPapers = useCallback(async (page: number, size: number, isInitialLoad: boolean = false) => {
    if (!hasNextPage && !isInitialLoad) return; // Don't fetch if no more pages, unless it's the very first load
    
    // Set appropriate loading state
    if (isInitialLoad) {
      setLoading(true);
    } else {
      setLoadingMore(true);
    }
    setError(null);
    
    // Parse sort option
    const getSortFieldAndDirection = (sortOption: SortCriterion): [string, string] => {
      switch (sortOption.field) {
        case 'score':
          return ['score', sortOption.direction];
        case 'profile_score':
          return ['profile_score', sortOption.direction];
        case 'date':
          return ['date', sortOption.direction];
        default:
          return ['score', 'desc'];
      }
    };

    // Use only the first sort criterion for API call (backend limitation)
    const [sortField, sortDirection] = getSortFieldAndDirection(sortCriteria[0]);
    
    try {
      let data;
      if (useHybridSearch && appliedFilters.search) {
        // Use hybrid search when enabled and search query exists
        const hybridData = await papersApi.hybridSearch(
          appliedFilters.search,
          page,
          size,
          semanticWeight,
          keywordWeight,
          0.3, // similarity threshold
          appliedFilters.minScore > 0 ? appliedFilters.minScore : undefined,
          appliedFilters.maxScore < 10 ? appliedFilters.maxScore : undefined,
          appliedFilters.fromDate ? appliedFilters.fromDate.toISOString().split('T')[0] : undefined,
          appliedFilters.toDate ? appliedFilters.toDate.toISOString().split('T')[0] : undefined
        );
        data = {
          items: hybridData.results,
          current_page: hybridData.current_page,
          nextPage: hybridData.current_page < hybridData.total_pages ? hybridData.current_page + 1 : null
        };
      } else {
        // Use regular search/filtering
        data = await papersApi.getPapers(
          page, 
          size, 
          sortField,
          sortDirection,
          appliedFilters.minScore > 0 ? appliedFilters.minScore : undefined,
          appliedFilters.maxScore < 10 ? appliedFilters.maxScore : undefined,
          appliedFilters.fromDate ? appliedFilters.fromDate.toISOString().split('T')[0] : undefined,
          appliedFilters.toDate ? appliedFilters.toDate.toISOString().split('T')[0] : undefined,
          appliedFilters.search || undefined,
          appliedFilters.topicId || undefined,
          selectedProfileIds.length > 0 ? selectedProfileIds : undefined,
          // Profile-aware parameters
          selectedProfileIds.length > 0 && appliedFilters.minProfileScore > 0 ? appliedFilters.minProfileScore : undefined,
          selectedProfileIds.length > 0 && appliedFilters.maxProfileScore < 10 ? appliedFilters.maxProfileScore : undefined,
          // Fixed profile relevance filtering logic
          selectedProfileIds.length > 0 && appliedFilters.relevanceFilter === 'relevant' ? true : undefined
        );
      }
      setAllPapers(prevPapers => isInitialLoad ? data.items : [...prevPapers, ...data.items]);
      setCurrentPage(data.current_page + 1); // Prepare for the next page
      setHasNextPage(data.nextPage !== null);
      if (!initialLoadComplete) setInitialLoadComplete(true);
    } catch (err) {
      console.error("Error fetching papers:", err);
      setError('Failed to fetch papers. Please try again.');
    }
    
    // Clear appropriate loading state
    if (isInitialLoad) {
      setLoading(false);
    } else {
      setLoadingMore(false);
    }
      }, [hasNextPage, initialLoadComplete, appliedFilters, useHybridSearch, semanticWeight, keywordWeight, selectedProfileIds, sortCriteria]);

  // Reset papers when filters change
  const resetAndFetch = useCallback(() => {
    setAllPapers([]);
    setCurrentPage(1);
    setHasNextPage(true);
    setInitialLoadComplete(false);
  }, []);

  // Smart sorting: automatically switch to profile-aware sorting when profiles are selected
  useEffect(() => {
    if (selectedProfileIds.length > 0) {
      // Switch to profile-aware sorting if currently using regular score sorting
      setSortCriteria(prev => {
        const updated = [...prev];
        if (updated[0].field === 'score') {
          updated[0] = { ...updated[0], field: 'profile_score' };
        }
        return updated;
      });
    } else {
      // Switch back to regular sorting if currently using profile-aware sorting
      setSortCriteria(prev => {
        const updated = [...prev];
        if (updated[0].field === 'profile_score') {
          updated[0] = { ...updated[0], field: 'score' };
        }
        return updated;
      });
    }
  }, [selectedProfileIds]);

  // Initial fetch
  useEffect(() => {
    resetAndFetch();
  }, [pageSize, appliedFilters, selectedProfileIds, sortCriteria, resetAndFetch]);

  useEffect(() => {
    if(!initialLoadComplete) {
        fetchPapers(1, pageSize, true);
    }
  }, [pageSize, fetchPapers, initialLoadComplete]);

  // Intersection Observer for infinite scrolling with improved performance
  useEffect(() => {
    let isRequestInProgress = false;
    let requestTimeout: NodeJS.Timeout;
    
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && 
            !loading && 
            !loadingMore && 
            !isRequestInProgress && 
            hasNextPage && 
            initialLoadComplete) {
          
          // If user is scrolling rapidly, wait a bit before making request
          if (isScrolling) {
            clearTimeout(requestTimeout);
            requestTimeout = setTimeout(() => {
              if (!isRequestInProgress) {
                isRequestInProgress = true;
                fetchPapers(currentPage, pageSize).finally(() => {
                  isRequestInProgress = false;
                });
              }
            }, 300);
          } else {
            isRequestInProgress = true;
            fetchPapers(currentPage, pageSize).finally(() => {
              isRequestInProgress = false;
            });
          }
        }
      },
      { 
        threshold: 0.1, // Trigger earlier when only 10% visible
        rootMargin: '200px' // Start loading 200px before reaching the loader
      }
    );

    const currentLoader = loader.current;
    if (currentLoader) {
      observer.observe(currentLoader);
    }

    return () => {
      clearTimeout(requestTimeout);
      if (currentLoader) {
        observer.unobserve(currentLoader);
      }
    };
  }, [loading, loadingMore, hasNextPage, currentPage, pageSize, fetchPapers, initialLoadComplete, isScrolling]);

  // Scroll event handler to detect rapid scrolling
  useEffect(() => {
    let scrollTimeout: NodeJS.Timeout;
    
    const handleScroll = () => {
      setIsScrolling(true);
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(() => {
        setIsScrolling(false);
      }, 150); // Consider scrolling stopped after 150ms of no scroll events
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    
    return () => {
      window.removeEventListener('scroll', handleScroll);
      clearTimeout(scrollTimeout);
    };
  }, []);

  // No need for client-side filtering anymore since it's handled at database level
  const sortedPapers = useMemo(() => {
    return allPapers;
  }, [allPapers, sortCriteria]);

  const handleViewModeChange = (
    _event: React.MouseEvent<HTMLElement>,
    newViewMode: ViewMode | null, 
  ) => {
    if (newViewMode !== null && newViewMode !== 'similarity') {
      setViewMode(newViewMode);
    }
  };

  const handleFindSimilar = (paper: PaperApiResponse) => {
    // Save current scroll position
    setScrollPosition(window.scrollY);
    setSelectedPaper(paper);
    setViewMode('similarity');
  };

  const handleCloseSimilarity = () => {
    setViewMode('grid'); // or return to previous view mode
    setSelectedPaper(null);
    // Restore scroll position
    setTimeout(() => {
      window.scrollTo(0, scrollPosition);
    }, 100);
  };

  const handleOpenMindMap = (paper: PaperApiResponse) => {
    setMindMapSeedPaper(paper);
    setMindMapOpen(true);
  };

  const handleCloseMindMap = () => {
    setMindMapOpen(false);
    setMindMapSeedPaper(null);
  };

  const handleTopicClick = (topicId: number) => {
    // Update filters to include the topic and apply them
    const newFilters = { ...filters, topicId };
    setFilters(newFilters);
    setAppliedFilters(newFilters);
  };

  const handleApplyFilters = () => {
    setAppliedFilters({ ...filters });
    setShowFilters(false);
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleApplyFilters();
    }
  };

  const handleResetFilters = () => {
    const resetFilters: FilterState = {
      minScore: 0,
      maxScore: 10,
      fromDate: null,
      toDate: null,
      search: '',
      topicId: null,
      // Profile-aware filters - defaults
      minProfileScore: 0,
      maxProfileScore: 10,
      relevanceFilter: 'all' as const
    };
    setFilters(resetFilters);
    setAppliedFilters(resetFilters);
  };

  const hasActiveFilters = useMemo(() => {
    return appliedFilters.minScore > 0 || 
           appliedFilters.maxScore < 10 || 
           appliedFilters.fromDate !== null || 
           appliedFilters.toDate !== null || 
           appliedFilters.search !== '' ||
           appliedFilters.topicId !== null ||
           appliedFilters.minProfileScore > 0 ||
           appliedFilters.maxProfileScore < 10 ||
           appliedFilters.relevanceFilter !== 'all';
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
    if (appliedFilters.topicId) {
      chips.push(`Filtered by Topic/Interest: ${appliedFilters.topicId}`);
    }
    if (appliedFilters.minProfileScore > 0) {
      chips.push(`Min Profile Score: ${appliedFilters.minProfileScore}`);
    }
    if (appliedFilters.maxProfileScore < 10) {
      chips.push(`Max Profile Score: ${appliedFilters.maxProfileScore}`);
    }
    if (appliedFilters.relevanceFilter !== 'all') {
      chips.push(`Relevance: ${appliedFilters.relevanceFilter}`);
    }
    return chips;
  };

  const getSortSummary = () => {
    const primary = sortCriteria[0];
    const fieldLabel = SORT_FIELD_LABELS[primary.field];
    const directionLabel = primary.direction === 'desc' ? '↓' : '↑';
    
    if (sortCriteria.length === 1) {
      return `${fieldLabel} ${directionLabel}`;
    } else {
      return `${fieldLabel} ${directionLabel} +${sortCriteria.length - 1}`;
    }
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
      {viewMode === 'similarity' && selectedPaper ? (
        <SimilarityView
          referencePaper={selectedPaper}
          onClose={handleCloseSimilarity}
        />
      ) : (
        <Box sx={{ position: 'relative', minHeight: '100vh' }}>
          {/* Fixed Header Container */}
          <Box sx={{ 
            position: 'fixed',
            top: `${headerHeight}px`, // Dynamic header height including ProfileSelector
            left: `${currentDrawerWidth}px`, // Dynamic sidebar width
            right: 0,
            zIndex: 1000, // Lower z-index than AppBar (1100) to allow ProfileSelector to overlay
            backgroundColor: 'background.default',
            boxShadow: 1,
            transition: 'left 0.3s, top 0.3s', // Smooth transition when sidebar toggles or header height changes
          }}>
            {/* Main header with title and controls */}
            <Box sx={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center', 
              px: 3, 
              py: 2,
              backgroundColor: 'background.default',
              borderBottom: 1,
              borderColor: 'divider',
              minHeight: '64px'
            }}>
              <Typography variant="h4" gutterBottom component="div" sx={{ mb: 3 }}>
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
                
                {/* Sorting controls - always visible */}
                <Button
                  variant="outlined"
                  startIcon={<SortIcon />}
                  endIcon={showSorting ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                  onClick={() => setShowSorting(!showSorting)}
                  color="inherit"
                  sx={{ minWidth: 200 }}
                >
                  {getSortSummary()}
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

            {/* Filter panel - only visible when showFilters is true */}
            <Collapse in={showFilters}>
              <Box sx={{ 
                backgroundColor: 'background.default',
                borderBottom: 1,
                borderColor: 'divider'
              }}>
                <Card sx={{ borderRadius: 0, boxShadow: 'none', backgroundColor: 'transparent' }}>
                  <CardContent sx={{ py: 2, px: 3 }}>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                      Filter Papers
                    </Typography>
                    
                    {/* Search Row */}
                    <Box sx={{ mb: 2 }}>
                      <Grid container spacing={2} sx={{ mb: 1.5 }}>
                        <Grid size={{ xs: 12 }}>
                          <TextField
                            fullWidth
                            size="small"
                            label="Search in title and abstract"
                            value={filters.search}
                            onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                            onKeyDown={handleSearchKeyDown}
                            placeholder="Enter keywords..."
                            helperText={useHybridSearch ? "Hybrid search: combines semantic similarity with keyword matching" : "Keyword search only"}
                          />
                        </Grid>
                      </Grid>
                      
                      {/* Hybrid Search Toggle */}
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: useHybridSearch ? 1.5 : 0 }}>
                        <input
                          type="checkbox"
                          id="hybrid-search-toggle"
                          checked={useHybridSearch}
                          onChange={(e) => setUseHybridSearch(e.target.checked)}
                          style={{ margin: 0 }}
                        />
                        <label htmlFor="hybrid-search-toggle">
                          <Typography variant="body2">
                            Enable Hybrid Search (combines keyword + semantic similarity)
                          </Typography>
                        </label>
                      </Box>
                      
                      {/* Weight Sliders - Compact Layout */}
                      {useHybridSearch && (
                        <Box sx={{ 
                          display: 'flex', 
                          gap: 3, 
                          alignItems: 'center',
                          pl: 2,
                          py: 1,
                          backgroundColor: 'action.hover',
                          borderRadius: 1
                        }}>
                          <Typography variant="caption" color="text.secondary" sx={{ minWidth: 'auto', fontSize: '0.75rem' }}>
                            Weights:
                          </Typography>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: '180px' }}>
                            <Typography variant="caption" sx={{ minWidth: '70px', fontSize: '0.7rem' }}>
                              Semantic: {semanticWeight}
                            </Typography>
                            <Slider
                              value={semanticWeight}
                              onChange={(_, newValue) => {
                                const newSemantic = newValue as number;
                                setSemanticWeight(newSemantic);
                                setKeywordWeight(Number((1 - newSemantic).toFixed(2)));
                              }}
                              min={0}
                              max={1}
                              step={0.1}
                              size="small"
                              sx={{ 
                                flex: 1,
                                '& .MuiSlider-markLabel': { 
                                  fontSize: '0.6rem'
                                }
                              }}
                              marks={[
                                { value: 0, label: '0' },
                                { value: 0.5, label: '0.5' },
                                { value: 1, label: '1' }
                              ]}
                            />
                          </Box>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: '180px' }}>
                            <Typography variant="caption" sx={{ minWidth: '70px', fontSize: '0.7rem' }}>
                              Keyword: {keywordWeight}
                            </Typography>
                            <Slider
                              value={keywordWeight}
                              onChange={(_, newValue) => {
                                const newKeyword = newValue as number;
                                setKeywordWeight(newKeyword);
                                setSemanticWeight(Number((1 - newKeyword).toFixed(2)));
                              }}
                              min={0}
                              max={1}
                              step={0.1}
                              size="small"
                              sx={{ 
                                flex: 1,
                                '& .MuiSlider-markLabel': { 
                                  fontSize: '0.6rem'
                                }
                              }}
                              marks={[
                                { value: 0, label: '0' },
                                { value: 0.5, label: '0.5' },
                                { value: 1, label: '1' }
                              ]}
                            />
                          </Box>
                        </Box>
                      )}
                    </Box>

                    {/* Score Range and Date Range Row */}
                    <Grid container spacing={2} sx={{ mb: 2 }}>
                      <Grid size={{ xs: 12, md: 4 }}>
                        <Typography variant="body2" sx={{ mb: 1 }}>
                          Score Range: {filters.minScore} - {filters.maxScore}
                        </Typography>
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
                          size="small"
                          sx={{ 
                            '& .MuiSlider-markLabel': { 
                              fontSize: '0.7rem'
                            }
                          }}
                          marks={[
                            { value: 0, label: '0' },
                            { value: 5, label: '5' },
                            { value: 10, label: '10' }
                          ]}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, md: 4 }}>
                        <DatePicker
                          label="From Date"
                          value={filters.fromDate}
                          onChange={(newValue) => setFilters(prev => ({ ...prev, fromDate: newValue }))}
                          slotProps={{ textField: { fullWidth: true, size: 'small' } }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, md: 4 }}>
                        <DatePicker
                          label="To Date"
                          value={filters.toDate}
                          onChange={(newValue) => setFilters(prev => ({ ...prev, toDate: newValue }))}
                          slotProps={{ textField: { fullWidth: true, size: 'small' } }}
                          minDate={filters.fromDate || undefined}
                        />
                      </Grid>
                    </Grid>

                    {/* Profile-aware Filters */}
                    {selectedProfileIds.length > 0 && (
                      <>
                        <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
                          Profile-Aware Filters
                        </Typography>
                        <Grid container spacing={2} sx={{ mb: 1.5 }}>
                          <Grid size={{ xs: 12, md: 6 }}>
                            <Typography variant="body2" sx={{ mb: 1 }}>
                              Profile Score Range: {filters.minProfileScore} - {filters.maxProfileScore}
                            </Typography>
                            <Slider
                              value={[filters.minProfileScore, filters.maxProfileScore]}
                              onChange={(_, newValue) => {
                                const [min, max] = newValue as number[];
                                setFilters(prev => ({ ...prev, minProfileScore: min, maxProfileScore: max }));
                              }}
                              valueLabelDisplay="auto"
                              min={0}
                              max={10}
                              step={0.1}
                              size="small"
                              sx={{ 
                                '& .MuiSlider-markLabel': { 
                                  fontSize: '0.7rem'
                                }
                              }}
                              marks={[
                                { value: 0, label: '0' },
                                { value: 5, label: '5' },
                                { value: 10, label: '10' }
                              ]}
                            />
                          </Grid>
                          <Grid size={{ xs: 12, md: 6 }}>
                            <Typography variant="body2" sx={{ mb: 1 }}>
                              Relevance Filter:
                            </Typography>
                            <ToggleButtonGroup
                                value={filters.relevanceFilter}
                                exclusive
                                onChange={(_, newFilter) => setFilters(prev => ({ ...prev, relevanceFilter: newFilter }))}
                                aria-label="relevance filter"
                                size="small"
                            >
                                <ToggleButton value="all" aria-label="all relevance">
                                    All
                                </ToggleButton>
                                <ToggleButton value="relevant" aria-label="relevant papers">
                                    Relevant
                                </ToggleButton>
                                <ToggleButton value="not_relevant" aria-label="not relevant papers" disabled>
                                    Not Relevant
                                </ToggleButton>
                            </ToggleButtonGroup>
                            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                              Note: "Not Relevant" filter is not currently supported by the API
                            </Typography>
                          </Grid>
                        </Grid>
                      </>
                    )}

                    {/* Filter Actions */}
                    <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
                      <Button variant="outlined" size="small" onClick={handleResetFilters} startIcon={<ClearIcon />}>
                        Reset
                      </Button>
                      <Button variant="contained" size="small" onClick={handleApplyFilters}>
                        Apply Filters
                      </Button>
                    </Box>
                  </CardContent>
                </Card>
              </Box>
            </Collapse>

            {/* Sorting panel - only visible when showSorting is true */}
            <Collapse in={showSorting}>
              <Box sx={{ 
                backgroundColor: 'background.default',
                borderBottom: 1,
                borderColor: 'divider'
              }}>
                <Card sx={{ borderRadius: 0, boxShadow: 'none', backgroundColor: 'transparent' }}>
                  <CardContent sx={{ py: 2, px: 3 }}>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                      Sort Papers
                    </Typography>
                    
                    {/* Sort criteria list */}
                    <DndContext
                      sensors={sensors}
                      collisionDetection={closestCenter}
                      onDragEnd={(event: DragEndEvent) => {
                        const { active, over } = event;
                        if (active.id !== over?.id) {
                          const oldIndex = sortCriteria.findIndex(criterion => criterion.id === active.id);
                          const newIndex = sortCriteria.findIndex(criterion => criterion.id === over?.id);
                          if (oldIndex !== -1 && newIndex !== -1) {
                            setSortCriteria(arrayMove(sortCriteria, oldIndex, newIndex));
                          }
                        }
                      }}
                    >
                      <SortableContext
                        items={sortCriteria.map(criterion => criterion.id)}
                        strategy={verticalListSortingStrategy}
                      >
                        <Stack spacing={2} sx={{ mb: 2 }}>
                          {sortCriteria.map((criterion, index) => (
                            <SortableItem
                              key={criterion.id}
                              id={criterion.id}
                              index={index}
                              criterion={criterion}
                              selectedProfileIds={selectedProfileIds}
                              sortCriteria={sortCriteria}
                              setSortCriteria={setSortCriteria}
                            />
                          ))}
                        </Stack>
                      </SortableContext>
                    </DndContext>
                    
                    {/* Sort actions */}
                    <Box sx={{ display: 'flex', gap: 2, justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography variant="body2" color="text.secondary">
                        {sortCriteria.length === 1 ? 'Single sort criterion' : `${sortCriteria.length} sort criteria (currently only primary is used)`}
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button 
                          variant="outlined" 
                          size="small" 
                          onClick={() => setSortCriteria((prev) => {
                            const newCriteria = [...prev, {
                              id: `sort-${Date.now()}`,
                              field: 'score' as 'score',
                              direction: 'desc' as 'desc'
                            }];
                            return newCriteria;
                          })}
                          startIcon={<AddIcon />}
                          disabled={sortCriteria.length >= 4}
                        >
                          Add Sort
                        </Button>
                        <Button
                          variant="outlined"
                          size="small"
                          onClick={() => {
                            const newCriteria = [{ id: 'primary', field: 'score' as 'score', direction: 'desc' as 'desc' }];
                            setSortCriteria(newCriteria);
                          }}
                          startIcon={<ClearIcon />}
                        >
                          Reset
                        </Button>
                      </Box>
                    </Box>
                  </CardContent>
                </Card>
              </Box>
            </Collapse>

            {/* Active filter chips - always part of sticky header when filters are active */}
            {hasActiveFilters && (
              <Box sx={{ 
                px: 3,
                py: 1,
                backgroundColor: 'background.default',
                borderBottom: 1,
                borderColor: 'divider'
              }}>
                <Stack direction="row" spacing={1} flexWrap="wrap" alignItems="center">
                  <Typography variant="body2" sx={{ mr: 1 }}>
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
          </Box>

          {/* Scrollable content area with padding for fixed header */}
          <Box sx={{ p: 3, pt: `${headerHeight + 150}px` }}> {/* Add top padding to account for fixed header + filter bar */}
            {/* Papers content based on viewMode */} 
            {viewMode === 'grid' ? (
              <Grid container spacing={3} sx={{ mb: 3 }}>
                {sortedPapers.map((paper) => (
                  <Grid size={{ xs: 12, sm: 6, md: 4 }} key={paper.id + "_" + paper.date_run + "_grid"}>
                    <PaperCard 
                      paper={paper} 
                      onFindSimilar={handleFindSimilar}
                      onOpenMindMap={handleOpenMindMap}
                      onTopicClick={handleTopicClick}
                      hasProfilesSelected={selectedProfileIds.length > 0}
                    />
                  </Grid>
                ))}
              </Grid>
            ) : (
              <Box sx={{ mb: 3 }}>
                {sortedPapers.map((paper) => (
                  <PaperRowCard 
                    key={paper.id + "_" + paper.date_run + "_list"} 
                    paper={paper} 
                    onFindSimilar={handleFindSimilar}
                    onOpenMindMap={handleOpenMindMap}
                    onTopicClick={handleTopicClick}
                    hasProfilesSelected={selectedProfileIds.length > 0}
                  />
                ))}
              </Box>
            )}

            {/* Infinite scroll elements */}
            <div ref={loader} style={{ height: '100px', margin: '40px 0' }}>
              {loadingMore && (
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
                  <CircularProgress size={24} />
                  <Typography variant="body2" color="text.secondary">
                    Loading more papers...
                  </Typography>
                </Box>
              )}
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
        </Box>
      )}

      {/* Mind-Map Explorer */}
      <MindMapExplorer
        open={mindMapOpen}
        onClose={handleCloseMindMap}
        seedPaper={mindMapSeedPaper}
      />
    </LocalizationProvider>
  );
};

export default Papers; 