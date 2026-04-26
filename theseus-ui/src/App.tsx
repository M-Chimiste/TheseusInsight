import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DesignProvider } from './contexts/DesignContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { LayoutProvider } from './contexts/LayoutContext';
import { ProfileProvider } from './contexts/ProfileContext';
import Layout from './components/Layout';
import React from 'react';

// Lazy load pages for better performance
const Settings = React.lazy(() => import('./pages/Settings'));
const Newsletter = React.lazy(() => import('./pages/Newsletter'));
const Podcast = React.lazy(() => import('./pages/Podcast'));
const Visualizer = React.lazy(() => import('./pages/Visualizer'));
const Papers = React.lazy(() => import('./pages/Papers'));
const RunHistory = React.lazy(() => import('./pages/RunHistory'));
const PodcastHistory = React.lazy(() => import('./pages/PodcastHistory'));
const PodcastDetail = React.lazy(() => import('./pages/PodcastDetail'));
const Dashboard = React.lazy(() => import('./pages/Dashboard'));
const ResearchAgent = React.lazy(() => import('./pages/ResearchAgent'));
const ResearchLibrary = React.lazy(() => import('./pages/ResearchLibrary'));
const ModelCatalog = React.lazy(() => import('./pages/ModelCatalog'));
const MindMapReports = React.lazy(() => import('./pages/MindMapReports'));
const ResearchTimeline = React.lazy(() => import('./pages/ResearchTimeline'));
const ProfileManagement = React.lazy(() => import('./pages/ProfileManagement'));
const BulkOperations = React.lazy(() => import('./pages/BulkOperations'));
const JobMonitoring = React.lazy(() => import('./pages/JobMonitoring'));
const ProfileStarMap = React.lazy(() => import('./pages/ProfileStarMap'));

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
      <DesignProvider>
        <ThemeProvider>
          <LayoutProvider>
            <ProfileProvider>
            <Router>
              <Layout>
                <React.Suspense fallback={<div>Loading...</div>}>
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/settings" element={<Settings />} />
                    <Route path="/newsletter" element={<Newsletter />} />
                    <Route path="/podcast" element={<Podcast />} />
                    <Route path="/visualizer" element={<Visualizer />} />
                    <Route path="/papers" element={<Papers />} />
                    <Route path="/run-history" element={<RunHistory />} />
                    <Route path="/podcast-history" element={<PodcastHistory />} />
                    <Route path="/podcast-history/:podcastId" element={<PodcastDetail />} />
                    <Route path="/research-agent" element={<ResearchAgent />} />
                    <Route path="/research-library" element={<ResearchLibrary />} />
                    <Route path="/model-catalog" element={<ModelCatalog />} />
                    <Route path="/mindmap-reports" element={<MindMapReports />} />
                    <Route path="/timeline" element={<ResearchTimeline />} />
                    <Route path="/profile-management" element={<ProfileManagement />} />
                    <Route path="/star-map" element={<ProfileStarMap />} />
                    <Route path="/bulk-operations" element={<BulkOperations />} />
                    <Route path="/job-monitoring" element={<JobMonitoring />} />
                    <Route path="/*" element={<Navigate to="/" replace />} />
                  </Routes>
                </React.Suspense>
              </Layout>
            </Router>
            </ProfileProvider>
          </LayoutProvider>
        </ThemeProvider>
      </DesignProvider>
    </QueryClientProvider>
  );
}

export default App;
