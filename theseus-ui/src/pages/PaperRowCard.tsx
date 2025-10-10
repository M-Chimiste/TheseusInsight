import React, { useState } from 'react';
import {
    Card,
    CardContent,
    Typography,
    Box,
    Link,
    Collapse,
    Chip,
    Button,
    Switch,
    FormControlLabel,
    TextField,
    Stack,
    IconButton
} from '@mui/material';
import { styled } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import SearchIcon from '@mui/icons-material/Search';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import EditIcon from '@mui/icons-material/Edit';
import type { PaperApiResponse } from '../services/api'; // Assuming PaperApiResponse is in services/api
import { papersApi } from '../services/api';

interface PaperRowCardProps {
  paper: PaperApiResponse;
  onFindSimilar?: (paper: PaperApiResponse) => void;
  onOpenMindMap?: (paper: PaperApiResponse) => void;
  onTopicClick?: (topicId: number) => void;
  hasProfilesSelected?: boolean;
  onPaperUpdated?: (paper: PaperApiResponse) => void;
  selectedProfileIds?: number[];
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

const PaperRowCard: React.FC<PaperRowCardProps> = ({ paper, onFindSimilar, onOpenMindMap, onTopicClick, hasProfilesSelected = false, onPaperUpdated, selectedProfileIds }) => {
  const [expanded, setExpanded] = useState(false);
  const [localScore, setLocalScore] = useState<number>(paper.score ?? paper.profile_score ?? 0);
  const [localRelated, setLocalRelated] = useState<boolean>(paper.related ?? false);
  const [saving, setSaving] = useState<boolean>(false);
  const [editing, setEditing] = useState<boolean>(false);
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
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', minWidth: '120px', width: '240px' }}>
          <Chip 
            label={hasProfilesSelected && paper.profile_score !== undefined 
              ? `Profile Score: ${paper.profile_score.toFixed(2)}` 
              : `Score: ${typeof paper.score === 'number' ? paper.score.toFixed(2) : '—'}`} 
            size="small" 
            color="primary" 
            variant="outlined" 
            sx={{ 
              mb: 1,
              borderColor: theme => theme.palette.mode === 'dark' ? theme.palette.primary.main : undefined,
              color: theme => theme.palette.mode === 'dark' ? theme.palette.common.white : theme.palette.primary.main,
            }} 
          />
          {/* Related status visual (no change here) */}
          {paper.related !== undefined && hasProfilesSelected && (
             <Chip 
                label={paper.related ? "Relevant" : "Not Relevant"} 
                color={paper.related ? "success" : "default"} 
                size="small"
                sx={{mb: 1, width: '100%'}}
             />
          )}
          {!hasProfilesSelected && (
             <Chip 
                label="Not Applicable" 
                color="default" 
                size="small"
                sx={{mb: 1, width: '100%'}}
             />
          )}
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1}}>
            <Typography variant="body2" color="text.secondary">
              {paper.date}
            </Typography>
            {!editing ? (
              <IconButton
                aria-label="edit"
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  const initialScore = (hasProfilesSelected && typeof (paper as any).profile_score === 'number')
                    ? (paper as any).profile_score as number
                    : paper.score;
                  setLocalScore(initialScore ?? 0);
                  setLocalRelated(paper.related ?? false);
                  setEditing(true);
                }}
              >
                <EditIcon />
              </IconButton>
            ) : (
              <Stack direction="row" spacing={1} alignItems="center">
                <Button
                  variant="outlined"
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditing(false);
                    setLocalScore(paper.score ?? paper.profile_score ?? 0);
                    setLocalRelated(paper.related ?? false);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  variant="contained"
                  size="small"
                  disabled={saving}
                  onClick={async (e) => {
                    e.stopPropagation();
                    let nextScore = localScore;
                    const nextRelated = localRelated;
                    if (nextRelated === false) {
                      nextScore = 0;
                      setLocalScore(0);
                    }
                    try {
                      setSaving(true);
                      const payload: any = { score: nextScore, related: nextRelated };
                      if (hasProfilesSelected && selectedProfileIds && selectedProfileIds.length > 0) {
                        payload.profile_ids = selectedProfileIds;
                      }
                      const updated = await papersApi.updatePaper(paper.id, payload);
                      setLocalScore(updated.score ?? updated.profile_score ?? 0);
                      setLocalRelated(updated.related ?? false);
                      setEditing(false);
                      onPaperUpdated && onPaperUpdated(updated);
                    } catch (err) {
                      console.error('Failed to save paper update', err);
                    } finally {
                      setSaving(false);
                    }
                  }}
                >
                  Save
                </Button>
              </Stack>
            )}
          </Box>
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
          {/* Editing controls for base paper fields (shown only in edit mode) */}
          {editing && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, mt: 1 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={localRelated}
                    onChange={(e) => {
                      e.stopPropagation();
                      const nextRelated = e.target.checked;
                      setLocalRelated(nextRelated);
                      if (nextRelated === false) {
                        setLocalScore(0);
                      }
                    }}
                    disabled={saving}
                  />
                }
                label={localRelated ? 'Relevant' : 'Not Relevant'}
              />

              <Stack direction="row" spacing={1} alignItems="center">
                <TextField
                  label="Score (0-10)"
                  type="number"
                  size="small"
                  value={localScore}
                  onChange={(e) => {
                    const val = Number(e.target.value);
                    if (!Number.isNaN(val)) setLocalScore(val);
                  }}
                  inputProps={{ step: 0.1, min: 0, max: 10 }}
                  sx={{ width: 140 }}
                />
              </Stack>
            </Box>
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