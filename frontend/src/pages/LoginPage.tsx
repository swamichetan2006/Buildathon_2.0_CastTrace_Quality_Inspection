import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  Eye,
  EyeOff,
  ArrowRight,
  Lock,
  User as UserIcon,
  Scan,
  Layers,
  GitBranch,
  ShieldCheck,
  Wrench,
  Loader2,
  ChevronRight,
  BarChart2,
} from 'lucide-react';

/* ─────────────────────────────────────────────────────────────
   Brand symbol — warm-yellow "C" mark
───────────────────────────────────────────────────────────── */
const CastTraceMark: React.FC<{ size?: number }> = ({ size = 36 }) => (
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
   Inspection Overlay — scanning line + markers + callouts
───────────────────────────────────────────────────────────── */
const InspectionOverlay: React.FC = () => (
  <div
    aria-hidden="true"
    style={{
      position: 'absolute',
      inset: 0,
      pointerEvents: 'none',
      overflow: 'hidden',
    }}
  >
    {/* Scan bracket frame */}
    <div
      style={{
        position: 'absolute',
        top: '22%',
        left: '8%',
        width: '58%',
        height: '56%',
        border: '1px solid rgba(251,191,36,0.25)',
        borderRadius: 2,
      }}
    >
      {/* Corner brackets */}
      {(['tl', 'tr', 'bl', 'br'] as const).map((corner) => (
        <span
          key={corner}
          style={{
            position: 'absolute',
            width: 20,
            height: 20,
            borderColor: '#FBBF24',
            borderStyle: 'solid',
            borderWidth: 0,
            ...(corner === 'tl' && { top: -1, left: -1, borderTopWidth: 2, borderLeftWidth: 2 }),
            ...(corner === 'tr' && { top: -1, right: -1, borderTopWidth: 2, borderRightWidth: 2 }),
            ...(corner === 'bl' && { bottom: -1, left: -1, borderBottomWidth: 2, borderLeftWidth: 2 }),
            ...(corner === 'br' && { bottom: -1, right: -1, borderBottomWidth: 2, borderRightWidth: 2 }),
            animation: `ct-corner-flash 3.5s ease-in-out infinite ${corner === 'tr' || corner === 'bl' ? '1.75s' : '0s'}`,
          }}
        />
      ))}

      {/* Scanning line */}
      <div
        className="ct-scan-line"
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          height: 2,
          background:
            'linear-gradient(90deg, transparent 0%, rgba(251,191,36,0.6) 30%, rgba(251,191,36,0.9) 50%, rgba(251,191,36,0.6) 70%, transparent 100%)',
          boxShadow: '0 0 12px 2px rgba(251,191,36,0.35)',
        }}
      />
    </div>

    {/* Marker 1 — yellow */}
    <div
      className="ct-pulse"
      style={{ position: 'absolute', top: '31%', left: '28%' }}
    >
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: '#FBBF24',
          boxShadow: '0 0 0 3px rgba(251,191,36,0.2)',
        }}
      />
    </div>

    {/* Marker 2 — red defect */}
    <div
      style={{
        position: 'absolute',
        top: '44%',
        left: '40%',
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: '#F87171',
        boxShadow: '0 0 0 3px rgba(248,113,113,0.2)',
        animation: 'ct-pulse-ring 2.5s ease-in-out infinite 1.2s',
      }}
    />

    {/* Marker 3 — green pass */}
    <div
      style={{
        position: 'absolute',
        top: '55%',
        left: '19%',
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: '#34D399',
        boxShadow: '0 0 0 3px rgba(52,211,153,0.2)',
        animation: 'ct-pulse-ring 2.5s ease-in-out infinite 0.7s',
      }}
    />

    {/* Surface defect callout panel */}
    <div
      style={{
        position: 'absolute',
        top: '10%',
        right: '3%',
        width: 180,
        background: 'rgba(16,18,22,0.90)',
        border: '1px solid rgba(251,191,36,0.35)',
        borderRadius: 8,
        padding: '10px 12px',
        backdropFilter: 'blur(8px)',
        animation: 'ct-fadeup 1.2s cubic-bezier(0.22,1,0.36,1) 0.6s both',
      }}
    >
      <div
        style={{
          width: '100%',
          height: 70,
          borderRadius: 4,
          background: 'linear-gradient(135deg, #1D232D 0%, #252C37 100%)',
          marginBottom: 8,
          overflow: 'hidden',
          position: 'relative',
          border: '1px solid rgba(251,191,36,0.15)',
        }}
      >
        {[20, 35, 50, 62].map((top) => (
          <div
            key={top}
            style={{
              position: 'absolute',
              top: `${top}%`,
              left: '5%',
              width: `${60 + Math.sin(top) * 25}%`,
              height: 1,
              background: `rgba(251,191,36,${0.08 + Math.sin(top) * 0.04})`,
              borderRadius: 1,
            }}
          />
        ))}
        <div
          style={{
            position: 'absolute',
            top: '30%',
            left: '45%',
            width: 22,
            height: 14,
            border: '1.5px solid rgba(251,191,36,0.7)',
            borderRadius: 2,
          }}
        />
        <div
          style={{
            position: 'absolute',
            bottom: 6,
            right: 8,
            fontSize: 9,
            color: '#FBBF24',
            fontFamily: 'DM Sans, sans-serif',
            letterSpacing: '0.05em',
            fontWeight: 600,
          }}
        >
          DEMO
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3 }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#FBBF24', flexShrink: 0 }} />
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: '#F5F5F5',
            fontFamily: 'Manrope, sans-serif',
          }}
        >
          Surface Porosity
        </span>
      </div>
      <div style={{ fontSize: 9, color: '#A8B0BD', fontFamily: 'DM Sans, sans-serif' }}>
        Confidence:{' '}
        <span style={{ color: '#FBBF24', fontWeight: 600 }}>96%</span>
        &nbsp;&nbsp;
        <span style={{ color: '#6B7280', fontStyle: 'italic' }}>illustrative</span>
      </div>
    </div>

    {/* Batch info ribbon */}
    <div
      style={{
        position: 'absolute',
        bottom: '8%',
        right: '3%',
        width: 180,
        background: 'rgba(16,18,22,0.85)',
        border: '1px solid rgba(148,163,184,0.15)',
        borderRadius: 8,
        padding: '9px 12px',
        backdropFilter: 'blur(6px)',
        animation: 'ct-fadeup 1.2s cubic-bezier(0.22,1,0.36,1) 0.9s both',
      }}
    >
      {[
        { label: 'Batch', value: 'IMP-2025-0847', color: '#F5F5F5' },
        { label: 'Status', value: 'In Inspection', color: '#FBBF24' },
        { label: 'Defects', value: '2 flagged', color: '#F87171' },
      ].map(({ label, value, color }) => (
        <div key={label} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 9, color: '#6B7280', fontFamily: 'DM Sans, sans-serif', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {label}
          </span>
          <span style={{ fontSize: 9, color, fontFamily: 'DM Sans, sans-serif', fontWeight: 600 }}>
            {value}
          </span>
        </div>
      ))}
      <div style={{ borderTop: '1px solid rgba(148,163,184,0.1)', marginTop: 4, paddingTop: 4 }}>
        <span style={{ fontSize: 8, color: '#6B7280', fontFamily: 'DM Sans, sans-serif', fontStyle: 'italic' }}>
          Illustrative demo data
        </span>
      </div>
    </div>
  </div>
);

/* ─────────────────────────────────────────────────────────────
   Main LoginPage Component
───────────────────────────────────────────────────────────── */
export const LoginPage: React.FC = () => {
  const { login, isLoading } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const usernameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    usernameRef.current?.focus();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setAuthError(null);
    try {
      await login(username.trim(), password);
    } catch (err: any) {
      setAuthError(err?.message || 'Invalid username or password. Please try again.');
    }
  };

  const handleQuickLogin = async (user: string, pass: string) => {
    setUsername(user);
    setPassword(pass);
    setAuthError(null);
    try {
      await login(user, pass);
    } catch (err: any) {
      setAuthError(err?.message || 'Quick sign-in failed. Please try again.');
    }
  };

  const capabilities = [
    { icon: <Scan size={13} />, label: 'AI Inspection', sub: 'Detect defects with precision' },
    { icon: <Layers size={13} />, label: 'Traceability', sub: 'From batch to component' },
    { icon: <GitBranch size={13} />, label: 'Release Gates', sub: 'Rule-based quality approval' },
    { icon: <BarChart2 size={13} />, label: 'Compliance', sub: 'Audit-ready records' },
  ];

  const personas = [
    { label: 'Inspector', sub: 'chen', icon: <Eye size={13} />, color: '#22D3EE', user: 'inspector_chen', pass: 'Password123!' },
    { label: 'Supervisor', sub: 'torres', icon: <Wrench size={13} />, color: '#FBBF24', user: 'supervisor_torres', pass: 'Password123!' },
    { label: 'Quality Mgr', sub: 'reynolds', icon: <ShieldCheck size={13} />, color: '#A78BFA', user: 'qm_reynolds', pass: 'Password123!' },
  ];

  return (
    <div
      role="main"
      style={{
        minHeight: '100vh',
        width: '100%',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        backgroundColor: '#101216',
        fontFamily: "'DM Sans', system-ui, sans-serif",
      }}
    >
      {/* Background impeller image with slow float */}
      <div
        aria-hidden="true"
        className="ct-float"
        style={{
          position: 'absolute',
          inset: '-5%',
          backgroundImage: 'url(/impeller-bg.jpg)',
          backgroundSize: 'cover',
          backgroundPosition: 'center 40%',
          zIndex: 0,
        }}
      />

      {/* Dark gradient overlay */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'linear-gradient(135deg, rgba(16,18,22,0.97) 0%, rgba(16,18,22,0.82) 45%, rgba(16,18,22,0.65) 70%, rgba(16,18,22,0.80) 100%)',
          zIndex: 1,
        }}
      />

      {/* Edge vignette */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          background: 'radial-gradient(ellipse at center, transparent 40%, rgba(16,18,22,0.70) 100%)',
          zIndex: 2,
        }}
      />

      {/* Ambient warm glow */}
      <div
        aria-hidden="true"
        className="ct-breathe"
        style={{
          position: 'absolute',
          right: '10%',
          top: '20%',
          width: '45%',
          height: '60%',
          background: 'radial-gradient(ellipse, rgba(251,191,36,0.07) 0%, transparent 70%)',
          zIndex: 3,
          pointerEvents: 'none',
        }}
      />

      {/* Page content */}
      <div style={{ position: 'relative', zIndex: 10, display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>

        {/* HEADER */}
        <header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '18px 32px',
            borderBottom: '1px solid rgba(148,163,184,0.08)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <CastTraceMark size={32} />
            <span
              style={{
                fontFamily: "'Manrope', sans-serif",
                fontWeight: 700,
                fontSize: 17,
                color: '#F5F5F5',
                letterSpacing: '-0.01em',
              }}
            >
              CastTrace AI
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {(['QUALITY', 'TRACEABILITY', 'COMPLIANCE'] as const).map((label, i) => (
              <React.Fragment key={label}>
                {i > 0 && (
                  <span style={{ fontSize: 8, color: '#374151', margin: '0 2px' }}>•</span>
                )}
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 600,
                    letterSpacing: '0.12em',
                    color: '#4B5563',
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
                fontSize: 9,
                color: '#374151',
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

        {/* MAIN THREE-COLUMN GRID */}
        <main
          className="login-grid"
          style={{
            flex: 1,
            display: 'grid',
            gridTemplateColumns: 'minmax(0,1fr) minmax(0,420px) minmax(0,1fr)',
            alignItems: 'center',
            padding: '32px 24px',
          }}
        >
          {/* LEFT HERO */}
          <div
            className="ct-hero-enter"
            style={{ padding: '0 24px 0 32px', opacity: 0 }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 24 }}>
              <div style={{ width: 28, height: 1, background: '#FBBF24' }} />
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 600,
                  letterSpacing: '0.18em',
                  color: '#FBBF24',
                  fontFamily: "'DM Sans', sans-serif",
                  textTransform: 'uppercase',
                }}
              >
                Pump Impeller Quality Inspection
              </span>
            </div>

            <h1
              style={{
                fontFamily: "'Manrope', sans-serif",
                fontWeight: 800,
                fontSize: 'clamp(36px, 4.5vw, 60px)',
                lineHeight: 1.08,
                margin: '0 0 24px',
                letterSpacing: '-0.03em',
                color: '#F5F5F5',
              }}
            >
              Every
              <br />
              <em
                style={{
                  fontFamily: "'Instrument Serif', Georgia, serif",
                  fontStyle: 'italic',
                  fontWeight: 400,
                  color: '#FBBF24',
                }}
              >
                component
              </em>
              <br />
              tells a story.
            </h1>

            <p
              style={{
                fontSize: 15,
                color: '#A8B0BD',
                lineHeight: 1.65,
                margin: '0 0 32px',
                maxWidth: 360,
                fontFamily: "'DM Sans', sans-serif",
                fontWeight: 400,
              }}
            >
              AI-assisted inspection, traceability and release governance for manufactured cast pump impellers.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, maxWidth: 380 }}>
              {capabilities.map(({ icon, label, sub }) => (
                <div
                  key={label}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    padding: '10px 12px',
                    background: 'rgba(37,44,55,0.60)',
                    border: '1px solid rgba(148,163,184,0.12)',
                    borderRadius: 8,
                    backdropFilter: 'blur(4px)',
                  }}
                >
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: 6,
                      background: 'rgba(251,191,36,0.10)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                      color: '#FBBF24',
                      marginTop: 1,
                    }}
                  >
                    {icon}
                  </div>
                  <div>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                        color: '#F5F5F5',
                        fontFamily: "'Manrope', sans-serif",
                        marginBottom: 2,
                      }}
                    >
                      {label}
                    </div>
                    <div style={{ fontSize: 10, color: '#6B7280', fontFamily: "'DM Sans', sans-serif", lineHeight: 1.4 }}>
                      {sub}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* CENTER SIGN-IN PANEL */}
          <div
            className="ct-panel-enter"
            style={{ opacity: 0, animationDelay: '0.15s', padding: '0 8px' }}
          >
            <div
              style={{
                background: 'rgba(29,35,45,0.88)',
                border: '1px solid rgba(148,163,184,0.18)',
                borderRadius: 16,
                padding: '32px 28px',
                backdropFilter: 'blur(20px)',
                boxShadow: '0 32px 80px rgba(0,0,0,0.55), inset 0 0 0 1px rgba(251,191,36,0.05)',
              }}
            >
              {/* Panel brand */}
              <div style={{ textAlign: 'center', marginBottom: 28 }}>
                <div style={{ display: 'inline-flex', marginBottom: 14 }}>
                  <CastTraceMark size={40} />
                </div>
                <div
                  style={{
                    fontFamily: "'Manrope', sans-serif",
                    fontWeight: 700,
                    fontSize: 20,
                    color: '#F5F5F5',
                    letterSpacing: '-0.02em',
                    marginBottom: 4,
                  }}
                >
                  CastTrace AI
                </div>
                <div
                  style={{
                    fontSize: 10,
                    color: '#6B7280',
                    fontFamily: "'DM Sans', sans-serif",
                    letterSpacing: '0.12em',
                    textTransform: 'uppercase',
                    fontWeight: 500,
                  }}
                >
                  Pump Impeller Manufacturing QA
                </div>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} noValidate>
                {/* Username */}
                <div style={{ marginBottom: 14 }}>
                  <label
                    htmlFor="login-username"
                    style={{
                      display: 'block',
                      fontSize: 10,
                      fontWeight: 600,
                      color: '#A8B0BD',
                      letterSpacing: '0.12em',
                      textTransform: 'uppercase',
                      marginBottom: 7,
                      fontFamily: "'DM Sans', sans-serif",
                    }}
                  >
                    Username
                  </label>
                  <div style={{ position: 'relative' }}>
                    <span
                      style={{
                        position: 'absolute',
                        left: 13,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        color: '#4B5563',
                        display: 'flex',
                        pointerEvents: 'none',
                      }}
                    >
                      <UserIcon size={15} />
                    </span>
                    <input
                      id="login-username"
                      ref={usernameRef}
                      type="text"
                      value={username}
                      onChange={(e) => { setUsername(e.target.value); setAuthError(null); }}
                      placeholder="e.g. qm_reynolds"
                      autoComplete="username"
                      required
                      aria-required="true"
                      aria-describedby={authError ? 'login-error' : undefined}
                      className="ct-input"
                    />
                  </div>
                </div>

                {/* Password */}
                <div style={{ marginBottom: 20 }}>
                  <label
                    htmlFor="login-password"
                    style={{
                      display: 'block',
                      fontSize: 10,
                      fontWeight: 600,
                      color: '#A8B0BD',
                      letterSpacing: '0.12em',
                      textTransform: 'uppercase',
                      marginBottom: 7,
                      fontFamily: "'DM Sans', sans-serif",
                    }}
                  >
                    Password
                  </label>
                  <div style={{ position: 'relative' }}>
                    <span
                      style={{
                        position: 'absolute',
                        left: 13,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        color: '#4B5563',
                        display: 'flex',
                        pointerEvents: 'none',
                      }}
                    >
                      <Lock size={15} />
                    </span>
                    <input
                      id="login-password"
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => { setPassword(e.target.value); setAuthError(null); }}
                      placeholder="••••••••••••"
                      autoComplete="current-password"
                      required
                      aria-required="true"
                      className="ct-input"
                      style={{ paddingRight: 42 }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      className="ct-eye-btn"
                    >
                      {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>

                {/* Error */}
                {authError && (
                  <div
                    id="login-error"
                    role="alert"
                    style={{
                      marginBottom: 14,
                      padding: '9px 12px',
                      borderRadius: 8,
                      background: 'rgba(248,113,113,0.08)',
                      border: '1px solid rgba(248,113,113,0.25)',
                      fontSize: 12,
                      color: '#FCA5A5',
                      fontFamily: "'DM Sans', sans-serif",
                      lineHeight: 1.5,
                    }}
                  >
                    {authError}
                  </div>
                )}

                {/* Submit */}
                <button
                  id="login-submit-btn"
                  type="submit"
                  disabled={isLoading || !username.trim() || !password}
                  aria-busy={isLoading}
                  className="ct-submit-btn"
                >
                  {isLoading ? (
                    <Loader2 size={16} className="ct-spin" />
                  ) : (
                    <ArrowRight size={16} />
                  )}
                  {isLoading ? 'Authenticating\u2026' : 'Sign In to QA Station'}
                </button>
              </form>

              {/* Quick login personas */}
              <div style={{ marginTop: 22, borderTop: '1px solid rgba(148,163,184,0.10)', paddingTop: 20 }}>
                <div
                  style={{
                    textAlign: 'center',
                    fontSize: 9,
                    color: '#4B5563',
                    letterSpacing: '0.14em',
                    textTransform: 'uppercase',
                    fontFamily: "'DM Sans', sans-serif",
                    fontWeight: 600,
                    marginBottom: 12,
                  }}
                >
                  Quick Sign-In by Persona
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                  {personas.map(({ label, sub, icon, color, user, pass }) => (
                    <button
                      key={label}
                      type="button"
                      id={`persona-${label.toLowerCase().replace(/\s/g, '-')}`}
                      disabled={isLoading}
                      onClick={() => handleQuickLogin(user, pass)}
                      className="ct-persona-btn"
                      data-hcolor={color}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3, color }}>
                        {icon}
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            fontFamily: "'Manrope', sans-serif",
                          }}
                        >
                          {label}
                        </span>
                      </div>
                      <div
                        style={{
                          fontSize: 9,
                          color: '#6B7280',
                          fontFamily: 'monospace',
                          letterSpacing: '0.02em',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {sub}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT VISUAL COLUMN */}
          <div
            style={{
              position: 'relative',
              height: '100%',
              minHeight: 400,
            }}
          >
            <InspectionOverlay />
          </div>
        </main>

        {/* FOOTER */}
        <footer
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 32px',
            borderTop: '1px solid rgba(148,163,184,0.07)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 20, height: 1, background: '#FBBF24', opacity: 0.6 }} />
            <span
              style={{
                fontSize: 9,
                color: '#374151',
                fontFamily: "'DM Sans', sans-serif",
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                fontWeight: 600,
              }}
            >
              Built for modern manufacturing
            </span>
          </div>
          <div
            style={{
              fontSize: 9,
              color: '#374151',
              fontFamily: 'monospace',
              letterSpacing: '0.06em',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <span>FastAPI · SQLAlchemy 2 · RBAC · SQLite</span>
            <ChevronRight size={10} style={{ opacity: 0.4 }} />
            <span>v2.0</span>
          </div>
        </footer>
      </div>

      {/* Scoped styles */}
      <style>{`
        @keyframes ct-spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        @keyframes ct-corner-flash {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.3; }
        }
        @keyframes ct-fadeup {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }

        .ct-spin { animation: ct-spin 1s linear infinite; }

        .ct-input {
          width: 100%;
          box-sizing: border-box;
          padding: 10px 14px 10px 38px;
          border-radius: 10px;
          background: rgba(16,18,22,0.70);
          border: 1px solid rgba(148,163,184,0.18);
          color: #F5F5F5;
          font-size: 14px;
          font-family: 'DM Sans', sans-serif;
          outline: none;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .ct-input:focus {
          border-color: #FBBF24;
          box-shadow: 0 0 0 2px rgba(251,191,36,0.15);
        }
        .ct-input::placeholder { color: #374151; }
        .ct-input:-webkit-autofill {
          -webkit-box-shadow: 0 0 0 100px #101216 inset !important;
          -webkit-text-fill-color: #F5F5F5 !important;
        }

        .ct-eye-btn {
          position: absolute;
          right: 12px;
          top: 50%;
          transform: translateY(-50%);
          background: none;
          border: none;
          cursor: pointer;
          color: #6B7280;
          display: flex;
          align-items: center;
          padding: 2px;
          transition: color 0.15s;
        }
        .ct-eye-btn:hover { color: #FBBF24; }

        .ct-submit-btn {
          width: 100%;
          padding: 11px 20px;
          border-radius: 10px;
          background: #FBBF24;
          border: none;
          color: #101216;
          font-size: 14px;
          font-weight: 700;
          font-family: 'Manrope', sans-serif;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          transition: background 0.2s, transform 0.1s, box-shadow 0.2s, opacity 0.2s;
          box-shadow: 0 4px 20px rgba(251,191,36,0.20);
          letter-spacing: 0.01em;
        }
        .ct-submit-btn:hover:not(:disabled) {
          background: #FCD34D;
          box-shadow: 0 6px 28px rgba(251,191,36,0.35);
        }
        .ct-submit-btn:active:not(:disabled) { transform: scale(0.985); }
        .ct-submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }

        .ct-persona-btn {
          padding: 9px 8px;
          border-radius: 8px;
          background: rgba(16,18,22,0.60);
          border: 1px solid rgba(148,163,184,0.12);
          cursor: pointer;
          text-align: left;
          transition: border-color 0.2s, background 0.2s, opacity 0.2s;
        }
        .ct-persona-btn:hover:not(:disabled) {
          background: rgba(37,44,55,0.60);
          border-color: rgba(251,191,36,0.45);
        }
        .ct-persona-btn:disabled { opacity: 0.55; cursor: not-allowed; }

        /* Responsive */
        @media (max-width: 1024px) {
          .login-grid {
            grid-template-columns: 1fr minmax(0,400px) !important;
            padding: 24px 16px !important;
          }
          .login-grid > div:last-child { display: none !important; }
        }
        @media (max-width: 640px) {
          .login-grid {
            grid-template-columns: 1fr !important;
            padding: 16px 12px !important;
            gap: 24px !important;
          }
          .login-grid > div:first-child { padding: 0 !important; }
          .login-grid > div:last-child { display: none !important; }
        }
      `}</style>
    </div>
  );
};

export default LoginPage;
