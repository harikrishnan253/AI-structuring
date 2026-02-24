import { Loader2, CheckCircle, XCircle, Clock, Zap } from 'lucide-react';
import { useQueueStatus } from '../hooks/useQueue';

export function QueueStatusBar() {
  const { data: status, isLoading } = useQueueStatus();
  
  if (isLoading || !status) {
    return (
      <div className="bg-white rounded-xl border p-6" style={{ borderColor: '#e5e2dc' }}>
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin" style={{ color: '#64748b' }} />
        </div>
      </div>
    );
  }
  
  return (
    <div className="bg-white rounded-xl border p-6" style={{ borderColor: '#e5e2dc' }}>
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg" style={{ backgroundColor: '#f1f5f9' }}>
            <Zap className="h-5 w-5" style={{ color: '#64748b' }} />
          </div>
          <div>
            <h3 className="font-semibold" style={{ color: '#1e293b' }}>Queue Status</h3>
            <p className="text-sm" style={{ color: '#64748b' }}>
              {status.total} total jobs
            </p>
          </div>
        </div>
        
        {status.is_processing && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full"
               style={{ backgroundColor: '#fef3c7' }}>
            <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            <span className="text-sm font-medium" style={{ color: '#b45309' }}>
              Processing
            </span>
          </div>
        )}
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatusCard
          icon={<Clock className="h-5 w-5" />}
          label="Pending"
          value={status.pending}
          bgColor="#f8fafc"
          iconColor="#64748b"
          textColor="#475569"
        />
        <StatusCard
          icon={<Loader2 className={`h-5 w-5 ${status.processing > 0 ? 'animate-spin' : ''}`} />}
          label="Processing"
          value={status.processing}
          bgColor="#fffbeb"
          iconColor="#d97706"
          textColor="#b45309"
          highlight={status.processing > 0}
        />
        <StatusCard
          icon={<CheckCircle className="h-5 w-5" />}
          label="Completed"
          value={status.completed}
          bgColor="#ecfdf5"
          iconColor="#059669"
          textColor="#047857"
        />
        <StatusCard
          icon={<XCircle className="h-5 w-5" />}
          label="Failed"
          value={status.failed}
          bgColor={status.failed > 0 ? '#fef2f2' : '#f8fafc'}
          iconColor={status.failed > 0 ? '#dc2626' : '#64748b'}
          textColor={status.failed > 0 ? '#b91c1c' : '#475569'}
        />
      </div>
    </div>
  );
}

interface StatusCardProps {
  icon: React.ReactNode;
  label: string;
  value: number;
  bgColor: string;
  iconColor: string;
  textColor: string;
  highlight?: boolean;
}

function StatusCard({ icon, label, value, bgColor, iconColor, textColor, highlight }: StatusCardProps) {
  return (
    <div 
      className={`rounded-xl p-4 transition-all duration-200 ${highlight ? 'animate-pulse-soft' : ''}`}
      style={{ backgroundColor: bgColor }}
    >
      <div className="flex items-center gap-3">
        <div style={{ color: iconColor }}>
          {icon}
        </div>
        <div>
          <p className="text-2xl font-bold" style={{ color: textColor }}>{value}</p>
          <p className="text-sm" style={{ color: '#64748b' }}>{label}</p>
        </div>
      </div>
    </div>
  );
}
