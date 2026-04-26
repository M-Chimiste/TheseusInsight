import React, { useMemo } from 'react';

interface MindMapHeroProps {
  width: number;
  height: number;
  seed?: number;
  accent?: string;
}

const MindMapHero: React.FC<MindMapHeroProps> = ({
  width,
  height,
  seed = 2,
  accent = '#5EEAD4',
}) => {
  const { nodes } = useMemo(() => {
    let r = seed * 11.3;
    const rand = () => {
      r = (r * 9301 + 49297) % 233280;
      return r / 233280;
    };
    const nodes: { x: number; y: number; r: number; parent?: number }[] = [
      { x: width / 2, y: height / 2, r: 28 },
    ];
    const ringDefs = [
      { count: 6, radius: Math.min(width, height) * 0.28, nodeR: 14 },
      { count: 10, radius: Math.min(width, height) * 0.44, nodeR: 9 },
    ];
    ringDefs.forEach((ring, ri) => {
      for (let i = 0; i < ring.count; i++) {
        const a = (i / ring.count) * Math.PI * 2 + ri * 0.2 + rand() * 0.1;
        nodes.push({
          x: width / 2 + Math.cos(a) * ring.radius,
          y: height / 2 + Math.sin(a) * ring.radius,
          r: ring.nodeR,
          parent: ri === 0 ? 0 : Math.max(1, Math.floor(i / (ring.count / 6)) + 1),
        });
      }
    });
    return { nodes };
  }, [width, height, seed]);

  return (
    <svg width={width} height={height} style={{ display: 'block' }} aria-hidden>
      {nodes.slice(1).map((n, i) => {
        const p = nodes[n.parent ?? 0];
        return (
          <line
            key={i}
            x1={p.x}
            y1={p.y}
            x2={n.x}
            y2={n.y}
            stroke={accent}
            opacity={0.2}
            strokeWidth={1}
          />
        );
      })}
      {nodes.map((n, i) => (
        <g key={i}>
          <circle cx={n.x} cy={n.y} r={n.r + 4} fill={accent} opacity={0.1} />
          <circle
            cx={n.x}
            cy={n.y}
            r={n.r}
            fill={i === 0 ? accent : 'none'}
            stroke={accent}
            strokeWidth={1.2}
            opacity={i === 0 ? 0.95 : 0.75}
          />
        </g>
      ))}
    </svg>
  );
};

export default MindMapHero;
