import React from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

interface AppShellProps {
  currentTab?: string;
  activeTab?: string;
  onNavigate?: (tab: string) => void;
  onTabChange?: (tab: string) => void;
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({
  currentTab,
  activeTab,
  onNavigate,
  onTabChange,
  children,
}) => {
  const active = currentTab || activeTab || 'dashboard';
  const handleNav = onNavigate || onTabChange || (() => {});

  return (
    <div className="flex h-screen bg-[#070b14] text-slate-100 font-sans overflow-hidden">
      <Sidebar currentTab={active} onNavigate={handleNav} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header currentTab={active} onNavigate={handleNav} />
        <main className="flex-1 overflow-y-auto p-6 md:p-8 space-y-8 bg-[#070b14]">
          <div className="max-w-7xl mx-auto w-full">{children}</div>
        </main>
      </div>
    </div>
  );
};

export default AppShell;
