import React from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  Package,
  Layers,
  FileCheck2,
  AlertOctagon,
  Wrench,
  ShieldCheck,
  Cpu,
  Activity,
  Sparkles,
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  onNavigate: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onNavigate }) => {
  const { user } = useAuth();

  const navItems = [
    {
      id: 'dashboard',
      label: 'Quality Dashboard',
      icon: <LayoutDashboard className="w-4 h-4" />,
      allowed: true,
    },
    {
      id: 'products',
      label: 'Products Catalog',
      icon: <Package className="w-4 h-4" />,
      allowed: true,
    },
    {
      id: 'batches',
      label: 'Production Batches',
      icon: <Layers className="w-4 h-4" />,
      allowed: true,
    },
    {
      id: 'inspections',
      label: 'Inspections & AI',
      icon: <FileCheck2 className="w-4 h-4" />,
      allowed: true,
    },
    {
      id: 'defects',
      label: 'Defect Registry',
      icon: <AlertOctagon className="w-4 h-4" />,
      allowed: true,
    },
    {
      id: 'capa',
      label: 'CAPA & Remediation',
      icon: <Wrench className="w-4 h-4" />,
      allowed: true,
    },
    {
      id: 'release-gates',
      label: 'Batch Release Gates',
      icon: <ShieldCheck className="w-4 h-4" />,
      allowed: true,
      highlight: true,
    },
    {
      id: 'quality-intelligence',
      label: 'Quality Intelligence',
      icon: <Sparkles className="w-4 h-4 text-teal-400" />,
      allowed: Boolean(user && ['INSPECTOR', 'SUPERVISOR', 'QUALITY_MANAGER', 'ADMIN'].includes(user.role)),
      highlight: true,
    },
    {
      id: 'health',
      label: 'System Diagnostics',
      icon: <Activity className="w-4 h-4" />,
      allowed: true,
    },
  ];

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-925 flex flex-col justify-between flex-shrink-0">
      <div>
        {/* Brand Header */}
        <div className="h-16 flex items-center px-6 border-b border-slate-800">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-teal-500 to-emerald-400 p-0.5 shadow-md shadow-teal-500/20">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Cpu className="w-5 h-5 text-teal-400" />
              </div>
            </div>
            <div>
              <div className="font-extrabold text-base tracking-tight bg-gradient-to-r from-teal-200 to-white bg-clip-text text-transparent">
                CastTrace AI
              </div>
              <div className="text-[10px] text-slate-400 font-mono">PUMP IMPELLER QA</div>
            </div>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="p-4 space-y-1">
          {navItems
            .filter((item) => item.allowed)
            .map((item) => {
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer text-left ${
                    isActive
                      ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30 shadow-sm shadow-teal-950/40 font-semibold'
                      : item.highlight
                      ? 'text-slate-200 hover:bg-slate-800/80 hover:text-white border border-teal-500/10'
                      : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-100'
                  }`}
                >
                  <span className={isActive ? 'text-teal-400' : 'text-slate-400'}>{item.icon}</span>
                  <span className="flex-1">{item.label}</span>
                  {item.highlight && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-teal-500/20 text-teal-300 font-mono font-bold">
                      CORE
                    </span>
                  )}
                </button>
              );
            })}
        </nav>
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-800/80 bg-slate-950/40">
        <div className="text-[11px] text-slate-400 space-y-1 font-mono">
          <div className="flex justify-between">
            <span>ACTIVE ROLE:</span>
            <span className="text-teal-300 font-bold">{user?.role || 'AUTH'}</span>
          </div>
          <div className="flex justify-between">
            <span>ENGINE:</span>
            <span className="text-emerald-400">SQLite 3</span>
          </div>
          <div className="flex justify-between">
            <span>MODEL:</span>
            <span className="text-teal-300">ResNet-18</span>
          </div>
          <div className="flex justify-between">
            <span>GATE RULES:</span>
            <span className="text-teal-400 font-bold">Phase 4C Active</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
