import React from 'react';
import type { BatchDecision, DecisionSnapshot } from '../../types';
import { Modal } from '../common/Modal';
import { StatusBadge, Badge } from '../common/Badge';
import { CheckCircle2 } from 'lucide-react';

interface DecisionSnapshotModalProps {
  decision?: BatchDecision | null;
  snapshot?: DecisionSnapshot | null;
  isOpen?: boolean;
  onClose: () => void;
}

export const DecisionSnapshotModal: React.FC<DecisionSnapshotModalProps> = ({
  decision,
  snapshot: passedSnapshot,
  isOpen = true,
  onClose,
}) => {
  const snapshot = passedSnapshot || decision?.snapshot || null;
  if (!decision && !passedSnapshot) return null;

  const decisionStatus = snapshot?.decision || decision?.decision || 'RELEASE';
  const decisionId = snapshot?.decision_id || decision?.id || 'SNAPSHOT';
  const decidedAt = snapshot?.decided_at || decision?.created_at || '';
  const decidedBy = snapshot?.decided_by || decision?.decided_by || 'Quality Manager';
  const reasonText = snapshot?.reason || decision?.reason || 'Documented quality release authorization.';
  const conditionsText = snapshot?.concession_justification || snapshot?.conditions || decision?.conditions || null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Immutable Decision Governance Snapshot"
      description="Point-in-time state recorded when the Quality Manager finalized this batch decision."
      maxWidth="2xl"
    >
      <div className="space-y-6 text-sm">
        {/* Banner with Decision and Authority */}
        <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <StatusBadge status={decisionStatus} />
            <div>
              <div className="text-xs text-slate-400 font-mono">DECISION RECORD ID:</div>
              <div className="text-xs font-mono text-slate-200">{decisionId}</div>
            </div>
          </div>
          <div className="text-right font-mono text-xs text-slate-400">
            <div>{new Date(decidedAt).toLocaleString()}</div>
            <div className="text-teal-400 font-bold">Authorized by: {decidedBy}</div>
          </div>
        </div>

        {/* Reason / Justification */}
        <div className="space-y-1.5">
          <label className="text-xs font-mono font-bold text-slate-400 uppercase">
            Mandatory Decision Justification
          </label>
          <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-slate-200 text-xs leading-relaxed">
            {reasonText}
          </div>
        </div>

        {/* Concession / Conditions if applicable */}
        {conditionsText && (
          <div className="space-y-1.5">
            <label className="text-xs font-mono font-bold text-purple-400 uppercase flex items-center space-x-1.5">
              <span>Engineering Concession / Permit Details</span>
            </label>
            <div className="p-3.5 rounded-xl bg-purple-950/20 border border-purple-500/30 text-purple-200 text-xs leading-relaxed">
              {conditionsText}
            </div>
          </div>
        )}

        {/* Snapshot Metrics Grid (Frozen At Decision Time) */}
        {snapshot?.counts && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-400 uppercase">
              <span>Item & Quality Metrics (Frozen Snapshot)</span>
              <span className="text-[10px] text-teal-400">Not Affected by Future Records</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800 text-xs">
                <span className="text-slate-400">Total Physical Items:</span>
                <span className="font-extrabold text-white ml-2">{snapshot.counts.total_items}</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800 text-xs">
                <span className="text-slate-400">Inspected Items:</span>
                <span className="font-extrabold text-white ml-2">{snapshot.counts.inspected_items}</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800 text-xs">
                <span className="text-slate-400">Reviewed Items:</span>
                <span className="font-extrabold text-white ml-2">{snapshot.counts.reviewed_items}</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800 text-xs">
                <span className="text-slate-400">Unresolved Defects:</span>
                <span className="font-extrabold text-rose-400 ml-2">{snapshot.counts.unresolved_defects}</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800 text-xs">
                <span className="text-slate-400">Resolved Defects:</span>
                <span className="font-extrabold text-emerald-400 ml-2">{snapshot.counts.resolved_defects}</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800 text-xs">
                <span className="text-slate-400">CAPA Verified:</span>
                <span className="font-extrabold text-teal-400 ml-2">{snapshot.counts.capa_verified}</span>
              </div>
            </div>
          </div>
        )}

        {/* Snapshot Blockers at Decision Time */}
        {snapshot?.blockers && (
          <div className="space-y-2">
            <div className="text-xs font-mono font-bold text-slate-400 uppercase">
              Blockers Present At Decision Time ({snapshot.blockers.length})
            </div>
            {snapshot.blockers.length === 0 ? (
              <div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-500/20 text-xs text-emerald-300 flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Zero release blockers were present when this decision was finalized.</span>
              </div>
            ) : (
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {snapshot.blockers.map((b, i) => (
                  <div
                    key={i}
                    className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80 text-xs flex items-center space-x-2"
                  >
                    <Badge variant="danger" size="sm">
                      {b.code}
                    </Badge>
                    <span className="text-slate-300 truncate">{b.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Linked Entity Lineage References */}
        {snapshot?.entities && (
          <div className="pt-2 border-t border-slate-800 text-[11px] font-mono text-slate-400 space-y-1">
            <div className="text-slate-500 uppercase font-bold">Traceability Lineage:</div>
            <div>Inspections ({snapshot.entities.inspection_ids.length}): {snapshot.entities.inspection_ids.join(', ') || 'None'}</div>
            <div>Defects ({snapshot.entities.defect_ids.length}): {snapshot.entities.defect_ids.join(', ') || 'None'}</div>
            <div>CAPA Records ({snapshot.entities.capa_ids.length}): {snapshot.entities.capa_ids.join(', ') || 'None'}</div>
            <div>Reinspections ({snapshot.entities.reinspection_ids.length}): {snapshot.entities.reinspection_ids.join(', ') || 'None'}</div>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default DecisionSnapshotModal;
