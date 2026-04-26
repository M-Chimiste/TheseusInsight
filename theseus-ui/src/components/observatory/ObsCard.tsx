import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { OBS } from '../../styles/observatoryTokens';
import type { CardStyle } from '../../styles/observatoryTokens';
import { useDesign } from '../../contexts/DesignContext';

interface ObsCardProps {
  title?: ReactNode;
  meta?: ReactNode;
  cardStyle?: CardStyle;
  accent?: string;
  padding?: number | string;
  children?: ReactNode;
  style?: CSSProperties;
  onClick?: React.MouseEventHandler<HTMLDivElement>;
  className?: string;
}

const ObsCard: React.FC<ObsCardProps> = ({
  title,
  meta,
  cardStyle: cardStyleProp,
  padding = 16,
  children,
  style = {},
  onClick,
  className,
}) => {
  const { cardStyle: ctxCardStyle } = useDesign();
  const cardStyle = cardStyleProp ?? ctxCardStyle;

  const base: CSSProperties = {
    borderRadius: OBS.radiusLg,
    padding,
    background: OBS.surface,
    color: OBS.text,
    border: `1px solid ${OBS.border}`,
    transition: 'border-color 0.15s ease, background 0.15s ease',
  };

  if (cardStyle === 'flat') {
    base.background = 'transparent';
  } else if (cardStyle === 'elevated') {
    base.background = OBS.surfaceHi;
    base.boxShadow =
      '0 1px 0 rgba(255,255,255,0.04) inset, 0 12px 32px rgba(0,0,0,0.35)';
  }

  return (
    <div className={className} style={{ ...base, ...style }} onClick={onClick}>
      {(title || meta) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 10,
            gap: 8,
          }}
        >
          {title ? (
            <div style={{ fontSize: 12, fontWeight: 600, letterSpacing: '-0.005em' }}>
              {title}
            </div>
          ) : (
            <span />
          )}
          {meta && (
            <div
              style={{
                fontFamily: OBS.mono,
                fontSize: 10,
                color: OBS.textDim,
                letterSpacing: '0.04em',
              }}
            >
              {meta}
            </div>
          )}
        </div>
      )}
      {children}
    </div>
  );
};

export default ObsCard;
