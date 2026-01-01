import React from 'react';
import { Box, Container, Typography } from '@mui/material';
import { useLayout } from '../contexts/LayoutContext';
import { PinnedShortcuts } from '../components/dashboard/PinnedShortcuts';
import { RecentOutputs } from '../components/dashboard/RecentOutputs';
import { InsightsStrip } from '../components/dashboard/InsightsStrip';
import { StarMapPreview } from '../components/dashboard/StarMapPreview';

const Dashboard: React.FC = () => {
  const { headerHeight } = useLayout(); // Get dynamic header height

  return (
    <Container maxWidth="xl" sx={{ pt: `${headerHeight + 24}px`, pb: 4 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight={800} gutterBottom>
          Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          A command center for your current work, outputs, and profile pulse.
        </Typography>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 3, mb: 3 }}>
        <PinnedShortcuts />
        <StarMapPreview />
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 3 }}>
        <RecentOutputs />
        <InsightsStrip />
      </Box>
    </Container>
  );
};

export default Dashboard; 