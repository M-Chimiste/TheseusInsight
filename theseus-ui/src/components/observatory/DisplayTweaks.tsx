import React from 'react';
import {
  Box,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  Button,
} from '@mui/material';
import { useDesign } from '../../contexts/DesignContext';
import { ACCENT_PRESETS, OBS, withAlpha } from '../../styles/observatoryTokens';
import type { CardStyle, Density } from '../../styles/observatoryTokens';

const sectionLabel = {
  fontFamily: OBS.mono,
  fontSize: 10,
  letterSpacing: '0.12em',
  textTransform: 'uppercase' as const,
  color: OBS.textDim,
  marginBottom: 8,
};

const DisplayTweaks: React.FC = () => {
  const { accent, density, cardStyle, setAccent, setDensity, setCardStyle, reset } = useDesign();

  return (
    <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
      {/* Accent color */}
      <Box>
        <div style={sectionLabel}>Accent color</div>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          {ACCENT_PRESETS.map((p) => {
            const selected = accent.toLowerCase() === p.value.toLowerCase();
            return (
              <Box
                key={p.value}
                onClick={() => setAccent(p.value)}
                title={p.label}
                sx={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  background: p.value,
                  cursor: 'pointer',
                  border: selected
                    ? `2px solid ${OBS.text}`
                    : `2px solid transparent`,
                  outline: selected ? `1px solid ${withAlpha(p.value, 0.5)}` : 'none',
                  outlineOffset: 2,
                  boxShadow: selected ? `0 0 12px ${withAlpha(p.value, 0.6)}` : 'none',
                  transition: 'transform 0.12s ease, box-shadow 0.12s ease',
                  '&:hover': { transform: 'scale(1.08)' },
                }}
              />
            );
          })}
          <Box
            component="label"
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              ml: 1,
              cursor: 'pointer',
              border: `1px dashed ${OBS.border}`,
              borderRadius: 1,
              px: 1,
              py: 0.5,
              fontFamily: OBS.mono,
              fontSize: 10,
              color: OBS.textMuted,
            }}
          >
            <Box
              sx={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                background: accent,
                border: `1px solid ${OBS.border}`,
              }}
            />
            <span>custom</span>
            <input
              type="color"
              value={accent}
              onChange={(e) => setAccent(e.target.value)}
              style={{ width: 0, height: 0, opacity: 0, position: 'absolute' }}
            />
          </Box>
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          Recolors charts, sparklines, score bars, sidebar active marker, and primary buttons.
        </Typography>
      </Box>

      {/* Density */}
      <Box>
        <div style={sectionLabel}>Density</div>
        <ToggleButtonGroup
          value={density}
          exclusive
          size="small"
          onChange={(_, v) => v && setDensity(v as Density)}
        >
          <ToggleButton value="spacious">Spacious</ToggleButton>
          <ToggleButton value="balanced">Balanced</ToggleButton>
          <ToggleButton value="dense">Dense</ToggleButton>
        </ToggleButtonGroup>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          Adjusts page padding and sidebar row height.
        </Typography>
      </Box>

      {/* Card style */}
      <Box>
        <div style={sectionLabel}>Card style</div>
        <ToggleButtonGroup
          value={cardStyle}
          exclusive
          size="small"
          onChange={(_, v) => v && setCardStyle(v as CardStyle)}
        >
          <ToggleButton value="flat">Flat</ToggleButton>
          <ToggleButton value="bordered">Bordered</ToggleButton>
          <ToggleButton value="elevated">Elevated</ToggleButton>
        </ToggleButtonGroup>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          Surface treatment for Observatory cards across every page.
        </Typography>
      </Box>

      {/* Reset */}
      <Box sx={{ display: 'flex', alignItems: 'flex-end' }}>
        <Button onClick={reset} variant="outlined" size="small">
          Reset to defaults
        </Button>
      </Box>
    </Box>
  );
};

export default DisplayTweaks;
