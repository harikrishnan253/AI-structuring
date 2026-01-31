import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import {
  FolderOpen,
  Search,
  Filter,
  Trash2,
  RefreshCw,
  Download,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  ChevronRight,
  FileText,
  Coins,
} from 'lucide-react';
import { useBatches, useDeleteBatch, useRetryBatchFailed } from '../hooks/useQueue';
import { getBatchZipUrl } from '../api/client';
import type { Batch, BatchStatus } from '../types';

export function BatchesPage() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<BatchStatus | 'all'>('all');
  
  const { data, isLoading } = useBatches(100);
  const deleteBatch = useDeleteBatch();
  const retryFailed = useRetryBatchFailed();
  
  const batches = data?.batches ?? [];
  
  const filteredBatches = batches.filter(batch => {
    const matchesSearch = !searchQuery || 
      batch.name?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || batch.status === statusFilter;
    return matchesSearch && matchesStatus;
  });
  
  const formatCost = (cost: number) => {
    if (cost < 0.01) return `$${cost.toFixed(4)}`;
    return `$${cost.toFixed(2)}`;
  };
  
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
  
  const getStatusBadge = (status: BatchStatus) => {
    switch (status) {
      case 'completed':
        return { bg: '#dcfce7', text: '#166534', label: 'Completed' };
      case 'processing':
        return { bg: '#fef3c7', text: '#b45309', label: 'Processing' };
      case 'pending':
        return { bg: '#f1f5f9', text: '#475569', label: 'Pending' };
      case 'completed_with_errors':
        return { bg: '#fee2e2', text: '#b91c1c', label: 'Has Errors' };
      default:
        return { bg: '#f1f5f9', text: '#475569', label: status };
    }
  };
  
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: '#1e293b' }}>Batches</h1>
          <p className="text-sm mt-1" style={{ color: '#64748b' }}>
            {batches.length} total batches
          </p>
        </div>
        <Link
          to="/upload"
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-white transition-all"
          style={{ 
            background: 'linear-gradient(135deg, #d97706 0%, #f59e0b 100%)',
            boxShadow: '0 2px 8px rgba(217, 119, 6, 0.3)'
          }}
        >
          New Batch
        </Link>
      </div>
      
      {/* Filters */}
      <div className="bg-white rounded-xl border p-4" style={{ borderColor: '#e5e2dc' }}>
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search batches..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-lg border focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
              style={{ borderColor: '#e5e2dc' }}
            />
          </div>
          
          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <Filter className="h-5 w-5 text-gray-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as BatchStatus | 'all')}
              className="px-4 py-2.5 rounded-lg border focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
              style={{ borderColor: '#e5e2dc' }}
            >
              <option value="all">All Status</option>
              <option value="pending">Pending</option>
              <option value="processing">Processing</option>
              <option value="completed">Completed</option>
              <option value="completed_with_errors">Has Errors</option>
            </select>
          </div>
        </div>
      </div>
      
      {/* Batch List */}
      <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#e5e2dc' }}>
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          </div>
        ) : filteredBatches.length === 0 ? (
          <div className="py-16 text-center">
            <FolderOpen className="h-12 w-12 mx-auto mb-3 text-gray-300" />
            <p className="font-medium" style={{ color: '#64748b' }}>
              {searchQuery || statusFilter !== 'all' ? 'No matching batches' : 'No batches yet'}
            </p>
            <Link to="/upload" className="text-sm mt-1 hover:underline" style={{ color: '#d97706' }}>
              Create your first batch
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b" style={{ backgroundColor: '#f8fafc', borderColor: '#e5e2dc' }}>
                  <th className="text-left px-6 py-4 text-sm font-semibold" style={{ color: '#475569' }}>
                    Batch Name
                  </th>
                  <th className="text-left px-6 py-4 text-sm font-semibold" style={{ color: '#475569' }}>
                    Status
                  </th>
                  <th className="text-left px-6 py-4 text-sm font-semibold" style={{ color: '#475569' }}>
                    Progress
                  </th>
                  <th className="text-left px-6 py-4 text-sm font-semibold" style={{ color: '#475569' }}>
                    Tokens
                  </th>
                  <th className="text-left px-6 py-4 text-sm font-semibold" style={{ color: '#475569' }}>
                    Cost
                  </th>
                  <th className="text-left px-6 py-4 text-sm font-semibold" style={{ color: '#475569' }}>
                    Created
                  </th>
                  <th className="text-right px-6 py-4 text-sm font-semibold" style={{ color: '#475569' }}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: '#f1f5f9' }}>
                {filteredBatches.map((batch) => {
                  const status = getStatusBadge(batch.status);
                  return (
                    <tr 
                      key={batch.batch_id}
                      className="hover:bg-stone-50 cursor-pointer transition-colors"
                      onClick={() => navigate(`/batches/${batch.batch_id}`)}
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-lg bg-slate-100">
                            <FileText className="h-4 w-4 text-slate-600" />
                          </div>
                          <div>
                            <p className="font-medium" style={{ color: '#1e293b' }}>{batch.name}</p>
                            <p className="text-sm" style={{ color: '#64748b' }}>{batch.document_type}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span 
                          className="px-2.5 py-1 text-xs font-semibold rounded-full"
                          style={{ backgroundColor: status.bg, color: status.text }}
                        >
                          {status.label}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-24 h-2 rounded-full overflow-hidden" style={{ backgroundColor: '#e5e2dc' }}>
                            <div
                              className="h-full rounded-full transition-all"
                              style={{ 
                                width: `${batch.progress_percent}%`,
                                backgroundColor: batch.failed_jobs > 0 ? '#ef4444' : '#22c55e'
                              }}
                            />
                          </div>
                          <span className="text-sm" style={{ color: '#64748b' }}>
                            {batch.completed_jobs}/{batch.total_jobs}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-sm font-medium" style={{ color: '#1e293b' }}>
                          {batch.total_tokens ? (batch.total_tokens / 1000).toFixed(1) + 'K' : '-'}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {batch.cost ? (
                          <span className="text-sm font-medium" style={{ color: '#16a34a' }}>
                            {formatCost(batch.cost.total_cost)}
                          </span>
                        ) : (
                          <span className="text-sm" style={{ color: '#94a3b8' }}>-</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-sm" style={{ color: '#64748b' }}>
                          {batch.created_at && formatDistanceToNow(new Date(batch.created_at), { addSuffix: true })}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center justify-end gap-1" onClick={e => e.stopPropagation()}>
                          {batch.failed_jobs > 0 && (
                            <button
                              onClick={() => retryFailed.mutate(batch.batch_id)}
                              className="p-2 rounded-lg hover:bg-amber-50"
                              title="Retry failed"
                            >
                              <RefreshCw className="h-4 w-4" style={{ color: '#d97706' }} />
                            </button>
                          )}
                          {batch.status === 'completed' && (
                            <a
                              href={getBatchZipUrl(batch.batch_id)}
                              className="p-2 rounded-lg hover:bg-emerald-50"
                              title="Download all"
                            >
                              <Download className="h-4 w-4" style={{ color: '#16a34a' }} />
                            </a>
                          )}
                          <button
                            onClick={() => {
                              if (confirm('Delete this batch?')) {
                                deleteBatch.mutate(batch.batch_id);
                              }
                            }}
                            className="p-2 rounded-lg hover:bg-red-50"
                            title="Delete"
                          >
                            <Trash2 className="h-4 w-4" style={{ color: '#dc2626' }} />
                          </button>
                          <ChevronRight className="h-4 w-4 ml-1" style={{ color: '#94a3b8' }} />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
