import React from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ViewInArIcon from '@mui/icons-material/ViewInAr';
import TuneIcon from '@mui/icons-material/Tune';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useLayout } from '../contexts/LayoutContext';
import { useProfile } from '../contexts/ProfileContext';
import { starMapApi, type StarMapPoint, createWebSocket } from '../services/api';
import { StarMapCanvas } from '../components/starMap/StarMapCanvas';
import { StarMap3DCanvas } from '../components/starMap/StarMap3DCanvas';
import { colorForKey } from '../components/starMap/colors';

export default function ProfileStarMap() {
  const navigate = useNavigate();
  const { headerHeight } = useLayout();
  const { profiles, selectedProfileIds } = useProfile();

  const [activeProfileId, setActiveProfileId] = React.useState<number | ''>('');
  const [selectedPoint, setSelectedPoint] = React.useState<StarMapPoint | null>(null);
  const [viewMode, setViewMode] = React.useState<'3d' | '2d'>('3d');

  // Keep activeProfileId in sync with selected profiles (default to first).
  React.useEffect(() => {
    if (selectedProfileIds.length === 0) {
      setActiveProfileId('');
      return;
    }
    setActiveProfileId((prev) => (prev === '' ? selectedProfileIds[0] : prev));
  }, [selectedProfileIds]);

  const profile = profiles.find((p) => p.id === activeProfileId) || null;

  const mapQuery = useQuery({
    queryKey: ['star-map', activeProfileId],
    queryFn: async () => {
      const res = await starMapApi.getProfileStarMap(activeProfileId as number, 10000);
      return res.data;
    },
    enabled: typeof activeProfileId === 'number',
    refetchInterval: 120000,
  });

  const recomputeMutation = useMutation({
    mutationFn: async () => {
      const res = await starMapApi.recomputeProfileStarMap(activeProfileId as number, { limit: 10000 });
      return res.data;
    },
    onSuccess: async (data) => {
      // Optionally stream progress (if backend supports it); then refetch at the end.
      try {
        const ws = createWebSocket(data.task_id, 'star-map');
        ws.onmessage = (event) => {
          // When the task completes, the websocket handler will close; we refetch on close.
          void event;
        };
        ws.onclose = () => {
          mapQuery.refetch();
        };
      } catch {
        // If websocket fails, do a timed refetch.
        setTimeout(() => mapQuery.refetch(), 4000);
      }
    },
  });

  const points = mapQuery.data?.points || [];
  const centroids = mapQuery.data?.centroids || [];
  const computedAt = mapQuery.data?.computed_at;

  const topAlignments = React.useMemo(() => {
    const counts = new Map<string, { label: string; id: number; count: number }>();
    let unknown = 0;
    for (const p of points) {
      if (!p.dominant_interest_id || !p.dominant_label) {
        unknown += 1;
        continue;
      }
      const key = `${p.dominant_interest_id}`;
      const existing = counts.get(key);
      if (existing) {
        existing.count += 1;
      } else {
        // Prefer short label if available.
        const displayLabel = p.dominant_short_label || p.dominant_label;
        counts.set(key, { id: p.dominant_interest_id, label: displayLabel, count: 1 });
      }
    }
    const list = Array.from(counts.values()).sort((a, b) => b.count - a.count).slice(0, 8);
    return { list, unknown };
  }, [points]);

  return (
    <Container maxWidth="xl" sx={{ pt: `${headerHeight + 24}px`, pb: 4 }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 2, mb: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Box sx={{
            fontFamily: '"Geist Mono", monospace',
            fontSize: 10,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: 'primary.main',
            mb: 0.75,
          }}>
            Profile · Constellation
          </Box>
          <Typography
            component="div"
            sx={{
              fontFamily: '"Instrument Serif", Georgia, serif',
              fontSize: 32,
              letterSpacing: '-0.02em',
              lineHeight: 1.05,
              mb: 0.5,
            }}
          >
            Star map
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Explore clusters and outliers across a profile's paper universe.
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={() => recomputeMutation.mutate()}
          disabled={recomputeMutation.isPending || typeof activeProfileId !== 'number'}
        >
          Recompute
        </Button>
      </Box>

      {selectedProfileIds.length > 1 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Multiple profiles are selected globally. Star Map currently visualizes one profile at a time—choose it below.
        </Alert>
      )}

      <Card sx={{ mb: 2 }}>
        <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 260 }}>
            <InputLabel>Profile</InputLabel>
            <Select
              value={activeProfileId}
              label="Profile"
              onChange={(e) => setActiveProfileId(e.target.value as any)}
            >
              {profiles.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Box sx={{ flex: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {profile ? (
                <>
                  <strong>{profile.name}</strong>
                  {profile.description ? ` — ${profile.description}` : ''}
                </>
              ) : (
                'Select a profile to load its map.'
              )}
            </Typography>
          </Box>

          <Button
            variant="text"
            onClick={() => navigate('/papers')}
            endIcon={<OpenInNewIcon />}
            disabled={selectedProfileIds.length === 0}
          >
            Open Papers
          </Button>
        </CardContent>
      </Card>

      {typeof activeProfileId !== 'number' ? (
        <Alert severity="warning">Select a profile to render its Star Map.</Alert>
      ) : mapQuery.isLoading ? (
        <Skeleton height={560} />
      ) : points.length === 0 ? (
        <Alert severity="info">
          No star map points yet for this profile. Click “Recompute” to generate a constellation (this requires papers
          with embeddings + profile scores).
        </Alert>
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', lg: '1fr 400px' },
            gap: 2,
            alignItems: 'start',
          }}
        >
          <Box>
            <Card sx={{ mb: 2 }}>
              <CardContent sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                <Button
                  size="small"
                  variant={viewMode === '3d' ? 'contained' : 'outlined'}
                  startIcon={<ViewInArIcon />}
                  onClick={() => setViewMode('3d')}
                >
                  3D
                </Button>
                <Button
                  size="small"
                  variant={viewMode === '2d' ? 'contained' : 'outlined'}
                  startIcon={<TuneIcon />}
                  onClick={() => setViewMode('2d')}
                >
                  2D
                </Button>
                <Box sx={{ flex: 1 }} />
                <Typography variant="caption" color="text.secondary">
                  {computedAt ? `Computed: ${new Date(computedAt).toLocaleString()}` : ''}
                </Typography>
              </CardContent>
            </Card>

            {viewMode === '3d' ? (
              <StarMap3DCanvas
                points={points}
                centroids={centroids}
                onPointClick={(p) => {
                  setSelectedPoint(p);
                }}
              />
            ) : (
              <StarMapCanvas
                points={points}
                centroids={centroids}
                onPointClick={(p) => {
                  setSelectedPoint(p);
                }}
              />
            )}
          </Box>

          <Card>
            <CardContent>
              <Typography variant="h6" fontWeight={800} gutterBottom>
                What you’re seeing
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Each dot is a paper scored for this profile. Nearby dots are semantically similar (embedding space).
                Color indicates the paper’s dominant matching profile interest (when available).
              </Typography>

              <Typography variant="subtitle2" fontWeight={800}>
                Quick stats
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {points.length.toLocaleString()} papers in view
                {topAlignments.unknown ? ` · ${topAlignments.unknown.toLocaleString()} unlabeled` : ''}
              </Typography>

              <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>
                Top constellations
              </Typography>
              <Box sx={{ display: 'grid', gap: 1 }}>
                {topAlignments.list.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No dominant interest labels found yet. (Run interest clustering to label papers.)
                  </Typography>
                ) : (
                  topAlignments.list.map((it) => (
                    <Box
                      key={it.id}
                      sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                    >
                      <Box
                        sx={{
                          width: 10,
                          height: 10,
                          borderRadius: 1,
                          bgcolor: colorForKey(it.id),
                          flexShrink: 0,
                        }}
                      />
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{ fontWeight: 800, flexShrink: 0 }}
                      >
                        {it.count.toLocaleString()}
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 600,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          flex: 1,
                          minWidth: 0,
                        }}
                      >
                        {it.label}
                      </Typography>
                    </Box>
                  ))
                )}
              </Box>

              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
                Controls: 3D rotate by dragging · zoom with scroll · click a dot for details.
              </Typography>
            </CardContent>
          </Card>
        </Box>
      )}

      <Dialog open={Boolean(selectedPoint)} onClose={() => setSelectedPoint(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Paper</DialogTitle>
        <DialogContent dividers>
          {selectedPoint && (
            <Box>
              <Typography variant="h6" gutterBottom>
                {selectedPoint.title || `Paper #${selectedPoint.paper_id}`}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {selectedPoint.date ? `Date: ${selectedPoint.date}` : ''}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {selectedPoint.dominant_label ? `Aligns to: ${selectedPoint.dominant_label}` : 'Aligns to: (unknown)'}
              </Typography>
              {selectedPoint.profile_score !== undefined && (
                <Typography variant="body2" color="text.secondary">
                  Profile score: {selectedPoint.profile_score}
                </Typography>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedPoint(null)}>Close</Button>
          {selectedPoint?.title && (
            <Button
              variant="contained"
              onClick={() => {
                const search = encodeURIComponent(selectedPoint.title || '');
                navigate(`/papers?search=${search}`);
                setSelectedPoint(null);
              }}
            >
              Open in Papers (search)
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Container>
  );
}

