import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  CardActionArea,
  Collapse,
  Link,
  Box,
  Chip,
  Tooltip,
  Button
} from '@mui/material';
import type { PaperApiResponse } from '../services/api'; // Assuming this path is correct
import { format } from 'date-fns';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import ScoreIcon from '@mui/icons-material/Stars'; // Example icon for score
import SearchIcon from '@mui/icons-material/Search';

interface PaperCardProps {
  paper: PaperApiResponse;
  onFindSimilar?: (paper: PaperApiResponse) => void;
}

const PaperCard: React.FC<PaperCardProps> = ({ paper, onFindSimilar }) => {
  const [expanded, setExpanded] = useState(false);

  const handleExpandClick = () => {
    setExpanded(!expanded);
  };

  const abstractSnippet = paper.abstract.length > 200 
    ? `${paper.abstract.substring(0, 200)}...` 
    : paper.abstract;

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardActionArea onClick={handleExpandClick} sx={{ flexGrow: 1}}>
        <CardContent>
          <Typography variant="h6" component="div" gutterBottom sx={{fontWeight: 'bold', color: theme => theme.palette.mode === 'dark' ? 'common.white' : 'text.primary'}}>
            {paper.title}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, gap: 0.5, flexWrap: 'wrap' }}>
            <ScoreIcon fontSize="small" color="action" />
            <Typography variant="body2" sx={{ color: theme => theme.palette.mode === 'dark' ? 'common.white' : 'text.secondary', mr: 1 }}>
              Score: {paper.score.toFixed(2)} 
            </Typography>
            {paper.related !== undefined && (
                <Chip 
                    label={paper.related ? "Relevant" : "Not Relevant"} 
                    color={paper.related ? "success" : "default"} 
                    size="small"
                    sx={{mr: 1}}
                />
            )}
            <Tooltip title={`Date Published: ${format(new Date(paper.date), 'MMM d, yyyy')}\nDate Processed: ${format(new Date(paper.date_run), 'MMM d, yyyy')}\nEmbedding Model: ${paper.embedding_model}`}>
                <InfoOutlinedIcon fontSize='small' color='action' sx={{ ml: 0.5}}/>
            </Tooltip>
          </Box>
          <Typography variant="body2" color="text.secondary" paragraph>
            Published: {format(new Date(paper.date), 'MMMM d, yyyy')}
          </Typography>
          {!expanded && (
            <Typography variant="body2" color="text.primary" paragraph>
              {abstractSnippet} {!expanded && paper.abstract.length > 200 && <Link component="span" sx={{cursor: 'pointer'}}>Read more</Link>}
            </Typography>
          )}
        </CardContent>
      </CardActionArea>
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <CardContent>
          <Typography variant="subtitle1" gutterBottom sx={{fontWeight: 'medium'}}>Full Abstract:</Typography>
          <Typography variant="body2" paragraph sx={{whiteSpace: 'pre-line'}}>
            {paper.abstract}
          </Typography>
          <Typography variant="subtitle1" gutterBottom sx={{fontWeight: 'medium', mt:2}}>Rationale:</Typography>
          <Typography variant="body2" paragraph sx={{whiteSpace: 'pre-line'}}>
            {paper.rationale}
          </Typography>
          {paper.related !== undefined && (
             <Chip label={paper.related ? "Considered Relevant" : "Considered Not Relevant"} color={paper.related ? "success" : "default"} sx={{mb:1}}/>
          )}
          <Typography variant="body2" sx={{mt:1}}>
            <Link href={paper.url} target="_blank" rel="noopener noreferrer">
              View on ArXiv
            </Link>
          </Typography>
          {onFindSimilar && (
            <Button
              variant="outlined"
              color="primary"
              startIcon={<SearchIcon />}
              onClick={() => onFindSimilar(paper)}
            >
              Find Similar
            </Button>
          )}
        </CardContent>
      </Collapse>
    </Card>
  );
};

export default PaperCard; 