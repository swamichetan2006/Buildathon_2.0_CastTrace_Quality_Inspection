import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { LogOut, User as UserIcon, Shield, Sparkles } from 'lucide-react';

interface HeaderProps {
  currentTab: string;
  onNavigate?: (tab: string) => void;
}

export const Header: React.FC<HeaderProps> = ({ currentTab }) => {
  const { user, logout, login, isQualityManager, isSupervisor, isInspector } = useAuth();

  const handleRoleQuickSwitch = async (roleName: string) => {
    if (roleName === 'INSPECTOR') {
      await login('inspector_chen', 'Password123!');
    } else if (roleName === 'SUPERVISOR') {
      await login('supervisor_torres', 'Password123!');
    } else if (roleName === 'QUALITY_MANAGER') {
      await login('qm_reynolds', 'Password123!');
    }
  };

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40 px-6 flex items-center justify-between">
      {/* Breadcrumb / Title Context */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2 text-sm">
          <span className="text-slate-400">CastTrace AI</span>
          <span className="text-slate-600">/</span>
          <span className="text-white font-semibold capitalize">{currentTab.replace('-', ' ')}</span>
        </div>
      </div>

      {/* Right controls: Demo Persona Switcher & User Account */}
      <div className="flex items-center space-x-4">
        {/* Quick Demo Persona Switcher */}
        <div className="hidden lg:flex items-center bg-slate-950/70 border border-slate-800 rounded-xl p-1 space-x-1">
          <span className="text-[10px] uppercase font-bold text-slate-500 px-2 flex items-center space-x-1">
            <Sparkles className="w-3 h-3 text-teal-400" />
            <span>Switch Role:</span>
          </span>
          <button
            onClick={() => handleRoleQuickSwitch('INSPECTOR')}
            className={`px-2.5 py-1 text-xs rounded-lg transition-colors cursor-pointer font-medium ${
              isInspector ? 'bg-teal-500/20 text-teal-300 font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Inspector
          </button>
          <button
            onClick={() => handleRoleQuickSwitch('SUPERVISOR')}
            className={`px-2.5 py-1 text-xs rounded-lg transition-colors cursor-pointer font-medium ${
              isSupervisor ? 'bg-amber-500/20 text-amber-300 font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Supervisor
          </button>
          <button
            onClick={() => handleRoleQuickSwitch('QUALITY_MANAGER')}
            className={`px-2.5 py-1 text-xs rounded-lg transition-colors cursor-pointer font-medium ${
              isQualityManager ? 'bg-purple-500/20 text-purple-300 font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Quality Mgr
          </button>
        </div>

        {/* Current User Badge & Profile */}
        <div className="flex items-center space-x-3 border-l border-slate-800 pl-4">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-teal-400">
              <UserIcon className="w-4 h-4" />
            </div>
            <div className="text-left hidden sm:block">
              <div className="text-xs font-semibold text-white leading-tight">{user?.full_name || user?.username}</div>
              <div className="flex items-center space-x-1 mt-0.5">
                <Shield className="w-2.5 h-2.5 text-slate-400" />
                <span className="text-[10px] text-slate-400 font-mono tracking-wider">{user?.role}</span>
              </div>
            </div>
          </div>

          <button
            onClick={logout}
            title="Log Out"
            className="p-2 text-slate-400 hover:text-rose-400 hover:bg-slate-800/60 rounded-lg transition-colors cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};
