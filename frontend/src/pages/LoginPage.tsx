import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import type { UserRole } from '../types';
import {
  Eye,
  EyeOff,
  ArrowRight,
  Lock,
  User as UserIcon,
  Scan,
  ShieldCheck,
  Wrench,
  Loader2,
  ChevronRight,
  AlertTriangle,
} from 'lucide-react';

/* ─────────────────────────────────────────────────────────────
   Types & Route Definitions
───────────────────────────────────────────────────────────── */
export type RoleWorkspace = 'inspector' | 'supervisor' | 'quality-manager';
type AuthView = 'selection' | RoleWorkspace;

interface RoleConfig {
  id: RoleWorkspace;
  backendRole: UserRole;
  title: string;
  badgeLabel: string;
  eyebrow: string;
  description: string;
  cardButtonText: string;
  formButtonText: string;
  formSubtitle: string;
  route: string;
  accentColor: string;
  accentBg: string;
  accentBorder: string;
  accentGlow: string;
  buttonBg: string;
  buttonText: string;
  icon: React.ReactNode;
}

const ROLE_CONFIGS: Record<RoleWorkspace, RoleConfig> = {
  inspector: {
    id: 'inspector',
    backendRole: 'INSPECTOR',
    title: 'Inspector',
    badgeLabel: 'Inspector',
    eyebrow: 'INSPECTION WORKSPACE',
    description: 'Inspect components, review AI-detected defects, and upload inspection evidence.',
    cardButtonText: 'Continue as Inspector',
    formButtonText: 'Sign In',
    formSubtitle: 'Enter your credentials to access the inspection workspace.',
    route: '/login/inspector',
    accentColor: '#22D3EE',
    accentBg: 'rgba(6, 182, 212, 0.12)',
    accentBorder: 'rgba(34, 211, 238, 0.35)',
    accentGlow: '0 0 28px rgba(6, 182, 212, 0.20)',
    buttonBg: '#00C2E0',
    buttonText: '#0A0F1A',
    icon: <Scan size={22} className="text-cyan-400" />,
  },
  supervisor: {
    id: 'supervisor',
    backendRole: 'SUPERVISOR',
    title: 'Supervisor',
    badgeLabel: 'Supervisor',
    eyebrow: 'SUPERVISOR WORKSPACE',
    description: 'Manage production batches, assign corrective actions, and track remediation.',
    cardButtonText: 'Continue as Supervisor',
    formButtonText: 'Sign In',
    formSubtitle: 'Enter your credentials to access the supervision workspace.',
    route: '/login/supervisor',
    accentColor: '#FBBF24',
    accentBg: 'rgba(245, 158, 11, 0.12)',
    accentBorder: 'rgba(245, 158, 11, 0.35)',
    accentGlow: '0 0 28px rgba(245, 158, 11, 0.20)',
    buttonBg: '#FBBF24',
    buttonText: '#0A0F1A',
    icon: <Wrench size={22} className="text-amber-400" />,
  },
  'quality-manager': {
    id: 'quality-manager',
    backendRole: 'QUALITY_MANAGER',
    title: 'Quality Manager',
    badgeLabel: 'Quality Manager',
    eyebrow: 'QUALITY MANAGEMENT',
    description: 'Review quality decisions, verify corrective actions, and manage release approvals.',
    cardButtonText: 'Continue as Quality Manager',
    formButtonText: 'Sign In',
    formSubtitle: 'Enter your credentials to access the quality management workspace.',
    route: '/login/quality-manager',
    accentColor: '#A78BFA',
    accentBg: 'rgba(167, 139, 250, 0.12)',
    accentBorder: 'rgba(167, 139, 250, 0.35)',
    accentGlow: '0 0 28px rgba(139, 92, 246, 0.22)',
    buttonBg: '#A78BFA',
    buttonText: '#0A0F1A',
    icon: <ShieldCheck size={22} className="text-purple-400" />,
  },
};

/* ─────────────────────────────────────────────────────────────
   Brand Mark — Warm yellow "C" mark
───────────────────────────────────────────────────────────── */
const CastTraceMark: React.FC<{ size?: number }> = ({ size = 34 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 36 36"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <rect width="36" height="36" rx="9" fill="#FBBF24" />
    <path
      d="M24.5 13.25C23.1 11.25 20.7 10 18 10C13.58 10 10 13.58 10 18C10 22.42 13.58 26 18 26C20.7 26 23.1 24.75 24.5 22.75"
      stroke="#101216"
      strokeWidth="2.8"
      strokeLinecap="round"
    />
  </svg>
);

/* ─────────────────────────────────────────────────────────────
   Common Header Bar
───────────────────────────────────────────────────────────── */
const AuthHeader: React.FC<{ onBrandClick?: () => void }> = ({ onBrandClick }) => (
  <header
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '20px 36px',
      borderBottom: '1px solid rgba(148,163,184,0.08)',
      position: 'relative',
      zIndex: 20,
    }}
  >
    <button
      type="button"
      onClick={onBrandClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        background: 'none',
        border: 'none',
        cursor: onBrandClick ? 'pointer' : 'default',
        padding: 0,
      }}
    >
      <CastTraceMark size={32} />
      <span
        style={{
          fontFamily: "'Manrope', sans-serif",
          fontWeight: 700,
          fontSize: 18,
          color: '#F5F5F5',
          letterSpacing: '-0.02em',
        }}
      >
        CastTrace AI
      </span>
    </button>

    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      {(['QUALITY', 'TRACEABILITY', 'COMPLIANCE'] as const).map((label, i) => (
        <React.Fragment key={label}>
          {i > 0 && (
            <span style={{ fontSize: 8, color: '#374151', margin: '0 3px' }}>•</span>
          )}
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: '0.14em',
              color: '#64748B',
              fontFamily: "'DM Sans', sans-serif",
            }}
          >
            {label}
          </span>
        </React.Fragment>
      ))}
      <span
        style={{
          marginLeft: 14,
          fontSize: 10,
          color: '#4B5563',
          fontFamily: 'monospace',
          letterSpacing: '0.06em',
          borderLeft: '1px solid rgba(148,163,184,0.15)',
          paddingLeft: 14,
        }}
      >
        v2.0
      </span>
    </div>
  </header>
);

/* ─────────────────────────────────────────────────────────────
   Common Footer
───────────────────────────────────────────────────────────── */
const AuthFooter: React.FC = () => (
  <footer
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 36px',
      borderTop: '1px solid rgba(148,163,184,0.08)',
      position: 'relative',
      zIndex: 20,
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 22, height: 1.5, background: '#FBBF24', opacity: 0.7 }} />
      <span
        style={{
          fontSize: 10,
          color: '#4B5563',
          fontFamily: "'DM Sans', sans-serif",
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          fontWeight: 600,
        }}
      >
        Built for modern manufacturing
      </span>
    </div>
    <div
      style={{
        fontSize: 10,
        color: '#4B5563',
        fontFamily: 'monospace',
        letterSpacing: '0.06em',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <span>FastAPI · SQLAlchemy · RBAC · SQLite</span>
      <ChevronRight size={10} style={{ opacity: 0.4 }} />
      <span>v2.0</span>
    </div>
  </footer>
);

/* ─────────────────────────────────────────────────────────────
   Subtle Ghosted Impeller SVG for Card Backgrounds
───────────────────────────────────────────────────────────── */
const GhostImpeller: React.FC<{ color: string; opacity?: number }> = ({ color, opacity = 0.08 }) => (
  <svg
    width="200"
    height="200"
    viewBox="0 0 200 200"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
    style={{
      position: 'absolute',
      right: -30,
      top: -30,
      pointerEvents: 'none',
      opacity,
      transition: 'opacity 0.3s ease, transform 0.4s ease',
    }}
    className="ct-card-ghost"
  >
    <circle cx="100" cy="100" r="85" stroke={color} strokeWidth="1.5" strokeDasharray="4 4" />
    <circle cx="100" cy="100" r="60" stroke={color} strokeWidth="1" />
    <circle cx="100" cy="100" r="30" stroke={color} strokeWidth="2" />
    <circle cx="100" cy="100" r="12" fill={color} />
    {/* Impeller Vane curves */}
    {[0, 45, 90, 135, 180, 225, 270, 315].map((angle) => (
      <path
        key={angle}
        d="M100 100 C120 70 150 75 175 90"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        transform={`rotate(${angle} 100 100)`}
      />
    ))}
  </svg>
);

/* ─────────────────────────────────────────────────────────────
   Dedicated Role Selection Screen
───────────────────────────────────────────────────────────── */
interface RoleSelectionProps {
  onSelectRole: (role: RoleWorkspace) => void;
}

const RoleSelectionView: React.FC<RoleSelectionProps> = ({ onSelectRole }) => {
  const roles: RoleWorkspace[] = ['inspector', 'supervisor', 'quality-manager'];

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '36px 24px',
        position: 'relative',
        zIndex: 10,
        maxWidth: 1240,
        margin: '0 auto',
        width: '100%',
        boxSizing: 'border-box',
      }}
    >
      {/* Eyebrow & Hero Header */}
      <div style={{ textAlign: 'center', marginBottom: 44 }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 14,
          }}
        >
          <div style={{ width: 20, height: 1.5, background: '#F59E0B' }} />
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.18em',
              color: '#F59E0B',
              fontFamily: "'DM Sans', sans-serif",
              textTransform: 'uppercase',
            }}
          >
            Pump Impeller Quality Inspection
          </span>
          <div style={{ width: 20, height: 1.5, background: '#F59E0B' }} />
        </div>

        <h1
          style={{
            fontFamily: "'Manrope', sans-serif",
            fontWeight: 800,
            fontSize: 'clamp(34px, 4.2vw, 48px)',
            lineHeight: 1.15,
            letterSpacing: '-0.03em',
            margin: '0 0 12px',
            color: '#F5F5F5',
          }}
        >
          Sign in to{' '}
          <span
            style={{
              background: 'linear-gradient(135deg, #FDE68A 0%, #F59E0B 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            CastTrace AI
          </span>
        </h1>

        <p
          style={{
            fontSize: 16,
            color: '#94A3B8',
            fontFamily: "'DM Sans', sans-serif",
            margin: 0,
            fontWeight: 400,
          }}
        >
          Choose your workspace to continue.
        </p>
      </div>

      {/* Responsive 3-Card Grid */}
      <div
        className="ct-roles-grid"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 24,
          width: '100%',
          maxWidth: 1160,
        }}
      >
        {roles.map((roleKey) => {
          const cfg = ROLE_CONFIGS[roleKey];
          return (
            <div
              key={cfg.id}
              className="ct-role-card"
              style={{
                position: 'relative',
                borderRadius: 16,
                backgroundColor: 'rgba(17, 24, 39, 0.75)',
                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',
                border: `1px solid ${cfg.accentBorder}`,
                padding: '32px 28px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                minHeight: 280,
                overflow: 'hidden',
                transition: 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
                boxShadow: '0 16px 40px rgba(0,0,0,0.45)',
              }}
            >
              <GhostImpeller color={cfg.accentColor} opacity={0.12} />

              <div>
                {/* Icon Badge */}
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: '50%',
                    backgroundColor: cfg.accentBg,
                    border: `1px solid ${cfg.accentBorder}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: 22,
                    boxShadow: cfg.accentGlow,
                  }}
                >
                  {cfg.icon}
                </div>

                {/* Role Title */}
                <h2
                  style={{
                    fontFamily: "'Manrope', sans-serif",
                    fontWeight: 700,
                    fontSize: 22,
                    color: '#FFFFFF',
                    margin: '0 0 10px',
                    letterSpacing: '-0.01em',
                  }}
                >
                  {cfg.title}
                </h2>

                {/* Description */}
                <p
                  style={{
                    fontSize: 14,
                    color: '#94A3B8',
                    fontFamily: "'DM Sans', sans-serif",
                    lineHeight: 1.55,
                    margin: '0 0 28px',
                    minHeight: 44,
                  }}
                >
                  {cfg.description}
                </p>
              </div>

              {/* Full-width CTA Button */}
              <button
                type="button"
                id={`continue-${cfg.id}`}
                onClick={() => onSelectRole(cfg.id)}
                className="ct-card-btn"
                style={{
                  width: '100%',
                  padding: '12px 18px',
                  borderRadius: 10,
                  backgroundColor: cfg.buttonBg,
                  color: cfg.buttonText,
                  border: 'none',
                  fontFamily: "'Manrope', sans-serif",
                  fontWeight: 700,
                  fontSize: 14,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  transition: 'all 0.2s ease',
                  boxShadow: `0 4px 18px ${cfg.accentBorder}`,
                  position: 'relative',
                  zIndex: 2,
                }}
              >
                <span>{cfg.cardButtonText}</span>
                <ArrowRight size={16} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────
   Visual HUD Overlay for Dedicated Role Sign In Screen
───────────────────────────────────────────────────────────── */
const RoleVisualHUD: React.FC<{ role: RoleWorkspace }> = ({ role }) => {
  if (role === 'inspector') {
    return (
      <div
        aria-hidden="true"
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          minHeight: 400,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'flex-end',
          paddingBottom: 24,
        }}
      >
        {/* Inspection scanner frame */}
        <div
          style={{
            position: 'absolute',
            top: '12%',
            left: '4%',
            width: '74%',
            height: '62%',
            border: '1px solid rgba(34, 211, 238, 0.35)',
            borderRadius: 4,
          }}
        >
          {/* Cyan scan line */}
          <div
            className="ct-scan-line-cyan"
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              height: 2,
              background:
                'linear-gradient(90deg, transparent 0%, rgba(34,211,238,0.7) 30%, rgba(34,211,238,1) 50%, rgba(34,211,238,0.7) 70%, transparent 100%)',
              boxShadow: '0 0 14px 3px rgba(34,211,238,0.45)',
            }}
          />
          {/* Target Box */}
          <div
            style={{
              position: 'absolute',
              top: '38%',
              left: '44%',
              width: 32,
              height: 24,
              border: '2px solid #22D3EE',
              borderRadius: 2,
              boxShadow: '0 0 10px rgba(34,211,238,0.6)',
            }}
          />
        </div>

        {/* AI Detection HUD Pill */}
        <div
          style={{
            position: 'relative',
            zIndex: 10,
            background: 'rgba(16, 21, 30, 0.88)',
            border: '1px solid rgba(34, 211, 238, 0.35)',
            borderRadius: 10,
            padding: '12px 16px',
            backdropFilter: 'blur(12px)',
            maxWidth: 260,
            boxShadow: '0 8px 30px rgba(0,0,0,0.5)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#22D3EE' }} />
            <span style={{ fontSize: 11, fontWeight: 700, color: '#F5F5F5', fontFamily: "'Manrope', sans-serif" }}>
              Surface Porosity Check
            </span>
          </div>
          <div style={{ fontSize: 10, color: '#94A3B8', fontFamily: "'DM Sans', sans-serif" }}>
            Model: ResNet-18 · Confidence: <strong style={{ color: '#22D3EE' }}>98.4%</strong>
          </div>
        </div>
      </div>
    );
  }

  if (role === 'supervisor') {
    return (
      <div
        aria-hidden="true"
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          minHeight: 400,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'flex-end',
          paddingBottom: 24,
        }}
      >
        <div
          style={{
            position: 'relative',
            zIndex: 10,
            background: 'rgba(24, 20, 16, 0.88)',
            border: '1px solid rgba(245, 158, 11, 0.35)',
            borderRadius: 10,
            padding: '14px 18px',
            backdropFilter: 'blur(12px)',
            maxWidth: 280,
            boxShadow: '0 8px 30px rgba(0,0,0,0.5)',
          }}
        >
          <div style={{ fontSize: 10, color: '#F59E0B', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6 }}>
            Active Production Batch
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 11, color: '#94A3B8' }}>Batch ID:</span>
            <span style={{ fontSize: 11, color: '#F5F5F5', fontWeight: 600 }}>IMP-2025-0847</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 11, color: '#94A3B8' }}>Remediation CAPA:</span>
            <span style={{ fontSize: 11, color: '#FBBF24', fontWeight: 600 }}>2 In Progress</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 11, color: '#94A3B8' }}>Gate Status:</span>
            <span style={{ fontSize: 11, color: '#34D399', fontWeight: 600 }}>Ready for Review</span>
          </div>
        </div>
      </div>
    );
  }

  // Quality Manager
  return (
    <div
      aria-hidden="true"
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        minHeight: 400,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'flex-end',
        paddingBottom: 24,
      }}
    >
      <div
        style={{
          position: 'relative',
          zIndex: 10,
          background: 'rgba(23, 18, 32, 0.88)',
          border: '1px solid rgba(167, 139, 250, 0.35)',
          borderRadius: 10,
          padding: '14px 18px',
          backdropFilter: 'blur(12px)',
          maxWidth: 280,
          boxShadow: '0 8px 30px rgba(0,0,0,0.5)',
        }}
      >
        <div style={{ fontSize: 10, color: '#A78BFA', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6 }}>
          Release Governance Gate
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 11, color: '#94A3B8' }}>Rule Set:</span>
          <span style={{ fontSize: 11, color: '#F5F5F5', fontWeight: 600 }}>Phase 4C Active</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 11, color: '#94A3B8' }}>Four-Eyes Auth:</span>
          <span style={{ fontSize: 11, color: '#34D399', fontWeight: 600 }}>Enforced</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 11, color: '#94A3B8' }}>Audit Trail:</span>
          <span style={{ fontSize: 11, color: '#A78BFA', fontWeight: 600 }}>Immutable Log</span>
        </div>
      </div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────
   Dedicated Role Sign In Form Component
───────────────────────────────────────────────────────────── */
interface RoleLoginScreenProps {
  role: RoleWorkspace;
  onBackToSelection: () => void;
  onSwitchWorkspace: (targetRole: RoleWorkspace, prefilledUsername?: string) => void;
}

const RoleLoginScreen: React.FC<RoleLoginScreenProps> = ({
  role,
  onBackToSelection,
  onSwitchWorkspace,
}) => {
  const { loginWorkspace, isLoading } = useAuth();
  const cfg = ROLE_CONFIGS[role];

  // Remembered username state
  const REMEMBER_KEY = 'casttrace_remembered_username';
  const savedUsername = typeof window !== 'undefined' ? localStorage.getItem(REMEMBER_KEY) || '' : '';

  const [username, setUsername] = useState(savedUsername);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(!!savedUsername);
  const [authError, setAuthError] = useState<string | null>(null);
  const [roleMismatch, setRoleMismatch] = useState<{ actualRole: string; suggestedWorkspace?: RoleWorkspace } | null>(null);

  const usernameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    usernameInputRef.current?.focus();
  }, [role]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password || isLoading) return;

    setAuthError(null);
    setRoleMismatch(null);

    // Persist or clear remembered username
    if (rememberMe) {
      localStorage.setItem(REMEMBER_KEY, username.trim());
    } else {
      localStorage.removeItem(REMEMBER_KEY);
    }

    try {
      // Authenticate with backend, strictly validating against allowed backend roles
      await loginWorkspace(username.trim(), password, [cfg.backendRole]);
      // On success, clean browser URL to root
      window.history.replaceState({}, '', '/');
    } catch (err: any) {
      if (err.code === 'ROLE_MISMATCH') {
        const actual: string = err.actualRole || 'ANOTHER_ROLE';
        let suggested: RoleWorkspace | undefined;
        if (actual === 'INSPECTOR') suggested = 'inspector';
        else if (actual === 'SUPERVISOR') suggested = 'supervisor';
        else if (actual === 'QUALITY_MANAGER') suggested = 'quality-manager';

        setRoleMismatch({
          actualRole: actual.replace('_', ' '),
          suggestedWorkspace: suggested,
        });
      } else {
        setAuthError(err?.message || 'Invalid username or password. Please try again.');
      }
    }
  };

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '32px 28px',
        position: 'relative',
        zIndex: 10,
        width: '100%',
        maxWidth: 1200,
        margin: '0 auto',
        boxSizing: 'border-box',
      }}
    >
      <div
        className="ct-login-split"
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.15fr) minmax(0, 440px)',
          gap: 48,
          alignItems: 'center',
          width: '100%',
        }}
      >
        {/* Left Column: Heading, Role Persona Context & Visual */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <div style={{ width: 22, height: 1.5, background: cfg.accentColor }} />
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: '0.18em',
                color: cfg.accentColor,
                fontFamily: "'DM Sans', sans-serif",
                textTransform: 'uppercase',
              }}
            >
              {cfg.eyebrow}
            </span>
          </div>

          <h1
            style={{
              fontFamily: "'Manrope', sans-serif",
              fontWeight: 800,
              fontSize: 'clamp(34px, 4vw, 50px)',
              lineHeight: 1.12,
              letterSpacing: '-0.03em',
              margin: '0 0 16px',
              color: '#F5F5F5',
            }}
          >
            {cfg.title} Sign In
          </h1>

          <p
            style={{
              fontSize: 15,
              color: '#94A3B8',
              lineHeight: 1.6,
              margin: '0 0 24px',
              maxWidth: 420,
              fontFamily: "'DM Sans', sans-serif",
            }}
          >
            {cfg.description}
          </p>

          <RoleVisualHUD role={role} />
        </div>

        {/* Right Column: Dedicated Glass Sign In Form Card */}
        <div>
          <div
            style={{
              backgroundColor: 'rgba(20, 26, 36, 0.88)',
              border: `1px solid ${cfg.accentBorder}`,
              borderRadius: 18,
              padding: '36px 32px',
              backdropFilter: 'blur(24px)',
              WebkitBackdropFilter: 'blur(24px)',
              boxShadow: `0 24px 70px rgba(0,0,0,0.6), ${cfg.accentGlow}`,
              position: 'relative',
            }}
          >
            {/* Card Header with Icon Badge */}
            <div style={{ textAlign: 'center', marginBottom: 28 }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: '50%',
                  backgroundColor: cfg.accentBg,
                  border: `1px solid ${cfg.accentBorder}`,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: 14,
                  boxShadow: cfg.accentGlow,
                }}
              >
                {cfg.icon}
              </div>

              <h2
                style={{
                  fontFamily: "'Manrope', sans-serif",
                  fontWeight: 700,
                  fontSize: 22,
                  color: '#FFFFFF',
                  margin: '0 0 6px',
                  letterSpacing: '-0.01em',
                }}
              >
                {cfg.title} Sign In
              </h2>

              <p
                style={{
                  fontSize: 13,
                  color: '#94A3B8',
                  fontFamily: "'DM Sans', sans-serif",
                  margin: 0,
                  lineHeight: 1.45,
                }}
              >
                {cfg.formSubtitle}
              </p>
            </div>

            {/* Error / Mismatch Alert */}
            {roleMismatch && (
              <div
                role="alert"
                style={{
                  marginBottom: 20,
                  padding: '14px 16px',
                  borderRadius: 10,
                  backgroundColor: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid rgba(239, 68, 68, 0.35)',
                  color: '#FCA5A5',
                  fontSize: 13,
                  fontFamily: "'DM Sans', sans-serif",
                  lineHeight: 1.5,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, marginBottom: 4, color: '#F87171' }}>
                  <AlertTriangle size={16} />
                  <span>Workspace Mismatch</span>
                </div>
                <div>
                  Your account is assigned the role of{' '}
                  <strong style={{ color: '#FFFFFF' }}>{roleMismatch.actualRole}</strong>, but this is the{' '}
                  <strong>{cfg.title}</strong> workspace. Access is denied for this workspace.
                </div>
                {roleMismatch.suggestedWorkspace && (
                  <button
                    type="button"
                    onClick={() => onSwitchWorkspace(roleMismatch.suggestedWorkspace!, username)}
                    style={{
                      marginTop: 10,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      background: 'rgba(239, 68, 68, 0.15)',
                      border: '1px solid rgba(239, 68, 68, 0.4)',
                      borderRadius: 6,
                      padding: '6px 12px',
                      color: '#FFFFFF',
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                      fontFamily: "'DM Sans', sans-serif",
                    }}
                  >
                    <span>Switch to {ROLE_CONFIGS[roleMismatch.suggestedWorkspace].title} Workspace</span>
                    <ArrowRight size={13} />
                  </button>
                )}
              </div>
            )}

            {authError && (
              <div
                role="alert"
                style={{
                  marginBottom: 18,
                  padding: '10px 14px',
                  borderRadius: 8,
                  backgroundColor: 'rgba(248, 113, 113, 0.08)',
                  border: '1px solid rgba(248, 113, 113, 0.3)',
                  color: '#FCA5A5',
                  fontSize: 13,
                  fontFamily: "'DM Sans', sans-serif",
                  lineHeight: 1.45,
                }}
              >
                {authError}
              </div>
            )}

            {/* Login Form */}
            <form onSubmit={handleSubmit} noValidate>
              {/* User ID or Email */}
              <div style={{ marginBottom: 16 }}>
                <label
                  htmlFor="login-username-input"
                  style={{
                    display: 'block',
                    fontSize: 11,
                    fontWeight: 600,
                    color: '#A8B0BD',
                    letterSpacing: '0.1em',
                    textTransform: 'uppercase',
                    marginBottom: 8,
                    fontFamily: "'DM Sans', sans-serif",
                  }}
                >
                  User ID or Email
                </label>
                <div style={{ position: 'relative' }}>
                  <span
                    style={{
                      position: 'absolute',
                      left: 14,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: '#64748B',
                      display: 'flex',
                      pointerEvents: 'none',
                    }}
                  >
                    <UserIcon size={16} />
                  </span>
                  <input
                    id="login-username-input"
                    ref={usernameInputRef}
                    type="text"
                    value={username}
                    onChange={(e) => {
                      setUsername(e.target.value);
                      setAuthError(null);
                      setRoleMismatch(null);
                    }}
                    placeholder="Enter your user ID or email"
                    autoComplete="username"
                    required
                    className="ct-role-input"
                    style={{
                      borderColor: authError || roleMismatch ? 'rgba(239, 68, 68, 0.5)' : undefined,
                    }}
                  />
                </div>
              </div>

              {/* Password */}
              <div style={{ marginBottom: 18 }}>
                <label
                  htmlFor="login-password-input"
                  style={{
                    display: 'block',
                    fontSize: 11,
                    fontWeight: 600,
                    color: '#A8B0BD',
                    letterSpacing: '0.1em',
                    textTransform: 'uppercase',
                    marginBottom: 8,
                    fontFamily: "'DM Sans', sans-serif",
                  }}
                >
                  Password
                </label>
                <div style={{ position: 'relative' }}>
                  <span
                    style={{
                      position: 'absolute',
                      left: 14,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: '#64748B',
                      display: 'flex',
                      pointerEvents: 'none',
                    }}
                  >
                    <Lock size={16} />
                  </span>
                  <input
                    id="login-password-input"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      setAuthError(null);
                      setRoleMismatch(null);
                    }}
                    placeholder="••••••••••••"
                    autoComplete="current-password"
                    required
                    className="ct-role-input"
                    style={{
                      paddingRight: 42,
                      borderColor: authError || roleMismatch ? 'rgba(239, 68, 68, 0.5)' : undefined,
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    style={{
                      position: 'absolute',
                      right: 12,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: '#64748B',
                      display: 'flex',
                      padding: 4,
                      transition: 'color 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = cfg.accentColor)}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#64748B')}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {/* Remember Me Checkbox */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 9,
                  marginBottom: 24,
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
                onClick={() => setRememberMe(!rememberMe)}
              >
                <input
                  type="checkbox"
                  id="remember-me"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  style={{
                    width: 16,
                    height: 16,
                    borderRadius: 4,
                    accentColor: cfg.accentColor,
                    cursor: 'pointer',
                  }}
                />
                <label
                  htmlFor="remember-me"
                  style={{
                    fontSize: 13,
                    color: '#94A3B8',
                    fontFamily: "'DM Sans', sans-serif",
                    cursor: 'pointer',
                  }}
                >
                  Remember me
                </label>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                id="role-login-submit"
                disabled={isLoading || !username.trim() || !password}
                aria-busy={isLoading}
                style={{
                  width: '100%',
                  padding: '13px 20px',
                  borderRadius: 10,
                  backgroundColor: cfg.buttonBg,
                  color: cfg.buttonText,
                  border: 'none',
                  fontSize: 14,
                  fontWeight: 700,
                  fontFamily: "'Manrope', sans-serif",
                  cursor: isLoading || !username.trim() || !password ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  transition: 'all 0.2s ease',
                  boxShadow: `0 4px 20px ${cfg.accentBorder}`,
                  opacity: isLoading || !username.trim() || !password ? 0.6 : 1,
                }}
              >
                {isLoading ? (
                  <Loader2 size={16} className="ct-spin" />
                ) : (
                  <ArrowRight size={16} />
                )}
                <span>{isLoading ? 'Authenticating…' : `${cfg.formButtonText} →`}</span>
              </button>
            </form>

            {/* Back to Role Selection Link */}
            <div style={{ textAlign: 'center', marginTop: 22 }}>
              <button
                type="button"
                onClick={onBackToSelection}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#94A3B8',
                  fontSize: 13,
                  fontFamily: "'DM Sans', sans-serif",
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '4px 8px',
                  borderRadius: 6,
                  transition: 'color 0.15s ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#F5F5F5')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#94A3B8')}
              >
                <span>← Back to role selection</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────
   Main Container Component with URL Routing
───────────────────────────────────────────────────────────── */
export const LoginPage: React.FC = () => {
  // Parse path to route
  const getInitialView = (): AuthView => {
    if (typeof window === 'undefined') return 'selection';
    const path = window.location.pathname.toLowerCase();
    if (path === '/login/inspector') return 'inspector';
    if (path === '/login/supervisor') return 'supervisor';
    if (path === '/login/quality-manager') return 'quality-manager';
    return 'selection';
  };

  const [currentView, setCurrentView] = useState<AuthView>(getInitialView);

  // Synchronize state with browser history (back/forward buttons)
  useEffect(() => {
    const handlePopState = () => {
      setCurrentView(getInitialView());
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigateTo = useCallback((view: AuthView) => {
    let targetPath = '/login';
    if (view === 'inspector') targetPath = '/login/inspector';
    else if (view === 'supervisor') targetPath = '/login/supervisor';
    else if (view === 'quality-manager') targetPath = '/login/quality-manager';

    if (window.location.pathname !== targetPath) {
      window.history.pushState({}, '', targetPath);
    }
    setCurrentView(view);
  }, []);

  const handleSwitchWorkspace = (targetRole: RoleWorkspace) => {
    navigateTo(targetRole);
  };

  return (
    <div
      role="main"
      style={{
        minHeight: '100vh',
        width: '100%',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#101216',
        color: '#F5F5F5',
        fontFamily: "'DM Sans', system-ui, sans-serif",
        overflowX: 'hidden',
      }}
    >
      {/* Background Impeller Image with Mood Grading */}
      <div
        aria-hidden="true"
        className="ct-float"
        style={{
          position: 'fixed',
          inset: '-5%',
          backgroundImage: 'url(/impeller-bg.jpg)',
          backgroundSize: 'cover',
          backgroundPosition: 'center 40%',
          zIndex: 0,
          pointerEvents: 'none',
        }}
      />

      {/* Dark Gradient Vignette Overlay */}
      <div
        aria-hidden="true"
        style={{
          position: 'fixed',
          inset: 0,
          background:
            'linear-gradient(135deg, rgba(16,18,22,0.95) 0%, rgba(16,18,22,0.85) 50%, rgba(16,18,22,0.95) 100%)',
          zIndex: 1,
          pointerEvents: 'none',
        }}
      />

      {/* Atmospheric Accent Radial Glow */}
      <div
        aria-hidden="true"
        style={{
          position: 'fixed',
          inset: 0,
          background:
            currentView === 'inspector'
              ? 'radial-gradient(ellipse at 70% 30%, rgba(6,182,212,0.12) 0%, transparent 65%)'
              : currentView === 'supervisor'
              ? 'radial-gradient(ellipse at 70% 30%, rgba(245,158,11,0.12) 0%, transparent 65%)'
              : currentView === 'quality-manager'
              ? 'radial-gradient(ellipse at 70% 30%, rgba(139,92,246,0.14) 0%, transparent 65%)'
              : 'radial-gradient(ellipse at 50% 20%, rgba(251,191,36,0.08) 0%, transparent 65%)',
          zIndex: 2,
          pointerEvents: 'none',
          transition: 'background 0.4s ease',
        }}
      />

      {/* Top Header */}
      <AuthHeader onBrandClick={() => navigateTo('selection')} />

      {/* Main View Transition */}
      <main style={{ flex: 1, display: 'flex', position: 'relative', zIndex: 10 }}>
        {currentView === 'selection' ? (
          <RoleSelectionView onSelectRole={(role) => navigateTo(role)} />
        ) : (
          <RoleLoginScreen
            role={currentView}
            onBackToSelection={() => navigateTo('selection')}
            onSwitchWorkspace={handleSwitchWorkspace}
          />
        )}
      </main>

      {/* Bottom Footer */}
      <AuthFooter />

      {/* Scoped CSS Styles */}
      <style>{`
        @keyframes ct-spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        .ct-spin { animation: ct-spin 1s linear infinite; }

        @keyframes ct-scan-cyan {
          0%   { transform: translateY(-100%); opacity: 0; }
          10%  { opacity: 1; }
          90%  { opacity: 1; }
          100% { transform: translateY(220%); opacity: 0; }
        }
        .ct-scan-line-cyan {
          animation: ct-scan-cyan 4.5s linear infinite;
        }

        .ct-role-input {
          width: 100%;
          box-sizing: border-box;
          padding: 11px 14px 11px 40px;
          border-radius: 10px;
          background: rgba(13, 17, 24, 0.75);
          border: 1px solid rgba(148, 163, 184, 0.22);
          color: #F5F5F5;
          font-size: 14px;
          font-family: 'DM Sans', sans-serif;
          outline: none;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .ct-role-input:focus {
          border-color: #FBBF24;
          box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.18);
        }
        .ct-role-input::placeholder { color: #475569; }
        .ct-role-input:-webkit-autofill {
          -webkit-box-shadow: 0 0 0 100px #0F141D inset !important;
          -webkit-text-fill-color: #F5F5F5 !important;
        }

        .ct-role-card:hover {
          transform: translateY(-4px);
          box-shadow: 0 24px 60px rgba(0, 0, 0, 0.65);
        }
        .ct-role-card:hover .ct-card-ghost {
          opacity: 0.22 !important;
          transform: scale(1.08) rotate(6deg);
        }
        .ct-card-btn:hover {
          filter: brightness(1.08);
          transform: translateY(-1px);
        }

        @media (max-width: 1024px) {
          .ct-roles-grid {
            grid-template-columns: 1fr !important;
            gap: 20px !important;
          }
          .ct-login-split {
            grid-template-columns: 1fr !important;
            gap: 32px !important;
          }
          .ct-login-split > div:first-child > div:last-child {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
};

export default LoginPage;
