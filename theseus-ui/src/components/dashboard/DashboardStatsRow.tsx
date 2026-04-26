import React from 'react';
import { Box } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { profileApi, taskApi } from '../../services/api';
import { useProfile } from '../../contexts/ProfileContext';
import ObsStatTile from '../observatory/ObsStatTile';
import { OBS } from '../../styles/observatoryTokens';
import { useDesign } from '../../contexts/DesignContext';

const TASK_TYPES_FOR_RECENT = [
  'newsletter',
  'custom_newsletter_run',
  'podcast',
  'visualizer',
  'mindmap_expand',
  'profile_aware_ingest',
  'bulk_embed',
  'star-map',
];

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

export const DashboardStatsRow: React.FC = () => {
  const { selectedProfileIds } = useProfile();
  const { accent } = useDesign();

  const profilesQuery = useQuery({
    queryKey: ['dashboard', 'profiles'],
    queryFn: async () => (await profileApi.getProfiles()).data,
    refetchInterval: 60_000,
  });

  const recentTasksQuery = useQuery({
    queryKey: ['dashboard', 'recent-tasks-row'],
    queryFn: async () => (await taskApi.getRecentCompletedTasks(TASK_TYPES_FOR_RECENT)).data,
    refetchInterval: 30_000,
  });

  const activeTasksQuery = useQuery({
    queryKey: ['dashboard', 'active-tasks'],
    queryFn: async () => (await taskApi.getActiveTasks()).data,
    refetchInterval: 15_000,
  });

  const profiles = (profilesQuery.data as any[]) || [];
  const totalPapers = profiles.reduce((sum, p) => sum + (p.total_papers || 0), 0);
  const recentPapers = profiles.reduce((sum, p) => sum + (p.recent_papers || 0), 0);
  const recentTasks = (recentTasksQuery.data as any)?.completed_tasks || [];
  const activeTasks = (activeTasksQuery.data as any)?.active_tasks || (activeTasksQuery.data as any) || [];
  const activeCount = Array.isArray(activeTasks) ? activeTasks.length : 0;

  const tiles = [
    {
      label: 'Papers ingested',
      value: totalPapers.toLocaleString(),
      delta: totalPapers > 0 ? `+${recentPapers}` : '—',
      seed: 1,
    },
    {
      label: 'Relevant today',
      value: pad2(recentPapers),
      delta: recentPapers > 0 ? 'this week' : 'idle',
      seed: 2,
    },
    {
      label: 'Active profiles',
      value: pad2(profiles.length),
      delta: selectedProfileIds.length > 0 ? `${selectedProfileIds.length} active` : '—',
      seed: 3,
    },
    {
      label: 'Jobs running',
      value: pad2(activeCount),
      delta: activeCount > 0 ? 'live' : `${recentTasks.length} done`,
      seed: 4,
    },
  ];

  return (
    <Box
      sx={{
        display: 'grid',
        gap: 1.5,
        gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' },
        mb: 2,
      }}
    >
      {tiles.map((t) => (
        <ObsStatTile
          key={t.label}
          label={t.label}
          value={
            <span style={{ color: OBS.text }}>{t.value}</span>
          }
          delta={
            <span style={{ color: t.delta === 'live' ? accent : OBS.textDim }}>{t.delta}</span>
          }
          seed={t.seed}
        />
      ))}
    </Box>
  );
};

export default DashboardStatsRow;
