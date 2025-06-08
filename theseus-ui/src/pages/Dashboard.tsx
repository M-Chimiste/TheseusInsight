import React from 'react';
import { Grid, Card, CardActionArea, CardContent, Typography, Box } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import SettingsIcon from '@mui/icons-material/Settings';
import EmailIcon from '@mui/icons-material/Email';
import MicIcon from '@mui/icons-material/Mic';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import HistoryIcon from '@mui/icons-material/History';
import PodcastsIcon from '@mui/icons-material/Podcasts';
import GraphicEqIcon from '@mui/icons-material/GraphicEq';
import ScienceIcon from '@mui/icons-material/Science';
import CollectionsBookmarkIcon from '@mui/icons-material/CollectionsBookmark';
import LocalLibraryIcon from '@mui/icons-material/LocalLibrary';

interface NavCardItem {
  title: string;
  description: string;
  icon: React.ReactElement;
  path: string;
}

const navItems: NavCardItem[] = [
  
  
  {
    title: 'Newsletter',
    description: 'Generate research newsletters based on criteria.',
    icon: <EmailIcon fontSize="large" color="primary" />,
    path: '/newsletter',
  },
  {
    title: 'Podcast Creator',
    description: 'Create podcasts from research papers or URLs.',
    icon: <MicIcon fontSize="large" color="primary" />,
    path: '/podcast',
  },
  {
    title: 'Papers',
    description: 'Browse and review historical research papers.',
    icon: <MenuBookIcon fontSize="large" color="primary" />,
    path: '/papers',
  },
  {
    title: 'Research Agent',
    description: 'Automated literature reviews with AI-generated reports.',
    icon: <ScienceIcon fontSize="large" color="primary" />,
    path: '/research-agent',
  },
  {
    title: 'Research Library',
    description: 'Browse and review historical research papers.',
    icon: <LocalLibraryIcon fontSize="large" color="primary" />,
    path: '/research-library',
  },
  {
    title: 'Podcast History',
    description: 'Browse and review previously generated podcasts.',
    icon: <PodcastsIcon fontSize="large" color="primary" />,
    path: '/podcast-history',
  },
  {
    title: 'Run History',
    description: 'View logs and history of past pipeline runs.',
    icon: <HistoryIcon fontSize="large" color="primary" />,
    path: '/run-history',
  },
  {
    title: 'Audio Visualizer',
    description: 'Generate video visualizations for audio files.',
    icon: <GraphicEqIcon fontSize="large" color="primary" />,
    path: '/visualizer',
  },
  {
    title: 'Settings',
    description: 'Configure application settings, models, and API keys.',
    icon: <SettingsIcon fontSize="large" color="primary" />,
    path: '/settings',
  },
  {
    title: 'Model Catalog',
    description: 'Browse and manage available models.',
    icon: <CollectionsBookmarkIcon fontSize="large" color="primary" />,
    path: '/model-catalog',
  }
];

const Dashboard: React.FC = () => {
  const navigate = useNavigate();

  const handleCardClick = (path: string) => {
    navigate(path);
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom component="div" sx={{ mb: 3 }}>
        Dashboard
      </Typography>
      <Grid container spacing={3}>
        {navItems.map((item) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={item.title}>
            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <CardActionArea onClick={() => handleCardClick(item.path)} sx={{ flexGrow: 1 }}>
                <CardContent sx={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%'}}>
                  <Box sx={{ mb: 2 }}>{item.icon}</Box>
                  <Typography variant="h6" component="div" gutterBottom>
                    {item.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {item.description}
                  </Typography>
                </CardContent>
              </CardActionArea>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default Dashboard; 