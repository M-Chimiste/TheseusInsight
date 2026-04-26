import React, { useMemo } from 'react';

interface MiniStarFieldProps {
  width: number;
  height: number;
  count?: number;
  seed?: number;
  palette?: string[];
  showClusters?: boolean;
  style?: React.CSSProperties;
}

const MiniStarField: React.FC<MiniStarFieldProps> = ({
  width,
  height,
  count = 280,
  seed = 3,
  palette = ['#22d3ee', '#a78bfa', '#f472b6', '#fbbf24'],
  showClusters = true,
  style,
}) => {
  const { stars, clusters } = useMemo(() => {
    let r = seed * 13.7;
    const rand = () => {
      r = (r * 9301 + 49297) % 233280;
      return r / 233280;
    };
    const stars: { cx: number; cy: number; rad: number; color: string; op: number }[] = [];
    for (let i = 0; i < count; i++) {
      const cx = rand() * width;
      const cy = rand() * height;
      const rad = 0.4 + rand() * 1.8;
      const color = palette[Math.floor(rand() * palette.length)];
      const op = 0.35 + rand() * 0.6;
      stars.push({ cx, cy, rad, color, op });
    }
    const clusters: { cx: number; cy: number; r: number; color: string }[] = [];
    if (showClusters) {
      for (let i = 0; i < 5; i++) {
        clusters.push({
          cx: rand() * width,
          cy: rand() * height,
          r: 60 + rand() * 90,
          color: palette[Math.floor(rand() * palette.length)],
        });
      }
    }
    return { stars, clusters };
  }, [width, height, count, seed, palette, showClusters]);

  return (
    <svg width={width} height={height} style={{ display: 'block', ...style }} aria-hidden>
      {clusters.map((c, i) => (
        <circle
          key={'c' + i}
          cx={c.cx}
          cy={c.cy}
          r={c.r}
          fill={c.color}
          opacity={0.06}
          style={{ filter: 'blur(18px)' }}
        />
      ))}
      {stars.map((s, i) => (
        <circle key={i} cx={s.cx} cy={s.cy} r={s.rad} fill={s.color} opacity={s.op} />
      ))}
    </svg>
  );
};

export default MiniStarField;
