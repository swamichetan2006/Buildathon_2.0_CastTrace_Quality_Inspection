import React from 'react';
import {
  LayoutDashboard,
  Package,
  Layers,
  FileCheck2,
  AlertOctagon,
  Wrench,
  ShieldCheck,
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  onNavigate: (tab: string) => void;
}

/* Warm-yellow "C" brand mark — same as login page */
const CastTraceMark: React.FC<{ size?: number }> = ({ size = 30 }) => (
  <svg width={size} height={size} viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <rect width="36" height="36" rx="9" fill="#FBBF24" />
    <path d="M24.5 13.25C23.1 11.25 20.7 10 18 10C13.58 10 10 13.58 10 18C10 22.42 13.58 26 18 26C20.7 26 23.1 24.75 24.5 22.75"
      stroke="#101216" strokeWidth="2.8" strokeLinecap="round" />
  </svg>
);

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onNavigate }) => {

  const navItems = [
    { id: 'dashboard',     label: 'Dashboard',           icon: <LayoutDashboard className="w-4 h-4" />, allowed: true },
    { id: 'products',      label: 'Products Catalog',    icon: <Package className="w-4 h-4" />,         allowed: true },
    { id: 'batches',       label: 'Production Batches',  icon: <Layers className="w-4 h-4" />,          allowed: true },
    { id: 'inspections',   label: 'Inspections & AI',    icon: <FileCheck2 className="w-4 h-4" />,      allowed: true },
    { id: 'defects',       label: 'Defect Registry',     icon: <AlertOctagon className="w-4 h-4" />,    allowed: true },
    { id: 'capa',          label: 'CAPA & Remediation',  icon: <Wrench className="w-4 h-4" />,          allowed: true },
    { id: 'release-gates', label: 'Batch Release Gates', icon: <ShieldCheck className="w-4 h-4" />,     allowed: true },
  ];

  return (
    <aside
      className="flex flex-col flex-shrink-0"
      style={{
        width: 240,
        backgroundColor: '#FFFFFF',
        borderRight: '1px solid #E7EAE8',
      }}
    >
      {/* Brand */}
      <div
        style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          padding: '0 20px',
          borderBottom: '1px solid #E7EAE8',
          gap: 10,
        }}
      >
        <CastTraceMark size={30} />
        <div>
          <div style={{
            fontFamily: "'Manrope', sans-serif",
            fontWeight: 700,
            fontSize: 15,
            color: '#142033',
            letterSpacing: '-0.01em',
            lineHeight: 1.2,
          }}>
            CastTrace AI
          </div>
          <div style={{
            fontSize: 9,
            color: '#8A96A8',
            fontFamily: "'DM Sans', sans-serif",
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            fontWeight: 500,
          }}>
            Pump Impeller QA
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, padding: '12px 12px', overflowY: 'auto' }}>
        {navItems.filter(i => i.allowed).map(item => {
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '9px 12px',
                borderRadius: 8,
                border: 'none',
                cursor: 'pointer',
                textAlign: 'left',
                marginBottom: 2,
                transition: 'background 0.15s, color 0.15s',
                backgroundColor: isActive ? '#FFF7E3' : 'transparent',
                color: isActive ? '#B77900' : '#64748B',
                fontFamily: "'DM Sans', sans-serif",
                fontSize: 13,
                fontWeight: isActive ? 600 : 400,
                position: 'relative',
              }}
              onMouseEnter={e => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = '#F7F8F6';
                  e.currentTarget.style.color = '#142033';
                }
              }}
              onMouseLeave={e => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = '#64748B';
                }
              }}
            >
              {/* Active indicator strip */}
              {isActive && (
                <span style={{
                  position: 'absolute',
                  left: 0,
                  top: '20%',
                  bottom: '20%',
                  width: 3,
                  borderRadius: 2,
                  backgroundColor: '#FBBF24',
                }} />
              )}
              <span style={{
                color: isActive ? '#B77900' : '#8A96A8',
                display: 'flex',
                flexShrink: 0,
              }}>
                {item.icon}
              </span>
              <span style={{ flex: 1 }}>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
};

export default Sidebar;
