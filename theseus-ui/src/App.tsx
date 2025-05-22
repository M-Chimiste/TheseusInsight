import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from './contexts/ThemeContext';
import Layout from './components/Layout';
import React from 'react';

// Lazy load pages for better performance
const Settings = React.lazy(() => import('./pages/Settings'));
const Newsletter = React.lazy(() => import('./pages/Newsletter'));
const Podcast = React.lazy(() => import('./pages/Podcast'));
const Visualizer = React.lazy(() => import('./pages/Visualizer'));
const RunHistory = React.lazy(() => import('./pages/RunHistory'));
const PodcastHistory = React.lazy(() => import('./pages/PodcastHistory'));
const PodcastDetail = React.lazy(() => import('./pages/PodcastDetail'));
const Papers = React.lazy(() => import('./pages/Papers'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <Router>
          <Layout>
            <React.Suspense fallback={<div>Loading...</div>}>
              <Routes>
                <Route path="/" element={<Navigate to="/settings" replace />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/newsletter" element={<Newsletter />} />
                <Route path="/podcast" element={<Podcast />} />
                <Route path="/visualizer" element={<Visualizer />} />
                <Route path="/run-history" element={<RunHistory />} />
                <Route path="/podcast-history" element={<PodcastHistory />} />
                <Route path="/podcast-history/:podcastId" element={<PodcastDetail />} />
                <Route path="/papers" element={<Papers />} />
                <Route path="/*" element={<Navigate to="/" replace />} />
              </Routes>
            </React.Suspense>
          </Layout>
        </Router>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
