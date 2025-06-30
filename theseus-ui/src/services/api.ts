import axios from 'axios';
import type { AxiosResponse } from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

// Configuration interfaces
export interface ModelConfig {
  model_name: string;
  model_type: string;
  max_new_tokens?: number;
  temperature?: number;
  num_ctx?: number;
  trust_remote_code?: boolean;
}

export interface MindMapConfig {
  k: number;
  similarity_threshold: number;
  layout_algorithm: 'force' | 'circular' | 'hierarchical';
  summarization_model: ModelConfig;
  expansion_order: number;
  max_nodes_per_order: number;
}

export interface OrchestrationConfig {
  embedding_model: ModelConfig;
  judge_model: ModelConfig;
  content_extraction_model: ModelConfig;
  newsletter_sections_model: ModelConfig;
  newsletter_intro_model: ModelConfig;
  podcast_model?: ModelConfig;
  tts_model?: any;
  research_agent_model_config?: any;
  mind_map_config?: MindMapConfig;
}

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
  getCredentials: () => api.get('/settings/credentials'),
  updateCredentials: (data: any) => api.put('/settings/credentials', data),
  getModelProviders: () => api.get('/model-providers'),
  getModels: () => api.get('/models'),
  runNewsletterPipeline: (params: any) => api.post('/actions/run-newsletter-pipeline', params),
  abortTask: (taskId: string) => api.post(`/api/tasks/${taskId}/abort`),
  exportDatabase: (onProgress?: (percent: number) => void) =>
    api.get('/settings/database/export', {
      responseType: 'blob',
      onDownloadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    }),
  startExportDatabase: () => api.post('/settings/database/export-task'),
  downloadExportDatabase: (
    taskId: string,
    onProgress?: (percent: number) => void
  ) =>
    api.get(`/settings/database/export-task/${taskId}/download`, {
      responseType: 'blob',
      onDownloadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    }),
  importDatabase: (file: File, importMode: 'merge' | 'overwrite' = 'merge') => {
    const formData = new FormData();
    formData.append('backup_file', file);
    formData.append('import_mode', importMode);
    return api.post('/settings/database/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
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

// Research Agent API
export const researchAgentApi = {
  startResearchTask: (request: any) => api.post('/research-agent/run', request),
  getTaskStatus: (taskId: string) => api.get(`/research-agent/status/${taskId}`),
  getTaskResult: (taskId: string) => api.get(`/research-agent/result/${taskId}`),
  getHistory: (limit: number = 50, offset: number = 0, statusFilter?: string) => {
    const params: any = { limit, offset };
    if (statusFilter) params.status_filter = statusFilter;
    return api.get('/research-agent/history', { params });
  },
  cancelTask: (taskId: string) => api.delete(`/research-agent/${taskId}`),
  getWorkflowInfo: () => api.get('/research-agent/workflow/info'),
  getHealth: () => api.get('/research-agent/health'),
};

// Model Catalog API
export const modelCatalogApi = {
  searchModels: (params: any) => api.get('/model-catalog/', { params }),
  createModel: (model: any) => api.post('/model-catalog/', model),
  updateModel: (modelId: number, model: any) => api.put(`/model-catalog/${modelId}`, model),
  deleteModel: (modelId: number) => api.delete(`/model-catalog/${modelId}`),
  toggleFavorite: (modelId: number) => api.post(`/model-catalog/${modelId}/toggle-favorite`),
  getModel: (modelId: number) => api.get(`/model-catalog/${modelId}`),
};

// Mind-Map API
export const mindMapApi = {
  expandMindMap: (request: MindMapExpandRequest) => 
    api.post('/mindmap/expand', request),
  parsePDFs: (request: MindMapPDFParseRequest) => 
    api.post('/mindmap/parse-pdfs', request),
  searchSeeds: (request: MindMapSeedSearchRequest) => 
    api.get('/mindmap/search-seeds', { params: request }),
  getPaper: (paperId: string) => 
    api.get(`/mindmap/paper/${paperId}`),
  
  // Report management
  getReports: async (): Promise<MindMapReportListResponse> => {
    const response: AxiosResponse<MindMapReportListResponse> = await api.get('/mindmap/reports');
    return response.data;
  },
  getReport: async (reportId: number): Promise<MindMapReport> => {
    const response: AxiosResponse<MindMapReport> = await api.get(`/mindmap/reports/${reportId}`);
    return response.data;
  },
  saveReport: async (request: MindMapReportSaveRequest): Promise<MindMapReportSaveResponse> => {
    const response: AxiosResponse<MindMapReportSaveResponse> = await api.post('/mindmap/reports', request);
    return response.data;
  },
  updateReport: async (reportId: number, request: MindMapReportSaveRequest): Promise<{ message: string; id: number }> => {
    const response: AxiosResponse<{ message: string; id: number }> = await axios.put(`/api/mindmap/reports/${reportId}`, request);
    return response.data;
  },
  deleteReport: async (reportId: number): Promise<{ status: string; message: string }> => {
    const response: AxiosResponse<{ status: string; message: string }> = await api.delete(`/mindmap/reports/${reportId}`);
    return response.data;
  },
  updateReportTitle: async (reportId: number, title: string): Promise<{ status: string; message: string; title: string }> => {
    const response: AxiosResponse<{ status: string; message: string; title: string }> = await api.put(`/mindmap/reports/${reportId}/title`, { title });
    return response.data;
  },
  updateReportDescription: async (reportId: number, description: string): Promise<{ status: string; message: string; description: string }> => {
    const response: AxiosResponse<{ status: string; message: string; description: string }> = await api.put(`/mindmap/reports/${reportId}/description`, { description });
    return response.data;
  },
};

// WebSocket connection
export const createWebSocket = (taskId: string, type: 'newsletter' | 'podcast' | 'visualizer' | 'research-agent' | 'mindmap' | 'mindmap-pdf-parse') => {
  const ws = new WebSocket(`ws://localhost:8000/ws/${type}/${taskId}`);
  return ws;
};

export interface LogEntry {
  task_id: string;
  status: string;
  datetime_run: string;
}

export interface TaskHistoryEntry {
  task_id: string;
  task_type: string;
  status: string;
  start_time: string;
  end_time: string | null;
  progress: number | null;
  current_step: string | null;
  message: string | null;
  error: string | null;
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

export const getTaskHistory = async (limit: number = 100, fromDate?: string, toDate?: string): Promise<TaskHistoryEntry[]> => {
  const params: Record<string, string | number> = { limit };
  if (fromDate) {
    params.from_date = fromDate;
  }
  if (toDate) {
    params.to_date = toDate;
  }
  const response: AxiosResponse<TaskHistoryEntry[]> = await api.get<TaskHistoryEntry[]>("/task-history", { params });
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
  keywords?: string[];
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

    deletePodcast: async (podcastId: number): Promise<{ status: string; message: string }> => {
        const response: AxiosResponse<{ status: string; message: string }> = await api.delete(`/podcasts/history/${podcastId}`);
        return response.data;
    },

    updatePodcastTitle: async (podcastId: number, title: string): Promise<{ status: string; message: string; title: string }> => {
        const response: AxiosResponse<{ status: string; message: string; title: string }> = await api.put(`/podcasts/history/${podcastId}/title`, { title });
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

// Research Agent Interfaces
export interface ResearchTaskRequest {
  research_question: string;
  config?: {
    search_config?: {
      local_limit?: number;
      external_limit?: number;
    };
    evidence_config?: {
      min_evidence_threshold?: number;
      quality_threshold?: number;
    };
    compression_config?: {
      compression_ratio?: number;
      max_tokens?: number;
    };
    answer_config?: {
      citation_style?: 'academic' | 'numbered' | 'apa';
      include_methodology?: boolean;
      include_limitations?: boolean;
    };
  };
  save_to_library?: boolean;
}

export interface ResearchTaskResponse {
  task_id: string;
  status: string;
  created_at: string;
  research_question: string;
}

export interface ResearchTaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress?: any;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface ResearchTaskResult {
  task_id: string;
  status: string;
  research_question: string;
  final_answer?: string;
  generation_summary?: string;
  statistics?: {
    research_loops: number;
    total_sources_found: number;
    selected_sources: number;
    evidence_pieces: number;
    evidence_sufficient: boolean;
    compression_used: boolean;
  };
  sub_queries: string[];
  sources_gathered: any[];
  judged_sources: any[];
  evidence: string[];
  compressed_notes: string;
  workflow_messages: any[];
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface ResearchHistoryItem {
  task_id: string;
  research_question: string;
  status: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  statistics?: {
    research_loops: number;
    total_sources_found: number;
    selected_sources: number;
    evidence_pieces: number;
    evidence_sufficient: boolean;
    compression_used: boolean;
  };
}

export interface ResearchWebSocketMessage {
  type: 'status_update' | 'task_completed';
  task_id: string;
  status: string;
  progress?: any;
  timestamp: string;
  error_message?: string;
  results?: {
    final_answer?: string;
    statistics?: any;
    sub_queries?: string[];
    sources_count?: number;
    evidence_count?: number;
  };
}

// Mind-Map API Types
export interface MindMapNode {
  id: string | number;
  title: string;
  abstract: string;
  date: string;
  url: string;
  score: number;
  rationale: string;
  similarity_score: number;
  summary?: string;
  keywords?: string[];
  has_fulltext?: boolean;
  is_seed?: boolean;
  colorIndex?: number;
}

export interface MindMapEdge {
  source_id: number;
  target_id: number;
  similarity_score: number;
  relationship_type?: string;
}

export interface MindMapData {
  nodes: MindMapNode[];
  edges: MindMapEdge[];
  seed_paper_id: string;
  layout_algorithm: string;
  generation_timestamp: string;
}

export interface MindMapExpandRequest {
  paper_id: string;
  k?: number;
  similarity_threshold?: number;
  layout_algorithm?: 'force' | 'circular' | 'hierarchical';
  model_config_override?: any;
  expansion_order?: number;
  max_nodes_per_order?: number;
}

export interface MindMapExpandResponse {
  task_id: string;
  message: string;
}

export interface MindMapPDFParseRequest {
  paper_ids: string[];
}

export interface MindMapPDFParseResponse {
  task_id: string;
  message: string;
  papers_count: number;
}

export interface MindMapSeedSearchRequest {
  query: string;
  limit?: number;
}

export interface MindMapSeedSearchResponse {
  papers: PaperApiResponse[];
  total_results: number;
}

export interface MindMapWebSocketMessage {
  type: 'progress_update' | 'task_completed' | 'task_failed';
  task_id: string;
  step: string;
  progress: number;
  message: string;
  timestamp: string;
  mindmap_data?: MindMapData;
  statistics?: {
    nodes_created: number;
    edges_created: number;
    layout_algorithm: string;
  };
  error?: string;
}

// Mind-Map Reports interfaces
export interface MindMapReport {
  id: number;
  title: string;
  description?: string;
  seed_paper_id: number;
  seed_paper_title: string;
  parameters: Record<string, any>;
  mindmap_data: MindMapData;
  statistics: Record<string, any>;
  created_at: string;
}

export interface MindMapReportSaveRequest {
  title: string;
  description?: string;
  mindmap_data: MindMapData;
  parameters: Record<string, any>;
}

export interface MindMapReportSaveResponse {
  id: number;
  title: string;
  message: string;
}

export interface MindMapReportListResponse {
  reports: MindMapReport[];
  total_count: number;
} 