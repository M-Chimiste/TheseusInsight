import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  useTheme,
} from '@mui/material';
import {
  Edit as EditIcon,
  Add as AddIcon,
  Visibility as VisibilityIcon,
  Dashboard as DashboardIcon,
  Science as ScienceIcon,
} from '@mui/icons-material';

const Navigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();

  const isActive = (path: string) => location.pathname === path;

  const navItems = [
    { path: '/', label: 'Dashboard', icon: <DashboardIcon /> },
    { path: '/editor', label: 'Script Editor', icon: <EditIcon /> },
    { path: '/generator', label: 'New Podcast', icon: <AddIcon /> },
    { path: '/visualizer', label: 'Visualizer', icon: <VisibilityIcon /> },
    { path: '/paperpal', label: 'Run PaperPal', icon: <ScienceIcon /> },
  ];

  return (
    <AppBar position="static" color="default" elevation={1}>
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 0, mr: 4 }}>
          PaperPal
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          {navItems.map(({ path, label, icon }) => (
            <Button
              key={path}
              startIcon={icon}
              onClick={() => navigate(path)}
              color={isActive(path) ? 'primary' : 'inherit'}
              variant={isActive(path) ? 'contained' : 'text'}
              sx={{
                borderRadius: 2,
                '&:hover': {
                  backgroundColor: isActive(path)
                    ? theme.palette.primary.dark
                    : 'rgba(255, 255, 255, 0.08)',
                },
              }}
            >
              {label}
            </Button>
          ))}
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navigation; 