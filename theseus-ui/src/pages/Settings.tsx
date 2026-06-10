import React, { useState } from 'react';
import {
  Alert, Box, Card, CardContent, CircularProgress, Container,
  FormControlLabel, Snackbar, Switch, Tooltip, Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { settingsApi, modelCatalogApi, ollamaServersApi } from '../services/api';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import SettingsIcon from '@mui/icons-material/Settings';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import PaletteIcon from '@mui/icons-material/Palette';
import { useTheme as useCustomTheme } from '../contexts/ThemeContext';
import { useLayout } from '../contexts/LayoutContext';
import { ScheduledTasksSettings } from '../components/ScheduledTasksSettings';
import { CredentialsSettings } from '../components/settings/CredentialsSettings';
import { DatabaseTransferSettings } from '../components/settings/DatabaseTransferSettings';
import { ResearchAgentSettings } from '../components/settings/ResearchAgentSettings';
import { ModelConfigurationSettings } from '../components/settings/ModelConfigurationSettings';
import { PerformanceSettings } from '../components/settings/PerformanceSettings';

/**
 * Settings page shell. Each section is a self-contained component under
 * components/settings/ owning its own queries, mutations, and state
 * (decomposed from a 2,974-line monolith in refactor F3). The page keeps
 * only the queries shared across sections (model catalog, providers,
 * inference-server hosts) and the theme toggle.
 */
const Settings: React.FC = () => {
  const { isDarkMode, toggleTheme } = useCustomTheme();
  const { headerHeight } = useLayout(); // Get dynamic header height
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  
  const { data: modelProviders, isLoading: isLoadingProviders, isError: isErrorProviders } = useQuery<any[], Error>({
    queryKey: ['modelProviders'],
    queryFn: () => settingsApi.getModelProviders().then(res => res.data || []),
  });

  // Query for model catalog to enable autocomplete
  const { data: modelCatalogData } = useQuery({
    queryKey: ['modelCatalogForSettings'],
    queryFn: () => modelCatalogApi.searchModels({
      page: 1,
      page_size: 100  // Maximum allowed by backend validation
    }).then(res => res.data),
  });

  // Query for inference servers to provide host autocomplete
  const { data: inferenceServers } = useQuery({
    queryKey: ['inferenceServersForSettings'],
    queryFn: () => ollamaServersApi.getAllServers().then((res: any) => res.data)
  });

  // Helper function to get hosts filtered by provider
  const getHostsByProvider = React.useCallback((provider: 'ollama' | 'lmstudio' | 'custom-oai') => {
    if (!inferenceServers || !Array.isArray(inferenceServers)) return [];

    // For custom-oai, we could show all hosts or none - let's show all
    if (provider === 'custom-oai') {
      const hosts = inferenceServers.map((server: any) => server.url);
      return Array.from(new Set(hosts)).sort();
    }

    // Filter by provider and extract URLs
    const hosts = inferenceServers
      .filter((server: any) => server.provider === provider)
      .map((server: any) => server.url);
    return Array.from(new Set(hosts)).sort();
  }, [inferenceServers]);

  // Query for research profiles (for profile-scoped export)
  
  // Handle when a model is selected from the catalog - auto-populate other fields

  if (isLoadingProviders) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh" sx={{ pt: `${headerHeight + 24}px` }}>
        <CircularProgress />
      </Box>
    );
  }
  
  if (isErrorProviders) setError('Failed to load model providers.');

  return (
    <Container maxWidth="lg" sx={{ pt: `${headerHeight + 32}px`, pb: 4 }}>
      <Snackbar
        open={Boolean(error)}
        autoHideDuration={4000}
        onClose={() => setError(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert onClose={() => setError(null)} severity="error" sx={{ width: '100%' }}>
          {error}
        </Alert>
      </Snackbar>

      <Snackbar
        open={Boolean(success)}
        autoHideDuration={4000}
        onClose={() => setSuccess(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert onClose={() => setSuccess(null)} severity="success" sx={{ width: '100%' }}>
          {success}
        </Alert>
      </Snackbar>

      <Typography variant="h4" gutterBottom component="div" sx={{ mb: 3 }}>
        <SettingsIcon sx={{ mr: 1, verticalAlign: 'middle' }}/> Settings
      </Typography>

      {/* Model Configuration Section */}
      <ModelConfigurationSettings
        modelCatalogData={modelCatalogData}
        modelProviders={modelProviders}
        getHostsByProvider={getHostsByProvider}
      />

      {/* Research Agent Configuration Section */}
      <ResearchAgentSettings
        modelCatalogData={modelCatalogData}
        modelProviders={modelProviders}
        getHostsByProvider={getHostsByProvider}
      />

      {/* Performance Configuration Section */}
      <PerformanceSettings />

      {/* Theme Preferences Section */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5" fontWeight={600} sx={{ flex: 1 }}>
              <PaletteIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              Theme Preferences
            </Typography>
            <Tooltip title="Choose between dark and light theme for the application interface.">
              <InfoOutlinedIcon color="action" />
            </Tooltip>
          </Box>
          <Typography variant="body2" sx={{ mb: 3 }}>
            Customize the appearance of Theseus Insight to match your preferences.
          </Typography>

          <Box sx={{ 
            p: 3,
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
            maxWidth: 400
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {isDarkMode ? (
                  <Brightness4Icon sx={{ color: 'warning.main' }} />
                ) : (
                  <Brightness7Icon sx={{ color: 'orange' }} />
                )}
                <Typography variant="h6">
                  {isDarkMode ? 'Dark Mode' : 'Light Mode'}
                </Typography>
              </Box>
              <Box sx={{ flex: 1 }} />
              <FormControlLabel
                control={
                  <Switch
                    checked={isDarkMode}
                    onChange={toggleTheme}
                    color="primary"
                  />
                }
                label=""
                sx={{ m: 0 }}
              />
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {isDarkMode 
                ? 'Switch to light mode for a brighter interface'
                : 'Switch to dark mode for easier viewing in low-light environments'
              }
            </Typography>
          </Box>
        </CardContent>
      </Card>

      {/* Scheduled Tasks Section */}
      <Box sx={{ mb: 4 }}>
        <ScheduledTasksSettings 
          onStatusChange={(message, severity) => {
            if (severity === 'success') {
              setSuccess(message);
            } else if (severity === 'error') {
              setError(message);
            }
          }}
        />
      </Box>

      {/* API Credentials Section */}
      <CredentialsSettings />

      {/* Database Management Section */}
      <DatabaseTransferSettings />


    </Container>
  );
};

export default Settings;
