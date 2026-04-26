import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { OBS, withAlpha } from '../../styles/observatoryTokens';
import { useDesign } from '../../contexts/DesignContext';

interface ObsChipProps {
  children: ReactNode;
  accent?: string;
  tone?: 'solid' | 'ghost';
  style?: CSSProperties;
  onClick?: React.MouseEventHandler<HTMLSpanElement>;
}

const ObsChip: React.FC<ObsChipProps> = ({
  children,
  accent: accentProp,
  tone = 'solid',
  style = {},
  onClick,
}) => {
  const { accent: ctxAccent } = useDesign();
  const accent = accentProp ?? ctxAccent;

  const base: CSSProperties = {
    fontFamily: OBS.mono,
    fontSize: 10,
    padding: '2px 6px',
    borderRadius: 3,
    letterSpacing: '0.04em',
    color: accent,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    cursor: onClick ? 'pointer' : 'default',
    whiteSpace: 'nowrap',
    lineHeight: 1.4,
  };

  if (tone === 'ghost') {
    base.border = `1px solid ${withAlpha(accent, 0.35)}`;
    base.background = 'transparent';
  } else {
    base.background = withAlpha(accent, 0.1);
  }

  return (
    <span style={{ ...base, ...style }} onClick={onClick}>
      {children}
    </span>
  );
};

export default ObsChip;
