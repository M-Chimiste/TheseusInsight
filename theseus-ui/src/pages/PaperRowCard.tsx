import React, { useState } from 'react';
import {
    Card,
    CardContent,
    Typography,
    Box,
    Link,
    Collapse,
    Chip,
    Button
} from '@mui/material';
import { styled } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import SearchIcon from '@mui/icons-material/Search';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import type { PaperApiResponse } from '../services/api'; // Assuming PaperApiResponse is in services/api

interface PaperRowCardProps {
  paper: PaperApiResponse;
  onFindSimilar?: (paper: PaperApiResponse) => void;
  onOpenMindMap?: (paper: PaperApiResponse) => void;
  onTopicClick?: (topicId: number) => void;
  hasProfilesSelected?: boolean;
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

const PaperRowCard: React.FC<PaperRowCardProps> = ({ paper, onFindSimilar, onOpenMindMap, onTopicClick, hasProfilesSelected = false }) => {
  const [expanded, setExpanded] = useState(false);
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
            label={hasProfilesSelected && paper.profile_score !== undefined 
              ? `Profile Score: ${paper.profile_score.toFixed(2)}` 
              : `Score: ${paper.score.toFixed(2)}`} 
            size="small" 
            color="primary" 
            variant="outlined" 
            sx={{ 
              mb: 1,
              borderColor: theme => theme.palette.mode === 'dark' ? theme.palette.primary.main : undefined,
              color: theme => theme.palette.mode === 'dark' ? theme.palette.common.white : theme.palette.primary.main,
            }} 
          />
          {paper.related !== undefined && hasProfilesSelected && (
             <Chip 
                label={paper.related ? "Relevant" : "Not Relevant"} 
                color={paper.related ? "success" : "default"} 
                size="small"
                sx={{mb: 1, width: '100%'}} // Make chip full width of its container
             />
          )}
          {!hasProfilesSelected && (
             <Chip 
                label="Not Applicable" 
                color="default" 
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
          {paper.related !== undefined && hasProfilesSelected && (
             <Chip 
               label={paper.related ? "Considered Relevant" : "Considered Not Relevant"} 
               color={paper.related ? "success" : "default"} 
               sx={{mb:1}}
             />
          )}
          {!hasProfilesSelected && (
             <Chip 
               label="Not Applicable - No Profile Selected" 
               color="default" 
               sx={{mb:1}}
             />
          )}
          {Array.isArray(paper.keywords) && paper.keywords.length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
              {paper.keywords.slice(0,5).map((kw)=> (
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
          <Typography variant="body2" sx={{mt:2}}>
            <Link href={paper.url} target="_blank" rel="noopener noreferrer">
              View on ArXiv
            </Link>
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
            {onFindSimilar && (
              <Button
                variant="outlined"
                color="primary"
                startIcon={<SearchIcon />}
                onClick={(e) => {
                  e.stopPropagation();
                  onFindSimilar(paper);
                }}
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
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenMindMap(paper);
                }}
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

export default PaperRowCard; 