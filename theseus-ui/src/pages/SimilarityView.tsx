import React, { useState, useEffect, useCallback} from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Tooltip,
  Button
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CloseIcon from '@mui/icons-material/Close';
import DownloadIcon from '@mui/icons-material/Download';
import { papersApi } from '../services/api';
import type { PaperApiResponse, SimilarPapersResponse } from '../services/api';
import PaperRowCard from './PaperRowCard';
import ReferencePaperCard from './ReferencePaperCard';
import { useLayout } from '../contexts/LayoutContext';

interface SimilarityViewProps {
  referencePaper: PaperApiResponse;
  onClose: () => void;
}

const SimilarityView: React.FC<SimilarityViewProps> = ({ referencePaper, onClose }) => {
  const [similarPapers, setSimilarPapers] = useState<PaperApiResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState<number>(10);
  
  // Get layout context
  const { headerHeight } = useLayout();


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

  // Export similar papers to CSV
  const handleExportCSV = () => {
    // Helper to escape CSV values (handle commas, quotes, newlines)
    const escapeCSV = (value: string): string => {
      if (value.includes(',') || value.includes('"') || value.includes('\n')) {
        return `"${value.replace(/"/g, '""')}"`;
      }
      return value;
    };

    // Format date for display
    const formatDate = (dateStr: string): string => {
      try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { 
          year: 'numeric', 
          month: 'short', 
          day: 'numeric' 
        });
      } catch {
        return dateStr;
      }
    };

    // Build CSV content
    const headers = ['Title', 'Published Date', 'URL', 'Similarity Score'];
    const rows: string[][] = [];

    // Add seed paper as first row
    rows.push([
      escapeCSV(referencePaper.title),
      escapeCSV(formatDate(referencePaper.date)),
      referencePaper.url,
      'Seed Paper'
    ]);

    // Add similar papers
    similarPapers.forEach((paper) => {
      const similarityPercent = `${((paper.similarity_score ?? 0) * 100).toFixed(1)}%`;
      rows.push([
        escapeCSV(paper.title),
        escapeCSV(formatDate(paper.date)),
        paper.url,
        similarityPercent
      ]);
    });

    // Combine headers and rows
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    // Create and trigger download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    
    // Create filename from reference paper title (sanitized)
    const sanitizedTitle = referencePaper.title
      .replace(/[^a-zA-Z0-9\s]/g, '')
      .replace(/\s+/g, '_')
      .substring(0, 50);
    link.download = `similar_papers_${sanitizedTitle}.csv`;
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (loading && similarPapers.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      {/* Header with close button and controls - FIXED */}
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        px: 2, 
        py: 1, 
        borderBottom: 1, 
        borderColor: 'divider',
        backgroundColor: 'background.paper',
        minHeight: 'auto',
        position: 'fixed',
        top: `${headerHeight}px`,
        left: 0,
        right: 0,
        zIndex: 999
      }}>
        <Typography variant="h6" component="h1" sx={{ fontWeight: 600 }}>
          Similar Papers
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <FormControl size="small" sx={{ minWidth: 100 }}>
            <InputLabel id="limit-select-label">Show</InputLabel>
            <Select
              labelId="limit-select-label"
              id="limit-select"
              value={limit}
              label="Show"
              onChange={handleLimitChange}
            >
              <MenuItem value={10}>10</MenuItem>
              <MenuItem value={30}>30</MenuItem>
              <MenuItem value={50}>50</MenuItem>
              <MenuItem value={100}>100</MenuItem>
              <MenuItem value={200}>200</MenuItem>
            </Select>
          </FormControl>
          <Tooltip title="Export to CSV">
            <Button
              variant="outlined"
              size="small"
              startIcon={<DownloadIcon />}
              onClick={handleExportCSV}
              disabled={loading || similarPapers.length === 0}
              sx={{ textTransform: 'none' }}
            >
              Export
            </Button>
          </Tooltip>
          <Box sx={{ display: 'flex' }}>
            <IconButton onClick={onClose} aria-label="back to papers" size="small">
              <ArrowBackIcon />
            </IconButton>
            <IconButton onClick={onClose} aria-label="close" size="small">
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </Box>

      {/* Main content area - add top padding to account for fixed header */}
      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden', pt: '57px' }}>
        {/* Left side - Reference paper */}
        <Box sx={{ 
          width: '40%', 
          borderRight: 1, 
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto'
        }}>
          <Box sx={{ p: 1.5 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
              Reference Paper
            </Typography>
            <ReferencePaperCard paper={referencePaper} />
          </Box>
        </Box>

        {/* Right side - Similar papers - SCROLLABLE */}
        <Box sx={{ 
          width: '60%', 
          overflow: 'auto'
        }}>
          <Box sx={{ p: 1.5 }}>
            {loading && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
                <CircularProgress size={20} />
              </Box>
            )}
            
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
            {similarPapers.map((paper, index) => (
              <Box key={`${paper.id}_${paper.date_run}_similar_${index}`} sx={{ mb: 1.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                  <Typography variant="body2" color="primary" sx={{ fontWeight: 'bold', mr: 1 }}>
                    Similarity: {((paper.similarity_score ?? 0) * 100).toFixed(1)}%
                  </Typography>
                </Box>
                <PaperRowCard 
                  paper={paper} 
                  hideRelevanceChip={true}
                  hideScoreChip={true}
                />
              </Box>
            ))}
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default SimilarityView; 