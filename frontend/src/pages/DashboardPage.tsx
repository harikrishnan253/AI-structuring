import { Link } from 'react-router-dom';
import {
  Upload,
  FolderOpen,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  Zap,
  Coins,
  TrendingUp,
  ArrowUpRight,
  FileText,
  Sparkles,
  BarChart3,
} from 'lucide-react';
import { useQueueStatus, useTokenStats, useBatches } from '../hooks/useQueue';
import { formatDistanceToNow } from 'date-fns';

export function DashboardPage() {
  const { data: queueStatus, isLoading: queueLoading } = useQueueStatus();
  const { data: tokenStats, isLoading: tokenLoading } = useTokenStats();
  const { data: batchesData, isLoading: batchesLoading } = useBatches(5);
  
  const formatNumber = (num: number) => {
    if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(2)}M`;
    if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
    return num.toLocaleString();
  };
  
  const formatCost = (cost: number) => {
    if (cost < 0.01) return `$${cost.toFixed(4)}`;
    return `$${cost.toFixed(2)}`;
  };
  
  return (
    <div className="space-y-8">
      {/* Welcome Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-amber-500/10 rounded-full blur-3xl" />
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-xl bg-amber-500/20">
              <Sparkles className="h-6 w-6 text-amber-400" />
            </div>
            <span className="px-3 py-1 text-xs font-semibold rounded-full bg-amber-500/20 text-amber-400 uppercase tracking-wider">
              AI-Powered
            </span>
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">
            Welcome to AI Structuring
          </h1>
          <p className="text-slate-400 max-w-xl mb-6">
            Intelligent document analysis and structural tagging powered by advanced AI. 
            Process academic papers, medical textbooks, and research documents with precision.
          </p>
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-slate-900 transition-all
                     bg-gradient-to-r from-amber-400 to-orange-400 hover:from-amber-300 hover:to-orange-300
                     shadow-lg shadow-amber-500/25 hover:shadow-amber-500/40"
          >
            <Upload className="h-5 w-5" />
            Process New Documents
          </Link>
        </div>
      </div>
      
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          title="In Queue"
          value={queueStatus?.pending ?? 0}
          subtitle="Waiting to process"
          icon={<Clock className="h-5 w-5" />}
          gradient="from-slate-500 to-slate-600"
          loading={queueLoading}
        />
        <StatCard
          title="Processing"
          value={queueStatus?.processing ?? 0}
          subtitle="Currently active"
          icon={<Loader2 className={`h-5 w-5 ${queueStatus?.processing ? 'animate-spin' : ''}`} />}
          gradient="from-amber-500 to-orange-500"
          loading={queueLoading}
          highlight={queueStatus?.processing ? true : false}
        />
        <StatCard
          title="Completed"
          value={queueStatus?.completed ?? 0}
          subtitle="Successfully processed"
          icon={<CheckCircle className="h-5 w-5" />}
          gradient="from-emerald-500 to-teal-500"
          loading={queueLoading}
        />
        <StatCard
          title="Failed"
          value={queueStatus?.failed ?? 0}
          subtitle="Requires attention"
          icon={<XCircle className="h-5 w-5" />}
          gradient="from-red-500 to-rose-500"
          loading={queueLoading}
        />
      </div>
      
      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Token Usage Card */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200/60 shadow-sm shadow-slate-200/50 overflow-hidden">
          <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-gradient-to-br from-amber-100 to-orange-100">
                <Zap className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-800">Token Consumption</h3>
                <p className="text-sm text-slate-500">AI processing metrics</p>
              </div>
            </div>
            <Link 
              to="/analytics" 
              className="flex items-center gap-1.5 text-sm font-medium text-amber-600 hover:text-amber-700 transition-colors"
            >
              View Analytics <ArrowUpRight className="h-4 w-4" />
            </Link>
          </div>
          
          <div className="p-6">
            {tokenLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-slate-300" />
              </div>
            ) : tokenStats ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricBox
                  label="Total Tokens"
                  value={formatNumber(tokenStats.all_time.total_tokens)}
                  sublabel="All time"
                />
                <MetricBox
                  label="Input"
                  value={formatNumber(tokenStats.all_time.input_tokens)}
                  sublabel="Prompt tokens"
                />
                <MetricBox
                  label="Output"
                  value={formatNumber(tokenStats.all_time.output_tokens)}
                  sublabel="Response tokens"
                />
                <MetricBox
                  label="Documents"
                  value={tokenStats.all_time.total_jobs.toString()}
                  sublabel="Processed"
                  highlight
                />
              </div>
            ) : null}
          </div>
        </div>
        
        {/* Cost Summary Card */}
        <div className="bg-white rounded-2xl border border-slate-200/60 shadow-sm shadow-slate-200/50 overflow-hidden">
          <div className="px-6 py-5 border-b border-slate-100">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-gradient-to-br from-emerald-100 to-teal-100">
                <Coins className="h-5 w-5 text-emerald-600" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-800">Cost Overview</h3>
                <p className="text-sm text-slate-500">{tokenStats?.pricing.model || 'Loading...'}</p>
              </div>
            </div>
          </div>
          
          <div className="p-6">
            {tokenLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-slate-300" />
              </div>
            ) : tokenStats ? (
              <div className="space-y-6">
                <div className="text-center py-4">
                  <p className="text-sm font-medium text-slate-500 mb-1">Total Spent</p>
                  <p className="text-4xl font-bold text-emerald-600">
                    {formatCost(tokenStats.all_time.cost.total_cost)}
                  </p>
                </div>
                
                <div className="space-y-3">
                  <div className="flex justify-between items-center py-2 border-t border-slate-100">
                    <span className="text-sm text-slate-500">Avg per document</span>
                    <span className="font-semibold text-slate-800">
                      {formatCost(tokenStats.averages.cost_per_job)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-2 border-t border-slate-100">
                    <span className="text-sm text-slate-500">Today</span>
                    <span className="font-semibold text-amber-600">
                      {formatCost(tokenStats.today.cost.total_cost)}
                    </span>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
      
      {/* Recent Batches */}
      <div className="bg-white rounded-2xl border border-slate-200/60 shadow-sm shadow-slate-200/50 overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-slate-100 to-slate-200">
              <FolderOpen className="h-5 w-5 text-slate-600" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-800">Recent Batches</h3>
              <p className="text-sm text-slate-500">Latest processing jobs</p>
            </div>
          </div>
          <Link 
            to="/batches" 
            className="flex items-center gap-1.5 text-sm font-medium text-amber-600 hover:text-amber-700 transition-colors"
          >
            View All <ArrowUpRight className="h-4 w-4" />
          </Link>
        </div>
        
        {batchesLoading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-slate-300" />
          </div>
        ) : batchesData?.batches && batchesData.batches.length > 0 ? (
          <div className="divide-y divide-slate-100">
            {batchesData.batches.slice(0, 5).map((batch) => (
              <Link
                key={batch.batch_id}
                to={`/batches/${batch.batch_id}`}
                className="flex items-center justify-between px-6 py-4 hover:bg-slate-50 transition-colors group"
              >
                <div className="flex items-center gap-4">
                  <div className={`p-2.5 rounded-xl transition-colors ${
                    batch.status === 'completed' ? 'bg-emerald-100 group-hover:bg-emerald-200' :
                    batch.status === 'processing' ? 'bg-amber-100 group-hover:bg-amber-200' :
                    batch.status === 'completed_with_errors' ? 'bg-red-100 group-hover:bg-red-200' :
                    'bg-slate-100 group-hover:bg-slate-200'
                  }`}>
                    <FileText className={`h-5 w-5 ${
                      batch.status === 'completed' ? 'text-emerald-600' :
                      batch.status === 'processing' ? 'text-amber-600' :
                      batch.status === 'completed_with_errors' ? 'text-red-600' :
                      'text-slate-600'
                    }`} />
                  </div>
                  <div>
                    <p className="font-medium text-slate-800 group-hover:text-slate-900">{batch.name}</p>
                    <p className="text-sm text-slate-500">
                      {batch.total_jobs} files • {batch.created_at && formatDistanceToNow(new Date(batch.created_at), { addSuffix: true })}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <p className="font-semibold text-slate-800">
                      {batch.completed_jobs}/{batch.total_jobs}
                    </p>
                    <p className="text-xs text-slate-500">completed</p>
                  </div>
                  {batch.cost && (
                    <div className="text-right min-w-[60px]">
                      <p className="font-semibold text-emerald-600">
                        {formatCost(batch.cost.total_cost)}
                      </p>
                      <p className="text-xs text-slate-500">cost</p>
                    </div>
                  )}
                  <ArrowUpRight className="h-4 w-4 text-slate-400 group-hover:text-amber-500 transition-colors" />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="py-16 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-slate-100 flex items-center justify-center">
              <FolderOpen className="h-8 w-8 text-slate-400" />
            </div>
            <p className="font-medium text-slate-600 mb-1">No batches yet</p>
            <p className="text-sm text-slate-500 mb-4">Get started by uploading your first documents</p>
            <Link 
              to="/upload" 
              className="inline-flex items-center gap-2 text-sm font-medium text-amber-600 hover:text-amber-700"
            >
              <Upload className="h-4 w-4" />
              Upload Documents
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: number;
  subtitle: string;
  icon: React.ReactNode;
  gradient: string;
  loading?: boolean;
  highlight?: boolean;
}

function StatCard({ title, value, subtitle, icon, gradient, loading, highlight }: StatCardProps) {
  return (
    <div className={`relative overflow-hidden rounded-2xl bg-white border border-slate-200/60 shadow-sm p-5 ${highlight ? 'ring-2 ring-amber-400 ring-offset-2' : ''}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          {loading ? (
            <div className="h-10 w-20 bg-slate-100 rounded-lg animate-pulse mt-2" />
          ) : (
            <p className="text-3xl font-bold text-slate-800 mt-1">{value}</p>
          )}
          <p className="text-xs text-slate-400 mt-1">{subtitle}</p>
        </div>
        <div className={`p-3 rounded-xl bg-gradient-to-br ${gradient} shadow-lg`}>
          <div className="text-white">{icon}</div>
        </div>
      </div>
      {highlight && (
        <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-amber-400 to-orange-400" />
      )}
    </div>
  );
}

interface MetricBoxProps {
  label: string;
  value: string;
  sublabel: string;
  highlight?: boolean;
}

function MetricBox({ label, value, sublabel, highlight }: MetricBoxProps) {
  return (
    <div className={`p-4 rounded-xl ${highlight ? 'bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-200/50' : 'bg-slate-50'}`}>
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${highlight ? 'text-emerald-600' : 'text-slate-800'}`}>{value}</p>
      <p className="text-xs text-slate-400 mt-0.5">{sublabel}</p>
    </div>
  );
}
