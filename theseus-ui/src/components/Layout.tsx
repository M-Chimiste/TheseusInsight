import React from 'react';
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
} from '@mui/icons-material';
import { useTheme as useCustomTheme } from '../contexts/ThemeContext';
import { useLayout } from '../contexts/LayoutContext';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { isDarkMode, toggleTheme } = useCustomTheme();
  const { isDrawerOpen, currentDrawerWidth, toggleDrawer } = useLayout();

  const menuItems = [
    { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
    { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
    { text: 'Newsletter Builder', icon: <ArticleIcon />, path: '/newsletter' },
    { text: 'Podcast Creator', icon: <PodcastIcon />, path: '/podcast' },
    { text: 'Visualizer', icon: <MovieIcon />, path: '/visualizer' },
    { text: 'Papers', icon: <MenuBookIcon />, path: '/papers' },
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
          bgcolor: 'background.paper',
          color: 'text.primary',
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
            background: 'linear-gradient(180deg, #1e3a8a 0%, #1e40af 100%)',
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
        {children}
      </Box>
    </Box>
  );
};

export default Layout; 