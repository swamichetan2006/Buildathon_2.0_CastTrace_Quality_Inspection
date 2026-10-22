import React, { useState } from 'react';
import type { CorrectiveAction } from '../../types';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { StatusBadge } from '../common/Badge';
import { capaApi } from '../../api/capa';
import { useNotification } from '../../context/NotificationContext';
import { useAuth } from '../../context/AuthContext';
import { Wrench, CheckCircle2, UserCheck, AlertTriangle } from 'lucide-react';

interface CAPAWorkflowModalProps {
  capa: CorrectiveAction | null;
  isOpen?: boolean;
  onClose: () => void;
  onActionComplete?: () => void;
  onSuccess?: () => void;
}

export const CAPAWorkflowModal: React.FC<CAPAWorkflowModalProps> = ({
  capa,
  isOpen = true,
  onClose,
  onActionComplete,
  onSuccess,
}) => {
  const triggerSuccess = () => {
    onActionComplete?.();
    onSuccess?.();
  };
  const { user, isQualityManager } = useAuth();
  const { success, error } = useNotification();
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Completion Form
  const [completionNotes, setCompletionNotes] = useState('');

  // Verification Form (QM)
  const [verificationDecision, setVerificationDecision] = useState<'APPROVED' | 'REJECTED'>('APPROVED');
  const [verificationNotes, setVerificationNotes] = useState('');

  if (!capa) return null;

  const isAssignee = user?.id === capa.assigned_to;
  const isVerifier = isQualityManager;
  const isFourEyesViolation = isVerifier && isAssignee;

  const handleStart = async () => {
    setIsSubmitting(true);
    try {
      await capaApi.start(capa.id);
      success('CAPA Started', `Action ${capa.action_number} marked IN_PROGRESS.`);
      triggerSuccess();
    } catch (err: any) {
      error('Failed to Start', err.message || 'Could not start corrective action.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleComplete = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!completionNotes || completionNotes.length < 10) {
      error('Notes Too Short', 'Completion notes must contain at least 10 characters.');
      return;
    }

    setIsSubmitting(true);
    try {
      await capaApi.complete(capa.id, { completion_notes: completionNotes });
      success('CAPA Completed', `Action ${capa.action_number} submitted for independent verification.`);
      triggerSuccess();
    } catch (err: any) {
      error('Failed to Complete', err.message || 'Could not complete corrective action.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!verificationNotes) {
      error('Notes Required', 'Verification notes are required.');
      return;
    }

    setIsSubmitting(true);
    try {
      await capaApi.verify(capa.id, {
        decision: verificationDecision,
        notes: verificationNotes,
      });
      success(
        verificationDecision === 'APPROVED' ? 'Verification Approved' : 'Verification Rejected',
        `Action ${capa.action_number} verification recorded.`
      );
      triggerSuccess();
    } catch (err: any) {
      error('Verification Failed', err.message || 'Could not record verification decision.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Corrective Action: ${capa.action_number}`}
      description={capa.title}
      maxWidth="xl"
    >
      <div className="space-y-6 text-xs">
        {/* Statuses Header */}
        <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <span className="text-slate-400">Implementation Status:</span>
            <StatusBadge status={capa.status} size="sm" />
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-slate-400">Independent Verification:</span>
            <StatusBadge status={capa.verification_status} size="sm" />
          </div>
        </div>

        {/* Details Grid */}
        <div className="grid grid-cols-2 gap-3 p-4 rounded-xl bg-slate-950/40 border border-slate-800/80">
          <div>
            <span className="text-slate-500 font-mono">Action Type:</span>
            <div className="font-semibold text-slate-200 mt-0.5">{capa.action_type}</div>
          </div>
          <div>
            <span className="text-slate-500 font-mono">Assigned Implementer:</span>
            <div className="font-semibold text-teal-300 mt-0.5 font-mono">{capa.assigned_to}</div>
          </div>
          <div>
            <span className="text-slate-500 font-mono">Due Date:</span>
            <div className="font-semibold text-slate-200 mt-0.5">{capa.due_date}</div>
          </div>
          <div>
            <span className="text-slate-500 font-mono">Defect Reference:</span>
            <div className="font-semibold text-rose-300 mt-0.5 font-mono">{capa.defect_id}</div>
          </div>
        </div>

        {/* Description & Root Cause */}
        <div className="space-y-3">
          <div>
            <label className="text-slate-400 font-mono uppercase font-bold">Planned Corrective Action</label>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 mt-1 leading-relaxed">
              {capa.description}
            </div>
          </div>

          {capa.root_cause && (
            <div>
              <label className="text-slate-400 font-mono uppercase font-bold">Root Cause Investigation</label>
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 mt-1 leading-relaxed">
                {capa.root_cause}
              </div>
            </div>
          )}
        </div>

        {/* Completion Section if COMPLETED */}
        {capa.completion_notes && (
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
            <div className="text-slate-400 font-mono font-bold uppercase">Completion Notes</div>
            <p className="text-slate-300 leading-relaxed">{capa.completion_notes}</p>
          </div>
        )}

        {/* Workflow Actions */}
        {capa.status === 'OPEN' && (
          <div className="pt-4 border-t border-slate-800 flex justify-end">
            <Button variant="primary" onClick={handleStart} isLoading={isSubmitting} icon={<Wrench className="w-4 h-4" />}>
              Start Implementation (IN_PROGRESS)
            </Button>
          </div>
        )}

        {capa.status === 'IN_PROGRESS' && (
          <form onSubmit={handleComplete} className="pt-4 border-t border-slate-800 space-y-3">
            <div className="text-xs font-mono font-bold text-teal-400 uppercase">
              Submit Completed Implementation
            </div>
            <textarea
              value={completionNotes}
              onChange={(e) => setCompletionNotes(e.target.value)}
              placeholder="Describe physical remediation completed (weld deposit, grinding depth, blending)..."
              rows={3}
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500"
              required
            />
            <div className="flex justify-end">
              <Button type="submit" variant="primary" isLoading={isSubmitting} icon={<CheckCircle2 className="w-4 h-4" />}>
                Complete Implementation & Submit for Verification
              </Button>
            </div>
          </form>
        )}

        {/* Independent Verification (QM only) */}
        {capa.status === 'COMPLETED' && capa.verification_status === 'PENDING' && isQualityManager && (
          <form onSubmit={handleVerify} className="pt-4 border-t border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div className="text-xs font-mono font-bold text-purple-400 uppercase flex items-center space-x-1.5">
                <UserCheck className="w-4 h-4" />
                <span>Independent Four-Eyes Verification (Quality Manager)</span>
              </div>
            </div>

            {isFourEyesViolation && (
              <div className="p-3 rounded-xl bg-rose-950/30 border border-rose-500/30 text-rose-300 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span>
                  Four-Eyes Rule: You are assigned as the implementer for this CAPA and cannot verify your own work. Another Quality Manager must verify.
                </span>
              </div>
            )}

            <div className="flex space-x-3">
              <button
                type="button"
                onClick={() => setVerificationDecision('APPROVED')}
                className={`flex-1 p-3 rounded-xl border text-center font-bold transition-all cursor-pointer ${
                  verificationDecision === 'APPROVED'
                    ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300'
                    : 'bg-slate-950 border-slate-800 text-slate-400'
                }`}
              >
                Approve Verification
              </button>

              <button
                type="button"
                onClick={() => setVerificationDecision('REJECTED')}
                className={`flex-1 p-3 rounded-xl border text-center font-bold transition-all cursor-pointer ${
                  verificationDecision === 'REJECTED'
                    ? 'bg-rose-500/20 border-rose-500 text-rose-300'
                    : 'bg-slate-950 border-slate-800 text-slate-400'
                }`}
              >
                Reject Verification (Rework)
              </button>
            </div>

            <textarea
              value={verificationNotes}
              onChange={(e) => setVerificationNotes(e.target.value)}
              placeholder="Record verifier observations, dimensional check, dye penetrant results..."
              rows={2}
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              required
            />

            <div className="flex justify-end">
              <Button
                type="submit"
                variant={verificationDecision === 'APPROVED' ? 'primary' : 'danger'}
                isLoading={isSubmitting}
                disabled={isFourEyesViolation}
              >
                Sign Off Verification Decision
              </Button>
            </div>
          </form>
        )}
      </div>
    </Modal>
  );
};

export default CAPAWorkflowModal;
