export interface ServerStats {
  server_id: string;
  server_name?: string;
  server_url: string;
  total: number;
  completed: number;
  in_progress: number;
  failed: number;
  papers_processed?: number;
  papers_failed?: number;
  avg_latency?: number;
  throughput?: number; // Papers per minute
  last_completed_at?: string;
  status?: 'idle' | 'busy' | 'offline' | 'unknown';
}

export interface TaskMetadata {
  // Harvest stage
  papers_discovered?: number;

  // Rank stage
  papers_to_score?: number;
  papers_scored?: number;
  papers_failed?: number;
  papers_pending?: number;
  papers_in_progress?: number;
  server_stats?: ServerStats[];
  avg_task_duration?: number;
  estimated_time_remaining?: number;

  // General
  current_step?: string;
  total_steps?: number;
  [key: string]: any;
}

export interface NewsletterState {
  taskId: string | null;
  status: 'idle' | 'running' | 'completed' | 'failed';
  stage: string;
  progress: number;
  message: string;
  metadata?: TaskMetadata;
  error?: string;
  result?: any;
}
