import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { LogOut, Bell, Search, ChevronDown } from 'lucide-react';

interface HeaderProps {
  currentTab: string;
  onNavigate?: (tab: string) => void;
}

const TAB_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  products: 'Products Catalog',
  batches: 'Production Batches',
  inspections: 'Inspections & AI',
  defects: 'Defect Registry',
  capa: 'CAPA & Remediation',
  'release-gates': 'Batch Release Gates',
};

/* Role-specific colors */
const ROLE_COLOR: Record<string, string> = {
  INSPECTOR: '#2563EB',
  SUPERVISOR: '#D97706',
  QUALITY_MANAGER: '#6D28D9',
  ADMIN: '#6D28D9',
};
const ROLE_BG: Record<string, string> = {
  INSPECTOR: '#EFF6FF',
  SUPERVISOR: '#FFFBEB',
  QUALITY_MANAGER: '#F5F3FF',
  ADMIN: '#F5F3FF',
};

export const Header: React.FC<HeaderProps> = ({ currentTab }) => {
  const { user, logout, login, isQualityManager, isSupervisor, isInspector } = useAuth();

  const handleRoleQuickSwitch = async (roleName: string) => {
    if (roleName === 'INSPECTOR') await login('inspector_chen', 'Password123!');
    else if (roleName === 'SUPERVISOR') await login('supervisor_torres', 'Password123!');
    else if (roleName === 'QUALITY_MANAGER') await login('qm_reynolds', 'Password123!');
  };

  const displayName = user?.full_name || user?.username || '';
  const initials = displayName
    .split(' ')
    .map(n => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const roleColor = ROLE_COLOR[user?.role || ''] || '#64748B';
  const roleBg = ROLE_BG[user?.role || ''] || '#F7F8F6';

  const roleLabel =
    user?.role === 'INSPECTOR' ? 'Inspector' :
    user?.role === 'SUPERVISOR' ? 'Supervisor' :
    user?.role === 'QUALITY_MANAGER' ? 'Quality Manager' :
    user?.role || '';

  return (
    <header
      style={{
        height: 64,
        backgroundColor: '#FFFFFF',
        borderBottom: '1px solid #E7EAE8',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 28px',
        position: 'sticky',
        top: 0,
        zIndex: 40,
        gap: 16,
      }}
    >
      {/* Search */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        flex: '0 1 320px',
        backgroundColor: '#F7F8F6',
        border: '1px solid #E7EAE8',
        borderRadius: 8,
        padding: '7px 12px',
        color: '#8A96A8',
      }}>
        <Search size={14} style={{ flexShrink: 0 }} />
        <span style={{
          fontSize: 13,
          fontFamily: "'DM Sans', sans-serif",
          color: '#8A96A8',
          userSelect: 'none',
        }}>
          Search batches, parts, defects…
        </span>
        <span style={{
          marginLeft: 'auto',
          fontSize: 10,
          color: '#B0BAC8',
          fontFamily: 'monospace',
          background: '#FFFFFF',
          border: '1px solid #E7EAE8',
          borderRadius: 4,
          padding: '1px 5px',
        }}>
          ⌘K
        </span>
      </div>

      {/* Role Switcher */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        backgroundColor: '#F7F8F6',
        border: '1px solid #E7EAE8',
        borderRadius: 8,
        padding: '4px',
        gap: 2,
      }}>
        {[
          { id: 'INSPECTOR', label: 'Inspector', active: isInspector },
          { id: 'SUPERVISOR', label: 'Supervisor', active: isSupervisor },
          { id: 'QUALITY_MANAGER', label: 'Quality Manager', active: isQualityManager && !isSupervisor },
        ].map(({ id, label, active }) => (
          <button
            key={id}
            onClick={() => handleRoleQuickSwitch(id)}
            style={{
              padding: '5px 10px',
              borderRadius: 6,
              border: 'none',
              cursor: 'pointer',
              fontSize: 12,
              fontFamily: "'DM Sans', sans-serif",
              fontWeight: active ? 600 : 400,
              transition: 'background 0.15s, color 0.15s',
              backgroundColor: active ? '#FFFFFF' : 'transparent',
              color: active ? ROLE_COLOR[id] || '#142033' : '#64748B',
              boxShadow: active ? '0 1px 3px rgba(0,0,0,0.07)' : 'none',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Right: Bell + User */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* Notifications */}
        <button
          style={{
            width: 34,
            height: 34,
            borderRadius: 8,
            border: '1px solid #E7EAE8',
            backgroundColor: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: '#64748B',
            transition: 'background 0.15s, color 0.15s',
          }}
          title="Notifications"
          onMouseEnter={e => { e.currentTarget.style.backgroundColor = '#F7F8F6'; e.currentTarget.style.color = '#142033'; }}
          onMouseLeave={e => { e.currentTarget.style.backgroundColor = '#FFFFFF'; e.currentTarget.style.color = '#64748B'; }}
        >
          <Bell size={15} />
        </button>

        {/* Separator */}
        <div style={{ width: 1, height: 28, backgroundColor: '#E7EAE8' }} />

        {/* User identity */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            backgroundColor: roleBg,
            border: `1px solid ${roleColor}30`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: "'Manrope', sans-serif",
            fontWeight: 700,
            fontSize: 11,
            color: roleColor,
            letterSpacing: '0.02em',
          }}>
            {initials || 'U'}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <div style={{
              fontSize: 12,
              fontWeight: 600,
              color: '#142033',
              fontFamily: "'DM Sans', sans-serif",
              lineHeight: 1.2,
            }}>
              {displayName}
            </div>
            <div style={{
              fontSize: 10,
              color: '#8A96A8',
              fontFamily: "'DM Sans', sans-serif",
              lineHeight: 1.2,
            }}>
              {roleLabel}
            </div>
          </div>
          <ChevronDown size={13} style={{ color: '#8A96A8', marginLeft: 2 }} />
        </div>

        {/* Logout */}
        <button
          onClick={logout}
          title="Log Out"
          style={{
            width: 30,
            height: 30,
            borderRadius: 6,
            border: 'none',
            backgroundColor: 'transparent',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: '#8A96A8',
            transition: 'background 0.15s, color 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.backgroundColor = '#FEE2E2'; e.currentTarget.style.color = '#DC2626'; }}
          onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = '#8A96A8'; }}
        >
          <LogOut size={14} />
        </button>
      </div>
    </header>
  );
};

export default Header;
