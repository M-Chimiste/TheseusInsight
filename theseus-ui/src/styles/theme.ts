import { createTheme } from '@mui/material/styles';
import type { Theme } from '@mui/material/styles';
import { OBS, onAccent, withAlpha } from './observatoryTokens';

interface BuildThemeOptions {
  accent?: string;
}

export function buildTheme({ accent = OBS.cyan }: BuildThemeOptions = {}): Theme {
  const fg = onAccent(accent);

  return createTheme({
    palette: {
      mode: 'dark',
      primary: {
        main: accent,
        light: accent,
        dark: accent,
        contrastText: fg,
      },
      secondary: {
        main: OBS.violet,
        contrastText: '#0A0A0A',
      },
      success: { main: OBS.success, contrastText: '#0A0A0A' },
      warning: { main: OBS.warning, contrastText: '#0A0A0A' },
      error:   { main: OBS.danger,  contrastText: '#FFFFFF' },
      info:    { main: OBS.violet,  contrastText: '#0A0A0A' },
      background: {
        default: OBS.bg,
        paper: OBS.surface,
      },
      text: {
        primary: OBS.text,
        secondary: OBS.textMuted,
        disabled: OBS.textDim,
      },
      divider: OBS.border,
      action: {
        hover: 'rgba(255,255,255,0.04)',
        selected: 'rgba(255,255,255,0.08)',
        active: OBS.text,
      },
    },
    typography: {
      fontFamily: OBS.sans,
      htmlFontSize: 16,
      h1: { fontFamily: OBS.serif, letterSpacing: '-0.02em', fontWeight: 400 },
      h2: { fontFamily: OBS.serif, letterSpacing: '-0.02em', fontWeight: 400 },
      h3: { fontFamily: OBS.serif, letterSpacing: '-0.02em', fontWeight: 400 },
      h4: { fontFamily: OBS.serif, letterSpacing: '-0.02em', fontWeight: 400 },
      h5: { fontFamily: OBS.serif, letterSpacing: '-0.015em', fontWeight: 400 },
      h6: { fontFamily: OBS.sans, letterSpacing: '-0.005em', fontWeight: 600 },
      subtitle1: { fontWeight: 500, letterSpacing: '-0.005em' },
      subtitle2: { fontWeight: 500, letterSpacing: '-0.005em' },
      body1: { fontFamily: OBS.sans },
      body2: { fontFamily: OBS.sans, color: OBS.textMuted },
      button: { fontFamily: OBS.sans, fontWeight: 600, letterSpacing: '-0.005em' },
      caption: { fontFamily: OBS.mono, letterSpacing: '0.04em' },
      overline: {
        fontFamily: OBS.mono,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        fontSize: 10,
      },
    },
    shape: { borderRadius: OBS.radius },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            backgroundColor: OBS.bg,
            color: OBS.text,
            fontFamily: OBS.sans,
          },
          '*::-webkit-scrollbar': { width: 10, height: 10 },
          '*::-webkit-scrollbar-track': { background: OBS.bg },
          '*::-webkit-scrollbar-thumb': {
            background: OBS.surfaceHi,
            borderRadius: 5,
            border: `2px solid ${OBS.bg}`,
          },
          '*::-webkit-scrollbar-thumb:hover': { background: OBS.surfaceMax },
        },
      },
      MuiPaper: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            backgroundColor: OBS.surface,
          },
        },
      },
      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            backgroundColor: OBS.surface,
            border: `1px solid ${OBS.border}`,
            borderRadius: OBS.radiusLg,
            boxShadow: 'none',
            backgroundImage: 'none',
          },
        },
      },
      MuiAppBar: {
        defaultProps: { elevation: 0, color: 'transparent' },
        styleOverrides: {
          root: {
            backgroundColor: 'rgba(7,11,20,0.85)',
            backdropFilter: 'blur(8px)',
            borderBottom: `1px solid ${OBS.border}`,
            backgroundImage: 'none',
          },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: {
            backgroundColor: OBS.bg,
            backgroundImage: 'none',
            borderRight: `1px solid ${OBS.border}`,
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true, disableRipple: false },
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderRadius: OBS.radius,
            fontWeight: 600,
            letterSpacing: '-0.005em',
          },
          containedPrimary: {
            backgroundColor: accent,
            color: fg,
            '&:hover': { backgroundColor: withAlpha(accent, 0.85), color: fg },
          },
          outlined: {
            borderColor: OBS.border,
            color: OBS.text,
            '&:hover': {
              borderColor: OBS.borderHi,
              backgroundColor: 'rgba(255,255,255,0.03)',
            },
          },
          text: {
            color: OBS.textMuted,
            '&:hover': { color: OBS.text, backgroundColor: 'rgba(255,255,255,0.04)' },
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            color: OBS.textMuted,
            '&:hover': { color: OBS.text, backgroundColor: 'rgba(255,255,255,0.05)' },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            fontFamily: OBS.mono,
            fontSize: 10,
            letterSpacing: '0.04em',
            borderRadius: 3,
            height: 22,
          },
          outlined: {
            borderColor: withAlpha(accent, 0.35),
            color: accent,
          },
          filled: {
            backgroundColor: withAlpha(accent, 0.1),
            color: accent,
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            backgroundColor: OBS.surface,
            borderRadius: OBS.radius,
            '& .MuiOutlinedInput-notchedOutline': { borderColor: OBS.border },
            '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: OBS.borderHi },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: accent, borderWidth: 1 },
          },
          input: { fontFamily: OBS.sans },
        },
      },
      MuiInputLabel: {
        styleOverrides: {
          root: {
            color: OBS.textMuted,
            '&.Mui-focused': { color: accent },
          },
        },
      },
      MuiTextField: {
        defaultProps: { variant: 'outlined', size: 'small' },
      },
      MuiSelect: {
        styleOverrides: {
          icon: { color: OBS.textMuted },
        },
      },
      MuiMenu: {
        styleOverrides: {
          paper: {
            backgroundColor: OBS.surfaceHi,
            border: `1px solid ${OBS.border}`,
            backgroundImage: 'none',
          },
        },
      },
      MuiMenuItem: {
        styleOverrides: {
          root: {
            fontSize: 13,
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.04)' },
            '&.Mui-selected': { backgroundColor: withAlpha(accent, 0.12), color: OBS.text },
            '&.Mui-selected:hover': { backgroundColor: withAlpha(accent, 0.18) },
          },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: {
            backgroundColor: OBS.surfaceHi,
            backgroundImage: 'none',
            border: `1px solid ${OBS.border}`,
            borderRadius: OBS.radiusLg,
          },
        },
      },
      MuiDialogTitle: {
        styleOverrides: {
          root: {
            fontFamily: OBS.serif,
            letterSpacing: '-0.015em',
            fontSize: 22,
          },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            backgroundColor: OBS.surfaceMax,
            border: `1px solid ${OBS.border}`,
            color: OBS.text,
            fontSize: 11,
            fontFamily: OBS.sans,
            padding: '6px 8px',
            borderRadius: OBS.radius,
          },
          arrow: { color: OBS.surfaceMax },
        },
      },
      MuiSwitch: {
        styleOverrides: {
          track: { backgroundColor: OBS.borderHi },
          switchBase: {
            '&.Mui-checked': { color: accent },
            '&.Mui-checked + .MuiSwitch-track': {
              backgroundColor: withAlpha(accent, 0.4),
            },
          },
        },
      },
      MuiCheckbox: {
        styleOverrides: {
          root: {
            color: OBS.borderHi,
            '&.Mui-checked': { color: accent },
          },
        },
      },
      MuiRadio: {
        styleOverrides: {
          root: {
            color: OBS.borderHi,
            '&.Mui-checked': { color: accent },
          },
        },
      },
      MuiSlider: {
        styleOverrides: {
          root: { color: accent },
          rail: { color: OBS.borderHi, opacity: 1 },
        },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: { backgroundColor: OBS.border, borderRadius: 1, height: 2 },
          bar: { backgroundColor: accent, borderRadius: 1 },
        },
      },
      MuiCircularProgress: {
        styleOverrides: {
          root: { color: accent },
        },
      },
      MuiTabs: {
        styleOverrides: {
          root: { borderBottom: `1px solid ${OBS.border}` },
          indicator: { backgroundColor: accent, height: 2 },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontFamily: OBS.sans,
            fontSize: 12,
            color: OBS.textMuted,
            minHeight: 40,
            '&.Mui-selected': { color: OBS.text },
          },
        },
      },
      MuiToggleButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderColor: OBS.border,
            color: OBS.textMuted,
            fontFamily: OBS.mono,
            fontSize: 11,
            letterSpacing: '0.04em',
            '&.Mui-selected': {
              backgroundColor: withAlpha(accent, 0.12),
              color: accent,
              borderColor: withAlpha(accent, 0.4),
              '&:hover': { backgroundColor: withAlpha(accent, 0.2) },
            },
          },
        },
      },
      MuiAlert: {
        styleOverrides: {
          root: {
            borderRadius: OBS.radius,
            border: `1px solid ${OBS.border}`,
            backgroundColor: OBS.surface,
          },
          standardWarning: {
            color: OBS.warning,
            border: `1px solid ${withAlpha(OBS.warning, 0.35)}`,
            backgroundColor: withAlpha(OBS.warning, 0.08),
          },
          standardError: {
            color: OBS.danger,
            border: `1px solid ${withAlpha(OBS.danger, 0.35)}`,
            backgroundColor: withAlpha(OBS.danger, 0.08),
          },
          standardSuccess: {
            color: OBS.success,
            border: `1px solid ${withAlpha(OBS.success, 0.35)}`,
            backgroundColor: withAlpha(OBS.success, 0.08),
          },
          standardInfo: {
            color: accent,
            border: `1px solid ${withAlpha(accent, 0.35)}`,
            backgroundColor: withAlpha(accent, 0.08),
          },
        },
      },
      MuiAutocomplete: {
        styleOverrides: {
          paper: {
            backgroundColor: OBS.surfaceHi,
            border: `1px solid ${OBS.border}`,
            backgroundImage: 'none',
          },
          option: {
            fontSize: 13,
            '&[aria-selected="true"]': { backgroundColor: withAlpha(accent, 0.12) },
          },
        },
      },
      MuiDivider: {
        styleOverrides: {
          root: { borderColor: OBS.border },
        },
      },
      MuiSkeleton: {
        styleOverrides: {
          root: { backgroundColor: OBS.surfaceHi },
        },
      },
      MuiList: {
        styleOverrides: {
          root: { paddingTop: 4, paddingBottom: 4 },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: OBS.radius,
            '&.Mui-selected': {
              backgroundColor: withAlpha(accent, 0.1),
              '&:hover': { backgroundColor: withAlpha(accent, 0.16) },
            },
          },
        },
      },
    },
  });
}

// Backwards-compat exports for any module that still imports the old names.
export const darkTheme = buildTheme();
export const lightTheme = darkTheme;
