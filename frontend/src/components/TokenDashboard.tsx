import { Coins, TrendingUp, Zap, Calculator, Clock, AlertCircle, Brain } from 'lucide-react';
import { useTokenStats } from '../hooks/useQueue';

export function TokenDashboard() {
  const { data: stats, isLoading } = useTokenStats();
  
  if (isLoading || !stats) {
    return (
      <div className="bg-white rounded-xl border p-6 animate-pulse" style={{ borderColor: '#e5e2dc' }}>
        <div className="h-32 bg-gray-100 rounded-lg" />
      </div>
    );
  }
  
  const formatNumber = (num: number) => {
    if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(2)}M`;
    if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
    return num.toLocaleString();
  };
  
  const formatCost = (cost: number) => {
    if (cost < 0.01) return `$${cost.toFixed(6)}`;
    if (cost < 1) return `$${cost.toFixed(4)}`;
    return `$${cost.toFixed(2)}`;
  };
  
  // Calculate thinking tokens (total - input - output visible)
  // Note: In Gemini 2.5, output_tokens already includes thinking tokens from backend
  // So we show a note about this
  const isGemini25 = stats.pricing.model.includes('2.5');
  
  return (
    <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#e5e2dc' }}>
      {/* Header */}
      <div className="px-6 py-4 border-b flex items-center justify-between" style={{ borderColor: '#e5e2dc' }}>
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg" style={{ backgroundColor: '#fef3c7' }}>
            <Coins className="h-5 w-5" style={{ color: '#d97706' }} />
          </div>
          <div>
            <h3 className="font-semibold" style={{ color: '#1e293b' }}>Token Usage & Costs</h3>
            <p className="text-sm" style={{ color: '#64748b' }}>
              Model: {stats.pricing.model}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs" style={{ color: '#64748b' }}>Pricing</p>
          <p className="text-sm font-medium" style={{ color: '#334155' }}>
            ${stats.pricing.rates.input_per_million}/M input • ${stats.pricing.rates.output_per_million}/M output
          </p>
        </div>
      </div>
      
      {/* Thinking Tokens Info Banner (for Gemini 2.5) */}
      {isGemini25 && (
        <div className="px-6 py-3 flex items-center gap-3" style={{ backgroundColor: '#fef3c7' }}>
          <Brain className="h-4 w-4 flex-shrink-0" style={{ color: '#b45309' }} />
          <p className="text-sm" style={{ color: '#92400e' }}>
            <strong>Note:</strong> Gemini 2.5 includes "thinking tokens" for internal reasoning. 
            These are billed at output rates and included in the output token count below.
          </p>
        </div>
      )}
      
      {/* Stats Grid */}
      <div className="p-6">
        {/* All Time Stats */}
        <div className="mb-6">
          <h4 className="text-sm font-medium mb-3 flex items-center gap-2" style={{ color: '#64748b' }}>
            <TrendingUp className="h-4 w-4" />
            All Time
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="Total Tokens"
              value={formatNumber(stats.all_time.total_tokens)}
              subValue={`${formatNumber(stats.all_time.input_tokens)} in / ${formatNumber(stats.all_time.output_tokens)} out${isGemini25 ? '*' : ''}`}
              icon={<Zap className="h-4 w-4" />}
              color="slate"
            />
            <StatCard
              label="Total Cost"
              value={formatCost(stats.all_time.cost.total_cost)}
              subValue={`${formatCost(stats.all_time.cost.input_cost)} + ${formatCost(stats.all_time.cost.output_cost)}`}
              icon={<Coins className="h-4 w-4" />}
              color="amber"
            />
            <StatCard
              label="Jobs Processed"
              value={stats.all_time.total_jobs.toLocaleString()}
              subValue="completed"
              icon={<Calculator className="h-4 w-4" />}
              color="emerald"
            />
            <StatCard
              label="Avg Cost/Job"
              value={formatCost(stats.averages.cost_per_job)}
              subValue={`~${formatNumber(stats.averages.tokens_per_job)} tokens`}
              icon={<TrendingUp className="h-4 w-4" />}
              color="blue"
            />
          </div>
          {isGemini25 && (
            <p className="text-xs mt-2" style={{ color: '#94a3b8' }}>
              * Output tokens include thinking tokens (internal AI reasoning)
            </p>
          )}
        </div>
        
        {/* Today Stats */}
        <div>
          <h4 className="text-sm font-medium mb-3 flex items-center gap-2" style={{ color: '#64748b' }}>
            <Clock className="h-4 w-4" />
            Today
          </h4>
          <div className="grid grid-cols-3 gap-4">
            <MiniStatCard
              label="Tokens"
              value={formatNumber(stats.today.total_tokens)}
            />
            <MiniStatCard
              label="Input"
              value={formatNumber(stats.today.input_tokens)}
            />
            <MiniStatCard
              label="Cost"
              value={formatCost(stats.today.cost.total_cost)}
              highlight
            />
          </div>
        </div>
      </div>
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string;
  subValue?: string;
  icon: React.ReactNode;
  color: 'slate' | 'amber' | 'emerald' | 'blue';
}

function StatCard({ label, value, subValue, icon, color }: StatCardProps) {
  const colors = {
    slate: { bg: '#f8fafc', icon: '#64748b', text: '#334155' },
    amber: { bg: '#fffbeb', icon: '#d97706', text: '#b45309' },
    emerald: { bg: '#ecfdf5', icon: '#059669', text: '#047857' },
    blue: { bg: '#eff6ff', icon: '#2563eb', text: '#1d4ed8' },
  };
  
  const c = colors[color];
  
  return (
    <div className="rounded-xl p-4" style={{ backgroundColor: c.bg }}>
      <div className="flex items-center gap-2 mb-2">
        <div style={{ color: c.icon }}>{icon}</div>
        <span className="text-sm" style={{ color: '#64748b' }}>{label}</span>
      </div>
      <p className="text-2xl font-bold" style={{ color: c.text }}>{value}</p>
      {subValue && (
        <p className="text-xs mt-1" style={{ color: '#94a3b8' }}>{subValue}</p>
      )}
    </div>
  );
}

interface MiniStatCardProps {
  label: string;
  value: string;
  highlight?: boolean;
}

function MiniStatCard({ label, value, highlight }: MiniStatCardProps) {
  return (
    <div 
      className="rounded-lg p-3 text-center"
      style={{ backgroundColor: highlight ? '#fffbeb' : '#f8fafc' }}
    >
      <p className="text-xs mb-1" style={{ color: '#64748b' }}>{label}</p>
      <p 
        className="text-lg font-semibold" 
        style={{ color: highlight ? '#b45309' : '#334155' }}
      >
        {value}
      </p>
    </div>
  );
}
