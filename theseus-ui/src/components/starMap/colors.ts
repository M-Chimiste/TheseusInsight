// Observatory star-map palette: cyan/violet/lime/amber/pink + supporting hues.
// Order matches the Direction A artboard. `colorForKey` distributes deterministically
// so the same cluster id always lights up the same color across views.
export const STAR_MAP_PALETTE = [
  '#5EEAD4', // cyan (Observatory primary accent)
  '#A78BFA', // violet
  '#D9F99D', // lime
  '#F472B6', // pink
  '#FCD34D', // amber
  '#7DD3FC', // sky
  '#34D399', // emerald
  '#FB7185', // rose
  '#FB923C', // orange
  '#94A3B8', // slate (other / "rest")
] as const;

export function colorForKey(key: number | null | undefined) {
  const idx = Math.abs(Number(key ?? 0)) % STAR_MAP_PALETTE.length;
  return STAR_MAP_PALETTE[idx];
}
