import React, { useState } from 'react';
import type { Defect } from '../../types';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { reinspectionsApi } from '../../api/capa';
import { useNotification } from '../../context/NotificationContext';
import { CheckCircle2, ShieldAlert, FileCheck } from 'lucide-react';

interface ReinspectionModalProps {
  defect?: Defect | null;
  defectId?: string;
  capaId?: string;
  isOpen?: boolean;
  onClose: () => void;
  onReinspectionCompleted?: () => void;
  onSuccess?: () => void;
}

export const ReinspectionModal: React.FC<ReinspectionModalProps> = ({
  defect,
  defectId,
  capaId,
  isOpen = true,
  onClose,
  onReinspectionCompleted,
  onSuccess,
}) => {
  const { success, error } = useNotification();
  const [outcome, setOutcome] = useState<'DEFECT_RESOLVED' | 'DEFECT_RECURRED_REOPENED'>('DEFECT_RESOLVED');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const effectiveDefectId = defect?.id || defectId;
  if (!effectiveDefectId) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!notes) {
      error('Notes Required', 'Please enter verification inspection notes.');
      return;
    }

    setIsSubmitting(true);
    try {
      await reinspectionsApi.create({
        defect_id: effectiveDefectId,
        corrective_action_id: capaId,
        outcome,
        notes,
      });

      success(
        outcome === 'DEFECT_RESOLVED' ? 'Defect Resolved' : 'Defect Reopened',
        outcome === 'DEFECT_RESOLVED'
          ? `Defect ${defect?.defect_number || effectiveDefectId.slice(0, 8)} successfully resolved and item cleared.`
          : `Defect ${defect?.defect_number || effectiveDefectId.slice(0, 8)} marked REOPENED due to recurring indication.`
      );
      onReinspectionCompleted?.();
      onSuccess?.();
      onClose();
    } catch (err: any) {
      error('Reinspection Failed', err.message || 'Could not record reinspection.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Reinspection: ${defect?.defect_number || effectiveDefectId.slice(0, 8)}`}
      description="Post-remediation physical quality verification inspection."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-5 text-xs">
        <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
          <div className="flex justify-between">
            <span className="text-slate-400 font-mono">Category:</span>
            <span className="font-bold text-white">{defect?.category || 'Remediation'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400 font-mono">Severity:</span>
            <span className="font-bold text-rose-300">{defect?.severity || 'Assigned'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400 font-mono">Location:</span>
            <span className="font-bold text-slate-200">{defect?.surface_location || 'N/A'}</span>
          </div>
        </div>

        <div>
          <label className="block text-slate-300 font-mono font-bold uppercase mb-2">
            Verification Outcome
          </label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setOutcome('DEFECT_RESOLVED')}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                outcome === 'DEFECT_RESOLVED'
                  ? 'bg-emerald-500/20 border-emerald-500 text-emerald-200'
                  : 'bg-slate-950 border-slate-800 text-slate-400'
              }`}
            >
              <div className="flex items-center space-x-1.5 font-bold mb-1 text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                <span>DEFECT RESOLVED</span>
              </div>
              <p className="text-[10px] text-slate-400">Non-conformance completely eliminated</p>
            </button>

            <button
              type="button"
              onClick={() => setOutcome('DEFECT_RECURRED_REOPENED')}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                outcome === 'DEFECT_RECURRED_REOPENED'
                  ? 'bg-rose-500/20 border-rose-500 text-rose-200'
                  : 'bg-slate-950 border-slate-800 text-slate-400'
              }`}
            >
              <div className="flex items-center space-x-1.5 font-bold mb-1 text-rose-400">
                <ShieldAlert className="w-4 h-4" />
                <span>DEFECT RECURRED</span>
              </div>
              <p className="text-[10px] text-slate-400">Residual defect; reopen for new CAPA</p>
            </button>
          </div>
        </div>

        <div>
          <label className="block text-slate-300 font-mono font-bold uppercase mb-1">
            Reinspection Notes & Test Procedure
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Record post-remediation observations (dye penetrant, dimensional caliper check)..."
            rows={3}
            className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500"
            required
          />
        </div>

        <div className="flex justify-end space-x-3 pt-3 border-t border-slate-800">
          <Button variant="ghost" type="button" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant={outcome === 'DEFECT_RESOLVED' ? 'primary' : 'danger'}
            isLoading={isSubmitting}
            icon={<FileCheck className="w-4 h-4" />}
          >
            Record Reinspection Outcome
          </Button>
        </div>
      </form>
    </Modal>
  );
};

export default ReinspectionModal;
