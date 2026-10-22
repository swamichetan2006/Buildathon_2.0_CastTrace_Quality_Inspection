import React from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ReleaseGateResponse } from '../../types';
import { batchesApi } from '../../api/batches';
import { ShieldCheck, ShieldAlert, AlertTriangle, RefreshCw, CheckCircle2 } from 'lucide-react';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';

interface ReleaseGateCardProps {
  gate?: ReleaseGateResponse | null;
  batchId?: string;
  isLoading?: boolean;
  onRefresh?: () => void;
  onResolveBlocker?: (entityType: string, entityId: string) => void;
  onOpenDecisionModal?: () => void;
  onOpenHoldModal?: () => void;
  canDecide?: boolean;
  onNavigateToInspection?: (inspectionId: string) => void;
  onNavigateToDefect?: (defectId: string) => void;
  onNavigateToCapa?: (capaId: string) => void;
}

export const ReleaseGateCard: React.FC<ReleaseGateCardProps> = ({
  gate: passedGate,
  batchId,
  isLoading: passedLoading = false,
  onRefresh: passedRefresh,
  onResolveBlocker,
  onOpenDecisionModal,
  onOpenHoldModal,
  canDecide = false,
  onNavigateToInspection,
  onNavigateToDefect,
  onNavigateToCapa,
}) => {
  const { data: fetchedGate, isLoading: fetchLoading, refetch } = useQuery<ReleaseGateResponse>({
    queryKey: ['release-gate', batchId],
    queryFn: () => (batchId ? batchesApi.getReleaseGate(batchId) : Promise.reject('No batch ID')),
    enabled: Boolean(batchId && !passedGate),
  });

  const gate = passedGate || fetchedGate || null;
  const isLoading = passedLoading || fetchLoading;
  const onRefresh = passedRefresh || (() => refetch());

  if (isLoading && !gate) {
    return (
      <div className="rounded-2xl bg-slate-900 border border-slate-800 p-8 text-center space-y-3">
        <RefreshCw className="w-8 h-8 text-teal-400 animate-spin mx-auto" />
        <p className="text-sm text-slate-400">Evaluating 6 release-gate domains across active lot state...</p>
      </div>
    );
  }

  if (!gate) return null;

  return (
    <div
      className={`rounded-2xl border p-6 shadow-xl transition-all ${
        gate.is_permitted
          ? 'bg-slate-900/90 border-emerald-500/30 shadow-emerald-950/20'
          : 'bg-slate-900/90 border-rose-500/30 shadow-rose-950/20'
      }`}
    >
      {/* Top Gate Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div className="flex items-start space-x-3.5">
          <div
            className={`p-3 rounded-xl flex-shrink-0 ${
              gate.is_permitted
                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
            }`}
          >
            {gate.is_permitted ? <ShieldCheck className="w-7 h-7" /> : <ShieldAlert className="w-7 h-7" />}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-mono font-bold tracking-wider text-slate-400 uppercase">
                RELEASE GATE EVALUATION
              </span>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold uppercase ${
                  gate.is_permitted
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                }`}
              >
                {gate.is_permitted ? 'RELEASE PERMITTED' : `${gate.blockers.length} BLOCKERS ACTIVE`}
              </span>
            </div>
            <h3 className="text-lg font-bold text-white mt-0.5">{gate.summary}</h3>
            <p className="text-xs text-slate-400 mt-1 font-mono">
              Evaluated: {new Date(gate.evaluated_at).toLocaleTimeString()} • Lot: {gate.batch_id}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2.5">
          <Button variant="outline" size="sm" onClick={onRefresh} isLoading={isLoading} icon={<RefreshCw className="w-3.5 h-3.5" />}>
            Re-evaluate
          </Button>

          {canDecide && onOpenHoldModal && (
            <Button variant="warning" size="sm" onClick={onOpenHoldModal}>
              Place Hold
            </Button>
          )}

          {canDecide && onOpenDecisionModal && (
            <Button
              variant={gate.is_permitted ? 'primary' : 'secondary'}
              size="sm"
              onClick={onOpenDecisionModal}
              icon={gate.is_permitted ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
            >
              {gate.is_permitted ? 'Authorize Release' : 'Authorise / Concession'}
            </Button>
          )}
        </div>
      </div>

      {/* Metrics Row (Strictly Distinct Physical Items, not photo counts) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 py-5 border-b border-slate-800/80">
        <div className="bg-slate-950/50 p-3 rounded-xl border border-slate-800">
          <div className="text-[10px] text-slate-400 uppercase font-mono">Physical Items</div>
          <div className="text-lg font-extrabold text-white mt-1">{gate.counts.total_items}</div>
          <div className="text-[10px] text-teal-400 font-mono">100% Normalized</div>
        </div>

        <div className="bg-slate-950/50 p-3 rounded-xl border border-slate-800">
          <div className="text-[10px] text-slate-400 uppercase font-mono">Reviewed Items</div>
          <div className="text-lg font-extrabold text-white mt-1">
            {gate.counts.reviewed_items} / {gate.counts.total_items}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">
            {gate.counts.pending_review_items > 0 ? (
              <span className="text-amber-400">{gate.counts.pending_review_items} Pending</span>
            ) : (
              <span className="text-emerald-400">All Reviewed</span>
            )}
          </div>
        </div>

        <div className="bg-slate-950/50 p-3 rounded-xl border border-slate-800">
          <div className="text-[10px] text-slate-400 uppercase font-mono">Unresolved Defects</div>
          <div
            className={`text-lg font-extrabold mt-1 ${
              gate.counts.unresolved_defects > 0 ? 'text-rose-400' : 'text-emerald-400'
            }`}
          >
            {gate.counts.unresolved_defects}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">
            {gate.counts.resolved_defects} Resolved
          </div>
        </div>

        <div className="bg-slate-950/50 p-3 rounded-xl border border-slate-800">
          <div className="text-[10px] text-slate-400 uppercase font-mono">Pending Reinspection</div>
          <div className="text-lg font-extrabold text-white mt-1">
            {gate.counts.defects_requiring_reinspection}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">Follow-up QA</div>
        </div>

        <div className="bg-slate-950/50 p-3 rounded-xl border border-slate-800">
          <div className="text-[10px] text-slate-400 uppercase font-mono">CAPA Verified</div>
          <div className="text-lg font-extrabold text-white mt-1">
            {gate.counts.capa_verified}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">
            {gate.counts.capa_requiring_verification > 0 ? (
              <span className="text-amber-400">{gate.counts.capa_requiring_verification} To Verify</span>
            ) : (
              <span className="text-emerald-400">Verified</span>
            )}
          </div>
        </div>

        <div className="bg-slate-950/50 p-3 rounded-xl border border-slate-800">
          <div className="text-[10px] text-slate-400 uppercase font-mono">Failed Reinspections</div>
          <div
            className={`text-lg font-extrabold mt-1 ${
              gate.counts.pending_or_failed_reinspections > 0 ? 'text-rose-400' : 'text-slate-300'
            }`}
          >
            {gate.counts.pending_or_failed_reinspections}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">Recurrences</div>
        </div>
      </div>

      {/* Blockers Manifest */}
      {gate.blockers.length > 0 ? (
        <div className="mt-5 space-y-3">
          <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-400 uppercase tracking-wider">
            <span className="flex items-center space-x-1.5 text-rose-400">
              <AlertTriangle className="w-4 h-4" />
              <span>Active Release Blockers ({gate.blockers.length})</span>
            </span>
            <span className="text-[11px] text-slate-500 font-normal">All must be resolved for standard release</span>
          </div>

          <div className="space-y-2">
            {gate.blockers.map((b, idx) => (
              <div
                key={`${b.code}-${idx}`}
                className="flex items-center justify-between p-3 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-slate-700 transition-colors text-xs"
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <Badge variant="danger" size="sm">
                    {b.code}
                  </Badge>
                  <span className="text-slate-200 truncate">{b.message}</span>
                </div>

                {(onResolveBlocker || onNavigateToInspection || onNavigateToDefect || onNavigateToCapa) && b.entity_id && (
                  <button
                    onClick={() => {
                      if (onResolveBlocker && b.entity_type) {
                        onResolveBlocker(b.entity_type, b.entity_id!);
                      } else if (b.entity_type === 'inspection' && onNavigateToInspection) {
                        onNavigateToInspection(b.entity_id!);
                      } else if (b.entity_type === 'defect' && onNavigateToDefect) {
                        onNavigateToDefect(b.entity_id!);
                      } else if (b.entity_type === 'capa' && onNavigateToCapa) {
                        onNavigateToCapa(b.entity_id!);
                      }
                    }}
                    className="ml-4 flex-shrink-0 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-teal-300 text-[11px] font-medium transition-colors cursor-pointer"
                  >
                    Investigate & Resolve →
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="mt-4 p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-500/20 text-xs text-emerald-300 flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>
            Every mandatory inspection, human review, defect remediation, CAPA verification, and reinspection requirement has been satisfied. The batch is eligible for official release sign-off by a Quality Manager.
          </span>
        </div>
      )}
    </div>
  );
};

export default ReleaseGateCard;
