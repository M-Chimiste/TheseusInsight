import React from 'react';
import { Box, Typography, Stack, Chip } from '@mui/material';
import { TrendingUp, TrendingFlat, TrendingDown, Whatshot } from '@mui/icons-material';

// Phase colors matching TimelineCanvas tooltip
const PHASE_INFO = [
  {
    phase: 'emerging',
    color: '#4caf50',
    description: 'High growth (>50%)',
    icon: Whatshot,
  },
  {
    phase: 'growth',
    color: '#2196f3',
    description: 'Growing (>10%)',
    icon: TrendingUp,
  },
  {
    phase: 'stable',
    color: '#9e9e9e',
    description: 'Stable (±10%)',
    icon: TrendingFlat,
  },
  {
    phase: 'declining',
    color: '#f44336',
    description: 'Declining (<-10%)',
    icon: TrendingDown,
  },
];

const TimelineLegend: React.FC = () => {
  return (
    <Box sx={{ mb: 2, p: 1.5, bgcolor: 'background.paper', borderRadius: 1, border: 1, borderColor: 'divider' }}>
      <Typography variant="caption" fontWeight="bold" sx={{ mb: 1, display: 'block' }}>
        How to Read the Timeline
      </Typography>
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
        {PHASE_INFO.map(({ phase, color, description, icon: Icon }) => (
          <Chip
            key={phase}
            icon={
              <Icon
                sx={{
                  color: `${color} !important`,
                  fontSize: 16,
                }}
              />
            }
            label={
              <Box>
                <Typography variant="caption" fontWeight="medium" sx={{ textTransform: 'capitalize' }}>
                  {phase}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                  {description}
                </Typography>
              </Box>
            }
            size="small"
            variant="outlined"
            sx={{ height: 'auto', py: 0.5 }}
          />
        ))}
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        Stream width = paper count • Hover to see details • Click to view papers
      </Typography>
    </Box>
  );
};

export default TimelineLegend;
