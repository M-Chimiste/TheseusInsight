import type { ReactElement } from 'react';
import React from 'react';
import PsychologyIcon from '@mui/icons-material/Psychology';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import PeopleIcon from '@mui/icons-material/People';
import WorkOutlineIcon from '@mui/icons-material/WorkOutline';
import TimelineIcon from '@mui/icons-material/Timeline';
import MovieIcon from '@mui/icons-material/Movie';
import StorageIcon from '@mui/icons-material/Storage';
import ArticleIcon from '@mui/icons-material/Article';
import PodcastsIcon from '@mui/icons-material/Podcasts';
import HistoryIcon from '@mui/icons-material/History';
import SettingsIcon from '@mui/icons-material/Settings';
import AutoGraphIcon from '@mui/icons-material/AutoGraph';

export type DashboardShortcutId =
  | 'research-agent'
  | 'papers'
  | 'research-library'
  | 'mindmap-reports'
  | 'timeline'
  | 'profile-management'
  | 'bulk-operations'
  | 'job-monitoring'
  | 'visualizer'
  | 'model-catalog'
  | 'newsletter'
  | 'podcast'
  | 'podcast-history'
  | 'run-history'
  | 'settings'
  | 'profile-star-map';

export interface DashboardShortcutDefinition {
  id: DashboardShortcutId;
  label: string;
  description?: string;
  icon: ReactElement;
  path: string;
}

export const DASHBOARD_SHORTCUTS: DashboardShortcutDefinition[] = [
  {
    id: 'research-agent',
    label: 'Research Agent',
    description: 'Run an AI research workflow',
    icon: React.createElement(PsychologyIcon, { fontSize: 'small' }),
    path: '/research-agent',
  },
  {
    id: 'papers',
    label: 'Papers',
    description: 'Browse papers',
    icon: React.createElement(MenuBookIcon, { fontSize: 'small' }),
    path: '/papers',
  },
  {
    id: 'research-library',
    label: 'Research Library',
    description: 'Your research runs',
    icon: React.createElement(LibraryBooksIcon, { fontSize: 'small' }),
    path: '/research-library',
  },
  {
    id: 'mindmap-reports',
    label: 'Mind-Map Reports',
    description: 'Saved mind-maps',
    icon: React.createElement(AccountTreeIcon, { fontSize: 'small' }),
    path: '/mindmap-reports',
  },
  {
    id: 'timeline',
    label: 'Research Timeline',
    description: 'Trends over time',
    icon: React.createElement(ShowChartIcon, { fontSize: 'small' }),
    path: '/timeline',
  },
  {
    id: 'profile-management',
    label: 'Profiles',
    description: 'Manage profiles',
    icon: React.createElement(PeopleIcon, { fontSize: 'small' }),
    path: '/profile-management',
  },
  {
    id: 'profile-star-map',
    label: 'Star Map',
    description: 'Profile paper constellation',
    icon: React.createElement(AutoGraphIcon, { fontSize: 'small' }),
    path: '/star-map',
  },
  {
    id: 'bulk-operations',
    label: 'Bulk Ops',
    description: 'Ingest/judge/embed',
    icon: React.createElement(WorkOutlineIcon, { fontSize: 'small' }),
    path: '/bulk-operations',
  },
  {
    id: 'job-monitoring',
    label: 'Jobs',
    description: 'Monitor workers & queue',
    icon: React.createElement(TimelineIcon, { fontSize: 'small' }),
    path: '/job-monitoring',
  },
  {
    id: 'visualizer',
    label: 'Visualizer',
    description: 'Audio → video',
    icon: React.createElement(MovieIcon, { fontSize: 'small' }),
    path: '/visualizer',
  },
  {
    id: 'model-catalog',
    label: 'Models',
    description: 'Model catalog',
    icon: React.createElement(StorageIcon, { fontSize: 'small' }),
    path: '/model-catalog',
  },
  {
    id: 'newsletter',
    label: 'Newsletter',
    description: 'Generate newsletter',
    icon: React.createElement(ArticleIcon, { fontSize: 'small' }),
    path: '/newsletter',
  },
  {
    id: 'podcast',
    label: 'Podcast',
    description: 'Generate podcast',
    icon: React.createElement(PodcastsIcon, { fontSize: 'small' }),
    path: '/podcast',
  },
  {
    id: 'podcast-history',
    label: 'Podcast History',
    description: 'Past podcasts',
    icon: React.createElement(PodcastsIcon, { fontSize: 'small' }),
    path: '/podcast-history',
  },
  {
    id: 'run-history',
    label: 'Run History',
    description: 'Task runs',
    icon: React.createElement(HistoryIcon, { fontSize: 'small' }),
    path: '/run-history',
  },
  {
    id: 'settings',
    label: 'Settings',
    description: 'Configure app',
    icon: React.createElement(SettingsIcon, { fontSize: 'small' }),
    path: '/settings',
  },
];

export const DEFAULT_PINNED_SHORTCUT_IDS: DashboardShortcutId[] = [
  'research-agent',
  'papers',
  'research-library',
  'timeline',
  'profile-star-map',
  'job-monitoring',
];

