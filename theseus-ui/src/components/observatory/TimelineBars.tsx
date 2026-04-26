import React, { useMemo } from 'react';

interface TimelineBarsProps {
  width: number;
  height: number;
  seed?: number;
  colors?: string[];
  cols?: number;
  style?: React.CSSProperties;
}

const TimelineBars: React.FC<TimelineBarsProps> = ({
  width,
  height,
  seed = 1,
  colors = ['#22d3ee', '#a78bfa', '#f472b6', '#fbbf24', '#34d399'],
  cols = 26,
  style,
}) => {
  const rows = useMemo(() => {
    let r = seed * 19.1;
    const rand = () => {
      r = (r * 9301 + 49297) % 233280;
      return r / 233280;
    };
    const colW = width / cols;
    const out: { y: number; h: number; fill: string; x: number; w: number }[][] = [];
    for (let c = 0; c < cols; c++) {
      const bars: { y: number; h: number; fill: string; x: number; w: number }[] = [];
      let y = height;
      const stacks = 3 + Math.floor(rand() * 3);
      for (let s = 0; s < stacks; s++) {
        const barH = 6 + rand() * (height / stacks - 4);
        y -= barH;
        bars.push({ y, h: barH - 1.5, fill: colors[s % colors.length], x: c * colW + 1, w: colW - 2 });
      }
      out.push(bars);
    }
    return out;
  }, [width, height, seed, colors, cols]);

  return (
    <svg width={width} height={height} style={{ display: 'block', ...style }} aria-hidden>
      {rows.map((bars, ci) =>
        bars.map((b, bi) => (
          <rect
            key={`${ci}-${bi}`}
            x={b.x}
            y={b.y}
            width={b.w}
            height={b.h}
            fill={b.fill}
            opacity={0.88}
            rx={1}
          />
        ))
      )}
    </svg>
  );
};

export default TimelineBars;
