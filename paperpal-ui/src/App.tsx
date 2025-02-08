import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box, Container } from '@mui/material';
import Navigation from './components/Navigation';
import Dashboard from './pages/Dashboard';
import PodcastEditor from './pages/PodcastEditor';
import PodcastGenerator from './pages/PodcastGenerator';
import VisualizerGenerator from './pages/VisualizerGenerator';
import PaperPal from './pages/PaperPal';

const App: React.FC = () => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Navigation />
      <Container component="main" sx={{ mt: 4, mb: 4, flex: 1 }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/editor" element={<PodcastEditor />} />
          <Route path="/generator" element={<PodcastGenerator />} />
          <Route path="/visualizer" element={<VisualizerGenerator />} />
          <Route path="/paperpal" element={<PaperPal />} />
        </Routes>
      </Container>
    </Box>
  );
};

export default App; 