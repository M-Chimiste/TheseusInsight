import React, { useState } from 'react';
import {
    Card,
    CardContent,
    Typography,
    Box,
    Link,
    Collapse,
    Chip
} from '@mui/material';
import { styled } from '@mui/material/styles';
import type { PaperApiResponse } from '../services/api'; // Assuming PaperApiResponse is in services/api

interface PaperRowCardProps {
  paper: PaperApiResponse;
}

const TruncatedTypography = styled(Typography)(() => ({
  display: '-webkit-box',
  WebkitBoxOrient: 'vertical',
  WebkitLineClamp: 2,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  maxHeight: '3em', // Approx 2 lines
  lineHeight: '1.5em' 
}));

const PaperRowCard: React.FC<PaperRowCardProps> = ({ paper }) => {
  const [expanded, setExpanded] = useState(false);

  const handleExpandClick = () => {
    setExpanded(!expanded);
  };

  return (
    <Card sx={{ display: 'flex', flexDirection: 'column', mb: 2, width: '100%' }}>
      <CardContent 
        sx={{ 
            flexGrow: 1, 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'flex-start',
            cursor: 'pointer'
        }}
        onClick={handleExpandClick}
      >
        <Box sx={{ flexGrow: 1, mr: 2 }}>
          <Typography variant="h6" component="div" gutterBottom sx={{ color: theme => theme.palette.mode === 'dark' ? 'common.white' : 'primary.main' }}>
            {paper.title}
          </Typography>
          <TruncatedTypography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {paper.abstract}
          </TruncatedTypography>
        </Box>
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', minWidth: '120px' }}>
          <Chip 
            label={`Score: ${paper.score.toFixed(2)}`} 
            size="small" 
            color="primary" 
            variant="outlined" 
            sx={{ 
              mb: 1,
              borderColor: theme => theme.palette.mode === 'dark' ? theme.palette.primary.main : undefined,
              color: theme => theme.palette.mode === 'dark' ? theme.palette.common.white : theme.palette.primary.main,
            }} 
          />
          {paper.related !== undefined && (
             <Chip 
                label={paper.related ? "Relevant" : "Not Relevant"} 
                color={paper.related ? "success" : "default"} 
                size="small"
                sx={{mb: 1, width: '100%'}} // Make chip full width of its container
             />
          )}
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1}}>
            {paper.date}
          </Typography>
        </Box>
      </CardContent>
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <CardContent sx={{ borderTop: '1px solid', borderColor: 'divider', pt: 2 }}>
          <Typography variant="subtitle2" gutterBottom>Full Abstract:</Typography>
          <Typography variant="body2" paragraph sx={{ whiteSpace: 'pre-line', maxHeight: '200px', overflowY: 'auto' }}>
            {paper.abstract}
          </Typography>
          {paper.rationale && (
            <>
              <Typography variant="subtitle2" gutterBottom sx={{mt:1}}>Rationale:</Typography>
              <Typography variant="body2" paragraph sx={{ whiteSpace: 'pre-line', maxHeight: '150px', overflowY: 'auto' }}>
                {paper.rationale}
              </Typography>
            </>
          )}
          <Typography variant="body2" sx={{mt:2}}>
            <Link href={paper.url} target="_blank" rel="noopener noreferrer">
              View on ArXiv
            </Link>
          </Typography>
        </CardContent>
      </Collapse>
    </Card>
  );
};

export default PaperRowCard; 