// API Types for the Pre-Editor Queue System

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';

export type BatchStatus = 
  | 'empty' 
  | 'pending' 
  | 'processing' 
  | 'completed' 
  | 'completed_with_errors';

export interface CostInfo {
  input_cost: number;
  output_cost: number;
  total_cost: number;
  model: string;
}

export interface Job {
  id: number;
  job_id: string;
  batch_id: number;
  original_filename: string;
  status: JobStatus;
  queue_position: number;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  output_path: string | null;
  review_path: string | null;
  json_path: string | null;
  error_message: string | null;
  total_paragraphs: number | null;
  auto_applied: number | null;
  needs_review: number | null;
  processing_time_seconds: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  cost?: CostInfo | null;
  timezone?: string;
  // Content integrity tracking
  original_paragraph_count?: number | null;
  processed_paragraph_count?: number | null;
  content_verified?: boolean | null;
}

export interface Batch {
  id: number;
  batch_id: string;
  name: string | null;
  created_at: string | null;
  completed_at: string | null;
  document_type: string;
  use_markers: boolean;
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  status: BatchStatus;
  progress_percent: number;
  output_folder: string | null;
  total_tokens?: number;
  cost?: CostInfo | null;
  timezone?: string;
}

export interface BatchStats {
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_processing_time: number;
  cost: CostInfo;
}

export interface QueueStatus {
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  total: number;
  is_processing: boolean;
  current_job_id: string | null;
  queue_mode: 'threading' | 'celery';
}

export interface TokenStats {
  all_time: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    total_jobs: number;
    cost: CostInfo;
  };
  today: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost: CostInfo;
  };
  averages: {
    tokens_per_job: number;
    cost_per_job: number;
  };
  pricing: {
    model: string;
    rates: {
      input_per_million: number;
      output_per_million: number;
    };
  };
  timezone?: string;
  current_time?: string;
}

export interface DailyStats {
  date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  jobs_completed: number;
  cost: CostInfo;
}

export interface BatchWithJobs {
  batch: Batch;
  jobs: Job[];
  stats: BatchStats;
}

export interface CreateBatchResponse {
  success: boolean;
  batch: Batch;
  message: string;
}

export interface BatchListResponse {
  batches: Batch[];
  total: number;
}

export type DocumentType = 
  | 'Academic Document'
  | 'Medical Textbook'
  | 'Research Paper'
  | 'Lab Manual'
  | 'Edwards Nursing Textbook';

export interface UploadOptions {
  document_type: DocumentType;
  use_markers: boolean;
  batch_name?: string;
}
