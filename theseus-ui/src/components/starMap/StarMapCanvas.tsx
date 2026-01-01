import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import { select } from 'd3-selection';
import { zoom, zoomIdentity, type ZoomTransform } from 'd3-zoom';
import { quadtree as d3Quadtree, type Quadtree } from 'd3-quadtree';
import type { StarMapPoint, StarMapCentroid } from '../../services/api';
import { colorForKey } from './colors';

type RenderPoint = StarMapPoint & {
  bx: number;
  by: number;
};

function clamp01(v: number) {
  if (Number.isNaN(v)) return 0;
  return Math.max(0, Math.min(1, v));
}

function colorFor(point: StarMapPoint) {
  const key = point.dominant_interest_id ?? point.cluster_id ?? 0;
  return colorForKey(Number(key));
}

export function StarMapCanvas(props: {
  points: StarMapPoint[];
  centroids?: StarMapCentroid[];
  showCentroids?: boolean;
  height?: number;
  onPointClick?: (p: StarMapPoint) => void;
}) {
  const { points, centroids = [], showCentroids = true, height = 560, onPointClick } = props;
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const zoomRef = React.useRef<ReturnType<typeof zoom<HTMLCanvasElement, unknown>> | null>(null);
  const selectionRef = React.useRef<any>(null);
  const isApplyingClampRef = React.useRef(false);

  const [hover, setHover] = React.useState<{ point: StarMapPoint; x: number; y: number } | null>(null);

  type RenderCentroid = StarMapCentroid & { bx: number; by: number };

  const renderStateRef = React.useRef<{
    transform: ZoomTransform;
    quadtree: Quadtree<RenderPoint> | null;
    renderPoints: RenderPoint[];
    renderCentroids: RenderCentroid[];
    cssWidth: number;
    cssHeight: number;
    bounds: { minBX: number; maxBX: number; minBY: number; maxBY: number; pad: number };
  }>({
    transform: zoomIdentity,
    quadtree: null,
    renderPoints: [],
    renderCentroids: [],
    cssWidth: 0,
    cssHeight: 0,
    bounds: { minBX: 0, maxBX: 1, minBY: 0, maxBY: 1, pad: 80 },
  });

  const clampTransform = React.useCallback((t: ZoomTransform) => {
    const state = renderStateRef.current;
    const { cssWidth: w, cssHeight: h } = state;
    const { minBX, maxBX, minBY, maxBY, pad } = state.bounds;
    const k = t.k;

    const boundsW = (maxBX - minBX) * k;
    const boundsH = (maxBY - minBY) * k;

    // If the content is smaller than the viewport (minus padding), keep it centered.
    const innerW = Math.max(1, w - pad * 2);
    const innerH = Math.max(1, h - pad * 2);

    let x: number;
    if (boundsW <= innerW) {
      x = (w - boundsW) / 2 - minBX * k;
    } else {
      const minX = pad - maxBX * k;
      const maxX = w - pad - minBX * k;
      x = Math.max(minX, Math.min(maxX, t.x));
    }

    let y: number;
    if (boundsH <= innerH) {
      y = (h - boundsH) / 2 - minBY * k;
    } else {
      const minY = pad - maxBY * k;
      const maxY = h - pad - minBY * k;
      y = Math.max(minY, Math.min(maxY, t.y));
    }

    return zoomIdentity.translate(x, y).scale(k);
  }, []);

  const redraw = React.useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const state = renderStateRef.current;
    const { transform, cssWidth, cssHeight, renderPoints } = state;

    ctx.save();
    ctx.clearRect(0, 0, cssWidth, cssHeight);

    // Background
    const bg = ctx.createLinearGradient(0, 0, cssWidth, cssHeight);
    bg.addColorStop(0, 'rgba(99, 102, 241, 0.08)');
    bg.addColorStop(1, 'rgba(20, 184, 166, 0.06)');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, cssWidth, cssHeight);

    // Apply zoom transform to canvas.
    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.k, transform.k);

    for (const p of renderPoints) {
      const alpha = 0.25 + 0.75 * clamp01(((p.profile_score ?? 5) - 1) / 9);
      ctx.fillStyle = colorFor(p);
      ctx.globalAlpha = alpha;
      ctx.fillRect(p.bx, p.by, 1.6, 1.6);
    }

    // Draw centroid markers (glowing dots) within the transform.
    const { renderCentroids } = state;
    if (showCentroids && renderCentroids.length > 0) {
      for (const c of renderCentroids) {
        const color = colorForKey(c.interest_id);

        // Outer glow (multiple layers).
        for (let r = 16; r > 0; r -= 3) {
          ctx.globalAlpha = 0.12 * (1 - r / 16);
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(c.bx, c.by, r, 0, Math.PI * 2);
          ctx.fill();
        }

        // Inner bright core.
        ctx.globalAlpha = 0.95;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(c.bx, c.by, 5, 0, Math.PI * 2);
        ctx.fill();

        // White center highlight.
        ctx.globalAlpha = 0.8;
        ctx.fillStyle = '#fff';
        ctx.beginPath();
        ctx.arc(c.bx, c.by, 2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    ctx.restore();
    ctx.globalAlpha = 1;

    // Draw centroid labels OUTSIDE the transform (in screen space) so they don't scale.
    if (showCentroids && renderCentroids.length > 0) {
      const k = transform.k;
      // Only show labels when zoomed in enough (reduces clutter at low zoom).
      const showLabels = k >= 0.8;

      if (showLabels) {
        ctx.save();
        ctx.font = 'bold 11px system-ui, sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';

        // Compute screen positions for all centroids.
        const labelData = renderCentroids.map((c) => {
          const sx = transform.applyX(c.bx);
          const sy = transform.applyY(c.by);
          const label = c.short_label || c.label;
          const metrics = ctx.measureText(label);
          const textW = metrics.width;
          const textH = 14;
          const padX = 6;
          const padY = 3;
          // Position label to the right of the centroid dot.
          const lx = sx + 10;
          const ly = sy;
          return { c, sx, sy, lx, ly, label, textW, textH, padX, padY };
        });

        // Simple collision avoidance: nudge overlapping labels vertically.
        for (let i = 0; i < labelData.length; i++) {
          for (let j = i + 1; j < labelData.length; j++) {
            const a = labelData[i];
            const b = labelData[j];
            const overlapX = Math.abs(a.lx - b.lx) < Math.max(a.textW, b.textW) + 20;
            const overlapY = Math.abs(a.ly - b.ly) < 18;
            if (overlapX && overlapY) {
              // Nudge the second one down.
              b.ly += 20;
            }
          }
        }

        // Draw labels with background pills.
        for (const { c, lx, ly, label, textW, padX, padY } of labelData) {
          const color = colorForKey(c.interest_id);
          const boxW = textW + padX * 2;
          const boxH = 14 + padY * 2;
          const boxX = lx - padX;
          const boxY = ly - boxH / 2;

          // Dark semi-transparent background pill.
          ctx.globalAlpha = 0.85;
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
          ctx.globalAlpha = 1;
          ctx.fillStyle = '#fff';
          ctx.fillText(label, lx, ly);
        }

        ctx.restore();
      }
    }
  }, [showCentroids]);

  // Handle sizing + quadtree rebuild whenever points change or container resizes.
  React.useEffect(() => {
    const el = containerRef.current;
    const canvas = canvasRef.current;
    if (!el || !canvas) return;

    const resize = () => {
      const rect = el.getBoundingClientRect();
      // Use container's actual rendered size; don't let canvas influence it.
      const cssWidth = Math.max(320, Math.floor(rect.width));
      const cssHeight = Math.max(200, Math.floor(rect.height));

      const dpr = window.devicePixelRatio || 1;
      // Set canvas buffer size (not CSS size - that's handled by absolute positioning).
      canvas.width = Math.floor(cssWidth * dpr);
      canvas.height = Math.floor(cssHeight * dpr);
      canvas.style.width = `${cssWidth}px`;
      canvas.style.height = `${cssHeight}px`;

      const ctx = canvas.getContext('2d');
      if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Fit-to-bounds mapping. We DO NOT re-normalize data here; backend already returns normalized-ish coordinates.
      let minX = Infinity;
      let maxX = -Infinity;
      let minY = Infinity;
      let maxY = -Infinity;
      for (const p of points) {
        if (p.x < minX) minX = p.x;
        if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y;
        if (p.y > maxY) maxY = p.y;
      }
      if (!Number.isFinite(minX)) {
        minX = -1;
        maxX = 1;
        minY = -1;
        maxY = 1;
      }
      const dx = maxX - minX || 1;
      const dy = maxY - minY || 1;

      const pad = 80;
      const innerW = Math.max(1, cssWidth - pad * 2);
      const innerH = Math.max(1, cssHeight - pad * 2);

      const renderPoints: RenderPoint[] = points.map((p) => {
        const nx = (p.x - minX) / dx;
        const ny = (p.y - minY) / dy;
        return {
          ...p,
          bx: pad + nx * innerW,
          by: pad + (1 - ny) * innerH,
        };
      });

      // Compute centroid render positions using the same mapping.
      const renderCentroids: RenderCentroid[] = centroids.map((c) => {
        const nx = (c.x - minX) / dx;
        const ny = (c.y - minY) / dy;
        return {
          ...c,
          bx: pad + nx * innerW,
          by: pad + (1 - ny) * innerH,
        };
      });

      // Constrain pan/zoom to the point cloud bounds (pre-transform coords).
      let minBX = Infinity;
      let maxBX = -Infinity;
      let minBY = Infinity;
      let maxBY = -Infinity;
      for (const p of renderPoints) {
        if (p.bx < minBX) minBX = p.bx;
        if (p.bx > maxBX) maxBX = p.bx;
        if (p.by < minBY) minBY = p.by;
        if (p.by > maxBY) maxBY = p.by;
      }
      if (!Number.isFinite(minBX)) {
        minBX = 0;
        maxBX = cssWidth;
        minBY = 0;
        maxBY = cssHeight;
      }
      const translateExtent: [[number, number], [number, number]] = [
        [minBX - pad, minBY - pad],
        [maxBX + pad, maxBY + pad],
      ];

      const qt = d3Quadtree<RenderPoint>()
        .x((d) => d.bx)
        .y((d) => d.by)
        .addAll(renderPoints);

      renderStateRef.current.cssWidth = cssWidth;
      renderStateRef.current.cssHeight = cssHeight;
      renderStateRef.current.renderPoints = renderPoints;
      renderStateRef.current.renderCentroids = renderCentroids;
      renderStateRef.current.quadtree = qt;
      renderStateRef.current.bounds = { minBX, maxBX, minBY, maxBY, pad };

      // Update zoom constraints for the current viewport + data bounds.
      const sel = selectionRef.current ?? select(canvas as any);
      selectionRef.current = sel;

      const z =
        zoomRef.current ??
        zoom<HTMLCanvasElement, unknown>().scaleExtent([0.5, 80]).on('zoom', (event) => {
          // When we programmatically re-apply a clamped transform, D3 emits another zoom event.
          if (isApplyingClampRef.current) {
            isApplyingClampRef.current = false;
            renderStateRef.current.transform = event.transform;
            redraw();
            return;
          }

          const clamped = clampTransform(event.transform);
          const dx = Math.abs(clamped.x - event.transform.x);
          const dy = Math.abs(clamped.y - event.transform.y);
          const dk = Math.abs(clamped.k - event.transform.k);
          if (dx > 0.5 || dy > 0.5 || dk > 1e-6) {
            const s = selectionRef.current;
            const zb = zoomRef.current;
            if (s && zb) {
              isApplyingClampRef.current = true;
              s.call(zb.transform as any, clamped);
              return;
            }
          }

          renderStateRef.current.transform = clamped;
          redraw();
        });

      zoomRef.current = z;
      sel.call(z as any);
      z.extent([
        [0, 0],
        [cssWidth, cssHeight],
      ]).translateExtent(translateExtent);

      // Re-apply current transform so it's clamped to the new extents.
      const clamped = clampTransform(renderStateRef.current.transform);
      renderStateRef.current.transform = clamped;
      isApplyingClampRef.current = true;
      sel.call(z.transform as any, clamped);

      redraw();
    };

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    return () => ro.disconnect();
  }, [height, points, centroids, redraw, clampTransform]);

  // Prevent page scroll while cursor is over the canvas (native listener with passive: false).
  React.useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const stopScroll = (e: WheelEvent) => {
      e.preventDefault();
    };

    el.addEventListener('wheel', stopScroll, { passive: false });
    return () => el.removeEventListener('wheel', stopScroll);
  }, []);

  const pickPoint = React.useCallback((clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const mx = clientX - rect.left;
    const my = clientY - rect.top;

    const state = renderStateRef.current;
    const t = state.transform;
    const q = state.quadtree;
    if (!q) return null;

    const invX = (mx - t.x) / t.k;
    const invY = (my - t.y) / t.k;
    const found = q.find(invX, invY, 6 / t.k);
    if (!found) return null;

    return { point: found as StarMapPoint, x: mx, y: my };
  }, []);

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
        // Prevent trackpad horizontal scroll from moving the page while interacting with the map.
        overscrollBehavior: 'contain',
      }}
      onMouseLeave={() => setHover(null)}
      onMouseMove={(e) => {
        const picked = pickPoint(e.clientX, e.clientY);
        setHover(picked);
      }}
      onClick={(e) => {
        if (!onPointClick) return;
        const picked = pickPoint(e.clientX, e.clientY);
        if (picked) onPointClick(picked.point);
      }}
    >
      {/* Canvas is absolute so it can't affect container layout (prevents resize loops). */}
      <canvas ref={canvasRef} style={{ display: 'block', position: 'absolute', top: 0, left: 0 }} />

      {hover?.point && (
        <Paper
          elevation={6}
          sx={{
            position: 'absolute',
            left: Math.min(hover.x + 12, (renderStateRef.current.cssWidth || 0) - 280),
            top: Math.max(hover.y - 12, 12),
            width: 280,
            p: 1.25,
            pointerEvents: 'none',
          }}
        >
          <Typography variant="subtitle2" fontWeight={700} noWrap>
            {hover.point.title || `Paper #${hover.point.paper_id}`}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            {hover.point.date ? `Date: ${hover.point.date}` : ''}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            {hover.point.dominant_label ? `Aligns to: ${hover.point.dominant_label}` : 'Aligns to: (unknown)'}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            {hover.point.profile_score !== undefined ? `Profile score: ${hover.point.profile_score}` : ''}
          </Typography>
        </Paper>
      )}
    </Box>
  );
}

