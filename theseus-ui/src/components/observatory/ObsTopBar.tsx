import React from 'react';
import type { ReactNode } from 'react';
import { OBS } from '../../styles/observatoryTokens';
import ObsKicker from './ObsKicker';

interface ObsTopBarProps {
  kicker?: ReactNode;
  title?: ReactNode;
  subtitle?: ReactNode;
  cta?: ReactNode;
  rightSlot?: ReactNode;
  bordered?: boolean;
}

const ObsTopBar: React.FC<ObsTopBarProps> = ({
  kicker,
  title,
  subtitle,
  cta,
  rightSlot,
  bordered = true,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-between',
        gap: 16,
        padding: '18px 0 16px',
        marginBottom: 20,
        borderBottom: bordered ? `1px solid ${OBS.border}` : 'none',
        background: `linear-gradient(180deg, ${OBS.bg}, ${OBS.bg}00)`,
      }}
    >
      <div style={{ minWidth: 0 }}>
        {kicker && <ObsKicker style={{ marginBottom: 6 }}>{kicker}</ObsKicker>}
        {title && (
          <div
            style={{
              fontFamily: OBS.serif,
              fontSize: 32,
              letterSpacing: '-0.02em',
              color: OBS.text,
              lineHeight: 1.05,
            }}
          >
            {title}
          </div>
        )}
        {subtitle && (
          <div
            style={{
              fontSize: 13,
              color: OBS.textMuted,
              marginTop: 6,
              lineHeight: 1.4,
              maxWidth: 720,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        {rightSlot}
        {cta}
      </div>
    </div>
  );
};

export default ObsTopBar;
