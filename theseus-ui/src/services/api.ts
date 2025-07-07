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

// Trends API Parameter Interfaces
export interface GetTrendingTopicsParams {
  limit?: number;
  period_type?: string;
  duration_months?: number;
  min_doc_count?: number;
  sort_by?: string;
}

export interface SearchTopicsParams {
  query: string;
  limit?: number;
}

export interface GetTopicDetailParams {
  period_type?: string;
  timeline_limit?: number;
  papers_limit?: number;
}

export interface GetTopicPapersParams {
  limit?: number;
  min_relevance?: number;
  sort_by?: 'relevance' | 'score' | 'date';
}

export interface GetResearchInterestPapersParams {
    limit?: number;
    min_similarity?: number;
    sort_by?: 'similarity' | 'score' | 'date';
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
  abortTask: (taskId: string) => api.post(`/tasks/${taskId}/abort`),
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

// Profile API Types
export interface ProfileApiResponse {
  id: number;
  name: string;
  description?: string;
  color?: string;
  tags?: string[];
  email_recipients?: string[];
  arxiv_filters?: string[];
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  total_papers?: number;
  recent_papers?: number;
}

export interface ProfileCreateRequest {
  name: string;
  description?: string;
  color?: string;
  tags?: string[];
  email_recipients?: string[];
  arxiv_filters?: string[];
}

export interface ProfileUpdateRequest {
  name?: string;
  description?: string;
  color?: string;
  tags?: string[];
  email_recipients?: string[];
  arxiv_filters?: string[];
  is_active?: boolean;
}

export interface ProfileAwareIngestRequest {
  start_date?: string;
  end_date?: string;
  profile_ids?: number[];
  profile_tags?: string[];
  score_all_profiles?: boolean;
  overwrite_existing?: boolean;
  cosine_threshold?: number;
  arxiv_categories?: string[];
  batch_size?: number;
  send_error_notifications?: boolean;
}

export interface ProfileAwareIngestResponse {
  task_id: string;
  message: string;
  profile_count: number;
  estimated_papers: number;
  status: string;
}

export interface TagSearchResponse {
  query: string;
  suggestions: Array<{
    tag: string;
    usage_count: number;
  }>;
  exact_match: boolean;
}

export interface BulkEmbedRequest {
  start_date: string;
  end_date: string;
  batch_size?: number;
  skip_existing?: boolean;
  arxiv_categories?: string[];
}

export interface BulkJudgeRunRequest {
  profile_ids?: number[];
  profile_tags?: string[];
  start_date?: string;
  end_date?: string;
  overwrite_existing?: boolean;
  cosine_threshold?: number;
  batch_size?: number;
}

export interface BulkJudgeRunResponse {
  task_id: string;
  message: string;
  profile_count: number;
  estimated_papers: number;
  status: string;
}

// Profile Research Interest API Types
export interface ProfileInterestResponse {
  id: number;
  interest_text: string;
  embedding_model?: string;
  created_at?: string;
  updated_at?: string;
}

// Profile API
export const profileApi = {
  // Profile Management
  getProfiles: () => api.get<ProfileApiResponse[]>('/profiles'),
  createProfile: (profile: ProfileCreateRequest) => api.post<ProfileApiResponse>('/profiles', profile),
  getProfile: (id: number) => api.get<ProfileApiResponse>(`/profiles/${id}`),
  updateProfile: (id: number, profile: ProfileUpdateRequest) => api.put<ProfileApiResponse>(`/profiles/${id}`, profile),
  deleteProfile: (id: number) => api.delete(`/profiles/${id}`),
  cloneProfile: (id: number, newName: string) => api.post<ProfileApiResponse>(`/profiles/${id}/clone`, { name: newName }),
  
  // Profile Research Interests
  getProfileInterests: (profileId: number) => api.get<ProfileInterestResponse[]>(`/profiles/${profileId}/interests`),
  createProfileInterest: (profileId: number, interestText: string) => api.post<ProfileInterestResponse>(`/profiles/${profileId}/interests`, { interest_text: interestText }),
  deleteProfileInterest: (profileId: number, interestId: number) => api.delete(`/profiles/${profileId}/interests/${interestId}`),
  
  // Profile Tags
  getAllTags: () => api.get<string[]>('/profiles/tags'),
  searchTags: (query: string, limit: number = 10) => api.get<TagSearchResponse>(`/profiles/tags/search`, { params: { q: query, limit } }),
  getProfilesByTag: (tag: string) => api.get<ProfileApiResponse[]>(`/profiles/by-tag/${tag}`),
  
  // Profile-Scoped Operations
  getProfilePapers: (id: number, params?: any) => api.get(`/profiles/${id}/papers`, { params }),
  runProfileJudge: (id: number, params: any) => api.post(`/profiles/${id}/judge-run`, params),
  getProfileTrends: (id: number, params?: any) => api.get(`/profiles/${id}/trends`, { params }),
  generateProfileNewsletter: (id: number, params: any) => api.post(`/profiles/${id}/newsletter`, params),
  generateProfileMindmap: (id: number, params: any) => api.post(`/profiles/${id}/mindmap`, params),
  
  // Bulk Operations
  runBulkJudge: (request: BulkJudgeRunRequest) => api.post<BulkJudgeRunResponse>('/profiles/bulk/judge-run', request),
  generateBulkNewsletters: (params: any) => api.post('/profiles/bulk/newsletter', params),
  getBulkTrends: (params: any) => api.get('/profiles/bulk/trends', { params }),
  
  // Profile-Aware Ingestion
  runProfileAwareIngest: (request: ProfileAwareIngestRequest) => api.post<ProfileAwareIngestResponse>('/papers/profile-aware-ingest', request),
  
  // Bulk Embedding
  runBulkEmbed: (request: BulkEmbedRequest) => api.post('/papers/bulk-embed', request),
  checkExistingBulkData: (params: { start_date: string; end_date: string }) => api.get('/papers/check-existing-bulk-data', { params }),
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
export const createWebSocket = (taskId: string, type: 'newsletter' | 'podcast' | 'visualizer' | 'research-agent' | 'mindmap' | 'mindmap-pdf-parse' | 'trends') => {
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
        search?: string,
        topicId?: number
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
        if (topicId !== undefined) params.topic_id = topicId;

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
  paper_id?: string;
  topic_id?: number;
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

// === Trends API Interfaces ===

export interface TopicApiResponse {
  id: number;
  label: string;
  keywords: string[];
  embedding_model?: string;
  created_at: string;
  updated_at: string;
  latest_doc_count?: number;
  latest_growth_rate?: number;
  total_papers?: number;
  forecast_1m?: number;
  forecast_3m?: number;
  forecast_6m?: number;
}

export interface TopicMetricResponse {
  id: number;
  topic_id: number;
  period_start: string;
  period_end: string;
  period_type: string;
  doc_count: number;
  avg_score?: number;
  growth_rate?: number;
  forecast_1m?: number;
  forecast_3m?: number;
  forecast_6m?: number;
  created_at: string;
}

export interface TopicDetailResponse {
  topic: TopicApiResponse;
  timeline: TopicMetricResponse[];
  representative_papers: PaperApiResponse[];
  total_papers: number;
}

export interface TrendsListResponse {
  topics: TopicApiResponse[];
  total_topics: number;
  total_papers_with_topics: number;
  period_type: string;
  duration_months: number;
}

export interface TrendsSearchResponse {
  query: string;
  topics: TopicApiResponse[];
  total_results: number;
}

export interface TrendsRecomputeRequest {
  lookback_months: number;
  duration_months: number;
  min_papers: number;
  force_full_recalc: boolean;
  validate_accuracy: boolean;
  clear_all_data: boolean;
}

export interface TrendsRecomputeResponse {
  task_id: string;
  message: string;
  estimated_duration_minutes: number;
}

export interface TopicPapersResponse {
  topic_id: number;
  topic_label: string;
  papers: PaperApiResponse[];
  total_papers: number;
}

export interface ResearchInterestPapersResponse {
    research_interest_id: number;
    interest_text: string;
    papers: PaperApiResponse[];
    total_papers: number;
}

// Trends API
export const trendsApi = {
  getTrendingTopics: async (params?: GetTrendingTopicsParams): Promise<AxiosResponse<TrendsListResponse>> => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.period_type) searchParams.append('period_type', params.period_type);
    if (params?.duration_months) searchParams.append('duration_months', params.duration_months.toString());
    if (params?.min_doc_count) searchParams.append('min_doc_count', params.min_doc_count.toString());
    if (params?.sort_by) searchParams.append('sort_by', params.sort_by);
    
    return api.get(`/trends?${searchParams.toString()}`);
  },

  searchTopics: async (params: SearchTopicsParams): Promise<AxiosResponse<TrendsSearchResponse>> => {
    const searchParams = new URLSearchParams();
    searchParams.append('query', params.query);
    if (params.limit) searchParams.append('limit', params.limit.toString());
    
    return api.get(`/trends/search?${searchParams.toString()}`);
  },

  getTopicDetail: async (topicId: number, params?: GetTopicDetailParams): Promise<AxiosResponse<TopicDetailResponse>> => {
    const searchParams = new URLSearchParams();
    if (params?.period_type) searchParams.append('period_type', params.period_type);
    if (params?.timeline_limit) searchParams.append('timeline_limit', params.timeline_limit.toString());
    if (params?.papers_limit) searchParams.append('papers_limit', params.papers_limit.toString());
    
    return api.get(`/trends/${topicId}?${searchParams.toString()}`);
  },

  recomputeTrends: async (params: TrendsRecomputeRequest): Promise<AxiosResponse<TrendsRecomputeResponse>> => {
    return api.post('/trends/recompute', params);
  },

  getTopicPapers: async (topicId: number, params?: GetTopicPapersParams): Promise<AxiosResponse<TopicPapersResponse>> => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.min_relevance) searchParams.append('min_relevance', params.min_relevance.toString());
    if (params?.sort_by) searchParams.append('sort_by', params.sort_by);
    return api.get(`/trends/${topicId}/papers?${searchParams.toString()}`);
  },

  summarizeLabels: async (labels: string[]): Promise<AxiosResponse<Record<string, string>>> => {
    return api.post('/trends/summarize-labels', labels);
  },

  getResearchInterestPapers: async (interestId: number, params?: GetResearchInterestPapersParams): Promise<AxiosResponse<ResearchInterestPapersResponse>> => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.min_similarity) searchParams.append('min_similarity', params.min_similarity.toString());
    if (params?.sort_by) searchParams.append('sort_by', params.sort_by);
    return api.get(`/trends/research-interests/${interestId}/papers`, { params: searchParams });
  },
};

// Research Interest Clustering API
export const researchInterestsApi = {
  getResearchInterests: async (params?: GetTrendingTopicsParams): Promise<AxiosResponse<TrendsListResponse>> => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.period_type) searchParams.append('period_type', params.period_type);
    if (params?.duration_months) searchParams.append('duration_months', params.duration_months.toString());
    if (params?.min_doc_count) searchParams.append('min_doc_count', params.min_doc_count.toString());
    if (params?.sort_by) searchParams.append('sort_by', params.sort_by);
    
    return api.get(`/trends/research-interests?${searchParams.toString()}`);
  },

  searchResearchInterests: async (params: SearchTopicsParams): Promise<AxiosResponse<TrendsSearchResponse>> => {
    const searchParams = new URLSearchParams();
    searchParams.append('query', params.query);
    if (params.limit) searchParams.append('limit', params.limit.toString());
    
    return api.get(`/trends/research-interests/search?${searchParams.toString()}`);
  },

  getResearchInterestDetail: async (interestId: number, params?: GetTopicDetailParams): Promise<AxiosResponse<ResearchInterestDetailResponse>> => {
    const searchParams = new URLSearchParams();
    if (params?.period_type) searchParams.append('period_type', params.period_type);
    if (params?.timeline_limit) searchParams.append('timeline_limit', params.timeline_limit.toString());
    if (params?.papers_limit) searchParams.append('papers_limit', params.papers_limit.toString());
    
    return api.get(`/trends/research-interests/${interestId}?${searchParams.toString()}`);
  },

  recomputeResearchInterests: async (params: TrendsRecomputeRequest): Promise<AxiosResponse<TrendsRecomputeResponse>> => {
    return api.post('/trends/research-interests/recompute', params);
  },

  getResearchInterestPapers: async (interestId: number, params?: GetResearchInterestPapersParams): Promise<AxiosResponse<ResearchInterestPapersResponse>> => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.min_similarity) searchParams.append('min_similarity', params.min_similarity.toString());
    if (params?.sort_by) searchParams.append('sort_by', params.sort_by);
    return api.get(`/trends/research-interests/${interestId}/papers`, { params: searchParams });
  },
};

// === Research Interest Clustering API Interfaces ===

export interface ResearchInterestApiResponse {
  id: number;
  interest_text: string;
  embedding_model?: string;
  created_at: string;
  updated_at?: string;
  latest_doc_count?: number;
  latest_growth_rate?: number;
  total_papers?: number;
  latest_avg_relevance?: number;
  latest_avg_score?: number;
  forecast_1m?: number;
  forecast_3m?: number;
  forecast_6m?: number;
}

export interface ResearchInterestMetricResponse {
  id: number;
  research_interest_id: number;
  period_start: string;
  period_end: string;
  period_type: string;
  doc_count: number;
  avg_relevance_score?: number;
  avg_paper_score?: number;
  growth_rate?: number;
  forecast_1m?: number;
  forecast_3m?: number;
  forecast_6m?: number;
  created_at: string;
}

export interface ResearchInterestDetailResponse {
  interest: ResearchInterestApiResponse;
  timeline: ResearchInterestMetricResponse[];
  representative_papers: PaperApiResponse[];
  total_papers: number;
}

// Union type for detail responses to handle both topics and research interests
export type EntityDetailResponse = TopicDetailResponse | ResearchInterestDetailResponse;

// Type guards to differentiate between topic and research interest responses
export function isTopicDetailResponse(response: EntityDetailResponse): response is TopicDetailResponse {
  return 'topic' in response;
}

export function isResearchInterestDetailResponse(response: EntityDetailResponse): response is ResearchInterestDetailResponse {
  return 'interest' in response;
}

// Performance Configuration interfaces
export interface PerformanceConfig {
  max_cores: number;
  max_memory_gb: number;
  hdbscan_n_jobs: number;
  clustering_batch_size: number;
  embedding_batch_size: number;
  vector_processing_workers: number;
  enable_memory_mapping: boolean;
  cache_embeddings: boolean;
  aggressive_garbage_collection: boolean;
  development_mode: boolean;
  development_max_papers: number;
}

export interface SystemInfo {
  cpu_count_physical: number;
  cpu_count_logical: number;
  memory_total_gb: number;
  memory_available_gb: number;
  gpu_available: boolean;
  gpu_name?: string;
  recommended_config: PerformanceConfig;
}

// Performance Configuration API
export const performanceApi = {
  getSystemInfo: async (): Promise<SystemInfo> => {
    const response = await api.get('/trends/system-info');
    return response.data;
  },

  getPerformanceConfig: async (): Promise<PerformanceConfig> => {
    const response = await api.get('/trends/performance-config');
    return response.data;
  },

  updatePerformanceConfig: async (config: PerformanceConfig): Promise<{ status: string; message: string }> => {
    const response = await api.post('/trends/performance-config', config);
    return response.data;
  },
}; 