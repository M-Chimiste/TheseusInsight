import React from 'react';
import { Box, Typography, Stack, Chip } from '@mui/material';
import { Circle as CircleIcon } from '@mui/icons-material';

// Phase colors matching TimelineCanvas
const PHASE_COLORS = {
  emerging: '#4caf50',   // Green
  growth: '#2196f3',     // Blue
  stable: '#9e9e9e',     // Gray
  declining: '#f44336',  // Red
  forecast: '#ff9800',   // Orange
};

const PHASE_DESCRIPTIONS = {
  emerging: 'High growth (>50%)',
  growth: 'Growing (>10%)',
  stable: 'Stable (±10%)',
  declining: 'Declining (<-10%)',
  forecast: 'Predicted (future)',
};

const TimelineLegend: React.FC = () => {
  return (
    <Box sx={{ mb: 2, p: 1.5, bgcolor: 'background.paper', borderRadius: 1, border: 1, borderColor: 'divider' }}>
      <Typography variant="caption" fontWeight="bold" sx={{ mb: 1, display: 'block' }}>
        Growth Phase Legend
      </Typography>
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
        {Object.entries(PHASE_COLORS).map(([phase, color]) => (
          <Chip
            key={phase}
            icon={
              <CircleIcon
                sx={{
                  color: `${color} !important`,
                  fontSize: 12,
                  ...(phase === 'forecast' && {
                    border: `2px dashed ${color}`,
                    borderRadius: '50%',
                    bgcolor: 'transparent',
                  }),
                }}
              />
            }
            label={
              <Box>
                <Typography variant="caption" fontWeight="medium" sx={{ textTransform: 'capitalize' }}>
                  {phase}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                  {PHASE_DESCRIPTIONS[phase as keyof typeof PHASE_DESCRIPTIONS]}
                </Typography>
              </Box>
            }
            size="small"
            variant="outlined"
            sx={{ height: 'auto', py: 0.5 }}
          />
        ))}
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
        Circle size indicates paper count. Click circles to view papers for that period.
      </Typography>
    </Box>
  );
};

export default TimelineLegend;
