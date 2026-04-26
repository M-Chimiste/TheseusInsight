import React from 'react';
import { Box, Button, Skeleton, Typography } from '@mui/material';
import ObsCard from '../observatory/ObsCard';
import ObsKicker from '../observatory/ObsKicker';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '@mui/material/styles';
import { ResponsiveContainer, AreaChart, Area, Tooltip as RechartsTooltip, XAxis, YAxis } from 'recharts';
import { createPortal } from 'react-dom';
import { useProfile } from '../../contexts/ProfileContext';
import { trendsApi } from '../../services/api';

type ChartPoint = {
  label: string;
  [topicKey: string]: number | string;
};

function periodLabel(periodStart: string) {
  const d = new Date(periodStart);
  if (Number.isNaN(d.getTime())) return periodStart;
  return d.toLocaleDateString(undefined, { year: '2-digit', month: 'short' });
}

function ThemedTooltip(props: any) {
  const theme = useTheme();
  const { active, payload, label, coordinate, containerEl } = props;

  if (!active || !payload || payload.length === 0) return null;

  const bg =
    theme.palette.mode === 'dark' ? 'rgba(15, 23, 42, 0.92)' : 'rgba(255, 255, 255, 0.96)';

  // Render via portal so it can't be clipped by chart/card containers.
  // Position is based on the chart container's screen rect + Recharts-provided coordinate (chart-local).
  const tooltipRef = React.useRef<HTMLDivElement | null>(null);
  const [measured, setMeasured] = React.useState({ w: 360, h: 220 });

  React.useLayoutEffect(() => {
    const el = tooltipRef.current;
    if (!el) return;
    const w = el.offsetWidth || measured.w;
    const h = el.offsetHeight || measured.h;
    if (w !== measured.w || h !== measured.h) setMeasured({ w, h });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [label, payload?.length]);

  if (!containerEl || !coordinate) return null;
  const rect = (containerEl as HTMLElement).getBoundingClientRect();
  const screenX = rect.left + (coordinate?.x ?? 0);
  const screenY = rect.top + (coordinate?.y ?? 0);

  const margin = 12;
  let left = screenX + margin;
  let top = screenY - margin;

  // Flip horizontally when we'd overflow the viewport.
  if (left + measured.w + margin > window.innerWidth) {
    left = screenX - margin - measured.w;
  }
  // Clamp to viewport.
  left = Math.max(margin, Math.min(window.innerWidth - margin - measured.w, left));

  // Prefer above cursor, but clamp vertically.
  if (top + measured.h + margin > window.innerHeight) {
    top = window.innerHeight - margin - measured.h;
  }
  top = Math.max(margin, Math.min(window.innerHeight - margin - measured.h, top));

  return createPortal(
    <Box
      ref={tooltipRef}
      sx={{
        position: 'fixed',
        left,
        top,
        minWidth: 320,
        maxWidth: 520,
        bgcolor: bg,
        color: 'text.primary',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        px: 1.5,
        py: 1.25,
        boxShadow: theme.palette.mode === 'dark' ? 8 : 6,
        backdropFilter: 'blur(8px)',
        zIndex: 4000,
        pointerEvents: 'none',
      }}
    >
      <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>
        {label}
      </Typography>
      <Box sx={{ display: 'grid', gap: 0.75 }}>
        {payload
          .filter((p: any) => typeof p?.value === 'number' && p.value > 0)
          .map((p: any) => (
            <Box
              key={p.name}
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 2,
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
                <Box
                  sx={{
                    width: 10,
                    height: 10,
                    borderRadius: 1,
                    bgcolor: p.color,
                    flex: '0 0 auto',
                  }}
                />
                <Typography
                  variant="body2"
                  sx={{
                    fontWeight: 600,
                    whiteSpace: 'normal',
                    overflowWrap: 'anywhere',
                    lineHeight: 1.25,
                  }}
                >
                  {p.name}
                </Typography>
              </Box>
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 800,
                  color: 'text.secondary',
                  flex: '0 0 auto',
                  pl: 2,
                }}
              >
                {p.value}
              </Typography>
            </Box>
          ))}
      </Box>
    </Box>,
    document.body,
  );
}

export function InsightsStrip() {
  const navigate = useNavigate();
  const { selectedProfileIds } = useProfile();
  const theme = useTheme();
  const chartContainerRef = React.useRef<HTMLDivElement | null>(null);

  const seriesColors = React.useMemo(() => {
    // High-contrast, theme-aligned palette (max 5 series in this widget).
    return [
      theme.palette.primary.main,
      theme.palette.secondary.main,
      theme.palette.success.main,
      theme.palette.warning.main,
      theme.palette.info.main,
    ];
  }, [theme.palette.info.main, theme.palette.primary.main, theme.palette.secondary.main, theme.palette.success.main, theme.palette.warning.main]);

  const query = useQuery({
    queryKey: ['dashboard', 'insights-strip', selectedProfileIds.sort().join(',')],
    queryFn: async () => {
      const res = await trendsApi.getTimelineData({
        profile_ids: selectedProfileIds.join(','),
        period_type: 'month',
        limit: 6,
        include_key_papers: false,
        source: 'profile_interests',
      });
      return res.data;
    },
    enabled: selectedProfileIds.length > 0,
    refetchInterval: 60000,
  });

  const chartData = React.useMemo<ChartPoint[]>(() => {
    const data = query.data;
    if (!data || !data.topics || data.topics.length === 0) return [];

    // Choose up to 5 topics, consistent order.
    const topics = data.topics.slice(0, 5);
    const periods = topics[0].periods || [];

    return periods.map((p: any, idx: number) => {
      const row: ChartPoint = { label: periodLabel(p.period_start) };
      topics.forEach((t: any, tIdx: number) => {
        const key = `t${tIdx}`;
        const tp = (t.periods || [])[idx];
        row[key] = tp?.doc_count || 0;
      });
      return row;
    });
  }, [query.data]);

  const topicLabels = React.useMemo(() => {
    const data = query.data;
    if (!data || !data.topics) return [];
    return data.topics.slice(0, 5).map((t: any) => t.topic_label || 'Topic');
  }, [query.data]);

  return (
    <ObsCard padding={18}>
        <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 2, mb: 1.5 }}>
          <Box>
            <ObsKicker>Trends</ObsKicker>
            <Typography
              sx={{ fontFamily: '"Instrument Serif", Georgia, serif', fontSize: 22, lineHeight: 1.1, mt: 0.5 }}
            >
              Research pulse
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              A quick pulse of profile interest activity.
            </Typography>
          </Box>
          <Button size="small" variant="outlined" onClick={() => navigate('/timeline')}>
            Open timeline
          </Button>
        </Box>

        {selectedProfileIds.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Select a profile to see timeline insights.
          </Typography>
        ) : query.isLoading ? (
          <Skeleton height={220} />
        ) : chartData.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No timeline data available yet.
          </Typography>
        ) : (
          <Box ref={chartContainerRef} sx={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} width={36} />
                <RechartsTooltip
                  cursor={{ stroke: 'rgba(255,255,255,0.12)', strokeWidth: 1 }}
                  allowEscapeViewBox={{ x: true, y: true }}
                  content={(p: any) => <ThemedTooltip {...p} containerEl={chartContainerRef.current} />}
                  wrapperStyle={{ outline: 'none', zIndex: 2000, pointerEvents: 'none' }}
                />
                {topicLabels.map((label, idx) => (
                  <Area
                    key={label}
                    type="monotone"
                    dataKey={`t${idx}`}
                    name={label}
                    stackId="1"
                    stroke={seriesColors[idx % seriesColors.length]}
                    fill={seriesColors[idx % seriesColors.length]}
                    fillOpacity={0.22}
                    strokeOpacity={0.95}
                    strokeWidth={2}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </Box>
        )}
    </ObsCard>
  );
}

