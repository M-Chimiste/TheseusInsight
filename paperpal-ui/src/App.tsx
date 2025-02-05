import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box, Container } from '@mui/material';
import Navigation from './components/Navigation';

// Lazy load pages
const Dashboard = React.lazy(() => import('./pages/Dashboard'));
const PodcastEditor = React.lazy(() => import('./pages/PodcastEditor'));
const PodcastGenerator = React.lazy(() => import('./pages/PodcastGenerator'));
const VisualizerGenerator = React.lazy(() => import('./pages/VisualizerGenerator'));

const App: React.FC = () => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Navigation />
      <Container component="main" sx={{ mt: 4, mb: 4, flex: 1 }}>
        <React.Suspense fallback={<div>Loading...</div>}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/editor" element={<PodcastEditor />} />
            <Route path="/generator" element={<PodcastGenerator />} />
            <Route path="/visualizer" element={<VisualizerGenerator />} />
          </Routes>
        </React.Suspense>
      </Container>
    </Box>
  );
};

export default App; 