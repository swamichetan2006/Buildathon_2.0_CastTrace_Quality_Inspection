import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { batchesApi } from '../api/batches';
import { inspectionsApi } from '../api/inspections';
import { defectsApi } from '../api/defects';
import { capaApi } from '../api/capa';
import { QualityIntelligencePanel } from '../components/dashboard/QualityIntelligencePanel';
import {
  Layers,
  FileCheck2,
  AlertOctagon,
  Wrench,
  ShieldCheck,
  ArrowRight,
  Clock,
  TrendingUp,
  CheckCircle2,
  BarChart2,
  CalendarDays,
} from 'lucide-react';

interface DashboardPageProps {
  onNavigate: (tab: string, contextId?: string, extraId?: string) => void;
}

/* ── Tiny helpers ────────────────────────────────────── */
const fmt = (d: string) =>
  new Date(d).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

const severityLabel: Record<string, string> = {
  CRITICAL: 'Critical',
  MAJOR: 'Major',
  MINOR: 'Medium',
};
const severityColor: Record<string, { bg: string; text: string }> = {
  CRITICAL: { bg: '#FEE2E2', text: '#DC2626' },
  MAJOR:    { bg: '#FEF3C7', text: '#D97706' },
  MINOR:    { bg: '#DBEAFE', text: '#2563EB' },
};
const defectStatusStyle: Record<string, { bg: string; text: string }> = {
  OPEN:                 { bg: '#FEE2E2', text: '#DC2626' },
  ACTION_ASSIGNED:      { bg: '#DBEAFE', text: '#2563EB' },
  IN_PROGRESS:          { bg: '#FEF3C7', text: '#D97706' },
  PENDING_REINSPECTION: { bg: '#FEF3C7', text: '#D97706' },
  REOPENED:             { bg: '#FEE2E2', text: '#DC2626' },
  RESOLVED:             { bg: '#DCFCE7', text: '#16A34A' },
};
const defectStatusLabel: Record<string, string> = {
  OPEN:                 'Open',
  ACTION_ASSIGNED:      'Assigned',
  IN_PROGRESS:          'In Progress',
  PENDING_REINSPECTION: 'Reinspect',
  REOPENED:             'Reopened',
  RESOLVED:             'Resolved',
};

/* ── KPI Card ────────────────────────────────────────── */
const KpiCard: React.FC<{
  label: string;
  value: number | string;
  icon: React.ReactNode;
  caption?: React.ReactNode;
  onClick?: () => void;
  accentColor?: string;
}> = ({ label, value, icon, caption, onClick, accentColor = '#FBBF24' }) => (
  <div
    onClick={onClick}
    role={onClick ? 'button' : undefined}
    tabIndex={onClick ? 0 : undefined}
    onKeyDown={onClick ? (e) => e.key === 'Enter' && onClick() : undefined}
    style={{
      backgroundColor: '#FFFFFF',
      border: '1px solid #E7EAE8',
      borderRadius: 14,
      padding: '20px 22px',
      cursor: onClick ? 'pointer' : 'default',
      transition: 'box-shadow 0.18s, border-color 0.18s',
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
    }}
    onMouseEnter={e => {
      if (onClick) {
        (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 18px rgba(0,0,0,0.06)';
        (e.currentTarget as HTMLElement).style.borderColor = '#D0D5D0';
      }
    }}
    onMouseLeave={e => {
      (e.currentTarget as HTMLElement).style.boxShadow = 'none';
      (e.currentTarget as HTMLElement).style.borderColor = '#E7EAE8';
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span style={{
        fontSize: 12,
        fontWeight: 600,
        color: '#64748B',
        fontFamily: "'DM Sans', sans-serif",
        letterSpacing: '0.02em',
      }}>
        {label}
      </span>
      <div style={{
        width: 32,
        height: 32,
        borderRadius: 8,
        backgroundColor: `${accentColor}18`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: accentColor,
        flexShrink: 0,
      }}>
        {icon}
      </div>
    </div>
    <div style={{
      fontFamily: "'Manrope', sans-serif",
      fontWeight: 800,
      fontSize: 30,
      color: '#142033',
      lineHeight: 1,
      letterSpacing: '-0.02em',
    }}>
      {value}
    </div>
    {caption && (
      <div style={{
        fontSize: 11,
        fontFamily: "'DM Sans', sans-serif",
        color: '#8A96A8',
        lineHeight: 1.4,
      }}>
        {caption}
      </div>
    )}
  </div>
);

/* ── Inspection bar chart (pure CSS/SVG, no extra lib) ── */
const InspectionBarChart: React.FC<{ inspections: any[] }> = ({ inspections }) => {
  /* Group by day over last 7 records */
  const last = inspections.slice(-28);
  const days: Record<string, number> = {};
  last.forEach(i => {
    const day = new Date(i.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    days[day] = (days[day] || 0) + 1;
  });
  const entries = Object.entries(days).slice(-7);
  const maxVal = Math.max(...entries.map(e => e[1]), 1);

  if (entries.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 180, color: '#8A96A8' }}>
        <BarChart2 size={32} style={{ marginBottom: 8, opacity: 0.4 }} />
        <div style={{ fontSize: 13, fontFamily: "'DM Sans', sans-serif" }}>No inspection activity yet</div>
        <div style={{ fontSize: 11, fontFamily: "'DM Sans', sans-serif", color: '#B0BAC8', marginTop: 4 }}>
          Activity will appear when inspection records are available
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 180, gap: 8 }}>
      {/* Y-axis scale */}
      <div style={{ display: 'flex', flex: 1, gap: 10, alignItems: 'flex-end' }}>
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%', paddingBottom: 20 }}>
          {[maxVal, Math.round(maxVal * 0.5), 0].map(v => (
            <span key={v} style={{ fontSize: 9, color: '#B0BAC8', fontFamily: "'DM Sans', sans-serif", lineHeight: 1 }}>{v}</span>
          ))}
        </div>
        {/* Bars */}
        <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', gap: 6, position: 'relative' }}>
          {/* Grid lines */}
          {[0, 0.5, 1].map(pct => (
            <div key={pct} style={{
              position: 'absolute',
              left: 0,
              right: 0,
              bottom: `calc(${pct * 100}% + 20px)`,
              borderTop: '1px dashed #E7EAE8',
              pointerEvents: 'none',
            }} />
          ))}
          {entries.map(([day, count]) => (
            <div key={day} style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 4,
              minWidth: 0,
            }}>
              <div
                style={{
                  width: '70%',
                  height: `${(count / maxVal) * 140}px`,
                  backgroundColor: '#FBBF24',
                  borderRadius: '4px 4px 0 0',
                  transition: 'height 0.3s ease',
                  minHeight: 4,
                  position: 'relative',
                }}
                title={`${count} inspections`}
              >
                {count > 0 && (
                  <div style={{
                    position: 'absolute',
                    top: -16,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    fontSize: 9,
                    color: '#64748B',
                    fontFamily: "'DM Sans', sans-serif",
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                  }}>
                    {count}
                  </div>
                )}
              </div>
              <span style={{
                fontSize: 9,
                color: '#8A96A8',
                fontFamily: "'DM Sans', sans-serif",
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                maxWidth: '100%',
              }}>
                {day}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingLeft: 24 }}>
        <div style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: '#FBBF24' }} />
        <span style={{ fontSize: 10, color: '#8A96A8', fontFamily: "'DM Sans', sans-serif" }}>Inspections per day</span>
      </div>
    </div>
  );
};

/* ── Release Readiness donut (pure SVG) ── */
const ReleaseReadinessChart: React.FC<{
  released: number;
  onHold: number;
  pending: number;
}> = ({ released, onHold, pending }) => {
  const total = released + onHold + pending;
  if (total === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 160, color: '#8A96A8' }}>
        <ShieldCheck size={28} style={{ marginBottom: 8, opacity: 0.4 }} />
        <div style={{ fontSize: 12, fontFamily: "'DM Sans', sans-serif" }}>No batch data</div>
      </div>
    );
  }

  const releasedPct = Math.round((released / total) * 100);
  const onHoldPct = Math.round((onHold / total) * 100);
  const pendingPct = Math.round((pending / total) * 100);

  /* SVG donut */
  const r = 52;
  const cx = 70;
  const cy = 70;
  const strokeW = 14;
  const circ = 2 * Math.PI * r;

  const segments = [
    { pct: releasedPct / 100, color: '#16A34A', label: 'Ready for release', count: released, pctLabel: releasedPct },
    { pct: pendingPct / 100,  color: '#D97706', label: 'In review',          count: pending,  pctLabel: pendingPct },
    { pct: onHoldPct / 100,   color: '#DC2626', label: 'On hold',            count: onHold,   pctLabel: onHoldPct },
  ];

  let cumulative = 0;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
      {/* SVG Donut */}
      <div style={{ position: 'relative', flexShrink: 0 }}>
        <svg width={140} height={140} viewBox="0 0 140 140">
          {/* Background ring */}
          <circle cx={cx} cy={cy} r={r} fill="none" stroke="#F1F3F1" strokeWidth={strokeW} />
          {/* Segments */}
          {segments.map((seg, i) => {
            const offset = circ * (1 - cumulative);
            const dashLen = circ * seg.pct;
            const el = (
              <circle
                key={i}
                cx={cx} cy={cy} r={r}
                fill="none"
                stroke={seg.color}
                strokeWidth={strokeW}
                strokeDasharray={`${dashLen} ${circ - dashLen}`}
                strokeDashoffset={offset}
                strokeLinecap="butt"
                style={{ transform: 'rotate(-90deg)', transformOrigin: `${cx}px ${cy}px` }}
              />
            );
            cumulative += seg.pct;
            return el;
          })}
        </svg>
        {/* Center label */}
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%,-50%)',
          textAlign: 'center',
        }}>
          <div style={{
            fontFamily: "'Manrope', sans-serif",
            fontWeight: 800,
            fontSize: 22,
            color: '#142033',
            lineHeight: 1,
          }}>
            {releasedPct}%
          </div>
          <div style={{
            fontSize: 9,
            color: '#8A96A8',
            fontFamily: "'DM Sans', sans-serif",
            marginTop: 2,
            lineHeight: 1.2,
          }}>
            Ready<br />for Release
          </div>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, flex: 1 }}>
        {segments.map(seg => (
          <div key={seg.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: seg.color, flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: '#64748B', fontFamily: "'DM Sans', sans-serif" }}>{seg.label}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: '#142033', fontFamily: "'Manrope', sans-serif" }}>
                {seg.count}
              </span>
              <span style={{ fontSize: 11, color: '#8A96A8', fontFamily: "'DM Sans', sans-serif", minWidth: 28, textAlign: 'right' }}>
                {seg.pctLabel}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/* ── Status pill ── */
const StatusPill: React.FC<{ status: string }> = ({ status }) => {
  const s = defectStatusStyle[status] || { bg: '#F1F3F1', text: '#64748B' };
  const l = defectStatusLabel[status] || status.replace(/_/g, ' ');
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '3px 8px',
      borderRadius: 5,
      fontSize: 10,
      fontWeight: 600,
      fontFamily: "'DM Sans', sans-serif",
      backgroundColor: s.bg,
      color: s.text,
      whiteSpace: 'nowrap',
    }}>
      {l}
    </span>
  );
};

const SeverityPill: React.FC<{ severity: string }> = ({ severity }) => {
  const s = severityColor[severity] || { bg: '#F1F3F1', text: '#64748B' };
  const l = severityLabel[severity] || severity;
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '3px 8px',
      borderRadius: 5,
      fontSize: 10,
      fontWeight: 600,
      fontFamily: "'DM Sans', sans-serif",
      backgroundColor: s.bg,
      color: s.text,
      whiteSpace: 'nowrap',
    }}>
      {l}
    </span>
  );
};

/* ── Card wrapper ── */
const Card: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ children, style }) => (
  <div style={{
    backgroundColor: '#FFFFFF',
    border: '1px solid #E7EAE8',
    borderRadius: 14,
    ...style,
  }}>
    {children}
  </div>
);

/* ── Card header ── */
const CardHeader: React.FC<{
  title: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}> = ({ title, icon, action }) => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '18px 22px 14px',
    borderBottom: '1px solid #F1F3F1',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {icon && <span style={{ color: '#8A96A8' }}>{icon}</span>}
      <h3 style={{
        fontFamily: "'Manrope', sans-serif",
        fontWeight: 700,
        fontSize: 14,
        color: '#142033',
        margin: 0,
        letterSpacing: '-0.01em',
      }}>
        {title}
      </h3>
    </div>
    {action}
  </div>
);

/* ── View all link ── */
const ViewAll: React.FC<{ onClick: () => void; label?: string }> = ({ onClick, label = 'View all' }) => (
  <button
    onClick={onClick}
    style={{
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      fontSize: 12,
      color: '#B77900',
      fontFamily: "'DM Sans', sans-serif",
      fontWeight: 600,
      display: 'flex',
      alignItems: 'center',
      gap: 4,
      padding: 0,
      transition: 'color 0.15s',
    }}
    onMouseEnter={e => { e.currentTarget.style.color = '#D97706'; }}
    onMouseLeave={e => { e.currentTarget.style.color = '#B77900'; }}
  >
    {label} <ArrowRight size={13} />
  </button>
);

/* ─────────────────────────────────────────────────────
   Main DashboardPage
────────────────────────────────────────────────────── */
export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate }) => {
  const { data: batches = [], isLoading: batchLoading } = useQuery({
    queryKey: ['batches-list'],
    queryFn: () => batchesApi.list(),
  });

  const { data: inspections = [], isLoading: inspLoading } = useQuery({
    queryKey: ['inspections-list'],
    queryFn: () => inspectionsApi.list(),
  });

  const { data: defectsData, isLoading: defLoading } = useQuery({
    queryKey: ['defects-list'],
    queryFn: () => defectsApi.list(),
  });

  const { data: capaData } = useQuery({
    queryKey: ['capa-list'],
    queryFn: () => capaApi.list(),
  });

  const defects = defectsData?.items || [];
  const capas = capaData?.items || [];

  /* Derived metrics */
  const heldBatches = batches.filter(b => b.status === 'ON_HOLD');
  const releasedBatches = batches.filter(b => b.status === 'RELEASED');
  const pendingBatches = batches.filter(b => b.status === 'PENDING' || b.status === 'IN_PRODUCTION');
  const openDefects = defects.filter(d => d.status === 'OPEN' || d.status === 'REOPENED');
  const activeCAPAs = capas.filter(c => c.status === 'OPEN' || c.status === 'IN_PROGRESS');
  const activeInspections = inspections.filter(i => i.status === 'DRAFT' || i.status === 'SUBMITTED' || i.status === 'IN_REVIEW');

  /* Open defects needing attention — for the table */
  const attentionDefects = defects
    .filter(d => d.status !== 'RESOLVED')
    .slice(0, 6);

  /* Recent activity derived from inspections + defects, sorted by date */
  type ActivityItem = { id: string; type: 'inspection' | 'defect' | 'capa' | 'batch'; label: string; sub: string; color: string; time: string; ts: number };
  const activity: ActivityItem[] = [
    ...inspections.slice(0, 8).map(i => ({
      id: i.id,
      type: 'inspection' as const,
      label: `Inspection ${i.status === 'COMPLETED' ? 'completed' : 'updated'}`,
      sub: `${i.inspection_number} · ${i.stage}`,
      color: i.status === 'COMPLETED' ? '#16A34A' : '#2563EB',
      time: fmt(i.created_at),
      ts: new Date(i.created_at).getTime(),
    })),
    ...defects.slice(0, 8).filter(d => d.status === 'OPEN' || d.status === 'REOPENED').map(d => ({
      id: d.id,
      type: 'defect' as const,
      label: d.status === 'REOPENED' ? 'Defect reopened' : 'Defect flagged',
      sub: `${d.defect_number} · ${d.category.replace(/_/g, ' ').toLowerCase()}`,
      color: '#DC2626',
      time: fmt(d.created_at),
      ts: new Date(d.created_at).getTime(),
    })),
    ...capas.slice(0, 4).map(c => ({
      id: c.id,
      type: 'capa' as const,
      label: 'CAPA updated',
      sub: `${c.action_number} · ${c.title.slice(0, 40)}`,
      color: '#D97706',
      time: fmt(c.created_at),
      ts: new Date(c.created_at).getTime(),
    })),
  ]
    .sort((a, b) => b.ts - a.ts)
    .slice(0, 8);

  const today = new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });

  const isLoading = batchLoading || inspLoading || defLoading;

  /* Loading skeleton */
  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24, animation: 'pulse 2s infinite' }}>
        {[64, 120, 220].map(h => (
          <div key={h} style={{
            height: h,
            borderRadius: 14,
            backgroundColor: '#F1F3F1',
          }} />
        ))}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, fontFamily: "'DM Sans', sans-serif" }}>

      {/* ── PAGE HEADING ──────────────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 16,
        flexWrap: 'wrap',
      }}>
        <div>
          {/* Eyebrow */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 8,
          }}>
            <div style={{ width: 20, height: 1.5, backgroundColor: '#FBBF24' }} />
            <span style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.14em',
              color: '#B77900',
              fontFamily: "'DM Sans', sans-serif",
              textTransform: 'uppercase',
            }}>
              Quality Operations
            </span>
          </div>
          {/* Headline */}
          <h1 style={{
            fontFamily: "'Manrope', sans-serif",
            fontWeight: 800,
            fontSize: 'clamp(24px, 3vw, 36px)',
            color: '#142033',
            margin: '0 0 8px',
            letterSpacing: '-0.025em',
            lineHeight: 1.15,
          }}>
            Quality keeps production{' '}
            <em style={{
              fontFamily: "'Instrument Serif', Georgia, serif",
              fontStyle: 'italic',
              fontWeight: 400,
              color: '#B77900',
            }}>
              moving.
            </em>
          </h1>
          <p style={{
            fontSize: 13,
            color: '#64748B',
            margin: 0,
            fontFamily: "'DM Sans', sans-serif",
            fontWeight: 400,
          }}>
            AI-assisted inspection and traceability for cast pump impellers.
          </p>
        </div>

        {/* Right controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
          {/* Date badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 14px',
            backgroundColor: '#FFFFFF',
            border: '1px solid #E7EAE8',
            borderRadius: 10,
          }}>
            <CalendarDays size={14} style={{ color: '#8A96A8', flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#142033', fontFamily: "'DM Sans', sans-serif" }}>{today}</div>
              <div style={{ fontSize: 10, color: '#8A96A8', fontFamily: "'DM Sans', sans-serif" }}>Day Shift (06:00 – 14:00)</div>
            </div>
          </div>
          {/* Primary action */}
          <button
            onClick={() => onNavigate('release-gates')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 18px',
              backgroundColor: '#FBBF24',
              border: 'none',
              borderRadius: 10,
              color: '#101216',
              fontSize: 13,
              fontWeight: 700,
              fontFamily: "'Manrope', sans-serif",
              cursor: 'pointer',
              transition: 'background 0.15s, box-shadow 0.15s',
              boxShadow: '0 2px 10px rgba(251,191,36,0.25)',
              whiteSpace: 'nowrap',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.backgroundColor = '#FCD34D';
              e.currentTarget.style.boxShadow = '0 4px 18px rgba(251,191,36,0.40)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.backgroundColor = '#FBBF24';
              e.currentTarget.style.boxShadow = '0 2px 10px rgba(251,191,36,0.25)';
            }}
          >
            <ShieldCheck size={15} />
            Review release gates
            <ArrowRight size={14} />
          </button>
        </div>
      </div>

      {/* ── KPI CARDS ─────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16 }} className="kpi-grid">
        <KpiCard
          label="Batches in Production"
          value={batches.length}
          icon={<Layers size={16} />}
          accentColor="#FBBF24"
          onClick={() => onNavigate('batches')}
          caption={
            heldBatches.length > 0 ? (
              <span style={{ color: '#D97706', fontWeight: 600 }}>{heldBatches.length} on hold</span>
            ) : (
              <span style={{ color: '#16A34A' }}>No holds active</span>
            )
          }
        />
        <KpiCard
          label="Active Inspections"
          value={activeInspections.length}
          icon={<FileCheck2 size={16} />}
          accentColor="#2563EB"
          onClick={() => onNavigate('inspections')}
          caption={<span>{inspections.length} total sessions</span>}
        />
        <KpiCard
          label="Open Defects"
          value={openDefects.length}
          icon={<AlertOctagon size={16} />}
          accentColor={openDefects.length > 0 ? '#DC2626' : '#16A34A'}
          onClick={() => onNavigate('defects')}
          caption={<span>{defects.length} cumulative</span>}
        />
        <KpiCard
          label="Active CAPAs"
          value={activeCAPAs.length}
          icon={<Wrench size={16} />}
          accentColor="#D97706"
          onClick={() => onNavigate('capa')}
          caption={
            <span>
              {capas.filter(c => c.verification_status === 'PENDING').length > 0
                ? <span style={{ color: '#D97706', fontWeight: 600 }}>{capas.filter(c => c.verification_status === 'PENDING').length} awaiting verification</span>
                : <span style={{ color: '#16A34A' }}>All verified</span>}
            </span>
          }
        />
      </div>

      {/* Quality Intelligence Assistant Panel */}
      <QualityIntelligencePanel
        batches={batches}
        onNavigateToIntelligence={(batchNumber, view) =>
          onNavigate('quality-intelligence', batchNumber, view)
        }
        onNavigate={onNavigate}
      />

      {/* ── CHARTS ROW ────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }} className="charts-grid">
        {/* Inspection Throughput */}
        <Card>
          <CardHeader
            title="Inspection Throughput"
            icon={<BarChart2 size={15} />}
            action={
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '5px 10px',
                backgroundColor: '#F7F8F6',
                border: '1px solid #E7EAE8',
                borderRadius: 7,
                fontSize: 11,
                color: '#64748B',
                fontFamily: "'DM Sans', sans-serif",
                fontWeight: 500,
              }}>
                <TrendingUp size={12} />
                Last 7 days
              </div>
            }
          />
          <div style={{ padding: '18px 22px' }}>
            <InspectionBarChart inspections={inspections} />
          </div>
        </Card>

        {/* Release Readiness */}
        <Card>
          <CardHeader
            title="Release Readiness"
            icon={<ShieldCheck size={15} />}
            action={<ViewAll onClick={() => onNavigate('release-gates')} />}
          />
          <div style={{ padding: '18px 22px' }}>
            <ReleaseReadinessChart
              released={releasedBatches.length}
              onHold={heldBatches.length}
              pending={pendingBatches.length}
            />
          </div>
        </Card>
      </div>

      {/* ── LOWER ROW ─────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }} className="lower-grid">

        {/* Inspections Requiring Attention */}
        <Card>
          <CardHeader
            title="Inspections Requiring Attention"
            icon={<AlertOctagon size={15} />}
            action={<ViewAll onClick={() => onNavigate('defects')} label="View all defects" />}
          />
          <div>
            {attentionDefects.length === 0 ? (
              <div style={{
                padding: '40px 22px',
                textAlign: 'center',
                color: '#8A96A8',
                fontFamily: "'DM Sans', sans-serif",
              }}>
                <CheckCircle2 size={28} style={{ marginBottom: 8, color: '#16A34A', opacity: 0.7 }} />
                <div style={{ fontSize: 13, fontWeight: 500 }}>No items requiring attention</div>
                <div style={{ fontSize: 11, marginTop: 4, color: '#B0BAC8' }}>All inspections are clear.</div>
              </div>
            ) : (
              <div>
                {/* Table head */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: '100px 1fr 110px 80px 80px 60px',
                  padding: '8px 22px',
                  borderBottom: '1px solid #F1F3F1',
                }}>
                  {['BATCH ID', 'DEFECT TYPE', 'SEVERITY', 'STATUS', 'ACTION', ''].map(h => (
                    <div key={h} style={{
                      fontSize: 9,
                      fontWeight: 700,
                      color: '#8A96A8',
                      letterSpacing: '0.09em',
                      fontFamily: "'DM Sans', sans-serif",
                      textTransform: 'uppercase',
                    }}>
                      {h}
                    </div>
                  ))}
                </div>
                {/* Rows */}
                {attentionDefects.map((d, idx) => (
                  <div
                    key={d.id}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '100px 1fr 110px 80px 80px 60px',
                      padding: '11px 22px',
                      borderBottom: idx < attentionDefects.length - 1 ? '1px solid #F7F8F6' : 'none',
                      alignItems: 'center',
                      transition: 'background 0.12s',
                      cursor: 'pointer',
                    }}
                    onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = '#FAFAFA'; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
                    onClick={() => onNavigate('defects')}
                  >
                    <div style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: '#142033',
                      fontFamily: "'DM Sans', sans-serif",
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {d.defect_number}
                    </div>
                    <div style={{
                      fontSize: 12,
                      color: '#64748B',
                      fontFamily: "'DM Sans', sans-serif",
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      paddingRight: 8,
                    }}>
                      {d.category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    </div>
                    <div><SeverityPill severity={d.severity} /></div>
                    <div><StatusPill status={d.status} /></div>
                    <div style={{ fontSize: 12, color: '#8A96A8', fontFamily: "'DM Sans', sans-serif" }}>
                      {fmtDate(d.created_at)}
                    </div>
                    <div>
                      <button
                        onClick={e => { e.stopPropagation(); onNavigate('defects'); }}
                        style={{
                          padding: '4px 10px',
                          borderRadius: 6,
                          border: '1px solid #E7EAE8',
                          backgroundColor: '#FFFFFF',
                          fontSize: 11,
                          color: '#64748B',
                          fontFamily: "'DM Sans', sans-serif",
                          cursor: 'pointer',
                          fontWeight: 500,
                          transition: 'border-color 0.12s, color 0.12s',
                          whiteSpace: 'nowrap',
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.borderColor = '#FBBF24';
                          e.currentTarget.style.color = '#B77900';
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.borderColor = '#E7EAE8';
                          e.currentTarget.style.color = '#64748B';
                        }}
                      >
                        View →
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader
            title="Recent Activity"
            icon={<Clock size={15} />}
            action={<ViewAll onClick={() => onNavigate('inspections')} label="View all activity" />}
          />
          <div style={{ padding: '0 0 8px' }}>
            {activity.length === 0 ? (
              <div style={{
                padding: '40px 22px',
                textAlign: 'center',
                color: '#8A96A8',
                fontFamily: "'DM Sans', sans-serif",
              }}>
                <Clock size={28} style={{ marginBottom: 8, opacity: 0.4 }} />
                <div style={{ fontSize: 13, fontWeight: 500 }}>No recent activity</div>
                <div style={{ fontSize: 11, marginTop: 4, color: '#B0BAC8' }}>Activity will appear as inspections run.</div>
              </div>
            ) : (
              activity.map((item, idx) => (
                <div
                  key={item.id + idx}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 12,
                    padding: '12px 22px',
                    borderBottom: idx < activity.length - 1 ? '1px solid #F7F8F6' : 'none',
                    transition: 'background 0.12s',
                    cursor: 'pointer',
                  }}
                  onClick={() => onNavigate(item.type === 'capa' ? 'capa' : item.type === 'defect' ? 'defects' : 'inspections')}
                  onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = '#FAFAFA'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
                >
                  {/* Status dot */}
                  <div style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: item.color,
                    flexShrink: 0,
                    marginTop: 4,
                  }} />
                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: '#142033',
                      fontFamily: "'DM Sans', sans-serif",
                      lineHeight: 1.3,
                    }}>
                      {item.label}
                    </div>
                    <div style={{
                      fontSize: 11,
                      color: '#8A96A8',
                      fontFamily: "'DM Sans', sans-serif",
                      marginTop: 2,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {item.sub}
                    </div>
                  </div>
                  {/* Time */}
                  <div style={{
                    fontSize: 11,
                    color: '#8A96A8',
                    fontFamily: "'DM Sans', sans-serif",
                    flexShrink: 0,
                  }}>
                    {item.time}
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      {/* Responsive overrides */}
      <style>{`
        @media (max-width: 1200px) {
          .kpi-grid { grid-template-columns: repeat(2,1fr) !important; }
        }
        @media (max-width: 900px) {
          .charts-grid, .lower-grid { grid-template-columns: 1fr !important; }
        }
        @media (max-width: 600px) {
          .kpi-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
};

export default DashboardPage;
