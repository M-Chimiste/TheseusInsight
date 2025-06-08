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
  Stack,
  IconButton,
  Tooltip,
  Paper,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  DialogContentText,
} from '@mui/material';
import { LocalizationProvider, DatePicker } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ViewListIcon from '@mui/icons-material/ViewList';
import FilterListIcon from '@mui/icons-material/FilterList';
import ClearIcon from '@mui/icons-material/Clear';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import DeleteIcon from '@mui/icons-material/Delete';
import ScienceIcon from '@mui/icons-material/Science';
import CloseIcon from '@mui/icons-material/Close';
import { alpha } from '@mui/material/styles';
import { useTheme } from '@mui/material/styles';
import { useLayout } from '../contexts/LayoutContext';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import CollapsibleContent from '../components/CollapsibleContent';

const DEFAULT_PAGE_SIZE = 20;

type ViewMode = 'grid' | 'list';

interface FilterState {
  fromDate: Date | null;
  toDate: Date | null;
  search: string;
}

interface ResearchLibraryItem {
  id: number;
  research_question: string;
  short_summary: string;
  created_ts: string;
  sources_count: number;
  has_report: boolean;
  themes: string[];
  report_text?: string;
  activity_log?: any[];
}

const ResearchLibrary: React.FC = () => {
  const theme = useTheme();
  const { currentDrawerWidth } = useLayout();
  
  const [allItems, setAllItems] = useState<ResearchLibraryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize] = useState<number>(DEFAULT_PAGE_SIZE);
  const [hasNextPage, setHasNextPage] = useState<boolean>(true);
  const [initialLoadComplete, setInitialLoadComplete] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  
  // Filter state
  const [filters, setFilters] = useState<FilterState>({
    fromDate: null,
    toDate: null,
    search: ''
  });
  const [showFilters, setShowFilters] = useState<boolean>(false);
  const [appliedFilters, setAppliedFilters] = useState<FilterState>({
    fromDate: null,
    toDate: null,
    search: ''
  });

  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState<boolean>(false);
  const [itemToDelete, setItemToDelete] = useState<ResearchLibraryItem | null>(null);
  const [deleting, setDeleting] = useState<boolean>(false);

  // Detail view state
  const [detailDialogOpen, setDetailDialogOpen] = useState<boolean>(false);
  const [selectedItem, setSelectedItem] = useState<ResearchLibraryItem | null>(null);

  const loader = useRef<HTMLDivElement>(null);

  // Helper function to extract and process thinking content
  const processThinkingContent = (content: string) => {
    if (!content) return { cleanContent: '', thinkingContent: null };
    
    // Look for <think> and </think> tags
    const thinkRegex = /<think>([\s\S]*?)<\/think>/gi;
    const matches = content.match(thinkRegex);
    
    if (matches) {
      // Extract thinking content (remove the tags)
      const thinkingContent = matches.map(match => 
        match.replace(/<\/?think>/gi, '').trim()
      ).join('\n\n');
      
      // Remove thinking content from the main content
      const cleanContent = content.replace(thinkRegex, '').trim();
      
      return { cleanContent, thinkingContent };
    }
    
    return { cleanContent: content, thinkingContent: null };
  };

  const fetchLibraryItems = useCallback(async (page: number, size: number, isInitialLoad: boolean = false) => {
    if (!hasNextPage && !isInitialLoad) return;
    
    if (isInitialLoad) {
      setLoading(true);
    } else {
      setLoadingMore(true);
    }
    setError(null);
    
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: size.toString(),
      });
      
      if (appliedFilters.search) params.append('query', appliedFilters.search);
      if (appliedFilters.fromDate) params.append('from_date', appliedFilters.fromDate.toISOString().split('T')[0]);
      if (appliedFilters.toDate) params.append('to_date', appliedFilters.toDate.toISOString().split('T')[0]);

      const response = await fetch(`/api/research-agent/library?${params}`);

      if (!response.ok) {
        throw new Error('Failed to fetch research library');
      }

      const data = await response.json();
      
      setAllItems(prevItems => isInitialLoad ? data.results : [...prevItems, ...data.results]);
      setCurrentPage(data.current_page + 1);
      setHasNextPage(data.has_next);
      if (!initialLoadComplete) setInitialLoadComplete(true);
    } catch (err) {
      console.error("Error fetching research library:", err);
      setError('Failed to fetch research library. Please try again.');
    }
    
    if (isInitialLoad) {
      setLoading(false);
    } else {
      setLoadingMore(false);
    }
  }, [hasNextPage, initialLoadComplete, appliedFilters]);

  const resetAndFetch = useCallback(() => {
    setAllItems([]);
    setCurrentPage(1);
    setHasNextPage(true);
    setInitialLoadComplete(false);
  }, []);

  useEffect(() => {
    resetAndFetch();
  }, [appliedFilters, resetAndFetch]);

  useEffect(() => {
    if (!initialLoadComplete) {
      fetchLibraryItems(1, pageSize, true);
    }
  }, [pageSize, fetchLibraryItems, initialLoadComplete]);

  // Infinite scroll observer
  useEffect(() => {
    let isRequestInProgress = false;
    
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && 
            !loading && 
            !loadingMore && 
            !isRequestInProgress && 
            hasNextPage && 
            initialLoadComplete) {
          
          isRequestInProgress = true;
          fetchLibraryItems(currentPage, pageSize).finally(() => {
            isRequestInProgress = false;
          });
        }
      },
      { threshold: 0.1, rootMargin: '200px' }
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
  }, [loading, loadingMore, hasNextPage, currentPage, pageSize, fetchLibraryItems, initialLoadComplete]);

  const handleViewModeChange = (_event: React.MouseEvent<HTMLElement>, newViewMode: ViewMode | null) => {
    if (newViewMode !== null) {
      setViewMode(newViewMode);
    }
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
    const resetFilters = {
      fromDate: null,
      toDate: null,
      search: ''
    };
    setFilters(resetFilters);
    setAppliedFilters(resetFilters);
  };

  const handleDeleteClick = (item: ResearchLibraryItem) => {
    setItemToDelete(item);
    setDeleteDialogOpen(true);
  };

  const openDetailView = async (item: ResearchLibraryItem) => {
    try {
      // Fetch full details for this review
      const response = await fetch(`/api/research-agent/reviews/${item.id}`);
      if (!response.ok) {
        throw new Error('Failed to fetch review details');
      }
      const fullReview = await response.json();
      
      // Merge the full data with the item
      const enrichedItem = {
        ...item,
        report_text: fullReview.report_text,
        activity_log: fullReview.activity_log || []
      };
      
      setSelectedItem(enrichedItem);
      setDetailDialogOpen(true);
    } catch (err) {
      console.error("Error fetching review details:", err);
      setError('Failed to load review details. Please try again.');
      // Still show the dialog with basic data
      setSelectedItem(item);
      setDetailDialogOpen(true);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!itemToDelete) return;
    
    setDeleting(true);
    try {
      const response = await fetch(`/api/research-agent/reviews/${itemToDelete.id}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete review');
      }

      setAllItems(prevItems => prevItems.filter(item => item.id !== itemToDelete.id));
      setDeleteDialogOpen(false);
      setItemToDelete(null);
    } catch (err) {
      console.error("Error deleting review:", err);
      setError('Failed to delete review. Please try again.');
    }
    setDeleting(false);
  };

  const hasActiveFilters = useMemo(() => {
    return appliedFilters.fromDate !== null || 
           appliedFilters.toDate !== null || 
           appliedFilters.search !== '';
  }, [appliedFilters]);

  const getActiveFilterChips = () => {
    const chips = [];
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

  if (loading && allItems.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error && allItems.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>
        <Button onClick={() => fetchLibraryItems(1, pageSize, true)} sx={{ mt: 2 }}>Retry</Button>
      </Box>
    );
  }

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ position: 'relative', minHeight: '100vh' }}>
        {/* Fixed Header */}
        <Box sx={{ 
          position: 'fixed',
          top: '84px',
          left: `${currentDrawerWidth}px`,
          right: 0,
          zIndex: 1100,
          backgroundColor: 'background.default',
          boxShadow: 1,
          transition: 'left 0.3s',
        }}>
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
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <ScienceIcon fontSize="large" color="primary" />
              <Typography variant="h4" component="div">
                Research Library
              </Typography>
            </Box>
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
            <Box sx={{ 
              backgroundColor: 'background.default',
              borderBottom: 1,
              borderColor: 'divider'
            }}>
              <Card sx={{ borderRadius: 0, boxShadow: 'none', backgroundColor: 'transparent' }}>
                <CardContent sx={{ py: 2, px: 3 }}>
                  <Typography variant="h6" sx={{ mb: 2 }}>
                    Filter Research Library
                  </Typography>
                  
                  <Box sx={{ mb: 2 }}>
                    <TextField
                      fullWidth
                      size="small"
                      label="Search research questions and summaries"
                      value={filters.search}
                      onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                      onKeyDown={handleSearchKeyDown}
                      placeholder="Enter keywords..."
                      sx={{ mb: 2 }}
                    />
                    <Grid container spacing={2}>
                      <Grid size={{ xs: 12, md: 6 }}>
                        <DatePicker
                          label="From Date"
                          value={filters.fromDate}
                          onChange={(newValue) => setFilters(prev => ({ ...prev, fromDate: newValue }))}
                          slotProps={{ textField: { fullWidth: true, size: 'small' } }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, md: 6 }}>
                        <DatePicker
                          label="To Date"
                          value={filters.toDate}
                          onChange={(newValue) => setFilters(prev => ({ ...prev, toDate: newValue }))}
                          slotProps={{ textField: { fullWidth: true, size: 'small' } }}
                          minDate={filters.fromDate || undefined}
                        />
                      </Grid>
                    </Grid>
                  </Box>

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

          {/* Active Filter Chips */}
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

        {/* Content Area */}
        <Box sx={{ p: 3, pt: '200px' }}>
          {viewMode === 'grid' ? (
            <Grid container spacing={3} sx={{ mb: 3 }}>
              {allItems.map((item) => (
                <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={item.id}>
                  <Paper
                    elevation={2}
                    sx={{
                      p: 2,
                      height: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      position: 'relative',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease-in-out',
                      '&:hover': {
                        elevation: 4,
                        backgroundColor: alpha(theme.palette.primary.main, 0.02),
                        transform: 'translateY(-2px)'
                      }
                    }}
                    onClick={() => openDetailView(item)}
                  >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                      <Typography variant="h6" sx={{ fontWeight: 600, flex: 1, fontSize: '1rem' }}>
                        {item.short_summary}
                      </Typography>
                      <Tooltip title="Delete Review">
                        <IconButton 
                          size="small" 
                          color="error" 
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteClick(item);
                          }}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                    
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        display: '-webkit-box',
                        WebkitLineClamp: 3,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        mb: 2,
                        flex: 1
                      }}
                    >
                      {item.research_question}
                    </Typography>

                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 2 }}>
                      {item.themes.map((theme) => (
                        <Chip key={theme} label={theme} size="small" variant="outlined" />
                      ))}
                    </Box>

                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 'auto' }}>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Chip size="small" label={`${item.sources_count} sources`} />
                        {item.has_report && <Chip size="small" label="Report" color="success" />}
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {new Date(item.created_ts).toLocaleDateString()}
                      </Typography>
                    </Box>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          ) : (
            <Box sx={{ mb: 3 }}>
              {allItems.map((item) => (
                <Paper 
                  key={item.id} 
                  elevation={1} 
                  sx={{ 
                    p: 2, 
                    mb: 2,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease-in-out',
                    '&:hover': {
                      elevation: 3,
                      backgroundColor: alpha(theme.palette.primary.main, 0.02)
                    }
                  }}
                  onClick={() => openDetailView(item)}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
                        {item.short_summary}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        {item.research_question}
                      </Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {item.themes.map((theme) => (
                            <Chip key={theme} label={theme} size="small" variant="outlined" />
                          ))}
                        </Box>
                        <Chip size="small" label={`${item.sources_count} sources`} />
                        {item.has_report && <Chip size="small" label="Report" color="success" />}
                        <Typography variant="caption" color="text.secondary">
                          {new Date(item.created_ts).toLocaleDateString()}
                        </Typography>
                      </Box>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 1, ml: 2 }}>
                      <Tooltip title="Delete Review">
                        <IconButton 
                          color="error" 
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteClick(item);
                          }}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </Box>
                </Paper>
              ))}
            </Box>
          )}

          {/* Infinite scroll loader */}
          <div ref={loader} style={{ height: '100px', margin: '40px 0' }}>
            {loadingMore && (
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={24} />
                <Typography variant="body2" color="text.secondary">
                  Loading more research...
                </Typography>
              </Box>
            )}
          </div>

          {!loading && !hasNextPage && initialLoadComplete && allItems.length > 0 && (
            <Typography textAlign="center" sx={{ my: 2 }}>
              You've reached the end of your research library.
            </Typography>
          )}

          {!loading && !hasNextPage && initialLoadComplete && allItems.length === 0 && (
            <Alert severity="info" sx={{ mt: 2 }}>
              No research found. Start by running some research queries!
            </Alert>
          )}
        </Box>

        {/* Research Detail Dialog */}
        <Dialog
          open={detailDialogOpen}
          onClose={() => setDetailDialogOpen(false)}
          maxWidth="lg"
          fullWidth
          keepMounted={false}
          aria-labelledby="research-detail-dialog-title"
        >
          <DialogTitle id="research-detail-dialog-title" sx={{ pb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <ScienceIcon color="primary" />
                <Typography variant="h5" component="h2" sx={{ fontWeight: 'bold' }}>
                  Research Details
                </Typography>
              </Box>
              <IconButton
                onClick={() => setDetailDialogOpen(false)}
                aria-label="Close dialog"
              >
                <CloseIcon />
              </IconButton>
            </Box>
          </DialogTitle>
          
          <DialogContent sx={{ pt: 0 }}>
            {selectedItem && (
              <Box>
                {/* Research Question */}
                <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                    Research Question
                  </Typography>
                  <Typography variant="body1" sx={{ lineHeight: 1.6 }}>
                    {selectedItem.research_question}
                  </Typography>
                </Paper>

                {/* Summary */}
                <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                    Summary
                  </Typography>
                  <Typography variant="body1" sx={{ lineHeight: 1.6 }}>
                    {selectedItem.short_summary}
                  </Typography>
                </Paper>

                {/* Themes and Metadata */}
                <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                    Research Metadata
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, sm: 6 }}>
                      <Typography variant="body2" color="text.secondary">
                        <strong>Sources Found:</strong>
                      </Typography>
                      <Typography variant="body1" sx={{ mb: 2 }}>
                        {selectedItem.sources_count} sources
                      </Typography>
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                      <Typography variant="body2" color="text.secondary">
                        <strong>Created:</strong>
                      </Typography>
                      <Typography variant="body1" sx={{ mb: 2 }}>
                        {new Date(selectedItem.created_ts).toLocaleString()}
                      </Typography>
                    </Grid>
                    {selectedItem.themes && selectedItem.themes.length > 0 && (
                      <Grid size={{ xs: 12 }}>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          <strong>Key Themes:</strong>
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                          {selectedItem.themes.map((theme, index) => (
                            <Chip key={index} label={theme} color="primary" variant="outlined" />
                          ))}
                        </Box>
                      </Grid>
                    )}
                    <Grid size={{ xs: 12 }}>
                      <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                        {selectedItem.has_report && (
                          <Chip label="Full Report Available" color="success" />
                        )}
                        <Chip label={`${selectedItem.sources_count} Sources`} variant="outlined" />
                      </Box>
                    </Grid>
                  </Grid>
                </Paper>

                                 {/* Full Report */}
                 {selectedItem.report_text && selectedItem.report_text.trim() && (() => {
                   const { cleanContent, thinkingContent } = processThinkingContent(selectedItem.report_text);
                   return (
                     <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
                       <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                         Full Research Report
                       </Typography>
                       
                       {/* Main report content without thinking */}
                       {cleanContent && (
                         <Box 
                           sx={{ 
                             '& h1, & h2, & h3, & h4, & h5, & h6': {
                               fontWeight: 'bold',
                               margin: '16px 0 8px 0',
                               '&:first-of-type': { marginTop: 0 }
                             },
                             '& h1': { fontSize: '1.5rem' },
                             '& h2': { fontSize: '1.25rem' },
                             '& h3': { fontSize: '1.1rem' },
                             '& p': {
                               margin: '8px 0',
                               lineHeight: 1.6
                             },
                             '& ul, & ol': {
                               margin: '8px 0',
                               paddingLeft: '24px'
                             },
                             '& li': {
                               margin: '4px 0'
                             },
                             '& code': {
                               backgroundColor: 'rgba(0, 0, 0, 0.05)',
                               padding: '2px 4px',
                               borderRadius: '4px',
                               fontFamily: 'monospace',
                               fontSize: '0.9em'
                             },
                             '& pre': {
                               backgroundColor: 'rgba(0, 0, 0, 0.05)',
                               padding: '12px',
                               borderRadius: '4px',
                               overflow: 'auto',
                               fontFamily: 'monospace'
                             },
                             '& blockquote': {
                               borderLeft: '4px solid',
                               borderColor: 'primary.main',
                               paddingLeft: '16px',
                               margin: '16px 0',
                               fontStyle: 'italic'
                             },
                             mb: thinkingContent ? 2 : 0
                           }}
                         >
                           <ReactMarkdown remarkPlugins={[remarkGfm]}>
                             {cleanContent}
                           </ReactMarkdown>
                         </Box>
                       )}
                       
                       {/* Thinking content in collapsible section */}
                       {thinkingContent && (
                         <CollapsibleContent
                           content={thinkingContent}
                           type="thinking"
                           defaultExpanded={false}
                         />
                       )}
                     </Paper>
                   );
                 })()}

                {/* Activity Log */}
                {selectedItem.activity_log && selectedItem.activity_log.length > 0 && (
                  <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                      Research Activity Log
                    </Typography>
                    <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
                      {selectedItem.activity_log.map((activity, index) => (
                        <Box key={index} sx={{ mb: 2, pb: 2, borderBottom: index < selectedItem.activity_log!.length - 1 ? 1 : 0, borderColor: 'divider' }}>
                          <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                            {activity.step_name || activity.action || `Step ${index + 1}`}
                          </Typography>
                                                     {activity.message && (() => {
                             const { cleanContent, thinkingContent } = processThinkingContent(activity.message);
                             return (
                               <Box sx={{ mb: 1 }}>
                                 {cleanContent && (
                                   <Typography variant="body2" color="text.secondary" sx={{ mb: thinkingContent ? 1 : 0 }}>
                                     {cleanContent}
                                   </Typography>
                                 )}
                                 {thinkingContent && (
                                   <CollapsibleContent
                                     content={thinkingContent}
                                     type="thinking"
                                     defaultExpanded={false}
                                   />
                                 )}
                               </Box>
                             );
                           })()}
                                                     {activity.data && (
                             <Box sx={{ ml: 2 }}>
                               {activity.data.thinking && (() => {
                                 const { cleanContent, thinkingContent } = processThinkingContent(activity.data.thinking);
                                 return (
                                   <Box>
                                     {cleanContent && (
                                       <Typography variant="body2" sx={{ mb: 1, lineHeight: 1.6 }}>
                                         {cleanContent}
                                       </Typography>
                                     )}
                                     {thinkingContent && (
                                       <CollapsibleContent
                                         content={thinkingContent}
                                         type="thinking"
                                         defaultExpanded={false}
                                       />
                                     )}
                                   </Box>
                                 );
                               })()}
                               {activity.data.queries && (
                                 <Box sx={{ mb: 1 }}>
                                   <Typography variant="caption" color="text.secondary">
                                     <strong>Queries:</strong> {Array.isArray(activity.data.queries) ? activity.data.queries.join(', ') : activity.data.queries}
                                   </Typography>
                                 </Box>
                               )}
                               {activity.data.sources_found && (
                                 <Box sx={{ mb: 1 }}>
                                   <Typography variant="caption" color="text.secondary">
                                     <strong>Sources Found:</strong> {activity.data.sources_found}
                                   </Typography>
                                 </Box>
                               )}
                               {activity.data.total_sources && (
                                 <Box sx={{ mb: 1 }}>
                                   <Typography variant="caption" color="text.secondary">
                                     <strong>Total Sources:</strong> {activity.data.total_sources}
                                   </Typography>
                                 </Box>
                               )}
                             </Box>
                           )}
                          {activity.timestamp && (
                            <Typography variant="caption" color="text.secondary">
                              {new Date(activity.timestamp).toLocaleString()}
                            </Typography>
                          )}
                        </Box>
                      ))}
                    </Box>
                  </Paper>
                )}
              </Box>
            )}
          </DialogContent>

          <DialogActions>
            <Button onClick={() => setDetailDialogOpen(false)}>
              Close
            </Button>
            {selectedItem && (
              <Button
                onClick={() => {
                  setDetailDialogOpen(false);
                  handleDeleteClick(selectedItem);
                }}
                color="error"
                startIcon={<DeleteIcon />}
              >
                Delete
              </Button>
            )}
          </DialogActions>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <Dialog
          open={deleteDialogOpen}
          onClose={() => !deleting && setDeleteDialogOpen(false)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Delete Research Review</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to delete this research review?
              <br />
              <strong>"{itemToDelete?.short_summary}"</strong>
              <br />
              This action cannot be undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteDialogOpen(false)} disabled={deleting}>
              Cancel
            </Button>
            <Button onClick={handleDeleteConfirm} color="error" disabled={deleting}>
              {deleting ? <CircularProgress size={20} /> : 'Delete'}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </LocalizationProvider>
  );
};

export default ResearchLibrary; 