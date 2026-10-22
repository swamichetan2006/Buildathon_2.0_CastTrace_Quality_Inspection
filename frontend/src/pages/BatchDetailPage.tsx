import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { batchesApi } from '../api/batches';
import { inspectionsApi } from '../api/inspections';
import type { Batch, BatchDecision, Inspection, DecisionSnapshot } from '../types';
import { useAuth } from '../context/AuthContext';
import { useNotification } from '../context/NotificationContext';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Modal from '../components/common/Modal';
import ConfirmDialog from '../components/common/ConfirmDialog';
import ReleaseGateCard from '../components/domain/ReleaseGateCard';
import DecisionSnapshotModal from '../components/domain/DecisionSnapshotModal';

interface BatchDetailPageProps {
  batchId: string;
  onBack: () => void;
  onNavigateToInspection: (inspectionId: string) => void;
  onNavigateToDefect?: (defectId: string) => void;
  onNavigateToCapa?: (capaId: string) => void;
}

export const BatchDetailPage: React.FC<BatchDetailPageProps> = ({
  batchId,
  onBack,
  onNavigateToInspection,
  onNavigateToDefect,
  onNavigateToCapa,
}) => {
  const { isQualityManager } = useAuth();
  const { addToast } = useNotification();
  const queryClient = useQueryClient();

  // Dialog states
  const [isHoldOpen, setIsHoldOpen] = useState(false);
  const [holdReason, setHoldReason] = useState('');

  const [isDecisionModalOpen, setIsDecisionModalOpen] = useState(false);
  const [decisionType, setDecisionType] = useState<'RELEASE' | 'HOLD' | 'REJECT_SCRAP' | 'CONCESSION_DEVIATION'>('RELEASE');
  const [decisionReason, setDecisionReason] = useState('');
  const [concessionJustification, setConcessionJustification] = useState('');
  const [concessionConditions, setConcessionConditions] = useState('');

  const [viewSnapshot, setViewSnapshot] = useState<DecisionSnapshot | null>(null);

  // Queries
  const { data: batch, isLoading: batchLoading, refetch: refetchBatch } = useQuery<Batch>({
    queryKey: ['batch', batchId],
    queryFn: () => batchesApi.get(batchId),
  });

  const { data: decisionsData } = useQuery<{
    items: BatchDecision[];
    total: number;
    batch_id: string;
  }>({
    queryKey: ['batch-decisions', batchId],
    queryFn: () => batchesApi.listDecisions(batchId),
  });

  const decisions = decisionsData?.items || [];

  const { data: inspections = [] } = useQuery<Inspection[]>({
    queryKey: ['batch-inspections', batchId],
    queryFn: () => inspectionsApi.list({ batch_id: batchId }),
  });

  // Hold Mutation
  const holdMutation = useMutation({
    mutationFn: (reason: string) => batchesApi.placeHold(batchId, reason),
    onSuccess: () => {
      addToast('warning', 'Operational containment hold placed on batch');
      setIsHoldOpen(false);
      setHoldReason('');
      queryClient.invalidateQueries({ queryKey: ['batch', batchId] });
      queryClient.invalidateQueries({ queryKey: ['batches'] });
    },
    onError: (err: any) => {
      addToast('error', err.message || 'Failed to place containment hold');
    },
  });

  // Quality Manager Official Decision Mutation
  const decisionMutation = useMutation({
    mutationFn: (payload: {
      decision: 'RELEASE' | 'HOLD' | 'REJECT_SCRAP' | 'CONCESSION_DEVIATION';
      reason: string;
      is_concession?: boolean;
      concession_justification?: string;
      conditions?: string;
    }) => batchesApi.createDecision(batchId, payload),
    onSuccess: () => {
      addToast(
        decisionType === 'RELEASE' ? 'success' : 'info',
        `Official decision "${decisionType}" finalized and immutable snapshot recorded.`
      );
      setIsDecisionModalOpen(false);
      setDecisionReason('');
      setConcessionJustification('');
      setConcessionConditions('');
      queryClient.invalidateQueries({ queryKey: ['batch', batchId] });
      queryClient.invalidateQueries({ queryKey: ['batch-decisions', batchId] });
      queryClient.invalidateQueries({ queryKey: ['batches'] });
    },
    onError: (err: any) => {
      if (err.status === 409) {
        addToast(
          'error',
          'Concurrency conflict: Batch state or release gate changed. Gate refreshed.'
        );
        refetchBatch();
        queryClient.invalidateQueries({ queryKey: ['release-gate', batchId] });
      } else {
        addToast('error', err.message || 'Decision failed');
      }
    },
  });

  if (batchLoading) {
    return <div className="p-12 text-center text-slate-500">Loading batch records...</div>;
  }

  if (!batch) {
    return (
      <div className="p-8 text-center text-rose-600">
        Batch record not found.{' '}
        <button onClick={onBack} className="text-sky-600 underline">
          Return to Batches
        </button>
      </div>
    );
  }

  const isTerminalDecision =
    batch.status === 'RELEASED' ||
    batch.status === 'SCRAPPED';

  return (
    <div className="space-y-6">
      {/* Navigation header */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-800 transition"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Batches
        </button>

        <div className="flex items-center gap-2">
          {batch.status !== 'ON_HOLD' && !isTerminalDecision && (
            <Button
              variant="warning"
              onClick={() => {
                setHoldReason('');
                setIsHoldOpen(true);
              }}
              className="text-xs"
            >
              Place Containment Hold
            </Button>
          )}

          {isQualityManager && !isTerminalDecision && (
            <Button
              variant="primary"
              onClick={() => {
                setDecisionType('RELEASE');
                setDecisionReason('');
                setIsDecisionModalOpen(true);
              }}
              className="text-xs flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              Execute QM Decision
            </Button>
          )}
        </div>
      </div>

      {/* Batch Overview Banner */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold font-mono text-slate-900">{batch.batch_number}</h1>
              <Badge status={batch.status} />
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Part:{' '}
              <span className="font-semibold text-slate-800">
                {batch.product?.name || 'Pump Impeller'}
              </span>{' '}
              {batch.product?.sku && (
                <span className="font-mono text-xs text-slate-400">
                  [{batch.product.sku}]
                </span>
              )}
              <span className="mx-2">•</span>
              Declared Lot Size:{' '}
              <span className="font-mono font-medium text-slate-800">{batch.declared_quantity} units</span>
              {batch.heat_number && (
                <>
                  <span className="mx-2">•</span>
                  Heat: <span className="font-mono font-medium text-slate-800">{batch.heat_number}</span>
                </>
              )}
            </p>
          </div>

          <div className="text-xs text-slate-400 text-left md:text-right space-y-0.5">
            <div>
              Manufacture Date:{' '}
              <span className="text-slate-600 font-medium">
                {new Date(batch.manufacture_date).toLocaleDateString()}
              </span>
            </div>
            <div>
              Created:{' '}
              <span className="text-slate-600 font-medium">
                {new Date(batch.created_at).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {batch.notes && (
          <div className="mt-4 pt-4 border-t border-slate-100 text-xs text-slate-600 bg-slate-50 p-3 rounded-lg">
            <span className="font-semibold uppercase tracking-wider text-slate-500 block mb-1">
              Manufacturing & Shift Notes:
            </span>
            {batch.notes}
          </div>
        )}
      </div>

      {/* Release Gate Governance Card */}
      <ReleaseGateCard
        batchId={batchId}
        onNavigateToInspection={onNavigateToInspection}
        onNavigateToDefect={onNavigateToDefect}
        onNavigateToCapa={onNavigateToCapa}
      />

      {/* Linked Inspections Section */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900">Physical Inspection Sessions</h2>
            <p className="text-xs text-slate-500">
              Inspection lots and physical impeller units submitted for QA verification.
            </p>
          </div>
        </div>

        {inspections.length === 0 ? (
          <div className="p-6 text-center text-slate-400 text-sm border border-dashed border-slate-200 rounded-lg">
            No inspection sessions recorded yet for this batch.
          </div>
        ) : (
          <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden">
            {inspections.map((ins) => (
              <div
                key={ins.id}
                className="p-4 flex items-center justify-between hover:bg-slate-50 transition"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-slate-800">
                      {ins.inspection_number || ins.id.slice(0, 8)}
                    </span>
                    <Badge status={ins.status} />
                  </div>
                  <div className="text-xs text-slate-500">
                    Stage: <span className="font-semibold">{ins.stage}</span> • Sampling: {ins.sampling_plan} • Created{' '}
                    {new Date(ins.created_at).toLocaleDateString()}
                  </div>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onNavigateToInspection(ins.id)}
                  className="text-xs"
                >
                  View Inspection →
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Historical Decision Snapshots Section */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              Historical Decision Snapshots (Phase 4C)
            </h2>
            <p className="text-xs text-slate-500">
              Immutable records of official Quality Manager release, rejection, and concession determinations.
            </p>
          </div>
          <span className="font-mono text-xs text-slate-400">{decisions.length} snapshot(s)</span>
        </div>

        {decisions.length === 0 ? (
          <div className="p-6 text-center text-slate-400 text-sm border border-dashed border-slate-200 rounded-lg">
            No official quality decisions have been rendered on this batch.
          </div>
        ) : (
          <div className="overflow-x-auto border border-slate-200 rounded-lg">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Decision</th>
                  <th className="px-4 py-3">Acting QM</th>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Justification</th>
                  <th className="px-4 py-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {decisions.map((dec) => (
                  <tr key={dec.id} className="hover:bg-slate-50 transition">
                    <td className="px-4 py-3 font-semibold">
                      <Badge status={dec.decision} />
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-slate-700">
                      {dec.decided_by ? dec.decided_by.slice(0, 8) : 'QM'}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {dec.decided_at ? new Date(dec.decided_at).toLocaleString() : new Date(dec.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-700 max-w-xs truncate">
                      {dec.reason}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {dec.snapshot && (
                        <button
                          onClick={() => setViewSnapshot(dec.snapshot || null)}
                          className="text-xs font-semibold text-sky-600 hover:text-sky-800 underline"
                        >
                          Inspect Snapshot
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Snapshot Modal */}
      {viewSnapshot && (
        <DecisionSnapshotModal snapshot={viewSnapshot} onClose={() => setViewSnapshot(null)} />
      )}

      {/* Operational Hold Confirmation Dialog */}
      <ConfirmDialog
        isOpen={isHoldOpen}
        onClose={() => setIsHoldOpen(false)}
        title="Place Containment Hold"
        message="This will halt downstream movement and flag this lot as ON_HOLD in the quality gate."
        confirmText="Confirm Hold"
        variant="warning"
        loading={holdMutation.isPending}
        onConfirm={() => {
          if (!holdReason.trim()) {
            addToast('error', 'Hold reason is required');
            return;
          }
          holdMutation.mutate(holdReason.trim());
        }}
      >
        <div className="mt-3">
          <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
            Containment Justification <span className="text-rose-500">*</span>
          </label>
          <textarea
            required
            rows={2}
            value={holdReason}
            onChange={(e) => setHoldReason(e.target.value)}
            placeholder="Describe the operational containment reason..."
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
        </div>
      </ConfirmDialog>

      {/* Official QM Decision Modal */}
      <Modal
        isOpen={isDecisionModalOpen}
        onClose={() => setIsDecisionModalOpen(false)}
        title="Execute Quality Manager Batch Decision"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!decisionReason.trim()) {
              addToast('error', 'Decision justification reason is required');
              return;
            }
            if (decisionType === 'CONCESSION_DEVIATION' && !concessionJustification.trim()) {
              addToast('error', 'Concession release requires engineering justification');
              return;
            }

            decisionMutation.mutate({
              decision: decisionType,
              reason: decisionReason.trim(),
              is_concession: decisionType === 'CONCESSION_DEVIATION',
              concession_justification:
                decisionType === 'CONCESSION_DEVIATION' ? concessionJustification.trim() : undefined,
              conditions:
                decisionType === 'CONCESSION_DEVIATION' ? concessionConditions.trim() : undefined,
            });
          }}
          className="space-y-4"
        >
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 leading-relaxed">
            <span className="font-bold">Governance Warning:</span> This action records an immutable
            Phase 4C decision snapshot. If the server release gate detects active blockers, an
            unjustified RELEASE attempt will be rejected.
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Decision Outcome <span className="text-rose-500">*</span>
            </label>
            <select
              value={decisionType}
              onChange={(e) =>
                setDecisionType(
                  e.target.value as 'RELEASE' | 'HOLD' | 'REJECT_SCRAP' | 'CONCESSION_DEVIATION'
                )
              }
              className="w-full px-3 py-2 text-sm font-semibold border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
            >
              <option value="RELEASE">RELEASE (Authorize full shipment)</option>
              <option value="HOLD">HOLD (Administrative Quality Hold)</option>
              <option value="REJECT_SCRAP">REJECT_SCRAP (Scrap / permanent rejection)</option>
              <option value="CONCESSION_DEVIATION">CONCESSION_DEVIATION (Authorize under formal deviation)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Quality Decision Justification <span className="text-rose-500">*</span>
            </label>
            <textarea
              required
              rows={3}
              value={decisionReason}
              onChange={(e) => setDecisionReason(e.target.value)}
              placeholder="State the formal engineering rationale and review basis..."
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          {decisionType === 'CONCESSION_DEVIATION' && (
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-3">
              <span className="font-semibold text-xs text-slate-700 uppercase tracking-wider block">
                Engineering Concession Metadata
              </span>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">
                  Concession Justification / Deviation # <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={concessionJustification}
                  onChange={(e) => setConcessionJustification(e.target.value)}
                  placeholder="e.g. Deviation DEV-2026-IMP-4412 approved by Chief Metallurgist"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">
                  Special Usage Conditions & Expiration
                </label>
                <textarea
                  rows={2}
                  value={concessionConditions}
                  onChange={(e) => setConcessionConditions(e.target.value)}
                  placeholder="e.g. Restricted to low-pressure secondary cooling pump applications only..."
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button variant="secondary" onClick={() => setIsDecisionModalOpen(false)} type="button">
              Cancel
            </Button>
            <Button
              type="submit"
              variant={decisionType === 'REJECT_SCRAP' ? 'danger' : 'primary'}
              loading={decisionMutation.isPending}
            >
              Finalize Official Decision
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
export default BatchDetailPage;
