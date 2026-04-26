import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { OBS } from '../../styles/observatoryTokens';
import { useDesign } from '../../contexts/DesignContext';

interface ObsKickerProps {
  children: ReactNode;
  accent?: string;
  muted?: boolean;
  style?: CSSProperties;
}

const ObsKicker: React.FC<ObsKickerProps> = ({ children, accent: accentProp, muted, style = {} }) => {
  const { accent: ctxAccent } = useDesign();
  const accent = accentProp ?? ctxAccent;

  return (
    <div
      style={{
        fontFamily: OBS.mono,
        fontSize: 10,
        letterSpacing: '0.12em',
        color: muted ? OBS.textDim : accent,
        textTransform: 'uppercase',
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export default ObsKicker;
