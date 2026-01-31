import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '../api/client';
import type { UploadOptions } from '../types';

// ============ Query Keys ============

export const queryKeys = {
  batches: ['batches'] as const,
  batch: (id: string) => ['batch', id] as const,
  queueStatus: ['queueStatus'] as const,
  job: (id: string) => ['job', id] as const,
  tokenStats: ['tokenStats'] as const,
  dailyStats: (days: number) => ['dailyStats', days] as const,
};

// ============ Batch Hooks ============

export function useBatches(limit = 50) {
  return useQuery({
    queryKey: queryKeys.batches,
    queryFn: () => api.listBatches(limit),
    refetchInterval: 5000,
  });
}

export function useBatch(batchId: string | null) {
  return useQuery({
    queryKey: queryKeys.batch(batchId ?? ''),
    queryFn: () => api.getBatch(batchId!),
    enabled: !!batchId,
    refetchInterval: 2000,
  });
}

export function useCreateBatch() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ files, options }: { files: File[]; options: UploadOptions }) =>
      api.createBatch(files, options),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.batches });
      queryClient.invalidateQueries({ queryKey: queryKeys.queueStatus });
      queryClient.invalidateQueries({ queryKey: queryKeys.tokenStats });
    },
  });
}

export function useDeleteBatch() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.deleteBatch,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.batches });
      queryClient.invalidateQueries({ queryKey: queryKeys.queueStatus });
    },
  });
}

export function useRetryBatchFailed() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.retryBatchFailed,
    onSuccess: (_, batchId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.batch(batchId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.queueStatus });
    },
  });
}

export function useStopBatch() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.stopBatch,
    onSuccess: (_, batchId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.batch(batchId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.batches });
      queryClient.invalidateQueries({ queryKey: queryKeys.queueStatus });
    },
  });
}

// ============ Job Hooks ============

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: queryKeys.job(jobId ?? ''),
    queryFn: () => api.getJob(jobId!),
    enabled: !!jobId,
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.cancelJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.batches });
      queryClient.invalidateQueries({ queryKey: queryKeys.queueStatus });
    },
  });
}

export function useRetryJob() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.retryJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.batches });
      queryClient.invalidateQueries({ queryKey: queryKeys.queueStatus });
    },
  });
}

// ============ Queue Status ============

export function useQueueStatus() {
  return useQuery({
    queryKey: queryKeys.queueStatus,
    queryFn: api.getQueueStatus,
    refetchInterval: 3000,
  });
}

// ============ Token Statistics ============

export function useTokenStats() {
  return useQuery({
    queryKey: queryKeys.tokenStats,
    queryFn: api.getTokenStats,
    refetchInterval: 10000, // Refresh every 10 seconds
  });
}

export function useDailyStats(days = 30) {
  return useQuery({
    queryKey: queryKeys.dailyStats(days),
    queryFn: () => api.getDailyStats(days),
    refetchInterval: 60000, // Refresh every minute
  });
}
