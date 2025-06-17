import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Alert,
  Tooltip,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Article as ArticleIcon,
  Podcasts as PodcastIcon,
  Brightness4 as DarkModeIcon,
  Brightness7 as LightModeIcon,
  Movie as MovieIcon,
  History as HistoryIcon,
  ListAlt as ListAltIcon,
  MenuBook as MenuBookIcon,
  Dashboard as DashboardIcon,
  Menu as MenuIcon,
  ChevronLeft as ChevronLeftIcon,
  Psychology as PsychologyIcon,
  LibraryBooks as LibraryBooksIcon,
  Storage as StorageIcon,
} from '@mui/icons-material';
import { useTheme as useCustomTheme } from '../contexts/ThemeContext';
import { useTheme } from '@mui/material/styles';
import { useLayout } from '../contexts/LayoutContext';
import { settingsApi } from '../services/api';

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
  const navigate = useNavigate();
  const location = useLocation();
  const { isDarkMode, toggleTheme } = useCustomTheme();
  const { isDrawerOpen, currentDrawerWidth, toggleDrawer } = useLayout();
  const theme = useTheme();

  const [missingKeys, setMissingKeys] = useState<string[]>([]);

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

  const drawerGradient = isDarkMode
    ? 'linear-gradient(180deg, #1e293b 0%, #0f172a 100%)'
    : `linear-gradient(180deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`;

  const menuItems = [
    { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
    { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
    { text: 'Model Catalog', icon: <StorageIcon />, path: '/model-catalog' },
    { text: 'Research Agent', icon: <PsychologyIcon />, path: '/research-agent' },
    { text: 'Newsletter Builder', icon: <ArticleIcon />, path: '/newsletter' },
    { text: 'Podcast Creator', icon: <PodcastIcon />, path: '/podcast' },
    { text: 'Visualizer', icon: <MovieIcon />, path: '/visualizer' },
    { text: 'Papers', icon: <MenuBookIcon />, path: '/papers' },
    { text: 'Research Library', icon: <LibraryBooksIcon />, path: '/research-library' },
    { text: 'Podcast History', icon: <ListAltIcon />, path: '/podcast-history' },
    { text: 'Run History', icon: <HistoryIcon />, path: '/run-history' },
  ];

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{
          width: `calc(100% - ${currentDrawerWidth}px)`,
          ml: `${currentDrawerWidth}px`,
          bgcolor: isDarkMode ? 'rgba(15,23,42,0.8)' : 'rgba(255,255,255,0.8)',
          color: 'text.primary',
          backdropFilter: 'blur(6px)',
          transition: 'width 0.3s, margin 0.3s',
        }}
      >
        <Toolbar>
          <IconButton
            onClick={toggleDrawer}
            color="inherit"
            sx={{ mr: 1 }}
          >
            {isDrawerOpen ? <ChevronLeftIcon /> : <MenuIcon />}
          </IconButton>
          <img src="/logo.png" alt="Theseus Insight Logo" style={{ height: 84, marginRight: 8 }} />
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            Theseus Insight
          </Typography>
          <IconButton onClick={toggleTheme} color="inherit">
            {isDarkMode ? <LightModeIcon /> : <DarkModeIcon />}
          </IconButton>
        </Toolbar>
      </AppBar>
      <Drawer
        sx={{
          width: currentDrawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: currentDrawerWidth,
            boxSizing: 'border-box',
            background: drawerGradient,
            color: 'white',
            transition: 'width 0.3s',
            overflowX: 'hidden',
          },
        }}
        variant="permanent"
        anchor="left"
      >
        <Toolbar />
        <List>
          {menuItems.map((item) => (
            <ListItem key={item.text} disablePadding>
              <Tooltip 
                title={isDrawerOpen ? '' : item.text} 
                placement="right"
                arrow
              >
                <ListItemButton
                  selected={location.pathname === item.path}
                  onClick={() => navigate(item.path)}
                  sx={{
                    minHeight: 48,
                    justifyContent: isDrawerOpen ? 'initial' : 'center',
                    px: 2.5,
                    '&.Mui-selected': {
                      backgroundColor: 'rgba(255, 255, 255, 0.1)',
                      borderLeft: isDrawerOpen ? '4px solid white' : 'none',
                      borderRight: !isDrawerOpen ? '4px solid white' : 'none',
                    },
                    '&:hover': {
                      backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    },
                  }}
                >
                  <ListItemIcon 
                    sx={{ 
                      color: 'white',
                      minWidth: 0,
                      mr: isDrawerOpen ? 3 : 'auto',
                      justifyContent: 'center',
                    }}
                  >
                    {item.icon}
                  </ListItemIcon>
                  <ListItemText 
                    primary={item.text} 
                    sx={{ opacity: isDrawerOpen ? 1 : 0 }} 
                  />
                </ListItemButton>
              </Tooltip>
            </ListItem>
          ))}
        </List>
      </Drawer>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: `calc(100% - ${currentDrawerWidth}px)`,
          minHeight: '100vh',
          bgcolor: 'background.default',
          transition: 'width 0.3s, margin 0.3s',
        }}
      >
        <Toolbar />
        {missingKeys.length > 0 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Some credentials are missing or invalid. Please review your API keys in the Settings page.
          </Alert>
        )}
        {children}
      </Box>
    </Box>
  );
};

export default Layout; 