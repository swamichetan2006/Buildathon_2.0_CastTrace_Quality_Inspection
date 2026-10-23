import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { batchesApi } from '../api/batches';
import { inspectionsApi } from '../api/inspections';
import { defectsApi } from '../api/defects';
import { capaApi } from '../api/capa';
import { StatusBadge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { QualityIntelligencePanel } from '../components/dashboard/QualityIntelligencePanel';
import {
  Layers,
  FileCheck2,
  AlertOctagon,
  Wrench,
  ShieldCheck,
  PauseCircle,
  Clock,
  Sparkles,
} from 'lucide-react';

interface DashboardPageProps {
  onNavigate: (tab: string, contextId?: string, extraId?: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate }) => {
  const { user, isQualityManager } = useAuth();

  const { data: batches = [] } = useQuery({
    queryKey: ['batches-list'],
    queryFn: () => batchesApi.list(),
  });

  const { data: inspections = [] } = useQuery({
    queryKey: ['inspections-list'],
    queryFn: () => inspectionsApi.list(),
  });

  const { data: defectsData } = useQuery({
    queryKey: ['defects-list'],
    queryFn: () => defectsApi.list(),
  });

  const { data: capaData } = useQuery({
    queryKey: ['capa-list'],
    queryFn: () => capaApi.list(),
  });

  const defects = defectsData?.items || [];
  const capas = capaData?.items || [];

  const heldBatches = batches.filter((b) => b.status === 'ON_HOLD');
  const openDefects = defects.filter((d) => d.status === 'OPEN' || d.status === 'REOPENED');
  const activeCAPAs = capas.filter((c) => c.status === 'OPEN' || c.status === 'IN_PROGRESS');
  const pendingVerifications = capas.filter(
    (c) => c.status === 'COMPLETED' && c.verification_status === 'PENDING'
  );
  const activeInspections = inspections.filter((i) => i.status === 'DRAFT' || i.status === 'SUBMITTED' || i.status === 'IN_REVIEW');

  return (
    <div className="space-y-8 animate-in fade-in">
      {/* Welcome & Role Context Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border border-slate-800 p-8 shadow-2xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center space-x-2 px-2.5 py-1 rounded-md bg-teal-500/10 text-teal-400 text-xs font-mono mb-2 border border-teal-500/20">
              <Sparkles className="w-3.5 h-3.5" />
              <span>LOGGED IN AS {user?.role}</span>
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              Quality Inspection & Manufacturing Ops
            </h1>
            <p className="text-sm text-slate-400 mt-1 max-w-2xl">
              Real-time quality intelligence for cast pump impellers. Machine learning tensor diagnostics paired with four-eyes verification and authorized release gates.
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <Button
              variant="primary"
              onClick={() => onNavigate('release-gates')}
              icon={<ShieldCheck className="w-4 h-4" />}
            >
              Evaluate Release Gates
            </Button>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div
          onClick={() => onNavigate('batches')}
          className="rounded-xl bg-slate-900/80 border border-slate-800 p-5 space-y-2 hover:border-slate-700 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs uppercase font-mono font-bold">Total Batches</span>
            <Layers className="w-4 h-4 text-teal-400 group-hover:scale-110 transition-transform" />
          </div>
          <div className="text-2xl font-extrabold text-white">{batches.length}</div>
          <div className="text-xs text-slate-500 font-mono">
            {heldBatches.length > 0 ? (
              <span className="text-amber-400 font-bold">{heldBatches.length} ON HOLD</span>
            ) : (
              <span className="text-emerald-400">0 On Hold</span>
            )}
          </div>
        </div>

        <div
          onClick={() => onNavigate('inspections')}
          className="rounded-xl bg-slate-900/80 border border-slate-800 p-5 space-y-2 hover:border-slate-700 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs uppercase font-mono font-bold">Active Inspections</span>
            <FileCheck2 className="w-4 h-4 text-sky-400 group-hover:scale-110 transition-transform" />
          </div>
          <div className="text-2xl font-extrabold text-white">{activeInspections.length}</div>
          <div className="text-xs text-slate-500 font-mono">
            <span>{inspections.length} Total Sessions</span>
          </div>
        </div>

        <div
          onClick={() => onNavigate('defects')}
          className="rounded-xl bg-slate-900/80 border border-slate-800 p-5 space-y-2 hover:border-slate-700 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs uppercase font-mono font-bold">Open Defects</span>
            <AlertOctagon className="w-4 h-4 text-rose-400 group-hover:scale-110 transition-transform" />
          </div>
          <div className="text-2xl font-extrabold text-white">
            <span className={openDefects.length > 0 ? 'text-rose-400' : 'text-emerald-400'}>
              {openDefects.length}
            </span>
          </div>
          <div className="text-xs text-slate-500 font-mono">
            <span>{defects.length} Cumulative</span>
          </div>
        </div>

        <div
          onClick={() => onNavigate('capa')}
          className="rounded-xl bg-slate-900/80 border border-slate-800 p-5 space-y-2 hover:border-slate-700 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs uppercase font-mono font-bold">Active CAPAs</span>
            <Wrench className="w-4 h-4 text-purple-400 group-hover:scale-110 transition-transform" />
          </div>
          <div className="text-2xl font-extrabold text-white">{activeCAPAs.length}</div>
          <div className="text-xs text-slate-500 font-mono">
            {pendingVerifications.length > 0 ? (
              <span className="text-amber-400 font-bold">{pendingVerifications.length} Awaiting Verification</span>
            ) : (
              <span className="text-emerald-400">All Verified</span>
            )}
          </div>
        </div>
      </div>

      {/* Quality Intelligence Assistant Panel */}
      <QualityIntelligencePanel
        batches={batches}
        onNavigateToIntelligence={(batchNumber, view) =>
          onNavigate('quality-intelligence', batchNumber, view)
        }
        onNavigate={onNavigate}
      />

      {/* Role-Specific Work Queues */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Quality Action Required Queue */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-teal-400" />
              <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                {isQualityManager ? 'Governance & Verification Queue' : 'Active Inspections Staging'}
              </h3>
            </div>
            <span className="text-xs text-slate-500 font-mono">Real-time DB</span>
          </div>

          <div className="space-y-2.5">
            {isQualityManager && pendingVerifications.length > 0 ? (
              pendingVerifications.map((c) => (
                <div
                  key={c.id}
                  onClick={() => onNavigate('capa')}
                  className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-purple-500/40 transition-colors flex items-center justify-between cursor-pointer"
                >
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold text-white font-mono">{c.action_number}</span>
                      <StatusBadge status="PENDING" size="sm" />
                    </div>
                    <div className="text-xs text-slate-300 mt-1">{c.title}</div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                      Assignee: {c.assigned_to} • Due: {c.due_date}
                    </div>
                  </div>
                  <Button variant="secondary" size="sm">
                    Verify →
                  </Button>
                </div>
              ))
            ) : activeInspections.length > 0 ? (
              activeInspections.slice(0, 4).map((insp) => (
                <div
                  key={insp.id}
                  onClick={() => onNavigate('inspections')}
                  className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-teal-500/40 transition-colors flex items-center justify-between cursor-pointer"
                >
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold text-white font-mono">{insp.inspection_number}</span>
                      <StatusBadge status={insp.status} size="sm" />
                    </div>
                    <div className="text-xs text-slate-400 mt-1 font-mono">
                      Stage: {insp.stage} • Batch: {insp.batch_id}
                    </div>
                  </div>
                  <Button variant="outline" size="sm">
                    Open Sheet →
                  </Button>
                </div>
              ))
            ) : (
              <div className="py-8 text-center text-xs text-slate-500 font-mono">
                Zero items pending action in this work queue.
              </div>
            )}
          </div>
        </div>

        {/* Right: Operational Containment & Blocked Lots */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center space-x-2">
              <PauseCircle className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                Quarantine & Quality Holds
              </h3>
            </div>
            <span className="text-xs text-slate-500 font-mono">{heldBatches.length} lots held</span>
          </div>

          <div className="space-y-2.5">
            {heldBatches.length > 0 ? (
              heldBatches.map((batch) => (
                <div
                  key={batch.id}
                  onClick={() => onNavigate('release-gates')}
                  className="p-3.5 rounded-xl bg-amber-950/15 border border-amber-500/20 hover:border-amber-500/40 transition-colors flex items-center justify-between cursor-pointer"
                >
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold text-amber-300 font-mono">{batch.batch_number}</span>
                      <StatusBadge status="ON_HOLD" size="sm" />
                    </div>
                    <div className="text-xs text-slate-300 mt-1">
                      {batch.notes || 'Containment hold initiated on shop floor.'}
                    </div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                      Qty: {batch.declared_quantity} • Heat: {batch.heat_number || 'N/A'}
                    </div>
                  </div>
                  <Button variant="outline" size="sm">
                    View Gate →
                  </Button>
                </div>
              ))
            ) : (
              <div className="py-8 text-center text-xs text-slate-500 font-mono">
                No batches currently under containment hold.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
