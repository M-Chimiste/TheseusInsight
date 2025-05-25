import React, { useState, useEffect, useCallback} from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  IconButton,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CloseIcon from '@mui/icons-material/Close';
import { papersApi } from '../services/api';
import type { PaperApiResponse, SimilarPapersResponse } from '../services/api';
import PaperCard from './PaperCard';
import PaperRowCard from './PaperRowCard';

interface SimilarityViewProps {
  referencePaper: PaperApiResponse;
  onClose: () => void;
}

const SimilarityView: React.FC<SimilarityViewProps> = ({ referencePaper, onClose }) => {
  const [similarPapers, setSimilarPapers] = useState<PaperApiResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState<number>(10);
  const [totalSimilar, setTotalSimilar] = useState<number>(0);


  const fetchSimilarPapers = useCallback(async (selectedLimit: number) => {
    setLoading(true);
    setError(null);
    
    try {
      const response: SimilarPapersResponse = await papersApi.findSimilarPapers(
        referencePaper.id,
        selectedLimit,
        0.6 // Lower threshold to get more results
      );
      
      setSimilarPapers(response.similar_papers);
      setTotalSimilar(response.total_similar);
    } catch (err: any) {
      console.error("Error fetching similar papers:", err);
      
      // Provide more specific error messages
      if (err.response?.status === 422) {
        setError('Invalid request parameters. Please try a smaller limit.');
      } else if (err.response?.status === 404) {
        setError('Reference paper not found or has no embedding data.');
      } else if (err.response?.status >= 500) {
        setError('Server error occurred. Please try again later.');
      } else {
        setError('Failed to fetch similar papers. Please try again.');
      }
    }
    
    setLoading(false);
  }, [referencePaper.id]);

  // Initial fetch
  useEffect(() => {
    fetchSimilarPapers(limit);
  }, [fetchSimilarPapers, limit]);

  const handleLimitChange = (event: SelectChangeEvent<number>) => {
    const newLimit = event.target.value as number;
    setLimit(newLimit);
    // fetchSimilarPapers will be called automatically due to the useEffect dependency on limit
  };

  if (loading && similarPapers.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header with close button and controls */}
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        p: 2, 
        borderBottom: 1, 
        borderColor: 'divider',
        backgroundColor: 'background.paper'
      }}>
        <Typography variant="h5" component="h1">
          Similar Papers
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel id="limit-select-label">Show</InputLabel>
            <Select
              labelId="limit-select-label"
              id="limit-select"
              value={limit}
              label="Show"
              onChange={handleLimitChange}
            >
              <MenuItem value={10}>10 papers</MenuItem>
              <MenuItem value={30}>30 papers</MenuItem>
              <MenuItem value={50}>50 papers</MenuItem>
              <MenuItem value={100}>100 papers</MenuItem>
              <MenuItem value={200}>200 papers</MenuItem>
            </Select>
          </FormControl>
          <Box>
            <IconButton onClick={onClose} aria-label="back to papers">
              <ArrowBackIcon />
            </IconButton>
            <IconButton onClick={onClose} aria-label="close">
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </Box>

      {/* Main content area */}
      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left side - Reference paper */}
        <Box sx={{ 
          width: '40%', 
          p: 2, 
          borderRight: 1, 
          borderColor: 'divider',
          overflow: 'auto'
        }}>
          <Typography variant="h6" gutterBottom>
            Reference Paper
          </Typography>
          <PaperCard paper={referencePaper} />
        </Box>

        {/* Right side - Similar papers */}
        <Box sx={{ 
          width: '60%', 
          p: 2, 
          overflow: 'auto',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              Similar Papers ({similarPapers.length} of {totalSimilar} found)
            </Typography>
            {loading && (
              <CircularProgress size={20} />
            )}
          </Box>
          
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {similarPapers.length === 0 && !loading && (
            <Alert severity="info" sx={{ mb: 2 }}>
              No similar papers found for this paper.
            </Alert>
          )}

          {/* Similar papers list */}
          <Box sx={{ flex: 1 }}>
            {similarPapers.map((paper, index) => (
              <Box key={`${paper.id}_${paper.date_run}_similar_${index}`} sx={{ mb: 2 }}>
                <Paper elevation={1} sx={{ p: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <Typography variant="body2" color="primary" sx={{ fontWeight: 'bold', mr: 1 }}>
                      Similarity: {((paper.similarity_score || 0) * 100).toFixed(1)}%
                    </Typography>
                  </Box>
                  <PaperRowCard paper={paper} />
                </Paper>
              </Box>
            ))}
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default SimilarityView; 