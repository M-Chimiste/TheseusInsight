import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
} from '@mui/material';
import {
  Edit as EditIcon,
  Add as AddIcon,
  Visibility as VisibilityIcon,
} from '@mui/icons-material';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();

  const features = [
    {
      title: 'Podcast Script Editor',
      description: 'Edit and manage your podcast scripts with an intuitive interface.',
      path: '/editor',
      icon: <EditIcon fontSize="large" />,
      color: '#00b000',
    },
    {
      title: 'New Podcast Generator',
      description: 'Create new podcasts from PDFs and other documents with AI assistance.',
      path: '/generator',
      icon: <AddIcon fontSize="large" />,
      color: '#d703fc',
    },
    {
      title: 'Visualizer Generator',
      description: 'Generate stunning visualizations for your podcast audio.',
      path: '/visualizer',
      icon: <VisibilityIcon fontSize="large" />,
      color: '#00FF80',
    },
  ];

  return (
    <Box>
      <Typography variant="h2" gutterBottom>
        Welcome to PaperPal
      </Typography>
      <Typography variant="h5" color="textSecondary" paragraph>
        Transform your documents into engaging podcasts with AI assistance
      </Typography>

      <Grid container spacing={4} sx={{ mt: 2 }}>
        {features.map(({ title, description, path, icon, color }) => (
          <Grid item xs={12} md={4} key={path}>
            <Card
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                transition: 'transform 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  cursor: 'pointer',
                },
              }}
              onClick={() => navigate(path)}
            >
              <CardContent sx={{ flexGrow: 1 }}>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    mb: 2,
                    color,
                  }}
                >
                  {icon}
                  <Typography variant="h5" component="div" sx={{ ml: 1 }}>
                    {title}
                  </Typography>
                </Box>
                <Typography variant="body1" color="textSecondary">
                  {description}
                </Typography>
              </CardContent>
              <CardActions>
                <Button
                  size="large"
                  startIcon={icon}
                  sx={{ ml: 1, mb: 1 }}
                >
                  Get Started
                </Button>
              </CardActions>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default Dashboard; 