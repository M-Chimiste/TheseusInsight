import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Grid,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material';
import { papersApi } from '../services/api';
import type { PaperApiResponse, PaginatedPapersResponse } from '../services/api';
import PaperCard from './PaperCard'; // Assuming PaperCard.tsx is in the same directory

const DEFAULT_PAGE_SIZE = 9; // 3 cards per row, 3 rows

const Papers: React.FC = () => {
  // Keep track of all fetched papers for infinite scroll
  const [allPapers, setAllPapers] = useState<PaperApiResponse[]>([]); 
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(DEFAULT_PAGE_SIZE);
  const [hasNextPage, setHasNextPage] = useState<boolean>(true); // Track if more pages are available
  const [initialLoadComplete, setInitialLoadComplete] = useState<boolean>(false);

  const loader = useRef<HTMLDivElement>(null); // For Intersection Observer

  const fetchPapers = useCallback(async (page: number, size: number, isInitialLoad: boolean = false) => {
    if (!hasNextPage && !isInitialLoad) return; // Don't fetch if no more pages, unless it's the very first load
    setLoading(true);
    setError(null);
    try {
      const data = await papersApi.getPapers(page, size, 'date', 'desc');
      setAllPapers(prevPapers => isInitialLoad ? data.items : [...prevPapers, ...data.items]);
      setCurrentPage(data.current_page + 1); // Prepare for the next page
      setHasNextPage(data.nextPage !== null);
      if (!initialLoadComplete) setInitialLoadComplete(true);
    } catch (err) {
      console.error("Error fetching papers:", err);
      setError('Failed to fetch papers. Please try again.');
    }
    setLoading(false);
  }, [hasNextPage, initialLoadComplete]);

  // Initial fetch
  useEffect(() => {
    setAllPapers([]); // Clear previous papers on page size change
    setCurrentPage(1); // Reset current page
    setHasNextPage(true); // Assume there's a next page
    setInitialLoadComplete(false); // Reset initial load flag
    // Trigger initial fetch by making fetchPapers depend on a changed value (e.g. an explicit fetch trigger state or by calling it directly)
    // For simplicity, we can call fetchPapers directly after resetting state.
    // The dependency array ensures this effect re-runs if pageSize changes. 
    // We will call fetchPapers(1, pageSize, true) directly within this useEffect for the first load.
  }, [pageSize]); // Re-run this effect when pageSize changes to reset and refetch

  useEffect(() => {
    if(!initialLoadComplete) { // Only run the first fetch, or when pageSize changes (covered by above useEffect)
        fetchPapers(1, pageSize, true);
    }
  }, [pageSize, fetchPapers, initialLoadComplete]); // Add initialLoadComplete to dependencies

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
    // Sort all accumulated papers
    return [...allPapers].sort((a, b) => b.score - a.score);
  }, [allPapers]);

  const handlePageSizeChange = (event: SelectChangeEvent<string>) => {
    const newPageSize = parseInt(event.target.value, 10);
    setPageSize(newPageSize);
    // The useEffect for pageSize will handle resetting and fetching
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
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2}}>
        <Typography variant="h4" gutterBottom component="div">
          Historical Papers
        </Typography>
        <FormControl sx={{ m: 1, minWidth: 120 }} size="small">
            <InputLabel id="page-size-select-label">Items per page</InputLabel>
            <Select<string>
                labelId="page-size-select-label"
                id="page-size-select"
                value={pageSize.toString()}
                label="Items per page"
                onChange={handlePageSizeChange}
            >
                <MenuItem value={"9"}>9</MenuItem>
                <MenuItem value={"15"}>15</MenuItem>
                <MenuItem value={"30"}>30</MenuItem>
                <MenuItem value={"60"}>60</MenuItem>
            </Select>
        </FormControl>
      </Box>
      
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {sortedPapers.map((paper) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={paper.id + "_" + paper.date_run}> {/* Ensure unique key if IDs can repeat across fetches, though unlikely with DB IDs */}
            <PaperCard paper={paper} />
          </Grid>
        ))}
      </Grid>

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
  );
};

export default Papers; 