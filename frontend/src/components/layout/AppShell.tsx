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
    <div className="flex h-screen font-sans overflow-hidden" style={{ backgroundColor: '#F7F8F6', color: '#142033' }}>
      <Sidebar currentTab={active} onNavigate={handleNav} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header currentTab={active} onNavigate={handleNav} />
        <main
          className="flex-1 overflow-y-auto"
          style={{ backgroundColor: '#F7F8F6', padding: '28px 32px' }}
        >
          <div className="max-w-7xl mx-auto w-full">{children}</div>
        </main>
      </div>
    </div>
  );
};

export default AppShell;
