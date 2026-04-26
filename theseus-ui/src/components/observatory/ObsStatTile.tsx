import React from 'react';
import type { ReactNode } from 'react';
import ObsCard from './ObsCard';
import Sparkline from './Sparkline';
import { OBS, withAlpha } from '../../styles/observatoryTokens';
import { useDesign } from '../../contexts/DesignContext';

interface ObsStatTileProps {
  label: string;
  value: ReactNode;
  delta?: ReactNode;
  seed?: number;
  values?: number[];
  accent?: string;
  trailingIcon?: ReactNode;
  onClick?: () => void;
}

const ObsStatTile: React.FC<ObsStatTileProps> = ({
  label,
  value,
  delta,
  seed = 1,
  values,
  accent: accentProp,
  trailingIcon,
  onClick,
}) => {
  const { accent: ctxAccent } = useDesign();
  const accent = accentProp ?? ctxAccent;

  return (
    <ObsCard
      meta={delta}
      onClick={onClick}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
    >
      <div
        style={{
          fontFamily: OBS.mono,
          fontSize: 10,
          color: OBS.textDim,
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          marginBottom: 8,
        }}
      >
        {label}
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <div
          style={{
            fontFamily: OBS.serif,
            fontSize: 30,
            lineHeight: 1,
            letterSpacing: '-0.02em',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {value}
        </div>
        {trailingIcon ?? (
          <Sparkline
            seed={seed}
            values={values}
            width={60}
            height={22}
            color={accent}
            fill={withAlpha(accent, 0.13)}
          />
        )}
      </div>
    </ObsCard>
  );
};

export default ObsStatTile;
