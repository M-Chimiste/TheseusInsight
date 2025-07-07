import React, { memo, useState } from 'react';
import { Handle, Position } from '@xyflow/react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  IconButton,
  Tooltip,
  Fade,
  Menu,
  MenuItem,
  useTheme,
  alpha,
  Collapse,
} from '@mui/material';
import {
  MoreVert as MoreVertIcon,
  Launch as LaunchIcon,
  AccountTree as ExpandIcon,
  DeleteOutline as DeleteIcon,
  Star as StarIcon,
  ReadMore as ReadMoreIcon,
  UnfoldLess as UnfoldLessIcon,
} from '@mui/icons-material';
import type { MindMapNode as MindMapNodeData } from '../services/api';

interface MindMapNodeProps {
  data: (MindMapNodeData & { colorIndex?: number }) & {
    isSelected: boolean;
    onExpand?: () => void;
    onDelete?: () => void;
  };
  selected?: boolean;
}

const MindMapNode: React.FC<MindMapNodeProps> = memo(({ data, selected }) => {
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const isMenuOpen = Boolean(anchorEl);

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleExpand = () => {
    data.onExpand?.();
    handleMenuClose();
  };

  const handleDelete = () => {
    data.onDelete?.();
    handleMenuClose();
  };

  const handleOpenUrl = () => {
    if (data.url) {
      window.open(data.url, '_blank', 'noopener,noreferrer');
    }
    handleMenuClose();
  };
  
  const toggleExpand = (event: React.MouseEvent) => {
    event.stopPropagation();
    setIsExpanded(!isExpanded);
  };

  // Use heat map color based on connection count
  const heatMapColor = (data as any).heatMapColor || theme.palette.primary.main;
  const connectionCount = (data as any).connectionCount || 0;

  const getNodeStyles = () => {
    const borderRadius = typeof theme.shape?.borderRadius === 'number' 
      ? theme.shape.borderRadius 
      : 4;
      
    const baseStyles = {
      minWidth: 200,
      maxWidth: 320,
      width: 'fit-content',
      border: `2px solid ${theme.palette.divider}`,
      borderRadius: borderRadius * 1.5,
      backgroundColor: theme.palette.background.paper,
      boxShadow: theme.shadows[1],
      transition: 'all 0.3s ease-in-out',
      cursor: 'pointer',
    };

    if (data.is_seed) {
      return {
        ...baseStyles,
        border: `3px solid ${heatMapColor}`,
        backgroundColor: alpha(heatMapColor, 0.1),
        boxShadow: theme.shadows[3],
        zIndex: 10,
      };
    }

    if (selected || data.isSelected) {
      return {
        ...baseStyles,
        border: `2px solid ${heatMapColor}`,
        backgroundColor: alpha(heatMapColor, 0.15),
        boxShadow: theme.shadows[2],
        zIndex: 5,
      };
    }

    return {
      ...baseStyles,
      border: `2px solid ${heatMapColor}`,
      backgroundColor: alpha(heatMapColor, 0.08),
      zIndex: 3,
    };
  };

  return (
    <>
      {/* Connection handles for all sides */}
      <Handle
        type="target"
        id="top"
        position={Position.Top}
        style={{ background: theme.palette.primary.main }}
      />
      <Handle
        type="source"
        id="top"
        position={Position.Top}
        style={{ background: theme.palette.primary.main }}
      />
      <Handle
        type="target"
        id="bottom"
        position={Position.Bottom}
        style={{ background: theme.palette.primary.main }}
      />
      <Handle
        type="source"
        id="bottom"
        position={Position.Bottom}
        style={{ background: theme.palette.primary.main }}
      />
      <Handle
        type="target"
        id="left"
        position={Position.Left}
        style={{ background: theme.palette.primary.main }}
      />
      <Handle
        type="source"
        id="left"
        position={Position.Left}
        style={{ background:theme.palette.primary.main }}
      />
      <Handle
        type="target"
        id="right"
        position={Position.Right}
        style={{ background: theme.palette.primary.main }}
      />
      <Handle
        type="source"
        id="right"
        position={Position.Right}
        style={{ background: theme.palette.primary.main }}
      />

      <Card sx={getNodeStyles()} onClick={toggleExpand}>
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
          {/* Header with title and menu */}
          <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 0.75 }}>
            <Box sx={{ flexGrow: 1, mr: 1 }}>
              <Typography
                variant="body2"
                sx={{
                  fontWeight: data.is_seed ? 'bold' : 'medium',
                  lineHeight: 1.2,
                  fontSize: '0.8rem',
                  color: data.is_seed 
                    ? theme.palette.primary.main 
                    : theme.palette.text.primary,
                }}
              >
                {data.title}
              </Typography>
            </Box>
            
            {/* Action icons */}
            <Tooltip title="Expand Node" TransitionComponent={Fade} TransitionProps={{ timeout: 0 }}>
              <IconButton
                size="small"
                onClick={(e) => { e.stopPropagation(); handleExpand(); }}
                sx={{ p: 0.25, opacity: 0.7, '&:hover': { opacity: 1 } }}
              >
                <ExpandIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {data.url && (
              <Tooltip title="Open Paper" TransitionComponent={Fade} TransitionProps={{ timeout: 0 }}>
                <IconButton
                  size="small"
                  onClick={(e) => { e.stopPropagation(); handleOpenUrl(); }}
                  sx={{ p: 0.25, opacity: 0.7, '&:hover': { opacity: 1 } }}
                >
                  <LaunchIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            {/* Fallback context menu for extra options */}
            <IconButton
              size="small"
              onClick={handleMenuClick}
              sx={{ 
                p: 0.25,
                opacity: 0.5,
                '&:hover': { opacity: 1 },
              }}
            >
              <MoreVertIcon fontSize="small" />
            </IconButton>
          </Box>

          {/* Collapsible content */}
          <Collapse in={isExpanded} timeout="auto" unmountOnExit>
            {/* Summary */}
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{
                mt: 0.5,
                mb: 0.75,
                lineHeight: 1,
                fontSize: '0.7rem',
                wordWrap: 'break-word',
                whiteSpace: 'normal',
              }}
            >
              {data.summary}
            </Typography>

            {/* Keywords */}
            {Array.isArray(data.keywords) && data.keywords.length > 0 && (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
                {data.keywords.slice(0,5).map((kw) => (
                  <Chip
                    key={kw}
                    label={kw}
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: '0.6rem', height: 18 }}
                  />
                ))}
              </Box>
            )}
          </Collapse>

          {/* Metadata chips */}
          <Box 
            sx={{ 
              display: 'flex', 
              flexWrap: 'wrap', 
              gap: 0.5, 
              mt: isExpanded ? 1 : 0.5,
              alignItems: 'center',
            }}
          >
            {!data.is_seed && (
              <Chip
                label={`${(data.similarity_score * 100).toFixed(0)}%`}
                size="small"
                color="primary"
                variant="outlined"
                sx={{ fontSize: '0.6rem', height: 18, minWidth: 'auto' }}
              />
            )}
            
            {/* Connection count indicator */}
            {connectionCount > 0 && (
              <Tooltip title={`${connectionCount} connection${connectionCount !== 1 ? 's' : ''}`} TransitionComponent={Fade} TransitionProps={{ timeout: 0 }}>
                <Chip
                  label={`${connectionCount}c`}
                  size="small"
                  variant="filled"
                  sx={{ 
                    fontSize: '0.6rem', 
                    height: 18, 
                    minWidth: 'auto',
                    backgroundColor: heatMapColor,
                    color: theme.palette.getContrastText(heatMapColor),
                  }}
                />
              </Tooltip>
            )}
            
            <Collapse in={isExpanded} timeout="auto" unmountOnExit>
              {data.has_fulltext && (
                <Chip
                  label="Full Text"
                  size="small"
                  color="success"
                  variant="outlined"
                  sx={{ fontSize: '0.6rem', height: 18, ml: 0.5 }}
                />
              )}
            </Collapse>

            {data.date && (
              <Chip
                label={new Date(data.date).getFullYear().toString()}
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.6rem', height: 18, minWidth: 'auto' }}
              />
            )}
            
            {data.is_seed && (
              <Tooltip title="Seed Paper" TransitionComponent={Fade} TransitionProps={{ timeout: 0 }}>
                <StarIcon 
                  sx={{ 
                    color: theme.palette.primary.main, 
                    fontSize: 14,
                    ml: 0.5,
                  }} 
                />
              </Tooltip>
            )}

            {/* Spacer */}
            <Box sx={{ flexGrow: 1 }} />

            {/* Expand/Collapse Button */}
            <Tooltip title={isExpanded ? 'Show less' : 'Show more'} TransitionComponent={Fade} TransitionProps={{ timeout: 0 }}>
              <IconButton size="small" sx={{ p: 0.25 }}>
                {isExpanded 
                  ? <UnfoldLessIcon sx={{ fontSize: 16 }} /> 
                  : <ReadMoreIcon sx={{ fontSize: 16 }} />}
              </IconButton>
            </Tooltip>
          </Box>
        </CardContent>
      </Card>

      {/* Context menu */}
      <Menu
        anchorEl={anchorEl}
        open={isMenuOpen}
        onClose={handleMenuClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        <MenuItem onClick={handleExpand}>
          <ExpandIcon sx={{ mr: 1, fontSize: 16 }} />
          Expand Node
        </MenuItem>
        <MenuItem onClick={handleDelete}>
          <DeleteIcon sx={{ mr: 1, fontSize: 16 }} />
          Delete Node
        </MenuItem>
        {data.url && (
          <MenuItem onClick={handleOpenUrl}>
            <LaunchIcon sx={{ mr: 1, fontSize: 16 }} />
            Open Paper
          </MenuItem>
        )}
      </Menu>
    </>
  );
});

MindMapNode.displayName = 'MindMapNode';

export default MindMapNode; 