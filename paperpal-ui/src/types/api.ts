// PDF Types
export interface PDFMetadata {
  num_pages: number;
  title: string;
  author: string;
}

export interface PDFProcessingResult {
  filename: string;
  text: string;
  metadata: PDFMetadata;
  sections: {
    title: string;
    content: string;
  }[];
}

export interface PDFBatchResult {
  filename: string;
  result: PDFProcessingResult;
}

export interface PDFUploadResult {
  filename: string;
  file_path: string;
}

// Script Types
export interface DialogueItem {
  speaker: string;
  text: string;
}

export interface Script {
  dialogue: DialogueItem[];
  metadata?: Record<string, any>;
}

export interface ScriptListItem {
  filename: string;
  last_modified: number;
}

// Podcast Types
export interface TextModel {
  model_name: string;
  model_type: string;
  max_new_tokens: number;
  temperature: number;
  num_ctx: number;
}

export interface PodcastGenerationConfig {
  text_model: {
    model_name: string;
    model_type: string;
    max_new_tokens: number;
    temperature: number;
    num_ctx: number;
  };
  tts_provider: string;
  speaker_1_voice: string;
  speaker_1_speed: number;
  speaker_2_voice: string;
  speaker_2_speed: number;
  output_format: string;
  visualizer: boolean;
  resolution: [number, number];
  fps: number;
  matrix_count: number;
  fade_time: number;
  head_saw_period: number;
  font_path: string;
}

export interface PodcastGenerationRequest {
  texts: string[];
  config?: PodcastGenerationConfig;
}

export interface PodcastGenerationResponse {
  task_id: string;
  status: TaskStatus['status'];
  message: string;
  transcript?: string;
  dict_transcript?: Script;
  segments?: string;
  final_podcast_path?: string;
  visualizer_path?: string;
  description?: string;
}

// Visualizer Types
export interface VisualizerConfig {
  resolution: [number, number];
  fps: number;
  matrix_count: number;
  matrix_head_color: string;
  matrix_tail_color: string;
  matrix_char_size: number;
  head_step_time: number;
  random_x_jitter: number;
  fade_time: number;
  head_glow_passes: number;
  head_glow_alpha_decay: number;
  head_spawn_delay_range: [number, number];
  head_saw_period: number;
  wave_color: string;
  trail_colors: string[];
  glow_passes: number;
  glow_alpha_decay: number;
  line_width: number;
  font_path: string;
}

export interface VisualizerResponse {
  message: string;
  output_file: string;
  status: TaskStatus['status'];
  task_id: string;
}

// Common Types
export interface TaskStatus {
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message?: string;
  current_step?: string;
  error?: string;
  output_url?: string;
  progress?: number;
  steps?: {
    name: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    progress?: number;
  }[];
} 