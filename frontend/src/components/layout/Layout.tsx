import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Upload,
  FolderOpen,
  BarChart3,
  Settings,
  Layers,
  Menu,
  X,
  ChevronRight,
  Activity,
} from 'lucide-react';
import { useQueueStatus } from '../../hooks/useQueue';

interface LayoutProps {
  children: React.ReactNode;
}

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Process Documents', href: '/upload', icon: Upload },
  { name: 'Batches', href: '/batches', icon: FolderOpen },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { data: queueStatus } = useQueueStatus();
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-50">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-slate-900/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      
      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-72 transform transition-transform duration-300 ease-in-out
        lg:translate-x-0 bg-gradient-to-b from-slate-900 via-slate-900 to-slate-800
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Logo */}
        <div className="h-20 flex items-center justify-between px-6 border-b border-slate-700/50">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg shadow-amber-500/20">
                <Layers className="h-5 w-5 text-white" />
              </div>
              <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-400 border-2 border-slate-900" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight">AI Structuring</h1>
              <p className="text-[11px] text-slate-400 font-medium tracking-wide uppercase">Document Intelligence</p>
            </div>
          </div>
          <button 
            className="lg:hidden p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        
        {/* Navigation */}
        <nav className="p-4 space-y-1.5">
          <p className="px-4 py-2 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Menu</p>
          {navigation.map((item) => {
            const isActive = location.pathname === item.href || 
              (item.href !== '/' && location.pathname.startsWith(item.href));
            return (
              <Link
                key={item.name}
                to={item.href}
                onClick={() => setSidebarOpen(false)}
                className={`
                  flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-all duration-200
                  ${isActive 
                    ? 'bg-gradient-to-r from-amber-500/20 to-orange-500/10 text-amber-400 shadow-lg shadow-amber-500/5' 
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'}
                `}
              >
                <item.icon className={`h-5 w-5 ${isActive ? 'text-amber-400' : ''}`} />
                <span>{item.name}</span>
                {item.name === 'Batches' && queueStatus && queueStatus.processing > 0 && (
                  <span className="ml-auto px-2.5 py-0.5 text-xs font-semibold rounded-full bg-amber-500/20 text-amber-400 animate-pulse">
                    {queueStatus.processing}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
        
        {/* Queue Status Card */}
        {queueStatus && (
          <div className="absolute bottom-0 left-0 right-0 p-4">
            <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-4 border border-slate-700/50">
              <div className="flex items-center gap-2 mb-4">
                <Activity className="h-4 w-4 text-slate-400" />
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Live Status</p>
                {queueStatus.is_processing && (
                  <span className="ml-auto flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                    <span className="text-xs text-amber-400 font-medium">Active</span>
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-slate-900/50 rounded-xl p-3 text-center">
                  <p className="text-2xl font-bold text-white">{queueStatus.pending}</p>
                  <p className="text-[10px] text-slate-500 font-medium uppercase tracking-wider mt-1">Queued</p>
                </div>
                <div className="bg-slate-900/50 rounded-xl p-3 text-center">
                  <p className="text-2xl font-bold text-amber-400">{queueStatus.processing}</p>
                  <p className="text-[10px] text-slate-500 font-medium uppercase tracking-wider mt-1">Processing</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </aside>
      
      {/* Main content */}
      <div className="lg:pl-72">
        {/* Top bar */}
        <header className="sticky top-0 z-30 h-16 bg-white/80 backdrop-blur-xl border-b border-slate-200/50 flex items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <button 
              className="lg:hidden p-2 rounded-xl hover:bg-slate-100 transition-colors"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="h-5 w-5 text-slate-600" />
            </button>
            
            {/* Breadcrumb */}
            <div className="flex items-center text-sm">
              <Link to="/" className="text-slate-400 hover:text-slate-600 transition-colors">Home</Link>
              {location.pathname !== '/' && (
                <>
                  <ChevronRight className="h-4 w-4 mx-2 text-slate-300" />
                  <span className="font-semibold text-slate-700">
                    {navigation.find(n => n.href === location.pathname)?.name || 
                     (location.pathname.startsWith('/batches/') ? 'Batch Details' : 'Page')}
                  </span>
                </>
              )}
            </div>
          </div>
          
          {/* Right side status */}
          <div className="flex items-center gap-3">
            {queueStatus?.is_processing && (
              <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200/50">
                <div className="relative">
                  <div className="w-2 h-2 rounded-full bg-amber-500" />
                  <div className="absolute inset-0 w-2 h-2 rounded-full bg-amber-500 animate-ping" />
                </div>
                <span className="text-sm font-semibold text-amber-700">Processing</span>
              </div>
            )}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100">
              <span className="text-xs font-medium text-slate-500">v3.0</span>
            </div>
          </div>
        </header>
        
        {/* Page content */}
        <main className="p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
