import React, { useEffect, useRef, useState } from 'react';
import { Box, Alert } from '@mui/material';
import { useLayout } from '../contexts/LayoutContext';
import { useProfile } from '../contexts/ProfileContext';
import { settingsApi } from '../services/api';
import ProfileSelector from './ProfileSelector';
import { OBS } from '../styles/observatoryTokens';
import ObsSidebar from './observatory/ObsSidebar';

const REQUIRED_KEYS = [
  'OPENAI_API_KEY',
  'ANTHROPIC_API_KEY',
  'GMAIL_SENDER_ADDRESS',
  'CLIENT_SECRET',
  'PROJECT_ID',
  'GMAIL_APP_PASSWORD',
];

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { isDrawerOpen, currentDrawerWidth, toggleDrawer, setHeaderHeight } = useLayout();
  useProfile(); // Initialize profile context

  const [missingKeys, setMissingKeys] = useState<string[]>([]);
  const headerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    settingsApi
      .getCredentials()
      .then((res) => {
        const creds = res.data as Record<string, string>;
        const missing = REQUIRED_KEYS.filter((key) => !creds[key]);
        setMissingKeys(missing);
      })
      .catch((err) => {
        console.error('Failed to fetch credentials:', err);
      });
  }, []);

  useEffect(() => {
    const update = () => {
      if (headerRef.current) setHeaderHeight(headerRef.current.offsetHeight);
    };
    update();
    const ro = new ResizeObserver(update);
    if (headerRef.current) ro.observe(headerRef.current);
    return () => ro.disconnect();
  }, [setHeaderHeight]);

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', background: OBS.bg }}>
      <ObsSidebar
        width={currentDrawerWidth}
        collapsed={!isDrawerOpen}
        onToggle={toggleDrawer}
      />

      {/* Top strip — thin, absolute, picks up width from drawer */}
      <Box
        ref={headerRef}
        sx={{
          position: 'fixed',
          top: 0,
          left: `${currentDrawerWidth}px`,
          right: 0,
          height: 56,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: 1.5,
          px: 2.5,
          zIndex: 1100,
          background: 'rgba(7,11,20,0.85)',
          backdropFilter: 'blur(8px)',
          borderBottom: `1px solid ${OBS.border}`,
          transition: 'left 0.25s ease',
        }}
      >
        <ProfileSelector allowMultiple={true} label="Profile" compact={true} />
      </Box>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          ml: `${currentDrawerWidth}px`,
          width: `calc(100% - ${currentDrawerWidth}px)`,
          minHeight: '100vh',
          background: OBS.bg,
          color: OBS.text,
          transition: 'margin-left 0.25s ease, width 0.25s ease',
        }}
      >
        {missingKeys.length > 0 && (
          <Box sx={{ px: 3, pt: '64px' }}>
            <Alert severity="warning" sx={{ mb: 2 }}>
              Some credentials are missing or invalid. Review your API keys in Settings.
            </Alert>
          </Box>
        )}
        {children}
      </Box>
    </Box>
  );
};

export default Layout;
