import { formatDistanceToNow, format } from 'date-fns';
import { 
  Folder, 
  Trash2, 
  RefreshCw, 
  Download,
  ChevronRight,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  Archive
} from 'lucide-react';
import { useBatches, useDeleteBatch, useRetryBatchFailed } from '../hooks/useQueue';
import { getBatchZipUrl } from '../api/client';
import type { Batch, BatchStatus } from '../types';

// Format date to IST display
const formatToIST = (dateString: string | null) => {
  if (!dateString) return '';
  const date = new Date(dateString);
  // The backend sends IST timestamps, display them directly
  return formatDistanceToNow(date, { addSuffix: true });
};

const formatFullIST = (dateString: string | null) => {
  if (!dateString) return '';
  const date = new Date(dateString);
  return format(date, 'dd MMM yyyy, hh:mm a') + ' IST';
};

interface BatchListProps {
  onSelectBatch?: (batchId: string) => void;
  selectedBatchId?: string | null;
}

export function BatchList({ onSelectBatch, selectedBatchId }: BatchListProps) {
  const { data, isLoading } = useBatches();
  const deleteBatch = useDeleteBatch();
  const retryFailed = useRetryBatchFailed();
  
  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border p-8" style={{ borderColor: '#e5e2dc' }}>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin" style={{ color: '#64748b' }} />
        </div>
      </div>
    );
  }
  
  const batches = data?.batches ?? [];
  
  if (batches.length === 0) {
    return (
      <div className="bg-white rounded-xl border p-8 text-center" style={{ borderColor: '#e5e2dc' }}>
        <div className="w-14 h-14 mx-auto mb-4 rounded-full flex items-center justify-center"
             style={{ backgroundColor: '#f1f5f9' }}>
          <Archive className="h-6 w-6" style={{ color: '#94a3b8' }} />
        </div>
        <p className="font-medium" style={{ color: '#64748b' }}>No batches yet</p>
        <p className="text-sm mt-1" style={{ color: '#94a3b8' }}>
          Upload documents to create your first batch
        </p>
      </div>
    );
  }
  
  return (
    <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#e5e2dc' }}>
      <div className="px-5 py-4 border-b flex items-center gap-3" style={{ borderColor: '#e5e2dc' }}>
        <div className="p-2 rounded-lg" style={{ backgroundColor: '#f1f5f9' }}>
          <Folder className="h-4 w-4" style={{ color: '#64748b' }} />
        </div>
        <h3 className="font-semibold" style={{ color: '#1e293b' }}>Recent Batches</h3>
      </div>
      
      <div className="divide-y" style={{ borderColor: '#f1f5f9' }}>
        {batches.map(batch => (
          <BatchItem
            key={batch.batch_id}
            batch={batch}
            isSelected={batch.batch_id === selectedBatchId}
            onSelect={() => onSelectBatch?.(batch.batch_id)}
            onDelete={() => {
              if (confirm('Delete this batch and all its files?')) {
                deleteBatch.mutate(batch.batch_id);
              }
            }}
            onRetry={() => retryFailed.mutate(batch.batch_id)}
          />
        ))}
      </div>
    </div>
  );
}

interface BatchItemProps {
  batch: Batch;
  isSelected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRetry: () => void;
}

function BatchItem({ batch, isSelected, onSelect, onDelete, onRetry }: BatchItemProps) {
  const statusConfig = getStatusConfig(batch.status);
  
  return (
    <div
      className={`px-5 py-4 cursor-pointer transition-all duration-200 hover:bg-stone-50`}
      style={{ 
        backgroundColor: isSelected ? '#fffbeb' : undefined,
        borderLeft: isSelected ? '3px solid #d97706' : '3px solid transparent'
      }}
      onClick={onSelect}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <div className="p-2 rounded-lg flex-shrink-0" style={{ backgroundColor: statusConfig.bgColor }}>
            <statusConfig.icon 
              className={`h-4 w-4 ${statusConfig.animate ? 'animate-spin' : ''}`} 
              style={{ color: statusConfig.iconColor }} 
            />
          </div>
          <div className="min-w-0">
            <p className="font-medium truncate" style={{ color: '#1e293b' }}>{batch.name}</p>
            <p className="text-sm" style={{ color: '#64748b' }}>
              {batch.total_jobs} file{batch.total_jobs !== 1 ? 's' : ''}
              {batch.created_at && (
                <span title={formatFullIST(batch.created_at)}> • {formatToIST(batch.created_at)}</span>
              )}
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Progress */}
          {(batch.status === 'processing' || batch.status === 'pending') && (
            <div className="flex items-center gap-2">
              <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: '#e5e2dc' }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ 
                    width: `${batch.progress_percent}%`,
                    background: 'linear-gradient(90deg, #d97706 0%, #f59e0b 100%)'
                  }}
                />
              </div>
              <span className="text-xs font-medium" style={{ color: '#64748b' }}>
                {batch.progress_percent}%
              </span>
            </div>
          )}
          
          {batch.status === 'completed' && (
            <span className="text-sm" style={{ color: '#059669' }}>
              {batch.completed_jobs}/{batch.total_jobs}
            </span>
          )}
          
          {/* Actions */}
          <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
            {batch.failed_jobs > 0 && (
              <button
                onClick={onRetry}
                className="p-2 rounded-lg transition-colors hover:bg-amber-50"
                title="Retry failed jobs"
              >
                <RefreshCw className="h-4 w-4" style={{ color: '#d97706' }} />
              </button>
            )}
            
            {batch.status === 'completed' && (
              <a
                href={getBatchZipUrl(batch.batch_id)}
                className="p-2 rounded-lg transition-colors hover:bg-emerald-50"
                title="Download all"
              >
                <Download className="h-4 w-4" style={{ color: '#059669' }} />
              </a>
            )}
            
            <button
              onClick={onDelete}
              className="p-2 rounded-lg transition-colors hover:bg-red-50"
              title="Delete batch"
            >
              <Trash2 className="h-4 w-4" style={{ color: '#dc2626' }} />
            </button>
            
            <ChevronRight className="h-4 w-4 ml-1" style={{ color: '#94a3b8' }} />
          </div>
        </div>
      </div>
    </div>
  );
}

function getStatusConfig(status: BatchStatus) {
  switch (status) {
    case 'pending':
      return {
        icon: Clock,
        bgColor: '#f1f5f9',
        iconColor: '#64748b',
        animate: false,
      };
    case 'processing':
      return {
        icon: Loader2,
        bgColor: '#fef3c7',
        iconColor: '#d97706',
        animate: true,
      };
    case 'completed':
      return {
        icon: CheckCircle,
        bgColor: '#d1fae5',
        iconColor: '#059669',
        animate: false,
      };
    case 'completed_with_errors':
      return {
        icon: XCircle,
        bgColor: '#fee2e2',
        iconColor: '#dc2626',
        animate: false,
      };
    default:
      return {
        icon: Folder,
        bgColor: '#f1f5f9',
        iconColor: '#64748b',
        animate: false,
      };
  }
}
