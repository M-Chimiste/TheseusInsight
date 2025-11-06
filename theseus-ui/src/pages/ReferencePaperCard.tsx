import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Link,
  Chip,
  Tooltip,
  Divider
} from '@mui/material';
import type { PaperApiResponse } from '../services/api';
import { format } from 'date-fns';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import ScoreIcon from '@mui/icons-material/Stars';

interface ReferencePaperCardProps {
  paper: PaperApiResponse;
}

const ReferencePaperCard: React.FC<ReferencePaperCardProps> = ({ paper }) => {
  return (
    <Card sx={{ height: 'fit-content', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ pb: 1 }}>
        {/* Header Section */}
        <Typography variant="h6" component="div" gutterBottom sx={{
          fontWeight: 'bold', 
          color: theme => theme.palette.mode === 'dark' ? 'common.white' : 'text.primary',
          lineHeight: 1.3,
          mb: 1.5
        }}>
          {paper.title}
        </Typography>
        
        {/* Metadata Row */}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5, gap: 1, flexWrap: 'wrap' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <ScoreIcon fontSize="small" color="action" />
            <Chip 
              label={`Score: ${typeof paper.score === 'number' ? paper.score.toFixed(2) : '—'}`} 
              size="small" 
              color="primary" 
              variant="outlined"
            />
          </Box>
          
          {paper.related !== undefined && (
            <Chip 
              label={paper.related ? "Relevant" : "Not Relevant"} 
              color={paper.related ? "success" : "default"} 
              size="small"
            />
          )}
          
          <Tooltip title={`Date Published: ${format(new Date(paper.date), 'MMM d, yyyy')}\nDate Processed: ${format(new Date(paper.date_run), 'MMM d, yyyy')}\nEmbedding Model: ${paper.embedding_model}`}>
            <InfoOutlinedIcon fontSize='small' color='action' />
          </Tooltip>
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Published: {format(new Date(paper.date), 'MMMM d, yyyy')}
        </Typography>

        <Divider sx={{ my: 1.5 }} />
        
        {/* Body Content */}
        <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 'medium', mt: 1 }}>
          Abstract:
        </Typography>
        <Typography variant="body2" paragraph sx={{ 
          whiteSpace: 'pre-line', 
          mb: 2,
          lineHeight: 1.4
        }}>
          {paper.abstract}
        </Typography>
        
        <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 'medium' }}>
          Rationale:
        </Typography>
        <Typography variant="body2" paragraph sx={{ 
          whiteSpace: 'pre-line',
          mb: 2,
          lineHeight: 1.4
        }}>
          {paper.rationale}
        </Typography>
        
        {paper.related !== undefined && (
          <Chip 
            label={paper.related ? "Considered Relevant" : "Considered Not Relevant"} 
            color={paper.related ? "success" : "default"} 
            sx={{ mb: 1.5 }}
          />
        )}
        
        <Typography variant="body2">
          <Link href={paper.url} target="_blank" rel="noopener noreferrer">
            View on ArXiv
          </Link>
        </Typography>
      </CardContent>
    </Card>
  );
};

export default ReferencePaperCard; 