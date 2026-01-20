import { useState } from 'react';
import {
  BarChart3,
  TrendingUp,
  Zap,
  Coins,
  Clock,
  Loader2,
  ArrowUp,
  ArrowDown,
  FileText,
  CheckCircle,
  XCircle,
  Download,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { useTokenStats, useDailyStats, useBatches } from '../hooks/useQueue';
import { getBatchZipUrl } from '../api/client';
import { format } from 'date-fns';
import { Link } from 'react-router-dom';

export function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState(30);
  const { data: tokenStats, isLoading: tokenLoading } = useTokenStats();
  const { data: dailyData, isLoading: dailyLoading } = useDailyStats(timeRange);
  const { data: batchesData, isLoading: batchesLoading } = useBatches(50);
  
  const formatNumber = (num: number) => {
    if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(2)}M`;
    if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
    return num.toLocaleString();
  };
  
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
  
  // Prepare chart data
  const chartData = dailyData?.daily_stats
    ?.slice()
    .reverse()
    .map(day => ({
      date: format(new Date(day.date), 'MMM d'),
      fullDate: day.date,
      tokens: day.total_tokens,
      input: day.input_tokens,
      output: day.output_tokens,
      cost: day.cost.total_cost,
      jobs: day.jobs_completed,
    })) ?? [];
  
  // Prepare batch analytics data
  const batches = batchesData?.batches ?? [];
  const completedBatches = batches.filter(b => b.status === 'completed' || b.completed_jobs > 0);
  
  // Calculate batch statistics
  const batchStats = completedBatches.map(batch => {
    const cost = batch.cost?.total_cost ?? 0;
    const tokens = batch.total_tokens ?? 0;
    const processingTime = batch.total_processing_time ?? 0;
    const avgTimePerDoc = batch.completed_jobs > 0 ? processingTime / batch.completed_jobs : 0;
    const costPerDoc = batch.completed_jobs > 0 ? cost / batch.completed_jobs : 0;
    const tokensPerDoc = batch.completed_jobs > 0 ? tokens / batch.completed_jobs : 0;
    
    return {
      ...batch,
      cost,
      tokens,
      processingTime,
      avgTimePerDoc,
      costPerDoc,
      tokensPerDoc,
    };
  });
  
  // Pie chart for status distribution
  const statusCounts = batches.reduce((acc, b) => {
    acc[b.status] = (acc[b.status] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  const statusPieData = [
    { name: 'Completed', value: statusCounts['completed'] || 0, color: '#22c55e' },
    { name: 'Processing', value: statusCounts['processing'] || 0, color: '#f59e0b' },
    { name: 'Pending', value: statusCounts['pending'] || 0, color: '#94a3b8' },
    { name: 'Failed', value: statusCounts['failed'] || 0, color: '#ef4444' },
  ].filter(d => d.value > 0);
  
  // Calculate trends
  const last7Days = chartData.slice(-7);
  const prev7Days = chartData.slice(-14, -7);
  
  const last7Total = last7Days.reduce((acc, d) => acc + d.tokens, 0);
  const prev7Total = prev7Days.reduce((acc, d) => acc + d.tokens, 0);
  const tokenTrend = prev7Total > 0 ? ((last7Total - prev7Total) / prev7Total) * 100 : 0;
  
  const last7Cost = last7Days.reduce((acc, d) => acc + d.cost, 0);
  const prev7Cost = prev7Days.reduce((acc, d) => acc + d.cost, 0);
  const costTrend = prev7Cost > 0 ? ((last7Cost - prev7Cost) / prev7Cost) * 100 : 0;
  
  const last7Jobs = last7Days.reduce((acc, d) => acc + d.jobs, 0);
  const prev7Jobs = prev7Days.reduce((acc, d) => acc + d.jobs, 0);
  const jobsTrend = prev7Jobs > 0 ? ((last7Jobs - prev7Jobs) / prev7Jobs) * 100 : 0;
  
  // Total stats from batches
  const totalBatches = batches.length;
  const totalDocs = batches.reduce((acc, b) => acc + b.total_jobs, 0);
  const totalProcessingTime = batchStats.reduce((acc, b) => acc + b.processingTime, 0);
  const avgProcessingTime = totalDocs > 0 ? totalProcessingTime / totalDocs : 0;
  
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: '#1e293b' }}>Analytics Dashboard</h1>
          <p className="text-sm mt-1" style={{ color: '#64748b' }}>
            Comprehensive insights into processing performance, costs, and usage
          </p>
        </div>
        
        {/* Time Range Selector */}
        <div className="flex items-center gap-2 bg-white rounded-lg border p-1" style={{ borderColor: '#e5e2dc' }}>
          {[7, 14, 30].map((days) => (
            <button
              key={days}
              onClick={() => setTimeRange(days)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                timeRange === days
                  ? 'bg-slate-900 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {days}D
            </button>
          ))}
        </div>
      </div>
      
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <OverviewCard
          title="Total Batches"
          value={totalBatches.toString()}
          subtitle={`${totalDocs} documents`}
          icon={<FileText className="h-5 w-5" />}
          color="slate"
          loading={batchesLoading}
        />
        <OverviewCard
          title="Total Tokens"
          value={formatNumber(tokenStats?.all_time.total_tokens ?? 0)}
          subtitle="All time"
          icon={<Zap className="h-5 w-5" />}
          color="amber"
          loading={tokenLoading}
        />
        <OverviewCard
          title="Total Cost"
          value={formatCost(tokenStats?.all_time.cost.total_cost ?? 0)}
          subtitle="All time"
          icon={<Coins className="h-5 w-5" />}
          color="green"
          loading={tokenLoading}
        />
        <OverviewCard
          title="Avg Time/Doc"
          value={formatTime(avgProcessingTime)}
          subtitle="Processing time"
          icon={<Clock className="h-5 w-5" />}
          color="blue"
          loading={batchesLoading}
        />
        <OverviewCard
          title="7-Day Documents"
          value={last7Jobs.toString()}
          subtitle={jobsTrend !== 0 ? `${jobsTrend > 0 ? '+' : ''}${jobsTrend.toFixed(1)}% vs prev` : 'No previous data'}
          icon={<TrendingUp className="h-5 w-5" />}
          color="purple"
          trend={jobsTrend}
          loading={dailyLoading}
        />
      </div>
      
      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Token Usage Chart */}
        <div className="lg:col-span-2 bg-white rounded-xl border p-6" style={{ borderColor: '#e5e2dc' }}>
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-semibold" style={{ color: '#1e293b' }}>Daily Processing Volume</h3>
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#3b82f6' }} />
                <span style={{ color: '#64748b' }}>Input Tokens</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#f59e0b' }} />
                <span style={{ color: '#64748b' }}>Output Tokens</span>
              </div>
            </div>
          </div>
          
          {dailyLoading ? (
            <div className="flex justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <BarChart3 className="h-12 w-12 mb-3" />
              <p>No data available</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="inputGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="outputGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e2dc" />
                <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 12 }} />
                <YAxis 
                  tickFormatter={(v) => formatNumber(v)} 
                  tick={{ fill: '#64748b', fontSize: 12 }}
                />
                <Tooltip
                  contentStyle={{ 
                    backgroundColor: '#fff', 
                    border: '1px solid #e5e2dc',
                    borderRadius: '8px',
                  }}
                  formatter={(value: number, name: string) => [
                    formatNumber(value), 
                    name === 'input' ? 'Input Tokens' : 'Output Tokens'
                  ]}
                />
                <Area 
                  type="monotone" 
                  dataKey="input" 
                  stroke="#3b82f6" 
                  fill="url(#inputGradient)" 
                  strokeWidth={2}
                />
                <Area 
                  type="monotone" 
                  dataKey="output" 
                  stroke="#f59e0b" 
                  fill="url(#outputGradient)" 
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
        
        {/* Batch Status Distribution */}
        <div className="bg-white rounded-xl border p-6" style={{ borderColor: '#e5e2dc' }}>
          <h3 className="font-semibold mb-6" style={{ color: '#1e293b' }}>Batch Status</h3>
          
          {batchesLoading ? (
            <div className="flex justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
            </div>
          ) : statusPieData.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <FileText className="h-12 w-12 mb-3" />
              <p>No batches yet</p>
            </div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={statusPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {statusPieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip 
                    formatter={(value: number, name: string) => [`${value} batches`, name]}
                    contentStyle={{ 
                      backgroundColor: '#fff', 
                      border: '1px solid #e5e2dc',
                      borderRadius: '8px',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              
              <div className="space-y-3 mt-4">
                {statusPieData.map((item) => (
                  <div key={item.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                      <span className="text-sm" style={{ color: '#64748b' }}>{item.name}</span>
                    </div>
                    <span className="text-sm font-medium" style={{ color: '#1e293b' }}>
                      {item.value}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
      
      {/* Daily Cost Chart */}
      <div className="bg-white rounded-xl border p-6" style={{ borderColor: '#e5e2dc' }}>
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-semibold" style={{ color: '#1e293b' }}>Daily Cost & Documents</h3>
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#22c55e' }} />
              <span style={{ color: '#64748b' }}>Cost ($)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#8b5cf6' }} />
              <span style={{ color: '#64748b' }}>Documents</span>
            </div>
          </div>
        </div>
        
        {dailyLoading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          </div>
        ) : chartData.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400">
            <Coins className="h-12 w-12 mb-3" />
            <p>No cost data available</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e2dc" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 12 }} />
              <YAxis 
                yAxisId="left"
                tickFormatter={(v) => `$${v.toFixed(2)}`} 
                tick={{ fill: '#64748b', fontSize: 12 }}
              />
              <YAxis 
                yAxisId="right"
                orientation="right"
                tick={{ fill: '#64748b', fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{ 
                  backgroundColor: '#fff', 
                  border: '1px solid #e5e2dc',
                  borderRadius: '8px',
                }}
                formatter={(value: number, name: string) => [
                  name === 'cost' ? `$${value.toFixed(4)}` : value,
                  name === 'cost' ? 'Cost' : 'Documents'
                ]}
              />
              <Bar yAxisId="left" dataKey="cost" fill="#22c55e" radius={[4, 4, 0, 0]} />
              <Bar yAxisId="right" dataKey="jobs" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
      
      {/* Batch-wise Analytics Table */}
      <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#e5e2dc' }}>
        <div className="px-6 py-4 border-b flex items-center justify-between" style={{ borderColor: '#e5e2dc' }}>
          <h3 className="font-semibold" style={{ color: '#1e293b' }}>Batch-wise Cost & Performance</h3>
          <span className="text-sm" style={{ color: '#64748b' }}>{batchStats.length} batches</span>
        </div>
        
        {batchesLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          </div>
        ) : batchStats.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <BarChart3 className="h-12 w-12 mb-3" />
            <p>No completed batches yet</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b" style={{ backgroundColor: '#f8fafc', borderColor: '#e5e2dc' }}>
                  <th className="text-left px-6 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                    Batch Name
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                    Status
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                    Docs
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                    Total Tokens
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                    Total Cost
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                    Total Time
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                    Cost/Doc
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                    Time/Doc
                  </th>
                  <th className="text-right px-6 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: '#f1f5f9' }}>
                {batchStats.map((batch) => (
                  <tr key={batch.batch_id} className="hover:bg-stone-50 transition-colors">
                    <td className="px-6 py-4">
                      <Link 
                        to={`/batches/${batch.batch_id}`}
                        className="font-medium hover:underline"
                        style={{ color: '#1e293b' }}
                      >
                        {batch.name || batch.batch_id.slice(0, 8)}
                      </Link>
                      <p className="text-xs" style={{ color: '#94a3b8' }}>
                        {batch.created_at ? format(new Date(batch.created_at), 'MMM d, h:mm a') : '-'}
                      </p>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <StatusBadge status={batch.status} />
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className="text-sm" style={{ color: '#1e293b' }}>
                        {batch.completed_jobs}/{batch.total_jobs}
                      </span>
                      {batch.failed_jobs > 0 && (
                        <span className="block text-xs" style={{ color: '#dc2626' }}>
                          {batch.failed_jobs} failed
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className="text-sm font-medium" style={{ color: '#d97706' }}>
                        {formatNumber(batch.tokens)}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className="text-sm font-medium" style={{ color: '#16a34a' }}>
                        {formatCost(batch.cost)}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className="text-sm" style={{ color: '#2563eb' }}>
                        {formatTime(batch.processingTime)}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className="text-sm" style={{ color: '#64748b' }}>
                        {formatCost(batch.costPerDoc)}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className="text-sm" style={{ color: '#64748b' }}>
                        {formatTime(batch.avgTimePerDoc)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      {batch.status === 'completed' && (
                        <a
                          href={getBatchZipUrl(batch.batch_id)}
                          className="p-1.5 rounded-lg hover:bg-emerald-50 inline-block"
                          title="Download"
                        >
                          <Download className="h-4 w-4" style={{ color: '#16a34a' }} />
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      
      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border p-5" style={{ borderColor: '#e5e2dc' }}>
          <p className="text-sm" style={{ color: '#64748b' }}>Avg Cost per Document</p>
          <p className="text-2xl font-bold mt-1" style={{ color: '#16a34a' }}>
            {formatCost(tokenStats?.averages.cost_per_job ?? 0)}
          </p>
        </div>
        <div className="bg-white rounded-xl border p-5" style={{ borderColor: '#e5e2dc' }}>
          <p className="text-sm" style={{ color: '#64748b' }}>Avg Tokens per Document</p>
          <p className="text-2xl font-bold mt-1" style={{ color: '#d97706' }}>
            {formatNumber(tokenStats?.averages.tokens_per_job ?? 0)}
          </p>
        </div>
        <div className="bg-white rounded-xl border p-5" style={{ borderColor: '#e5e2dc' }}>
          <p className="text-sm" style={{ color: '#64748b' }}>Success Rate</p>
          <p className="text-2xl font-bold mt-1" style={{ color: '#166534' }}>
            {totalDocs > 0 ? (
              (batches.reduce((acc, b) => acc + b.completed_jobs, 0) / totalDocs * 100).toFixed(1)
            ) : '0'}%
          </p>
        </div>
        <div className="bg-white rounded-xl border p-5" style={{ borderColor: '#e5e2dc' }}>
          <p className="text-sm" style={{ color: '#64748b' }}>Total Processing Time</p>
          <p className="text-2xl font-bold mt-1" style={{ color: '#2563eb' }}>
            {formatTime(totalProcessingTime)}
          </p>
        </div>
      </div>
      
      {/* Pricing Info */}
      {tokenStats && (
        <div className="bg-white rounded-xl border p-6" style={{ borderColor: '#e5e2dc' }}>
          <h3 className="font-semibold mb-4" style={{ color: '#1e293b' }}>Pricing Info ({tokenStats.pricing.model})</h3>
          
          {/* Thinking tokens note for Gemini 2.5 */}
          {tokenStats.pricing.model.includes('2.5') && (
            <div className="mb-4 p-3 rounded-lg flex items-start gap-3" style={{ backgroundColor: '#fef3c7' }}>
              <Zap className="h-5 w-5 mt-0.5 flex-shrink-0" style={{ color: '#b45309' }} />
              <div>
                <p className="text-sm font-medium" style={{ color: '#92400e' }}>Thinking Tokens Included</p>
                <p className="text-sm mt-1" style={{ color: '#a16207' }}>
                  Gemini 2.5 models use "thinking tokens" for internal reasoning. These are automatically 
                  included in the output token count and billed at output token rates. This ensures accurate 
                  cost tracking that matches your Google Cloud billing.
                </p>
              </div>
            </div>
          )}
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-4 rounded-lg" style={{ backgroundColor: '#f8fafc' }}>
              <p className="text-sm" style={{ color: '#64748b' }}>Input Rate</p>
              <p className="text-xl font-bold mt-1" style={{ color: '#1e293b' }}>
                ${tokenStats.pricing.rates.input_per_million}/1M tokens
              </p>
            </div>
            <div className="p-4 rounded-lg" style={{ backgroundColor: '#f8fafc' }}>
              <p className="text-sm" style={{ color: '#64748b' }}>Output Rate</p>
              <p className="text-xl font-bold mt-1" style={{ color: '#1e293b' }}>
                ${tokenStats.pricing.rates.output_per_million}/1M tokens
              </p>
              {tokenStats.pricing.model.includes('2.5') && (
                <p className="text-xs mt-1" style={{ color: '#94a3b8' }}>
                  (includes thinking tokens)
                </p>
              )}
            </div>
            <div className="p-4 rounded-lg" style={{ backgroundColor: '#fffbeb' }}>
              <p className="text-sm" style={{ color: '#64748b' }}>Today's Usage</p>
              <p className="text-xl font-bold mt-1" style={{ color: '#b45309' }}>
                {formatNumber(tokenStats.today.total_tokens)} tokens ({formatCost(tokenStats.today.cost.total_cost)})
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface OverviewCardProps {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ReactNode;
  color: 'amber' | 'green' | 'blue' | 'purple' | 'slate';
  trend?: number;
  loading?: boolean;
}

function OverviewCard({ title, value, subtitle, icon, color, trend, loading }: OverviewCardProps) {
  const colors = {
    amber: { bg: '#fffbeb', icon: '#d97706' },
    green: { bg: '#dcfce7', icon: '#16a34a' },
    blue: { bg: '#dbeafe', icon: '#2563eb' },
    purple: { bg: '#f3e8ff', icon: '#9333ea' },
    slate: { bg: '#f1f5f9', icon: '#475569' },
  };
  
  const c = colors[color];
  
  return (
    <div className="bg-white rounded-xl border p-5" style={{ borderColor: '#e5e2dc' }}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm" style={{ color: '#64748b' }}>{title}</p>
          {loading ? (
            <div className="h-8 w-24 bg-gray-100 rounded animate-pulse mt-2" />
          ) : (
            <p className="text-2xl font-bold mt-1" style={{ color: '#1e293b' }}>{value}</p>
          )}
          <div className="flex items-center gap-2 mt-1">
            {trend !== undefined && trend !== 0 && (
              <span className={`flex items-center text-xs font-medium ${trend > 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {trend > 0 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
                {Math.abs(trend).toFixed(1)}%
              </span>
            )}
            <span className="text-xs" style={{ color: '#94a3b8' }}>{subtitle}</span>
          </div>
        </div>
        <div className="p-3 rounded-xl" style={{ backgroundColor: c.bg }}>
          <div style={{ color: c.icon }}>{icon}</div>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const configs: Record<string, { bg: string; color: string; label: string }> = {
    completed: { bg: '#dcfce7', color: '#166534', label: 'Completed' },
    processing: { bg: '#fef3c7', color: '#b45309', label: 'Processing' },
    pending: { bg: '#f1f5f9', color: '#64748b', label: 'Pending' },
    failed: { bg: '#fee2e2', color: '#b91c1c', label: 'Failed' },
  };
  
  const config = configs[status] || configs.pending;
  
  return (
    <span 
      className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full"
      style={{ backgroundColor: config.bg, color: config.color }}
    >
      {status === 'completed' && <CheckCircle className="h-3 w-3" />}
      {status === 'failed' && <XCircle className="h-3 w-3" />}
      {status === 'processing' && <Loader2 className="h-3 w-3 animate-spin" />}
      {config.label}
    </span>
  );
}
