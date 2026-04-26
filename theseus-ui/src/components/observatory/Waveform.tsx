import React, { useMemo } from 'react';

interface WaveformProps {
  width: number;
  height: number;
  seed?: number;
  color?: string;
  bars?: number;
  progress?: number; // 0..1
  trackColor?: string;
}

const Waveform: React.FC<WaveformProps> = ({
  width,
  height,
  seed = 5,
  color = '#22d3ee',
  bars = 64,
  progress,
  trackColor = 'rgba(255,255,255,0.12)',
}) => {
  const data = useMemo(() => {
    let r = seed * 17.1;
    const rand = () => {
      r = (r * 9301 + 49297) % 233280;
      return r / 233280;
    };
    return Array.from({ length: bars }).map((_, i) => {
      const v = 0.15 + Math.abs(Math.sin(i * 0.4 + seed)) * 0.4 + rand() * 0.45;
      return v;
    });
  }, [seed, bars]);

  const bw = width / bars;
  const cutoff = progress != null ? Math.floor(progress * bars) : bars;

  return (
    <svg width={width} height={height} style={{ display: 'block' }} aria-hidden>
      {data.map((v, i) => {
        const bh = v * height;
        const fill = i <= cutoff ? color : trackColor;
        return (
          <rect
            key={i}
            x={i * bw + 0.5}
            y={(height - bh) / 2}
            width={bw - 1}
            height={bh}
            fill={fill}
            opacity={0.85}
            rx={0.5}
          />
        );
      })}
    </svg>
  );
};

export default Waveform;
