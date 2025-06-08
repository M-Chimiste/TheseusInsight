import React, { useState } from 'react';
import { Box, Typography, Collapse, IconButton, Chip } from '@mui/material';
import { ExpandMore as ExpandMoreIcon, ExpandLess as ExpandLessIcon, Psychology as ThinkingIcon } from '@mui/icons-material';

interface CollapsibleContentProps {
  content: string;
  type?: 'thinking' | 'generic';
  defaultExpanded?: boolean;
}

const CollapsibleContent: React.FC<CollapsibleContentProps> = ({ 
  content, 
  type = 'generic',
  defaultExpanded = false 
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const getLabel = () => {
    switch (type) {
      case 'thinking':
        return 'Chain of Thought';
      default:
        return 'Details';
    }
  };

  const getIcon = () => {
    switch (type) {
      case 'thinking':
        return <ThinkingIcon sx={{ fontSize: 16 }} />;
      default:
        return undefined;
    }
  };

  const getChipColor = () => {
    switch (type) {
      case 'thinking':
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <Box sx={{ my: 1 }}>
      <Box 
        sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 1, 
          cursor: 'pointer',
          '&:hover': {
            backgroundColor: 'action.hover'
          },
          p: 0.5,
          borderRadius: 1
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Chip
          icon={getIcon()}
          label={getLabel()}
          size="small"
          color={getChipColor()}
          variant="outlined"
        />
        <IconButton size="small">
          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Box>
      
      <Collapse in={expanded}>
        <Box sx={{ 
          p: 2, 
          backgroundColor: 'action.hover', 
          borderRadius: 1, 
          mt: 1,
          borderLeft: 3,
          borderColor: type === 'thinking' ? 'warning.main' : 'primary.main'
        }}>
          <Typography 
            variant="body2" 
            component="pre"
            sx={{ 
              whiteSpace: 'pre-wrap',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              lineHeight: 1.4
            }}
          >
            {content}
          </Typography>
        </Box>
      </Collapse>
    </Box>
  );
};

export default CollapsibleContent; 