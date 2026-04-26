// Observatory design tokens — Direction A from the Claude Design handoff.
// Dark navy console, luminous cyan/violet/lime accents, mixed grotesk + serif + mono.

export const OBS = {
  // Surfaces
  bg: '#070B14',
  surface: '#0C1424',
  surfaceHi: '#11192B',
  surfaceMax: '#172139',

  // Lines
  border: 'rgba(255,255,255,0.06)',
  borderHi: 'rgba(255,255,255,0.10)',

  // Text
  text: '#E8EDF7',
  textMuted: 'rgba(232,237,247,0.62)',
  textDim: 'rgba(232,237,247,0.42)',

  // Accents (defaults; runtime accent overrides cyan)
  cyan: '#5EEAD4',
  violet: '#A78BFA',
  lime: '#D9F99D',
  amber: '#FCD34D',
  pink: '#F472B6',

  // States
  success: '#34D399',
  warning: '#FCD34D',
  danger: '#F87171',

  // Type stacks
  sans: '"Geist", "Inter", ui-sans-serif, system-ui, sans-serif',
  serif: '"Instrument Serif", "Source Serif Pro", Georgia, serif',
  mono: '"Geist Mono", "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace',

  // Geometry
  radiusSm: 4,
  radius: 6,
  radiusLg: 10,
} as const;

export type Density = 'spacious' | 'balanced' | 'dense';
export type CardStyle = 'flat' | 'bordered' | 'elevated';

export const DENSITY: Record<Density, { pad: number; rowH: number; gap: number }> = {
  dense:    { pad: 16, rowH: 28, gap: 8 },
  balanced: { pad: 20, rowH: 32, gap: 12 },
  spacious: { pad: 28, rowH: 36, gap: 16 },
};

// Foreground used over an accent-filled chip / button. Cyan/lime accents need
// a near-black foreground; saturated accents (violet, pink) want white.
export function onAccent(accent: string): string {
  const hex = accent.replace('#', '');
  if (hex.length < 6) return '#0A0A0A';
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  // perceptual luminance
  const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  return lum > 0.55 ? '#042120' : '#F5FBFA';
}

// Translucent accent — useful for backgrounds / glow halos.
export function withAlpha(color: string, alpha: number): string {
  const a = Math.max(0, Math.min(1, alpha));
  if (color.startsWith('rgba') || color.startsWith('rgb')) return color;
  const hex = color.replace('#', '');
  if (hex.length === 3) {
    const r = parseInt(hex[0] + hex[0], 16);
    const g = parseInt(hex[1] + hex[1], 16);
    const b = parseInt(hex[2] + hex[2], 16);
    return `rgba(${r}, ${g}, ${b}, ${a})`;
  }
  if (hex.length >= 6) {
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${a})`;
  }
  return color;
}

export const ACCENT_PRESETS: { label: string; value: string }[] = [
  { label: 'Cyan',   value: '#5EEAD4' },
  { label: 'Violet', value: '#A78BFA' },
  { label: 'Lime',   value: '#D9F99D' },
  { label: 'Amber',  value: '#FCD34D' },
  { label: 'Pink',   value: '#F472B6' },
  { label: 'Sky',    value: '#7DD3FC' },
];
