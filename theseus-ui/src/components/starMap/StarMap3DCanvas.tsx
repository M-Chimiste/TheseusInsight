import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import { quadtree as d3Quadtree, type Quadtree } from 'd3-quadtree';
import type { StarMapPoint, StarMapCentroid } from '../../services/api';
import { colorForKey } from './colors';

type ScreenPoint = StarMapPoint & { sx: number; sy: number; sz: number };

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

export function StarMap3DCanvas(props: {
  points: StarMapPoint[];
  centroids?: StarMapCentroid[];
  showCentroids?: boolean;
  height?: number;
  onPointClick?: (p: StarMapPoint) => void;
}) {
  const { points, centroids = [], showCentroids = true, height = 560, onPointClick } = props;
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const containerRef = React.useRef<HTMLDivElement | null>(null);

  const [hover, setHover] = React.useState<{ point: StarMapPoint; x: number; y: number } | null>(null);
  const [isInteracting, setIsInteracting] = React.useState(false);

  // Rotation (radians)
  const [yaw, setYaw] = React.useState(0.6);
  const [pitch, setPitch] = React.useState(-0.35);
  const [zoom, setZoom] = React.useState(1.0);

  const stateRef = React.useRef<{
    cssW: number;
    cssH: number;
    screenPoints: ScreenPoint[];
    index: Quadtree<ScreenPoint> | null;
  }>({ cssW: 0, cssH: 0, screenPoints: [], index: null });

  const rebuildIndex = React.useCallback(() => {
    const sp = stateRef.current.screenPoints;
    stateRef.current.index = d3Quadtree<ScreenPoint>()
      .x((d) => d.sx)
      .y((d) => d.sy)
      .addAll(sp);
  }, []);

  const redraw = React.useCallback(
    (buildIndex: boolean) => {
      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (!canvas || !container) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const rect = container.getBoundingClientRect();
      // Use container's actual rendered size; don't let canvas influence it.
      const cssW = Math.max(320, Math.floor(rect.width));
      const cssH = Math.max(200, Math.floor(rect.height));

      // Setup DPR correctly; draw in CSS pixels.
      const dpr = window.devicePixelRatio || 1;
      canvas.style.width = `${cssW}px`;
      canvas.style.height = `${cssH}px`;
      canvas.width = Math.floor(cssW * dpr);
      canvas.height = Math.floor(cssH * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      stateRef.current.cssW = cssW;
      stateRef.current.cssH = cssH;

      // Background.
      ctx.clearRect(0, 0, cssW, cssH);
      const bg = ctx.createLinearGradient(0, 0, cssW, cssH);
      bg.addColorStop(0, 'rgba(99, 102, 241, 0.08)');
      bg.addColorStop(1, 'rgba(20, 184, 166, 0.06)');
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, cssW, cssH);

      const cx = cssW / 2;
      const cy = cssH / 2;
      const base = Math.min(cssW, cssH) * 0.38 * zoom;
      const cameraDist = 2.8; // closer camera = stronger perspective

      const localPoints: ScreenPoint[] = [];

      // Project points with perspective
      for (const p of points) {
        const x0 = p.x;
        const y0 = p.y;
        const z0 = p.z ?? 0;

        const ry = rotateY(x0, z0, yaw);
        const rx = rotateX(y0, ry.z, pitch);

        const z = rx.z;
        const f = 1 / Math.max(0.25, cameraDist - z); // perspective factor (stronger)
        const sx = cx + ry.x * f * base;
        const sy = cy + rx.y * f * base;

        localPoints.push({ ...p, sx, sy, sz: z });
      }

      // Draw back-to-front for depth ordering.
      localPoints.sort((a, b) => a.sz - b.sz);

      for (const p of localPoints) {
        const depth = clamp01((p.sz + 1) / 2); // 0 = far, 1 = near
        // Larger, brighter points when near; smaller, dimmer when far.
        const baseAlpha = 0.25 + 0.75 * clamp01(((p.profile_score ?? 5) - 1) / 9);
        const depthAlpha = 0.35 + depth * 0.65; // far = 0.35, near = 1.0
        ctx.globalAlpha = baseAlpha * depthAlpha;
        const size = 1.0 + depth * 2.5; // far = 1.0, near = 3.5
        ctx.fillStyle = colorForKey(p.dominant_interest_id ?? p.cluster_id ?? 0);
        ctx.beginPath();
        ctx.arc(p.sx, p.sy, size, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;

      // Draw centroids as glowing markers.
      type CentroidScreenData = {
        c: StarMapCentroid;
        sx: number;
        sy: number;
        depth: number;
        color: string;
        label: string;
        lx: number;
        ly: number;
        textW: number;
      };
      const centroidScreenData: CentroidScreenData[] = [];

      if (showCentroids && centroids.length > 0) {
        ctx.font = 'bold 11px system-ui, sans-serif';

        for (const c of centroids) {
          const x0 = c.x;
          const y0 = c.y;
          const z0 = c.z;

          const ry = rotateY(x0, z0, yaw);
          const rx = rotateX(y0, ry.z, pitch);
          const z = rx.z;
          const f = 1 / Math.max(0.25, cameraDist - z);
          const sx = cx + ry.x * f * base;
          const sy = cy + rx.y * f * base;

          const depth = clamp01((z + 1) / 2);
          const color = colorForKey(c.interest_id);

          // Draw the glowing dot.
          for (let r = 20; r > 0; r -= 4) {
            ctx.globalAlpha = 0.1 * (1 - r / 20) * (0.4 + depth * 0.6);
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(sx, sy, r, 0, Math.PI * 2);
            ctx.fill();
          }

          // Inner bright core.
          ctx.globalAlpha = 0.95;
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(sx, sy, 6, 0, Math.PI * 2);
          ctx.fill();

          // White center highlight.
          ctx.globalAlpha = 0.8;
          ctx.fillStyle = '#fff';
          ctx.beginPath();
          ctx.arc(sx, sy, 2.5, 0, Math.PI * 2);
          ctx.fill();

          // Collect label data for later (drawn after all dots).
          const label = c.short_label || c.label;
          const textW = ctx.measureText(label).width;
          centroidScreenData.push({
            c,
            sx,
            sy,
            depth,
            color,
            label,
            lx: sx + 12,
            ly: sy,
            textW,
          });
        }
        ctx.globalAlpha = 1;

        // Simple collision avoidance for labels.
        for (let i = 0; i < centroidScreenData.length; i++) {
          for (let j = i + 1; j < centroidScreenData.length; j++) {
            const a = centroidScreenData[i];
            const b = centroidScreenData[j];
            const overlapX = Math.abs(a.lx - b.lx) < Math.max(a.textW, b.textW) + 20;
            const overlapY = Math.abs(a.ly - b.ly) < 20;
            if (overlapX && overlapY) {
              b.ly += 22;
            }
          }
        }

        // Draw labels with background pills.
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        const padX = 6;
        const padY = 4;

        for (const { color, label, lx, ly, textW, depth } of centroidScreenData) {
          const boxW = textW + padX * 2;
          const boxH = 16 + padY * 2;
          const boxX = lx - padX;
          const boxY = ly - boxH / 2;

          // Dark semi-transparent background pill (fade with depth).
          ctx.globalAlpha = 0.7 + depth * 0.2;
          ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
          ctx.beginPath();
          ctx.roundRect(boxX, boxY, boxW, boxH, 4);
          ctx.fill();

          // Colored left border accent.
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.roundRect(boxX, boxY, 3, boxH, [4, 0, 0, 4]);
          ctx.fill();

          // Label text.
          ctx.globalAlpha = 0.85 + depth * 0.15;
          ctx.fillStyle = '#fff';
          ctx.fillText(label, lx, ly);
        }
        ctx.globalAlpha = 1;
      }

      stateRef.current.screenPoints = localPoints;
      if (buildIndex) rebuildIndex();
    },
    [height, points, centroids, showCentroids, pitch, rebuildIndex, yaw, zoom],
  );

  // Initial draw and on dependency changes (rebuild index when not interacting).
  React.useEffect(() => {
    redraw(!isInteracting);
  }, [redraw, isInteracting]);

  // Resize observer.
  React.useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => redraw(!isInteracting));
    ro.observe(el);
    return () => ro.disconnect();
  }, [redraw, isInteracting]);

  // Wheel handler for zoom (native listener with passive: false to block page scroll).
  React.useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      const delta = Math.sign(e.deltaY);
      setZoom((z) => Math.max(0.3, Math.min(12, z * (delta > 0 ? 0.88 : 1.12))));
    };

    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, []);

  const pick = React.useCallback((clientX: number, clientY: number) => {
    const container = containerRef.current;
    if (!container) return null;
    const rect = container.getBoundingClientRect();
    const mx = clientX - rect.left;
    const my = clientY - rect.top;

    const idx = stateRef.current.index;
    if (!idx) return null;
    const found = idx.find(mx, my, 10);
    if (!found) return null;
    return { point: found as StarMapPoint, x: mx, y: my };
  }, []);

  const dragRef = React.useRef<{ x: number; y: number; yaw: number; pitch: number } | null>(null);

  return (
    <Box
      ref={containerRef}
      sx={{
        position: 'relative',
        width: '100%',
        height,
        borderRadius: 2,
        overflow: 'hidden',
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.paper',
        overscrollBehavior: 'contain',
      }}
      onMouseLeave={() => setHover(null)}
      onMouseMove={(e) => {
        if (isInteracting) return;
        const picked = pick(e.clientX, e.clientY);
        setHover(picked);
      }}
      onClick={(e) => {
        if (!onPointClick) return;
        const picked = pick(e.clientX, e.clientY);
        if (picked) onPointClick(picked.point);
      }}
      onMouseDown={(e) => {
        dragRef.current = { x: e.clientX, y: e.clientY, yaw, pitch };
        setIsInteracting(true);
        setHover(null);
      }}
      onMouseUp={() => {
        dragRef.current = null;
        setIsInteracting(false);
        // rebuild index after interaction ends
        setTimeout(() => redraw(true), 0);
      }}
      onMouseMoveCapture={(e) => {
        const d = dragRef.current;
        if (!d) return;
        const dx = e.clientX - d.x;
        const dy = e.clientY - d.y;
        setYaw(d.yaw + dx * 0.006);
        setPitch(Math.max(-1.2, Math.min(1.2, d.pitch + dy * 0.006)));
      }}
    >
      {/* Canvas is absolute so it can't affect container layout (prevents resize loops). */}
      <canvas ref={canvasRef} style={{ display: 'block', position: 'absolute', top: 0, left: 0 }} />

      {hover?.point && (
        <Paper
          elevation={6}
          sx={{
            position: 'absolute',
            left: Math.min(hover.x + 12, (stateRef.current.cssW || 0) - 320),
            top: Math.max(hover.y - 12, 12),
            width: 320,
            p: 1.25,
            pointerEvents: 'none',
          }}
        >
          <Typography variant="subtitle2" fontWeight={800} noWrap>
            {hover.point.title || `Paper #${hover.point.paper_id}`}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            {hover.point.date ? `Date: ${hover.point.date}` : ''}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            {hover.point.dominant_label ? `Aligns to: ${hover.point.dominant_label}` : 'Aligns to: (unknown)'}
          </Typography>
        </Paper>
      )}
    </Box>
  );
}

