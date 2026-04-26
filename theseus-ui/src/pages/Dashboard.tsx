import React from 'react';
import { Box } from '@mui/material';
import { Sparkles } from 'lucide-react';
import PageShell from '../components/observatory/PageShell';
import ObsButton from '../components/observatory/ObsButton';
import { PinnedShortcuts } from '../components/dashboard/PinnedShortcuts';
import { RecentOutputs } from '../components/dashboard/RecentOutputs';
import { InsightsStrip } from '../components/dashboard/InsightsStrip';
import { StarMapPreview } from '../components/dashboard/StarMapPreview';
import DashboardStatsRow from '../components/dashboard/DashboardStatsRow';
import { useNavigate } from 'react-router-dom';
import { onAccent } from '../styles/observatoryTokens';
import { useDesign } from '../contexts/DesignContext';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { accent } = useDesign();

  return (
    <PageShell
      kicker="Command center"
      title="Good evening, researcher."
      subtitle="A consolidated view of your corpus, recent outputs, and live work."
      cta={
        <ObsButton
          startIcon={<Sparkles size={12} color={onAccent(accent)} strokeWidth={2} />}
          onClick={() => navigate('/research-agent')}
        >
          New research run
        </ObsButton>
      }
    >
      <DashboardStatsRow />

      <Box
        sx={{
          display: 'grid',
          gap: 1.5,
          gridTemplateColumns: { xs: '1fr', lg: '7fr 5fr' },
          mb: 1.5,
        }}
      >
        <StarMapPreview />
        <RecentOutputs />
      </Box>

      <Box
        sx={{
          display: 'grid',
          gap: 1.5,
          gridTemplateColumns: { xs: '1fr', lg: '7fr 5fr' },
        }}
      >
        <InsightsStrip />
        <PinnedShortcuts />
      </Box>
    </PageShell>
  );
};

export default Dashboard;
