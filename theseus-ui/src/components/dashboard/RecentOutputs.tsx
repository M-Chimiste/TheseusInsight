import React from 'react';
import {
  Box,
  Button,
  Chip,
  Skeleton,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import ObsCard from '../observatory/ObsCard';
import ObsKicker from '../observatory/ObsKicker';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { podcastHistoryApi, researchAgentApi, taskApi } from '../../services/api';

function formatDate(d: string | undefined) {
  if (!d) return '';
  const date = new Date(d);
  if (Number.isNaN(date.getTime())) return d;
  // Shorter format: "Dec 31, 11:20 AM"
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
    ', ' +
    date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

function statusChipColor(status?: string): 'default' | 'success' | 'warning' | 'error' | 'info' {
  switch ((status || '').toLowerCase()) {
    case 'completed':
      return 'success';
    case 'running':
      return 'warning';
    case 'pending':
      return 'info';
    case 'failed':
      return 'error';
    case 'cancelled':
    case 'canceled':
      return 'default';
    default:
      return 'default';
  }
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <Box
      role="tabpanel"
      hidden={value !== index}
      {...other}
      sx={{ pt: 2 }}
    >
      {value === index && children}
    </Box>
  );
}

interface OutputRowProps {
  title: string;
  status?: string;
  date?: string;
  onClick: () => void;
}

function OutputRow({ title, status, date, onClick }: OutputRowProps) {
  return (
    <Box
      onClick={onClick}
      sx={{
        display: 'grid',
        gridTemplateColumns: '1fr 140px 100px',
        alignItems: 'center',
        gap: 2,
        py: 1.25,
        px: 1.5,
        borderRadius: 1,
        cursor: 'pointer',
        '&:hover': { bgcolor: 'action.hover' },
      }}
    >
      <Typography
        variant="body2"
        fontWeight={600}
        noWrap
      >
        {title}
      </Typography>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ whiteSpace: 'nowrap' }}
      >
        {date}
      </Typography>
      {status ? (
        <Chip
          size="small"
          label={status}
          color={statusChipColor(status)}
          sx={{ height: 22, fontSize: '0.75rem', justifySelf: 'end' }}
        />
      ) : (
        <Box />
      )}
    </Box>
  );
}

export function RecentOutputs() {
  const navigate = useNavigate();
  const [tabIndex, setTabIndex] = React.useState(0);

  const researchHistoryQuery = useQuery({
    queryKey: ['dashboard', 'recent', 'research-agent-history'],
    queryFn: async () => {
      const res = await researchAgentApi.getHistory(10, 0);
      return res.data;
    },
    refetchInterval: 30000,
  });

  const podcastHistoryQuery = useQuery({
    queryKey: ['dashboard', 'recent', 'podcasts'],
    queryFn: () => podcastHistoryApi.getPodcastHistoryList(),
    refetchInterval: 60000,
  });

  const recentTasksQuery = useQuery({
    queryKey: ['dashboard', 'recent', 'tasks'],
    queryFn: async () => {
      const res = await taskApi.getRecentCompletedTasks([
        'newsletter',
        'custom_newsletter_run',
        'podcast',
        'visualizer',
        'mindmap_expand',
        'mindmap_pdf_parse',
        'profile_interest_clustering',
        'profile_aware_ingest',
        'bulk_embed',
        'star-map',
      ]);
      return res.data;
    },
    refetchInterval: 30000,
  });

  const researchItems = (researchHistoryQuery.data as any)?.items || [];
  const podcastItems = podcastHistoryQuery.data || [];
  const taskItems = (recentTasksQuery.data as any)?.completed_tasks || [];

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setTabIndex(newValue);
  };

  return (
    <ObsCard padding={18}>
        <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 2, mb: 1.5 }}>
          <Box>
            <ObsKicker>Pulse</ObsKicker>
            <Typography
              sx={{ fontFamily: '"Instrument Serif", Georgia, serif', fontSize: 22, lineHeight: 1.1, mt: 0.5 }}
            >
              Recent outputs
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              What you (or the system) produced recently.
            </Typography>
          </Box>
          <Button onClick={() => navigate('/run-history')} size="small" variant="outlined">
            View all runs
          </Button>
        </Box>

        <Tabs
          value={tabIndex}
          onChange={handleTabChange}
          variant="fullWidth"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label={`Jobs (${taskItems.length})`} />
          <Tab label={`Research Agent (${researchItems.length})`} />
          <Tab label={`Podcasts (${Array.isArray(podcastItems) ? podcastItems.length : 0})`} />
        </Tabs>

        {/* Jobs Tab */}
        <TabPanel value={tabIndex} index={0}>
          {recentTasksQuery.isLoading ? (
            <>
              <Skeleton height={36} />
              <Skeleton height={36} />
              <Skeleton height={36} />
            </>
          ) : !Array.isArray(taskItems) || taskItems.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
              No recent jobs.
            </Typography>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              {taskItems.slice(0, 8).map((t: any, idx: number) => (
                <OutputRow
                  key={t.task_id || idx}
                  title={t.task_type || 'task'}
                  status={t.status}
                  date={formatDate(t.start_time || t.datetime_run || t.created_at)}
                  onClick={() => navigate('/run-history')}
                />
              ))}
            </Box>
          )}
          <Button onClick={() => navigate('/run-history')} size="small" sx={{ mt: 1 }}>
            Open run history
          </Button>
        </TabPanel>

        {/* Research Agent Tab */}
        <TabPanel value={tabIndex} index={1}>
          {researchHistoryQuery.isLoading ? (
            <>
              <Skeleton height={36} />
              <Skeleton height={36} />
              <Skeleton height={36} />
            </>
          ) : researchItems.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
              No research runs yet.
            </Typography>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              {researchItems.slice(0, 8).map((item: any) => (
                <OutputRow
                  key={item.task_id}
                  title={item.research_question || 'Untitled'}
                  status={item.status}
                  date={formatDate(item.created_at)}
                  onClick={() => navigate('/research-library')}
                />
              ))}
            </Box>
          )}
          <Button onClick={() => navigate('/research-library')} size="small" sx={{ mt: 1 }}>
            Open library
          </Button>
        </TabPanel>

        {/* Podcasts Tab */}
        <TabPanel value={tabIndex} index={2}>
          {podcastHistoryQuery.isLoading ? (
            <>
              <Skeleton height={36} />
              <Skeleton height={36} />
              <Skeleton height={36} />
            </>
          ) : !Array.isArray(podcastItems) || podcastItems.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
              No podcasts yet.
            </Typography>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              {podcastItems.slice(0, 8).map((p: any) => (
                <OutputRow
                  key={p.id}
                  title={p.title || `Podcast #${p.id}`}
                  date={p.date || ''}
                  onClick={() => navigate(`/podcast-history/${p.id}`)}
                />
              ))}
            </Box>
          )}
          <Button onClick={() => navigate('/podcast-history')} size="small" sx={{ mt: 1 }}>
            View history
          </Button>
        </TabPanel>
    </ObsCard>
  );
}
