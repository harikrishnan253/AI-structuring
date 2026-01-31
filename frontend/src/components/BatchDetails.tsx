import {
  FileText,
  Download,
  RefreshCw,
  XCircle,
  CheckCircle,
  Loader2,
  Clock,
  AlertTriangle,
  Package,
  Coins,
  Zap,
} from 'lucide-react';
import { useBatch, useRetryJob, useCancelJob } from '../hooks/useQueue';
import { getDownloadUrl, getBatchZipUrl } from '../api/client';
import type { Job, JobStatus, CostInfo } from '../types';

interface BatchDetailsProps {
  batchId: string;
}

export function BatchDetails({ batchId }: BatchDetailsProps) {
  const { data, isLoading } = useBatch(batchId);
  const retryJob = useRetryJob();
  const cancelJob = useCancelJob();
  
  if (isLoading || !data) {
    return (
      <div className="bg-white rounded-xl border p-8" style={{ borderColor: '#e5e2dc' }}>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin" style={{ color: '#64748b' }} />
        </div>
      </div>
    );
  }
  
  const { batch, jobs, stats } = data;
  
  const formatCost = (cost: number) => {
    if (cost < 0.01) return `$${cost.toFixed(6)}`;
    if (cost < 1) return `$${cost.toFixed(4)}`;
    return `$${cost.toFixed(2)}`;
  };
  
  const formatTokens = (num: number) => {
    if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(2)}M`;
    if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
    return num.toLocaleString();
  };
  
  return (
    <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#e5e2dc' }}>
      {/* Header */}
      <div className="px-6 py-5 border-b" style={{ borderColor: '#e5e2dc' }}>
        <div className="flex justify-between items-start">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg" style={{ backgroundColor: '#f1f5f9' }}>
              <Package className="h-5 w-5" style={{ color: '#64748b' }} />
            </div>
            <div>
              <h3 className="text-lg font-semibold" style={{ color: '#1e293b' }}>{batch.name}</h3>
              <p className="text-sm" style={{ color: '#64748b' }}>
                {batch.document_type} • {batch.use_markers ? 'XML Markers' : 'Word Styles'}
              </p>
            </div>
          </div>
          
          {batch.status === 'completed' && (
            <a
              href={getBatchZipUrl(batch.batch_id)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-white transition-all"
              style={{ 
                background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
                boxShadow: '0 2px 4px rgba(5, 150, 105, 0.25)'
              }}
            >
              <Download className="h-4 w-4" />
              Download All
            </a>
          )}
        </div>
        
        {/* Progress Bar */}
        {(batch.status === 'processing' || batch.status === 'pending') && (
          <div className="mt-5">
            <div className="flex justify-between text-sm mb-2">
              <span style={{ color: '#64748b' }}>Progress</span>
              <span className="font-medium" style={{ color: '#1e293b' }}>
                {batch.completed_jobs + batch.failed_jobs} / {batch.total_jobs}
              </span>
            </div>
            <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: '#e5e2dc' }}>
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ 
                  width: `${batch.progress_percent}%`,
                  background: 'linear-gradient(90deg, #d97706 0%, #f59e0b 100%)'
                }}
              />
            </div>
          </div>
        )}
        
        {/* Summary Stats - Jobs */}
        <div className="mt-5 grid grid-cols-3 gap-3">
          <div className="rounded-lg p-3 text-center" style={{ backgroundColor: '#f8fafc' }}>
            <p className="text-xl font-bold" style={{ color: '#1e293b' }}>{batch.total_jobs}</p>
            <p className="text-xs" style={{ color: '#64748b' }}>Total</p>
          </div>
          <div className="rounded-lg p-3 text-center" style={{ backgroundColor: '#ecfdf5' }}>
            <p className="text-xl font-bold" style={{ color: '#059669' }}>{batch.completed_jobs}</p>
            <p className="text-xs" style={{ color: '#059669' }}>Completed</p>
          </div>
          <div className="rounded-lg p-3 text-center" 
               style={{ backgroundColor: batch.failed_jobs > 0 ? '#fef2f2' : '#f8fafc' }}>
            <p className="text-xl font-bold" 
               style={{ color: batch.failed_jobs > 0 ? '#dc2626' : '#64748b' }}>
              {batch.failed_jobs}
            </p>
            <p className="text-xs" style={{ color: batch.failed_jobs > 0 ? '#dc2626' : '#64748b' }}>
              Failed
            </p>
          </div>
        </div>
        
        {/* Token & Cost Stats */}
        {stats.total_tokens > 0 && (
          <div className="mt-4 p-4 rounded-lg" style={{ backgroundColor: '#fffbeb' }}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Zap className="h-4 w-4" style={{ color: '#d97706' }} />
                  <span className="text-sm" style={{ color: '#92400e' }}>
                    <strong>{formatTokens(stats.total_tokens)}</strong> tokens
                  </span>
                </div>
                <span className="text-xs" style={{ color: '#b45309' }}>
                  ({formatTokens(stats.total_input_tokens)} in / {formatTokens(stats.total_output_tokens)} out*)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Coins className="h-4 w-4" style={{ color: '#d97706' }} />
                <span className="font-semibold" style={{ color: '#92400e' }}>
                  {formatCost(stats.cost.total_cost)}
                </span>
              </div>
            </div>
            <p className="text-xs mt-2" style={{ color: '#a16207' }}>
              * Output includes thinking tokens (Gemini 2.5 internal reasoning)
            </p>
          </div>
        )}
      </div>
      
      {/* Jobs List */}
      <div className="max-h-80 overflow-y-auto">
        {jobs.map(job => (
          <JobItem
            key={job.job_id}
            job={job}
            batchId={batch.batch_id}
            onRetry={() => retryJob.mutate(job.job_id)}
            onCancel={() => cancelJob.mutate(job.job_id)}
          />
        ))}
      </div>
    </div>
  );
}

interface JobItemProps {
  job: Job;
  batchId: string;
  onRetry: () => void;
  onCancel: () => void;
}

function JobItem({ job, batchId, onRetry, onCancel }: JobItemProps) {
  const statusConfig = getJobStatusConfig(job.status);
  
  const getFilename = (path: string | null): string | null => {
    if (!path) return null;
    // Handle both Windows and Unix paths
    // First normalize by replacing backslashes with forward slashes
    const normalized = path.replace(/\\/g, '/');
    const parts = normalized.split('/');
    return parts[parts.length - 1] || null;
  };
  
  const formatCost = (cost: CostInfo) => {
    if (cost.total_cost < 0.01) return `$${cost.total_cost.toFixed(6)}`;
    if (cost.total_cost < 1) return `$${cost.total_cost.toFixed(4)}`;
    return `$${cost.total_cost.toFixed(2)}`;
  };
  
  return (
    <div className="px-6 py-4 border-b transition-colors hover:bg-stone-50" 
         style={{ borderColor: '#f5f5f4' }}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="p-2 rounded-lg flex-shrink-0" style={{ backgroundColor: statusConfig.bgColor }}>
            <statusConfig.icon 
              className={`h-4 w-4 ${statusConfig.animate ? 'animate-spin' : ''}`} 
              style={{ color: statusConfig.iconColor }} 
            />
          </div>
          <div className="min-w-0">
            <p className="font-medium text-sm truncate" style={{ color: '#1e293b' }}>
              {job.original_filename}
            </p>
            <div className="flex items-center gap-2 text-xs flex-wrap" style={{ color: '#64748b' }}>
              {job.status === 'completed' && (
                <>
                  {job.total_paragraphs && (
                    <span>{job.total_paragraphs} paragraphs</span>
                  )}
                  {job.processing_time_seconds && (
                    <span>• {job.processing_time_seconds.toFixed(1)}s</span>
                  )}
                  {job.total_tokens && (
                    <span>• {job.total_tokens.toLocaleString()} tokens</span>
                  )}
                  {job.cost && (
                    <span className="font-medium" style={{ color: '#b45309' }}>
                      • {formatCost(job.cost)}
                    </span>
                  )}
                </>
              )}
              {job.error_message && (
                <span className="truncate max-w-[200px]" style={{ color: '#dc2626' }} title={job.error_message}>
                  • {job.error_message}
                </span>
              )}
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-2 flex-shrink-0 ml-4">
          {/* Status Badge */}
          <span 
            className="px-2 py-1 text-xs font-medium rounded-full"
            style={{ 
              backgroundColor: statusConfig.badgeBg,
              color: statusConfig.badgeColor,
            }}
          >
            {statusConfig.label}
          </span>
          
          {/* Actions */}
          {job.status === 'failed' && (
            <button
              onClick={onRetry}
              className="p-1.5 rounded-lg transition-colors hover:bg-amber-50"
              title="Retry"
            >
              <RefreshCw className="h-4 w-4" style={{ color: '#d97706' }} />
            </button>
          )}
          
          {job.status === 'pending' && (
            <button
              onClick={onCancel}
              className="p-1.5 rounded-lg transition-colors hover:bg-red-50"
              title="Cancel"
            >
              <XCircle className="h-4 w-4" style={{ color: '#dc2626' }} />
            </button>
          )}
          
          {job.status === 'completed' && job.output_path && (
            <a
              href={getDownloadUrl(batchId, 'processed', getFilename(job.output_path) || '')}
              className="p-1.5 rounded-lg transition-colors hover:bg-emerald-50"
              title="Download"
            >
              <Download className="h-4 w-4" style={{ color: '#059669' }} />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

function getJobStatusConfig(status: JobStatus) {
  switch (status) {
    case 'pending':
      return {
        icon: Clock,
        bgColor: '#f1f5f9',
        iconColor: '#64748b',
        label: 'Pending',
        badgeBg: '#f1f5f9',
        badgeColor: '#475569',
        animate: false,
      };
    case 'processing':
      return {
        icon: Loader2,
        bgColor: '#fef3c7',
        iconColor: '#d97706',
        label: 'Processing',
        badgeBg: '#fef3c7',
        badgeColor: '#b45309',
        animate: true,
      };
    case 'completed':
      return {
        icon: CheckCircle,
        bgColor: '#d1fae5',
        iconColor: '#059669',
        label: 'Completed',
        badgeBg: '#d1fae5',
        badgeColor: '#047857',
        animate: false,
      };
    case 'failed':
      return {
        icon: AlertTriangle,
        bgColor: '#fee2e2',
        iconColor: '#dc2626',
        label: 'Failed',
        badgeBg: '#fee2e2',
        badgeColor: '#b91c1c',
        animate: false,
      };
    case 'cancelled':
      return {
        icon: XCircle,
        bgColor: '#f1f5f9',
        iconColor: '#64748b',
        label: 'Cancelled',
        badgeBg: '#f1f5f9',
        badgeColor: '#475569',
        animate: false,
      };
    default:
      return {
        icon: FileText,
        bgColor: '#f1f5f9',
        iconColor: '#64748b',
        label: status,
        badgeBg: '#f1f5f9',
        badgeColor: '#475569',
        animate: false,
      };
  }
}
