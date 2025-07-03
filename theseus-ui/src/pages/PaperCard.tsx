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
import { useNavigate } from 'react-router-dom';
import type { PaperApiResponse } from '../services/api'; // Assuming this path is correct
import { format } from 'date-fns';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import ScoreIcon from '@mui/icons-material/Stars'; // Example icon for score
import SearchIcon from '@mui/icons-material/Search';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';

interface PaperCardProps {
  paper: PaperApiResponse;
  onFindSimilar?: (paper: PaperApiResponse) => void;
  onOpenMindMap?: (paper: PaperApiResponse) => void;
  onTopicClick?: (topicId: number) => void;
  initialExpanded?: boolean;
}

const PaperCard: React.FC<PaperCardProps> = ({ paper, onFindSimilar, onOpenMindMap, onTopicClick, initialExpanded = false }) => {
  const [expanded, setExpanded] = useState(initialExpanded);
  const navigate = useNavigate();

  const handleExpandClick = () => {
    setExpanded(!expanded);
  };

  const handleTopicClick = (topicId: number) => {
    if (onTopicClick) {
      // If a topic click handler is provided (e.g., for filtering current page), use it
      onTopicClick(topicId);
    } else {
      // Otherwise, navigate to trends page with topic filter
      navigate(`/trends?topic_id=${topicId}`);
    }
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
          {Array.isArray(paper.keywords) && paper.keywords.length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
              {paper.keywords.slice(0,5).map((kw) => (
                <Chip key={kw} label={kw} size="small" variant="outlined" sx={{ fontSize: '0.6rem', height: 18 }} />
              ))}
            </Box>
          )}
          {/* Topic tags placeholder - will be populated when backend includes topic data */}
          {(paper as any).topics && Array.isArray((paper as any).topics) && (paper as any).topics.length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
              <Typography variant="body2" color="text.secondary" sx={{ mr: 1, alignSelf: 'center' }}>
                Topics:
              </Typography>
              {(paper as any).topics.slice(0, 3).map((topic: any) => (
                <Chip 
                  key={topic.id} 
                  label={topic.label} 
                  size="small" 
                  color="primary"
                  variant="filled"
                  icon={<TrendingUpIcon />}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleTopicClick(topic.id);
                  }}
                  sx={{ fontSize: '0.7rem', height: 20, cursor: 'pointer' }} 
                />
              ))}
            </Box>
          )}
          {paper.related !== undefined && (
             <Chip label={paper.related ? "Considered Relevant" : "Considered Not Relevant"} color={paper.related ? "success" : "default"} sx={{mb:1}}/>
          )}
          <Typography variant="body2" sx={{mt:1}}>
            <Link href={paper.url} target="_blank" rel="noopener noreferrer">
              View on ArXiv
            </Link>
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
            {onFindSimilar && (
              <Button
                variant="outlined"
                color="primary"
                startIcon={<SearchIcon />}
                onClick={() => onFindSimilar(paper)}
                size="small"
              >
                Find Similar
              </Button>
            )}
            {onOpenMindMap && (
              <Button
                variant="outlined"
                color="secondary"
                startIcon={<AccountTreeIcon />}
                onClick={() => onOpenMindMap(paper)}
                size="small"
              >
                Mind Map
              </Button>
            )}
          </Box>
        </CardContent>
      </Collapse>
    </Card>
  );
};

export default PaperCard; 