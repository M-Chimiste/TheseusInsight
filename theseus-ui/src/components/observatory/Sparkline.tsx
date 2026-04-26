import React, { useMemo } from 'react';

interface SparklineProps {
  values?: number[];
  seed?: number;
  width?: number;
  height?: number;
  color?: string;
  fill?: string;
  strokeWidth?: number;
}

function pseudoRandom(seed: number, count: number): number[] {
  const out: number[] = [];
  let x = seed * 7.3;
  for (let i = 0; i < count; i++) {
    x = (x * 9301 + 49297) % 233280;
    out.push(x / 233280);
  }
  return out;
}

const Sparkline: React.FC<SparklineProps> = ({
  values,
  seed = 1,
  width = 60,
  height = 22,
  color = 'currentColor',
  fill,
  strokeWidth = 1.25,
}) => {
  const data = useMemo(() => {
    if (values && values.length > 1) return values;
    return pseudoRandom(seed, 24);
  }, [values, seed]);

  const { path, area } = useMemo(() => {
    const max = Math.max(...data);
    const min = Math.min(...data);
    const norm = data.map((p) => (p - min) / (max - min || 1));
    const pts = norm.map((v, i) => {
      const px = (i / (norm.length - 1)) * width;
      const py = height - v * (height - 2) - 1;
      return `${i === 0 ? 'M' : 'L'}${px.toFixed(1)} ${py.toFixed(1)}`;
    });
    const path = pts.join(' ');
    return { path, area: `${path} L${width} ${height} L0 ${height} Z` };
  }, [data, width, height]);

  return (
    <svg width={width} height={height} style={{ display: 'block' }} aria-hidden>
      {fill && <path d={area} fill={fill} />}
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
};

export default Sparkline;
