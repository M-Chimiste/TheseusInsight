import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Settings API
export const settingsApi = {
  getOrchestrationConfig: () => api.get('/settings/orchestration'),
  updateOrchestrationConfig: (config: any) => api.put('/settings/orchestration', config),
  getArxivCategories: () => api.get('/settings/arxiv-categories'),
  updateArxivCategories: (config: any) => api.put('/settings/arxiv-categories', config),
  getResearchInterests: () => api.get('/settings/research-interests'),
  updateResearchInterests: (data: any) => api.put('/settings/research-interests', data),
  getEmailRecipients: () => api.get('/settings/email-recipients'),
  updateEmailRecipients: (data: any) => api.put('/settings/email-recipients', data),
  getVisualizerSettings: () => api.get('/settings/visualizer-settings'),
  sendTestEmail: () => api.post('/settings/send-test-email'),
  getModelProviders: () => api.get('/model-providers'),
  getModels: () => api.get('/models'),
  runNewsletterPipeline: (params: any) => api.post('/actions/run-newsletter-pipeline', params),
};

// Newsletter API
export const newsletterApi = {
  runNewsletter: (config: any, introMusicFile?: File) => {
    const formData = new FormData();
    formData.append('config', JSON.stringify(config));
    if (introMusicFile) {
      formData.append('intro_music_file', introMusicFile);
    }
    return api.post('/newsletter/run', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
};

// Podcast API
export const podcastApi = {
  generatePodcast: (params: any, introMusicFile?: File, pdfFiles?: File[]) => {
    const formData = new FormData();
    formData.append('params_json', JSON.stringify(params));
    if (introMusicFile) {
      formData.append('intro_music_file', introMusicFile);
    }
    if (pdfFiles) {
      pdfFiles.forEach((file) => {
        formData.append('pdf_files', file);
      });
    }
    return api.post('/podcast/generate', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
};

// Task API
export const taskApi = {
  getTaskStatus: (taskId: string) => api.get(`/tasks/${taskId}/status`),
  getTaskResult: (taskId: string) => api.get(`/tasks/${taskId}/result`),
  downloadTaskArtifact: (taskId: string, fileType: string) =>
    api.get(`/tasks/${taskId}/download/${fileType}`, { responseType: 'blob' }),
};

// Runs API
export const runsApi = {
  getRuns: (page: number = 1) => api.get('/runs', { params: { page } }),
  deleteRunArtifact: (runId: number) => api.delete(`/runs/${runId}/artifact`),
};

// WebSocket connection
export const createWebSocket = (taskId: string, type: 'newsletter' | 'podcast') => {
  const ws = new WebSocket(`ws://localhost:8000/ws/${type}/${taskId}`);
  return ws;
}; 