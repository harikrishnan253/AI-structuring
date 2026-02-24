import axios from 'axios';
import type { 
  Batch, 
  BatchWithJobs, 
  CreateBatchResponse, 
  BatchListResponse,
  QueueStatus,
  Job,
  UploadOptions,
  TokenStats,
  DailyStats,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============ Batch Operations ============

export async function createBatch(
  files: File[],
  options: UploadOptions
): Promise<CreateBatchResponse> {
  const formData = new FormData();
  
  files.forEach(file => {
    formData.append('files', file);
  });
  
  formData.append('document_type', options.document_type);
  formData.append('use_markers', String(options.use_markers));
  
  if (options.batch_name) {
    formData.append('batch_name', options.batch_name);
  }
  
  const response = await api.post<CreateBatchResponse>('/queue/batch', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
}

export async function getBatch(batchId: string): Promise<BatchWithJobs> {
  const response = await api.get<BatchWithJobs>(`/queue/batch/${batchId}`);
  return response.data;
}

export async function deleteBatch(batchId: string): Promise<void> {
  await api.delete(`/queue/batch/${batchId}`);
}

export async function retryBatchFailed(batchId: string): Promise<{ retried_jobs: number }> {
  const response = await api.post<{ success: boolean; retried_jobs: number }>(
    `/queue/batch/${batchId}/retry`
  );
  return response.data;
}

export async function stopBatch(batchId: string): Promise<{ cancelled_jobs: number }> {
  const response = await api.post<{ success: boolean; cancelled_jobs: number; message: string }>(
    `/queue/batch/${batchId}/stop`
  );
  return response.data;
}

export async function listBatches(limit = 50): Promise<BatchListResponse> {
  const response = await api.get<BatchListResponse>('/queue/batches', {
    params: { limit },
  });
  return response.data;
}

// ============ Job Operations ============

export async function getJob(jobId: string): Promise<{ job: Job }> {
  const response = await api.get<{ job: Job }>(`/queue/job/${jobId}`);
  return response.data;
}

export async function cancelJob(jobId: string): Promise<void> {
  await api.post(`/queue/job/${jobId}/cancel`);
}

export async function retryJob(jobId: string): Promise<void> {
  await api.post(`/queue/job/${jobId}/retry`);
}

// ============ Queue Status ============

export async function getQueueStatus(): Promise<QueueStatus> {
  const response = await api.get<QueueStatus>('/queue/status');
  return response.data;
}

// ============ Token Statistics ============

export async function getTokenStats(): Promise<TokenStats> {
  const response = await api.get<TokenStats>('/queue/stats/tokens');
  return response.data;
}

export async function getDailyStats(days = 30): Promise<{ daily_stats: DailyStats[]; period_days: number }> {
  const response = await api.get<{ daily_stats: DailyStats[]; period_days: number }>(
    '/queue/stats/daily',
    { params: { days } }
  );
  return response.data;
}

// ============ Downloads ============

export function getDownloadUrl(batchId: string, fileType: string, filename: string): string {
  return `/api/download/${batchId}/${fileType}/${filename}`;
}

export function getBatchZipUrl(batchId: string): string {
  return `/api/download/${batchId}/zip`;
}

export default api;
