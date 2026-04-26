import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { OBS, onAccent, withAlpha } from '../../styles/observatoryTokens';
import { useDesign } from '../../contexts/DesignContext';

type Variant = 'solid' | 'outline' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

interface ObsButtonProps {
  children: ReactNode;
  variant?: Variant;
  size?: Size;
  accent?: string;
  startIcon?: ReactNode;
  endIcon?: ReactNode;
  fullWidth?: boolean;
  disabled?: boolean;
  type?: 'button' | 'submit' | 'reset';
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
  style?: CSSProperties;
  title?: string;
}

const SIZE: Record<Size, { h: number; px: number; fs: number }> = {
  sm: { h: 24, px: 8,  fs: 11 },
  md: { h: 30, px: 12, fs: 12 },
  lg: { h: 36, px: 16, fs: 13 },
};

const ObsButton: React.FC<ObsButtonProps> = ({
  children,
  variant = 'solid',
  size = 'md',
  accent: accentProp,
  startIcon,
  endIcon,
  fullWidth,
  disabled,
  type = 'button',
  onClick,
  style = {},
  title,
}) => {
  const { accent: ctxAccent } = useDesign();
  const accent = accentProp ?? ctxAccent;
  const fg = onAccent(accent);
  const sz = SIZE[size];

  const base: CSSProperties = {
    height: sz.h,
    padding: `0 ${sz.px}px`,
    fontSize: sz.fs,
    fontFamily: OBS.sans,
    fontWeight: variant === 'ghost' ? 500 : 600,
    letterSpacing: '-0.005em',
    borderRadius: OBS.radius,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.4 : 1,
    width: fullWidth ? '100%' : undefined,
    transition: 'background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease',
    border: '1px solid transparent',
    whiteSpace: 'nowrap',
  };

  if (variant === 'solid') {
    base.background = accent;
    base.color = fg;
    base.borderColor = accent;
  } else if (variant === 'outline') {
    base.background = withAlpha(accent, 0.08);
    base.color = accent;
    base.borderColor = withAlpha(accent, 0.45);
  } else {
    base.background = 'transparent';
    base.color = OBS.text;
    base.borderColor = OBS.border;
  }

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      title={title}
      style={{ ...base, ...style }}
    >
      {startIcon}
      {children}
      {endIcon}
    </button>
  );
};

export default ObsButton;
