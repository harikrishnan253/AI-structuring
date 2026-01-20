import { useParams, Link, useNavigate } from 'react-router-dom';
import { formatDistanceToNow, format } from 'date-fns';
import {
  ArrowLeft,
  Download,
  RefreshCw,
  Trash2,
  FileText,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  AlertTriangle,
  Zap,
  Coins,
  ChevronRight,
  ExternalLink,
  StopCircle,
  AlertOctagon,
} from 'lucide-react';
import { useBatch, useRetryJob, useCancelJob, useDeleteBatch, useRetryBatchFailed, useStopBatch } from '../hooks/useQueue';
import { getDownloadUrl, getBatchZipUrl } from '../api/client';
import type { Job, JobStatus, CostInfo } from '../types';

export function BatchDetailPage() {
  const { batchId } = useParams<{ batchId: string }>();
  const navigate = useNavigate();
  const { data, isLoading } = useBatch(batchId || null);
  const retryJob = useRetryJob();
  const cancelJob = useCancelJob();
  const deleteBatch = useDeleteBatch();
  const retryFailed = useRetryBatchFailed();
  const stopBatch = useStopBatch();
  
  if (isLoading || !data) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }
  
  const { batch, jobs, stats } = data;
  
  const formatTime = (seconds: number) => {
    if (!seconds || seconds === 0) return '-';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    if (mins < 60) return `${mins}m ${secs}s`;
    const hours = Math.floor(mins / 60);
    const remainMins = mins % 60;
    return `${hours}h ${remainMins}m`;
  };
  
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
  
  const getFilename = (path: string | null): string | null => {
    if (!path) return null;
    const normalized = path.replace(/\\/g, '/');
    const parts = normalized.split('/');
    return parts[parts.length - 1] || null;
  };
  
  const handleDelete = () => {
    if (confirm('Delete this batch and all its files?')) {
      deleteBatch.mutate(batch.batch_id, {
        onSuccess: () => navigate('/batches')
      });
    }
  };
  
  const handleStop = () => {
    if (confirm('⚠️ TERMINATE BATCH\n\nThis will cancel all pending jobs in this batch.\nCompleted jobs will be kept.\n\nAre you sure you want to terminate?')) {
      stopBatch.mutate(batch.batch_id);
    }
  };
  
  // Check if batch has pending/processing jobs
  const hasPendingJobs = jobs.some(j => j.status === 'pending' || j.status === 'processing');
  
  return (
    <div className="space-y-6">
      {/* Back Link */}
      <Link 
        to="/batches" 
        className="inline-flex items-center gap-2 text-sm font-medium hover:underline"
        style={{ color: '#64748b' }}
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Batches
      </Link>
      
      {/* Terminate Batch Banner - Show when processing */}
      {hasPendingJobs && (
        <div className="p-4 rounded-xl border-2 flex items-center justify-between"
             style={{ 
               background: 'linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)',
               borderColor: '#fca5a5'
             }}>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg" style={{ backgroundColor: '#fee2e2' }}>
              <AlertOctagon className="h-5 w-5" style={{ color: '#dc2626' }} />
            </div>
            <div>
              <p className="font-semibold" style={{ color: '#991b1b' }}>Processing in Progress</p>
              <p className="text-sm" style={{ color: '#b91c1c' }}>
                {jobs.filter(j => j.status === 'pending').length} pending, {jobs.filter(j => j.status === 'processing').length} processing
              </p>
            </div>
          </div>
          <button
            onClick={handleStop}
            disabled={stopBatch.isPending}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-white transition-all hover:scale-105 disabled:opacity-50"
            style={{ 
              background: 'linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)',
              boxShadow: '0 4px 12px rgba(220, 38, 38, 0.4)'
            }}
          >
            {stopBatch.isPending ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <StopCircle className="h-5 w-5" />
            )}
            Terminate
          </button>
        </div>
      )}
      
      {/* Header Card */}
      <div className="bg-white rounded-xl border p-6" style={{ borderColor: '#e5e2dc' }}>
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl" style={{ backgroundColor: '#f1f5f9' }}>
              <FileText className="h-8 w-8" style={{ color: '#64748b' }} />
            </div>
            <div>
              <h1 className="text-2xl font-bold" style={{ color: '#1e293b' }}>{batch.name}</h1>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-sm" style={{ color: '#64748b' }}>{batch.document_type}</span>
                <span className="text-sm" style={{ color: '#94a3b8' }}>•</span>
                <span className="text-sm" style={{ color: '#64748b' }}>
                  {batch.use_markers ? 'XML Markers' : 'Word Styles'}
                </span>
                {batch.created_at && (
                  <>
                    <span className="text-sm" style={{ color: '#94a3b8' }}>•</span>
                    <span className="text-sm" style={{ color: '#64748b' }}>
                      {format(new Date(batch.created_at), 'MMM d, yyyy h:mm a')}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {batch.failed_jobs > 0 && (
              <button
                onClick={() => retryFailed.mutate(batch.batch_id)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all"
                style={{ backgroundColor: '#fef3c7', color: '#b45309' }}
              >
                <RefreshCw className="h-4 w-4" />
                Retry Failed ({batch.failed_jobs})
              </button>
            )}
            
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
            
            <button
              onClick={handleDelete}
              className="p-2 rounded-lg hover:bg-red-50"
              title="Delete batch"
            >
              <Trash2 className="h-5 w-5" style={{ color: '#dc2626' }} />
            </button>
          </div>
        </div>
        
        {/* Progress */}
        {(batch.status === 'processing' || batch.status === 'pending') && (
          <div className="mt-6 pt-6 border-t" style={{ borderColor: '#e5e2dc' }}>
            <div className="flex justify-between text-sm mb-2">
              <span style={{ color: '#64748b' }}>Progress</span>
              <span className="font-medium" style={{ color: '#1e293b' }}>
                {batch.completed_jobs + batch.failed_jobs} / {batch.total_jobs} files
              </span>
            </div>
            <div className="h-3 rounded-full overflow-hidden" style={{ backgroundColor: '#e5e2dc' }}>
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
      </div>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard label="Total Files" value={batch.total_jobs} color="slate" />
        <StatCard label="Completed" value={batch.completed_jobs} color="emerald" />
        <StatCard label="Failed" value={batch.failed_jobs} color="red" />
        <StatCard 
          label="Total Tokens" 
          value={formatTokens(stats.total_tokens)} 
          color="amber" 
          icon={<Zap className="h-4 w-4" />}
        />
        <StatCard 
          label="Total Cost" 
          value={formatCost(stats.cost.total_cost)} 
          color="green"
          icon={<Coins className="h-4 w-4" />}
        />
      </div>
      
      {/* Token Breakdown */}
      {stats.total_tokens > 0 && (
        <div className="bg-white rounded-xl border p-6" style={{ borderColor: '#e5e2dc' }}>
          <h3 className="font-semibold mb-4" style={{ color: '#1e293b' }}>Token Breakdown</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-lg" style={{ backgroundColor: '#f8fafc' }}>
              <p className="text-sm" style={{ color: '#64748b' }}>Input Tokens</p>
              <p className="text-xl font-bold mt-1" style={{ color: '#1e293b' }}>
                {formatTokens(stats.total_input_tokens)}
              </p>
              <p className="text-xs mt-1" style={{ color: '#94a3b8' }}>
                Cost: {formatCost(stats.cost.input_cost)}
              </p>
            </div>
            <div className="p-4 rounded-lg" style={{ backgroundColor: '#f8fafc' }}>
              <p className="text-sm" style={{ color: '#64748b' }}>Output Tokens</p>
              <p className="text-xl font-bold mt-1" style={{ color: '#1e293b' }}>
                {formatTokens(stats.total_output_tokens)}
              </p>
              <p className="text-xs mt-1" style={{ color: '#94a3b8' }}>
                Cost: {formatCost(stats.cost.output_cost)}
              </p>
            </div>
            <div className="p-4 rounded-lg" style={{ backgroundColor: '#f8fafc' }}>
              <p className="text-sm" style={{ color: '#64748b' }}>Avg per File</p>
              <p className="text-xl font-bold mt-1" style={{ color: '#1e293b' }}>
                {formatTokens(Math.round(stats.total_tokens / batch.total_jobs))}
              </p>
            </div>
            <div className="p-4 rounded-lg" style={{ backgroundColor: '#f8fafc' }}>
              <p className="text-sm" style={{ color: '#64748b' }}>Processing Time</p>
              <p className="text-xl font-bold mt-1" style={{ color: '#1e293b' }}>
                {formatTime(stats.total_processing_time)}
              </p>
            </div>
          </div>
        </div>
      )}
      
      {/* Jobs Table */}
      <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#e5e2dc' }}>
        <div className="px-6 py-4 border-b" style={{ borderColor: '#e5e2dc' }}>
          <h3 className="font-semibold" style={{ color: '#1e293b' }}>Files ({jobs.length})</h3>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b" style={{ backgroundColor: '#f8fafc', borderColor: '#e5e2dc' }}>
                <th className="text-left px-6 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                  File
                </th>
                <th className="text-left px-6 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                  Status
                </th>
                <th className="text-left px-6 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                  Paragraphs
                </th>
                <th className="text-left px-6 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                  Tokens
                </th>
                <th className="text-left px-6 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                  Cost
                </th>
                <th className="text-left px-6 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                  Time
                </th>
                <th className="text-right px-6 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: '#f1f5f9' }}>
              {jobs.map((job) => (
                <JobRow
                  key={job.job_id}
                  job={job}
                  batchId={batch.batch_id}
                  onRetry={() => retryJob.mutate(job.job_id)}
                  onCancel={() => cancelJob.mutate(job.job_id)}
                  getFilename={getFilename}
                  formatCost={formatCost}
                  formatTokens={formatTokens}
                  formatTime={formatTime}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string | number;
  color: 'slate' | 'emerald' | 'red' | 'amber' | 'green';
  icon?: React.ReactNode;
}

function StatCard({ label, value, color, icon }: StatCardProps) {
  const colors = {
    slate: { bg: '#f8fafc', text: '#334155' },
    emerald: { bg: '#ecfdf5', text: '#047857' },
    red: { bg: '#fef2f2', text: '#b91c1c' },
    amber: { bg: '#fffbeb', text: '#b45309' },
    green: { bg: '#dcfce7', text: '#166534' },
  };
  
  const c = colors[color];
  
  return (
    <div className="bg-white rounded-xl border p-4" style={{ borderColor: '#e5e2dc' }}>
      <div className="flex items-center gap-2 mb-1">
        {icon && <span style={{ color: c.text }}>{icon}</span>}
        <p className="text-sm" style={{ color: '#64748b' }}>{label}</p>
      </div>
      <p className="text-2xl font-bold" style={{ color: c.text }}>{value}</p>
    </div>
  );
}

interface JobRowProps {
  job: Job;
  batchId: string;
  onRetry: () => void;
  onCancel: () => void;
  getFilename: (path: string | null) => string | null;
  formatCost: (cost: number) => string;
  formatTokens: (num: number) => string;
  formatTime: (seconds: number) => string;
}

function JobRow({ job, batchId, onRetry, onCancel, getFilename, formatCost, formatTokens, formatTime }: JobRowProps) {
  const getStatusConfig = (status: JobStatus) => {
    switch (status) {
      case 'pending':
        return { icon: Clock, bg: '#f1f5f9', color: '#64748b', label: 'Pending' };
      case 'processing':
        return { icon: Loader2, bg: '#fef3c7', color: '#b45309', label: 'Processing', animate: true };
      case 'completed':
        return { icon: CheckCircle, bg: '#dcfce7', color: '#166534', label: 'Completed' };
      case 'failed':
        return { icon: AlertTriangle, bg: '#fee2e2', color: '#b91c1c', label: 'Failed' };
      case 'cancelled':
        return { icon: XCircle, bg: '#f1f5f9', color: '#64748b', label: 'Cancelled' };
      default:
        return { icon: FileText, bg: '#f1f5f9', color: '#64748b', label: status };
    }
  };
  
  const config = getStatusConfig(job.status);
  const StatusIcon = config.icon;
  
  return (
    <tr className="hover:bg-stone-50 transition-colors">
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg" style={{ backgroundColor: config.bg }}>
            <StatusIcon 
              className={`h-4 w-4 ${config.animate ? 'animate-spin' : ''}`} 
              style={{ color: config.color }} 
            />
          </div>
          <div className="min-w-0">
            <p className="font-medium truncate max-w-xs" style={{ color: '#1e293b' }}>
              {job.original_filename}
            </p>
            {job.error_message && (
              <p className="text-xs truncate max-w-xs" style={{ color: '#dc2626' }} title={job.error_message}>
                {job.error_message}
              </p>
            )}
          </div>
        </div>
      </td>
      <td className="px-6 py-4">
        <span 
          className="px-2 py-1 text-xs font-medium rounded-full"
          style={{ backgroundColor: config.bg, color: config.color }}
        >
          {config.label}
        </span>
      </td>
      <td className="px-6 py-4">
        <span className="text-sm" style={{ color: '#1e293b' }}>
          {job.total_paragraphs ?? '-'}
        </span>
      </td>
      <td className="px-6 py-4">
        <span className="text-sm" style={{ color: '#1e293b' }}>
          {job.total_tokens ? formatTokens(job.total_tokens) : '-'}
        </span>
      </td>
      <td className="px-6 py-4">
        {job.cost ? (
          <span className="text-sm font-medium" style={{ color: '#166534' }}>
            {formatCost(job.cost.total_cost)}
          </span>
        ) : (
          <span className="text-sm" style={{ color: '#94a3b8' }}>-</span>
        )}
      </td>
      <td className="px-6 py-4">
        <span className="text-sm" style={{ color: '#64748b' }}>
          {job.processing_time_seconds ? formatTime(job.processing_time_seconds) : '-'}
        </span>
      </td>
      <td className="px-6 py-4">
        <div className="flex items-center justify-end gap-1">
          {job.status === 'failed' && (
            <button
              onClick={onRetry}
              className="p-1.5 rounded-lg hover:bg-amber-50"
              title="Retry"
            >
              <RefreshCw className="h-4 w-4" style={{ color: '#d97706' }} />
            </button>
          )}
          {job.status === 'pending' && (
            <button
              onClick={onCancel}
              className="p-1.5 rounded-lg hover:bg-red-50"
              title="Cancel"
            >
              <XCircle className="h-4 w-4" style={{ color: '#dc2626' }} />
            </button>
          )}
          {job.status === 'completed' && job.output_path && (
            <a
              href={getDownloadUrl(batchId, 'processed', getFilename(job.output_path) || '')}
              className="p-1.5 rounded-lg hover:bg-emerald-50"
              title="Download"
            >
              <Download className="h-4 w-4" style={{ color: '#16a34a' }} />
            </a>
          )}
        </div>
      </td>
    </tr>
  );
}
