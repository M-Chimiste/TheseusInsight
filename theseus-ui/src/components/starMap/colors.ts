export const STAR_MAP_PALETTE = [
  '#60a5fa', // blue
  '#34d399', // emerald
  '#f472b6', // pink
  '#fbbf24', // amber
  '#a78bfa', // violet
  '#fb7185', // rose
  '#22d3ee', // cyan
  '#4ade80', // green
  '#f97316', // orange
  '#94a3b8', // slate
] as const;

export function colorForKey(key: number | null | undefined) {
  const idx = Math.abs(Number(key ?? 0)) % STAR_MAP_PALETTE.length;
  return STAR_MAP_PALETTE[idx];
}

