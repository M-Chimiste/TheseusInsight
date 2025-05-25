import axios from 'axios';
import type { AxiosResponse } from 'axios';

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
  abortTask: (taskId: string) => api.post(`/tasks/${taskId}/abort`),
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
    if (pdfFiles && pdfFiles.length > 0) {
      pdfFiles.forEach(file => formData.append('pdf_files', file));
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
  getActiveTasks: (taskTypes?: string[]) => {
    const params = taskTypes ? { task_types: taskTypes.join(',') } : {};
    return api.get('/tasks/active', { params });
  },
  getRecentCompletedTasks: (taskTypes?: string[]) => {
    const params = taskTypes ? { task_types: taskTypes.join(',') } : {};
    return api.get('/tasks/recent-completed', { params });
  },
  downloadTaskArtifact: (taskId: string, fileType: 'markdown' | 'audio' | 'video') => 
    api.get(`/tasks/${taskId}/download/${fileType}`, { responseType: 'blob' }),
  runVisualizerPipeline: (audioFile: File, visualizerParams: any) => {
    const formData = new FormData();
    formData.append('audio_file', audioFile);
    formData.append('visualizer_params_json', JSON.stringify(visualizerParams));
    return api.post('/actions/run-visualizer-pipeline', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
  },
};

// Runs API
export const runsApi = {
  getRuns: (page: number = 1) => api.get('/runs', { params: { page } }),
  deleteRunArtifact: (runId: number) => api.delete(`/runs/${runId}/artifact`),
};

// WebSocket connection
export const createWebSocket = (taskId: string, type: 'newsletter' | 'podcast' | 'visualizer') => {
  const ws = new WebSocket(`ws://localhost:8000/ws/${type}/${taskId}`);
  return ws;
};

export interface LogEntry {
  task_id: string;
  status: string;
  datetime_run: string;
}

export const getLogs = async (limit: number = 100, fromDate?: string, toDate?: string): Promise<LogEntry[]> => {
  const params: Record<string, string | number> = { limit };
  if (fromDate) {
    params.from_date = fromDate;
  }
  if (toDate) {
    params.to_date = toDate;
  }
  const response: AxiosResponse<LogEntry[]> = await api.get<LogEntry[]>("/logs", { params });
  return response.data;
};

// Task API calls
export interface RunStatusPayload { 
  taskId: string;
  status: string;
  progress?: number;
  message?: string;
}

export const getTaskStatus = async (taskId: string): Promise<RunStatusPayload | null> => {
  if (!taskId || taskId.startsWith("dummy-")) return null; // Avoid calling API with placeholder
  try {
    const response = await api.get<RunStatusPayload>(`/tasks/${taskId}/status`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching status for task ${taskId}:`, error);
    return null;
  }
};

// Interfaces for Podcast History
export interface PodcastScriptItem {
    text: string;
    speaker: string;
    segment_label?: string | null;
}

export interface PodcastDetailResponse {
    id: number;
    title: string;
    date: string;
    description: string;
    script: PodcastScriptItem[];
}

export interface PodcastListItemResponse {
    id: number;
    title: string;
    date: string;
    description_snippet: string;
}

// Interfaces for Papers Page
export interface PaperApiResponse {
  id: number;
  title: string;
  abstract: string;
  date: string;
  date_run: string;
  score: number;
  rationale: string;
  related: boolean;
  cosine_similarity: number;
  url: string;
  embedding_model: string;
  similarity_score?: number; // Optional field for similarity search results
}

export interface PaginatedPapersResponse {
  items: PaperApiResponse[];
  total_items: number;
  total_pages: number;
  current_page: number;
  nextPage: number | null;
}

export interface SimilarPapersResponse {
    reference_paper: PaperApiResponse;
    similar_papers: PaperApiResponse[];
    total_similar: number;
}

export interface HybridSearchResponse {
    query_text: string;
    results: PaperApiResponse[];
    total_results: number;
    total_pages: number;
    current_page: number;
    semantic_weight: number;
    keyword_weight: number;
}

// Podcast History API functions
export const podcastHistoryApi = {
    getPodcastHistoryList: async (): Promise<PodcastListItemResponse[]> => {
        const response: AxiosResponse<PodcastListItemResponse[]> = await api.get<PodcastListItemResponse[]>('/podcasts/history');
        return response.data;
    },

    getPodcastDetail: async (podcastId: string): Promise<PodcastDetailResponse> => {
        const response: AxiosResponse<PodcastDetailResponse> = await api.get<PodcastDetailResponse>(`/podcasts/history/${podcastId}`);
        return response.data;
    },
};

// Papers API functions
export const papersApi = {
    getPapers: async (
        page: number = 1,
        pageSize: number = 10,
        sortField: string = 'score',
        sortDirection: string = 'desc',
        minScore?: number,
        maxScore?: number,
        fromDate?: string,
        toDate?: string,
        search?: string
    ): Promise<PaginatedPapersResponse> => {
        const params: Record<string, any> = {
            page,
            page_size: pageSize,
            sort_field: sortField,
            sort_direction: sortDirection
        };
        
        if (minScore !== undefined) params.score = minScore;
        if (maxScore !== undefined) params.max_score = maxScore;
        if (fromDate) params.from_date = fromDate;
        if (toDate) params.to_date = toDate;
        if (search) params.search = search;

        const response: AxiosResponse<PaginatedPapersResponse> = await api.get<PaginatedPapersResponse>('/papers', {
            params
        });
        return response.data;
    },

    findSimilarPapers: async (
        paperId: number,
        limit: number = 10,
        similarityThreshold: number = 0.7
    ): Promise<SimilarPapersResponse> => {
        const params = {
            limit,
            similarity_threshold: similarityThreshold
        };

        const response: AxiosResponse<SimilarPapersResponse> = await api.get<SimilarPapersResponse>(`/papers/${paperId}/similar`, {
            params
        });
        return response.data;
    },

    hybridSearch: async (
        queryText: string,
        page: number = 1,
        pageSize: number = 10,
        semanticWeight: number = 0.6,
        keywordWeight: number = 0.4,
        similarityThreshold: number = 0.3,
        minScore?: number,
        maxScore?: number,
        fromDate?: string,
        toDate?: string
    ): Promise<HybridSearchResponse> => {
        const requestBody = {
            query_text: queryText,
            page,
            page_size: pageSize,
            semantic_weight: semanticWeight,
            keyword_weight: keywordWeight,
            similarity_threshold: similarityThreshold,
            min_score: minScore,
            max_score: maxScore,
            from_date: fromDate,
            to_date: toDate
        };

        const response: AxiosResponse<HybridSearchResponse> = await api.post<HybridSearchResponse>('/papers/hybrid-search', requestBody);
        return response.data;
    },
}; 