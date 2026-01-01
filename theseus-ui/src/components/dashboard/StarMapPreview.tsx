import React from 'react';
import { Box, Button, Card, CardContent, Divider, Skeleton, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useProfile } from '../../contexts/ProfileContext';
import { useQuery } from '@tanstack/react-query';
import { starMapApi, type StarMapPoint } from '../../services/api';
import { colorForKey } from '../starMap/colors';

function clamp01(v: number) {
  if (Number.isNaN(v)) return 0;
  return Math.max(0, Math.min(1, v));
}

function rotateY(x: number, z: number, yaw: number) {
  const c = Math.cos(yaw);
  const s = Math.sin(yaw);
  return { x: x * c - z * s, z: x * s + z * c };
}

function rotateX(y: number, z: number, pitch: number) {
  const c = Math.cos(pitch);
  const s = Math.sin(pitch);
  return { y: y * c - z * s, z: y * s + z * c };
}

export function StarMapPreview() {
  const navigate = useNavigate();
  const { selectedProfileIds } = useProfile();

  const primaryProfileId = selectedProfileIds[0];

  const query = useQuery({
    queryKey: ['dashboard', 'star-map-preview', primaryProfileId],
    queryFn: async () => {
      if (!primaryProfileId) return [];
      const res = await starMapApi.getProfileStarMap(primaryProfileId, 2000);
      return res.data.points;
    },
    enabled: Boolean(primaryProfileId),
    refetchInterval: 120000,
  });

  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const containerRef = React.useRef<HTMLDivElement | null>(null);

  // Rotation and zoom state
  const [yaw, setYaw] = React.useState(0.5);
  const [pitch, setPitch] = React.useState(-0.3);
  const [zoom, setZoom] = React.useState(3.0); // Start zoomed in
  const dragRef = React.useRef<{ x: number; y: number; yaw: number; pitch: number } | null>(null);

  // Auto-rotate when not dragging
  const autoRotateRef = React.useRef<number | null>(null);
  const [isInteracting, setIsInteracting] = React.useState(false);

  React.useEffect(() => {
    if (isInteracting || !query.data || query.data.length === 0) {
      if (autoRotateRef.current) {
        cancelAnimationFrame(autoRotateRef.current);
        autoRotateRef.current = null;
      }
      return;
    }

    let lastTime = performance.now();
    const animate = (now: number) => {
      const dt = (now - lastTime) / 1000;
      lastTime = now;
      setYaw((y) => y + dt * 0.15); // Slow rotation
      autoRotateRef.current = requestAnimationFrame(animate);
    };
    autoRotateRef.current = requestAnimationFrame(animate);

    return () => {
      if (autoRotateRef.current) cancelAnimationFrame(autoRotateRef.current);
    };
  }, [isInteracting, query.data]);

  // Draw function
  const draw = React.useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const points = query.data || [];

    const rect = container.getBoundingClientRect();
    const cssW = Math.floor(rect.width);
    const cssH = Math.floor(rect.height);
    const dpr = window.devicePixelRatio || 1;

    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
    canvas.style.width = `${cssW}px`;
    canvas.style.height = `${cssH}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Background gradient
    ctx.clearRect(0, 0, cssW, cssH);
    const g = ctx.createLinearGradient(0, 0, cssW, cssH);
    g.addColorStop(0, 'rgba(99, 102, 241, 0.12)');
    g.addColorStop(1, 'rgba(16, 185, 129, 0.08)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, cssW, cssH);

    if (points.length === 0) return;

    const cx = cssW / 2;
    const cy = cssH / 2;
    const base = Math.min(cssW, cssH) * 0.4 * zoom;
    const cameraDist = 2.8;

    type ScreenPoint = StarMapPoint & { sx: number; sy: number; sz: number };
    const screenPoints: ScreenPoint[] = [];

    for (const p of points) {
      const x0 = p.x;
      const y0 = p.y;
      const z0 = p.z ?? 0;

      const ry = rotateY(x0, z0, yaw);
      const rx = rotateX(y0, ry.z, pitch);

      const z = rx.z;
      const f = 1 / Math.max(0.25, cameraDist - z);
      const sx = cx + ry.x * f * base;
      const sy = cy + rx.y * f * base;

      screenPoints.push({ ...p, sx, sy, sz: z });
    }

    // Sort back-to-front
    screenPoints.sort((a, b) => a.sz - b.sz);

    for (const p of screenPoints) {
      const depth = clamp01((p.sz + 1) / 2);
      const alpha = 0.3 + depth * 0.6;
      const size = 1.0 + depth * 1.5;

      ctx.globalAlpha = alpha;
      ctx.fillStyle = colorForKey(p.dominant_interest_id ?? p.cluster_id ?? 0);
      ctx.beginPath();
      ctx.arc(p.sx, p.sy, size, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }, [query.data, yaw, pitch, zoom]);

  React.useEffect(() => {
    draw();
  }, [draw]);

  // Wheel handler for zoom (native listener with passive: false to prevent page scroll)
  React.useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      const delta = Math.sign(e.deltaY);
      setZoom((z) => Math.max(0.8, Math.min(4, z * (delta > 0 ? 0.9 : 1.1))));
      setIsInteracting(true);
      // Resume auto-rotate after a delay
      setTimeout(() => setIsInteracting(false), 2000);
    };

    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, []);

  // Mouse handlers for drag rotation
  const handleMouseDown = (e: React.MouseEvent) => {
    dragRef.current = { x: e.clientX, y: e.clientY, yaw, pitch };
    setIsInteracting(true);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const d = dragRef.current;
    if (!d) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    setYaw(d.yaw + dx * 0.008);
    setPitch(Math.max(-1.2, Math.min(1.2, d.pitch + dy * 0.008)));
  };

  const handleMouseUp = () => {
    dragRef.current = null;
    // Resume auto-rotate after a delay
    setTimeout(() => setIsInteracting(false), 2000);
  };

  const handleMouseLeave = () => {
    if (dragRef.current) {
      dragRef.current = null;
      setTimeout(() => setIsInteracting(false), 2000);
    }
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 2 }}>
          <Box>
            <Typography variant="h6" fontWeight={700}>
              Profile Star Map
            </Typography>
            <Typography variant="body2" color="text.secondary">
              A constellation snapshot of papers aligned to your selected profile.
            </Typography>
          </Box>
          <Button size="small" variant="outlined" onClick={() => navigate('/star-map')}>
            Open Star Map
          </Button>
        </Box>

        <Divider sx={{ my: 2 }} />

        {selectedProfileIds.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Select a profile to render its star map.
          </Typography>
        ) : query.isLoading ? (
          <Skeleton height={220} />
        ) : (
          <Box
            ref={containerRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseLeave}
            sx={{
              height: 220,
              borderRadius: 2,
              overflow: 'hidden',
              border: '1px solid',
              borderColor: 'divider',
              cursor: dragRef.current ? 'grabbing' : 'grab',
              position: 'relative',
            }}
          >
            <canvas
              ref={canvasRef}
              style={{ width: '100%', height: '100%', display: 'block' }}
            />
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{
                position: 'absolute',
                bottom: 6,
                right: 8,
                opacity: 0.6,
                pointerEvents: 'none',
                fontSize: '0.7rem',
              }}
            >
              Drag to rotate
            </Typography>
          </Box>
        )}

        {selectedProfileIds.length > 1 && (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            Showing a preview for the first selected profile. Open Star Map to switch/compare.
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}
