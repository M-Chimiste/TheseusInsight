import React, { memo } from 'react';
import { BaseEdge, getStraightPath, EdgeLabelRenderer } from '@xyflow/react';
import { Chip, useTheme } from '@mui/material';

interface MindMapEdgeData {
  similarity_score: number;
  colorIndex?: number;
}

interface MindMapEdgeProps {
  id: string;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  data?: MindMapEdgeData;
  selected?: boolean;
}

const MindMapEdge: React.FC<MindMapEdgeProps> = memo(({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
  selected,
}) => {
  const theme = useTheme();
  
  const [edgePath, labelX, labelY] = getStraightPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  });

  const similarity = data?.similarity_score || 0;
  const palette = ['#8e24aa','#3949ab','#00897b','#f9a825','#d81b60','#00acc1'];
  const colorIndex = (data as any)?.colorIndex;

  let edgeColor: string;
  if (colorIndex !== undefined) {
    edgeColor = palette[colorIndex % palette.length];
  } else {
    // original similarity-based coloring
    const getEdgeColor = () => {
      if (similarity > 0.75) return theme.palette.primary.main;
      if (similarity > 0.55) return theme.palette.primary.light;
      return theme.palette.mode === 'dark'
        ? theme.palette.grey[600]
        : theme.palette.grey[400];
    };
    edgeColor = getEdgeColor();
  }

  const strokeWidth = Math.max(1, similarity * 4);
  const opacity = selected ? 1 : 0.8;

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: edgeColor,
          strokeWidth,
          opacity,
          strokeDasharray: selected ? '5,5' : 'none',
        }}
      />
      
      {/* Edge label showing similarity score */}
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
        >
          <Chip
            label={`${(similarity * 100).toFixed(0)}%`}
            size="small"
            variant="filled"
            sx={{
              fontSize: '0.6rem',
              height: 18,
              backgroundColor: edgeColor,
              color: theme.palette.getContrastText(edgeColor),
              opacity: selected ? 1 : 0.8,
              '&:hover': {
                opacity: 1,
              },
            }}
          />
        </div>
      </EdgeLabelRenderer>
    </>
  );
});

MindMapEdge.displayName = 'MindMapEdge';

export default MindMapEdge; 