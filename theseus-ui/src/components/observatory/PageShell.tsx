import React from 'react';
import type { ReactNode } from 'react';
import { Box } from '@mui/material';
import { useLayout } from '../../contexts/LayoutContext';
import { useDesign } from '../../contexts/DesignContext';
import { DENSITY, OBS } from '../../styles/observatoryTokens';
import ObsTopBar from './ObsTopBar';

interface PageShellProps {
  kicker?: ReactNode;
  title?: ReactNode;
  subtitle?: ReactNode;
  cta?: ReactNode;
  rightSlot?: ReactNode;
  maxWidth?: number | string;
  children: ReactNode;
}

const PageShell: React.FC<PageShellProps> = ({
  kicker,
  title,
  subtitle,
  cta,
  rightSlot,
  maxWidth = 1640,
  children,
}) => {
  const { headerHeight } = useLayout();
  const { density } = useDesign();
  const pad = DENSITY[density].pad;

  return (
    <Box
      sx={{
        pt: `${headerHeight + 8}px`,
        pb: 4,
        px: { xs: 2, md: `${pad}px` },
        minHeight: '100vh',
        background: `radial-gradient(ellipse at top, ${OBS.surface}, ${OBS.bg} 60%)`,
      }}
    >
      <Box sx={{ maxWidth, mx: 'auto' }}>
        {(kicker || title || subtitle || cta || rightSlot) && (
          <ObsTopBar
            kicker={kicker}
            title={title}
            subtitle={subtitle}
            cta={cta}
            rightSlot={rightSlot}
          />
        )}
        {children}
      </Box>
    </Box>
  );
};

export default PageShell;
