import { useState } from 'react';
import {
  Settings,
  Zap,
  Database,
  Server,
  Info,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react';
import { useQueueStatus, useTokenStats } from '../hooks/useQueue';

export function SettingsPage() {
  const { data: queueStatus } = useQueueStatus();
  const { data: tokenStats } = useTokenStats();
  
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold" style={{ color: '#1e293b' }}>Settings</h1>
        <p className="text-sm mt-1" style={{ color: '#64748b' }}>
          System configuration and information
        </p>
      </div>
      
      {/* System Status */}
      <div className="bg-white rounded-xl border p-6" style={{ borderColor: '#e5e2dc' }}>
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 rounded-lg" style={{ backgroundColor: '#dcfce7' }}>
            <Server className="h-5 w-5" style={{ color: '#16a34a' }} />
          </div>
          <div>
            <h3 className="font-semibold" style={{ color: '#1e293b' }}>System Status</h3>
            <p className="text-sm" style={{ color: '#64748b' }}>Current system health and configuration</p>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <StatusItem
            label="Queue Mode"
            value={queueStatus?.queue_mode === 'celery' ? 'Celery + Redis' : 'Threading'}
            status="success"
          />
          <StatusItem
            label="Backend Status"
            value="Connected"
            status="success"
          />
          <StatusItem
            label="Queue Status"
            value={queueStatus?.is_processing ? 'Processing' : 'Idle'}
            status={queueStatus?.is_processing ? 'warning' : 'success'}
          />
          <StatusItem
            label="Pending Jobs"
            value={`${queueStatus?.pending ?? 0} jobs`}
            status={queueStatus?.pending && queueStatus.pending > 10 ? 'warning' : 'success'}
          />
        </div>
      </div>
      
      {/* AI Model Configuration */}
      <div className="bg-white rounded-xl border p-6" style={{ borderColor: '#e5e2dc' }}>
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 rounded-lg" style={{ backgroundColor: '#fef3c7' }}>
            <Zap className="h-5 w-5" style={{ color: '#d97706' }} />
          </div>
          <div>
            <h3 className="font-semibold" style={{ color: '#1e293b' }}>AI Model</h3>
            <p className="text-sm" style={{ color: '#64748b' }}>Current model configuration and pricing</p>
          </div>
        </div>
        
        {tokenStats && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-lg" style={{ backgroundColor: '#f8fafc' }}>
                <p className="text-sm" style={{ color: '#64748b' }}>Model Name</p>
                <p className="text-lg font-semibold mt-1" style={{ color: '#1e293b' }}>
                  {tokenStats.pricing.model}
                </p>
              </div>
              <div className="p-4 rounded-lg" style={{ backgroundColor: '#f8fafc' }}>
                <p className="text-sm" style={{ color: '#64748b' }}>Input Price</p>
                <p className="text-lg font-semibold mt-1" style={{ color: '#1e293b' }}>
                  ${tokenStats.pricing.rates.input_per_million}/1M
                </p>
              </div>
              <div className="p-4 rounded-lg" style={{ backgroundColor: '#f8fafc' }}>
                <p className="text-sm" style={{ color: '#64748b' }}>Output Price</p>
                <p className="text-lg font-semibold mt-1" style={{ color: '#1e293b' }}>
                  ${tokenStats.pricing.rates.output_per_million}/1M
                </p>
              </div>
            </div>
            
            <div className="p-4 rounded-lg border" style={{ backgroundColor: '#eff6ff', borderColor: '#bfdbfe' }}>
              <div className="flex gap-3">
                <Info className="h-5 w-5 flex-shrink-0" style={{ color: '#3b82f6' }} />
                <div className="text-sm" style={{ color: '#1e40af' }}>
                  <p className="font-medium">Pricing Note</p>
                  <p className="mt-1">
                    Costs are calculated based on actual token usage. The average cost per document 
                    is approximately ${tokenStats.averages.cost_per_job.toFixed(4)} based on your usage patterns.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* Database Info */}
      <div className="bg-white rounded-xl border p-6" style={{ borderColor: '#e5e2dc' }}>
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 rounded-lg" style={{ backgroundColor: '#f1f5f9' }}>
            <Database className="h-5 w-5" style={{ color: '#64748b' }} />
          </div>
          <div>
            <h3 className="font-semibold" style={{ color: '#1e293b' }}>Storage</h3>
            <p className="text-sm" style={{ color: '#64748b' }}>Database and file storage information</p>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-lg" style={{ backgroundColor: '#f8fafc' }}>
            <p className="text-sm" style={{ color: '#64748b' }}>Database Type</p>
            <p className="text-lg font-semibold mt-1" style={{ color: '#1e293b' }}>SQLite</p>
          </div>
          <div className="p-4 rounded-lg" style={{ backgroundColor: '#f8fafc' }}>
            <p className="text-sm" style={{ color: '#64748b' }}>Total Jobs Processed</p>
            <p className="text-lg font-semibold mt-1" style={{ color: '#1e293b' }}>
              {tokenStats?.all_time.total_jobs ?? 0}
            </p>
          </div>
        </div>
      </div>
      
      {/* About */}
      <div className="bg-white rounded-xl border p-6" style={{ borderColor: '#e5e2dc' }}>
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 rounded-lg" style={{ backgroundColor: '#f1f5f9' }}>
            <Info className="h-5 w-5" style={{ color: '#64748b' }} />
          </div>
          <div>
            <h3 className="font-semibold" style={{ color: '#1e293b' }}>About</h3>
            <p className="text-sm" style={{ color: '#64748b' }}>Application information</p>
          </div>
        </div>
        
        <div className="space-y-3">
          <div className="flex justify-between py-2 border-b" style={{ borderColor: '#f1f5f9' }}>
            <span style={{ color: '#64748b' }}>Application</span>
            <span className="font-medium" style={{ color: '#1e293b' }}>AI Structuring</span>
          </div>
          <div className="flex justify-between py-2 border-b" style={{ borderColor: '#f1f5f9' }}>
            <span style={{ color: '#64748b' }}>Version</span>
            <span className="font-medium" style={{ color: '#1e293b' }}>3.0.0</span>
          </div>
          <div className="flex justify-between py-2 border-b" style={{ borderColor: '#f1f5f9' }}>
            <span style={{ color: '#64748b' }}>Organization</span>
            <span className="font-medium" style={{ color: '#1e293b' }}>S4Carlisle Publishing</span>
          </div>
          <div className="flex justify-between py-2 border-b" style={{ borderColor: '#f1f5f9' }}>
            <span style={{ color: '#64748b' }}>Frontend</span>
            <span className="font-medium" style={{ color: '#1e293b' }}>React + TypeScript + Vite</span>
          </div>
          <div className="flex justify-between py-2 border-b" style={{ borderColor: '#f1f5f9' }}>
            <span style={{ color: '#64748b' }}>Backend</span>
            <span className="font-medium" style={{ color: '#1e293b' }}>Flask + SQLAlchemy</span>
          </div>
          <div className="flex justify-between py-2">
            <span style={{ color: '#64748b' }}>AI Provider</span>
            <span className="font-medium" style={{ color: '#1e293b' }}>Google Gemini</span>
          </div>
        </div>
      </div>
    </div>
  );
}

interface StatusItemProps {
  label: string;
  value: string;
  status: 'success' | 'warning' | 'error';
}

function StatusItem({ label, value, status }: StatusItemProps) {
  const statusConfig = {
    success: { bg: '#dcfce7', icon: CheckCircle, color: '#16a34a' },
    warning: { bg: '#fef3c7', icon: AlertTriangle, color: '#d97706' },
    error: { bg: '#fee2e2', icon: AlertTriangle, color: '#dc2626' },
  };
  
  const config = statusConfig[status];
  const Icon = config.icon;
  
  return (
    <div className="flex items-center justify-between p-4 rounded-lg" style={{ backgroundColor: '#f8fafc' }}>
      <div>
        <p className="text-sm" style={{ color: '#64748b' }}>{label}</p>
        <p className="font-medium mt-0.5" style={{ color: '#1e293b' }}>{value}</p>
      </div>
      <div className="p-2 rounded-full" style={{ backgroundColor: config.bg }}>
        <Icon className="h-4 w-4" style={{ color: config.color }} />
      </div>
    </div>
  );
}
