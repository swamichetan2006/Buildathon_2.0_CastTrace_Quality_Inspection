import React, { useState } from 'react';
import type { InspectionItem, ReviewDecision, DefectCategory, DefectSeverity } from '../../types';
import { StatusBadge } from '../common/Badge';
import { Button } from '../common/Button';
import { CheckCircle2, ShieldAlert, AlertTriangle, HelpCircle, FileText, Sparkles } from 'lucide-react';
import { reviewsApi } from '../../api/reviews';
import type { DefectPayloadForReview } from '../../api/reviews';
import { useNotification } from '../../context/NotificationContext';
import { useAuth } from '../../context/AuthContext';

interface ReviewPanelProps {
  item: InspectionItem;
  onReviewSubmitted: () => void;
  onDisputeSubmitted?: () => void;
}

const DEFECT_CATEGORIES: DefectCategory[] = [
  'BLOWHOLE',
  'SHRINKAGE_POROSITY',
  'PINHOLE',
  'HOT_TEAR',
  'COLD_SHUT',
  'CRACK',
  'SURFACE_ROUGHNESS',
  'INCLUSION',
  'OTHER',
];

const DEFECT_SEVERITIES: DefectSeverity[] = ['CRITICAL', 'MAJOR', 'MINOR'];

export const ReviewPanel: React.FC<ReviewPanelProps> = ({
  item,
  onReviewSubmitted,
  onDisputeSubmitted,
}) => {
  const { isQualityManager } = useAuth();
  const { success, error } = useNotification();
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form State
  const [decision, setDecision] = useState<ReviewDecision>('CONFIRMED_GOOD');
  const [notes, setNotes] = useState('');

  // Defect Sub-form
  const [category, setCategory] = useState<DefectCategory>('SHRINKAGE_POROSITY');
  const [severity, setSeverity] = useState<DefectSeverity>('MAJOR');
  const [surfaceLocation, setSurfaceLocation] = useState('BLADE_ROOT');
  const [description, setDescription] = useState('');

  // Adjudication Mode (if item is currently disputed and user is QM)
  const isDisputed = item.status === 'DISPUTED';

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      if (isDisputed && isQualityManager) {
        // QM Adjudication
        let defectData: DefectPayloadForReview | undefined = undefined;
        if (decision === 'CONFIRMED_DEFECTIVE') {
          defectData = {
            category,
            severity,
            surface_location: surfaceLocation,
            description: description || 'Adjudicated non-conformance.',
          };
        }

        await reviewsApi.adjudicate(
          item.reviews?.[0]?.id || '',
          decision as 'CONFIRMED_GOOD' | 'CONFIRMED_DEFECTIVE',
          notes || 'QM Formal Adjudication sign-off.',
          defectData
        );
        success('Review Adjudicated', 'Dispute successfully resolved by Quality Manager.');
      } else {
        // Standard Inspector Review
        let defectData: DefectPayloadForReview | undefined = undefined;
        if (decision === 'CONFIRMED_DEFECTIVE') {
          if (!description) {
            error('Description Required', 'Please provide defect description.');
            setIsSubmitting(false);
            return;
          }
          defectData = {
            category,
            severity,
            surface_location: surfaceLocation,
            description,
          };
        }

        await reviewsApi.create({
          inspection_item_id: item.id,
          decision,
          notes,
          defect: defectData,
        });
        success('Human Review Recorded', `Decision recorded: ${decision.replace(/_/g, ' ')}`);
      }

      onReviewSubmitted();
      onDisputeSubmitted?.();
    } catch (err: any) {
      error('Review Submission Failed', err.message || 'Could not record review decision.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl space-y-6">
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-mono font-bold text-slate-400 uppercase">
              {isDisputed ? 'QUALITY MANAGER DISPUTE ADJUDICATION' : 'HUMAN REVIEW WORKSPACE'}
            </span>
            <StatusBadge status={item.status} size="sm" />
          </div>
          <h3 className="text-base font-bold text-white mt-1">
            Physical Item: {item.item_identifier} (Cavity #{item.cavity_number || '1'})
          </h3>
        </div>

        {isDisputed && (
          <div className="text-xs font-mono px-3 py-1 rounded-lg bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold">
            QM ACTION REQUIRED
          </div>
        )}
      </div>

      <form onSubmit={handleSubmitReview} className="space-y-5">
        {/* Outcome Selector */}
        <div>
          <label className="block text-xs font-mono font-bold text-slate-300 uppercase mb-2">
            Select Review Outcome
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
            <button
              type="button"
              onClick={() => setDecision('CONFIRMED_GOOD')}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                decision === 'CONFIRMED_GOOD'
                  ? 'bg-emerald-500/15 border-emerald-500 text-emerald-200'
                  : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              <div className="flex items-center space-x-2 font-bold text-xs mb-1">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>CONFIRMED GOOD</span>
              </div>
              <p className="text-[10px] text-slate-400">Specimen meets casting tolerances</p>
            </button>

            <button
              type="button"
              onClick={() => setDecision('CONFIRMED_DEFECTIVE')}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                decision === 'CONFIRMED_DEFECTIVE'
                  ? 'bg-rose-500/15 border-rose-500 text-rose-200'
                  : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              <div className="flex items-center space-x-2 font-bold text-xs mb-1">
                <ShieldAlert className="w-4 h-4 text-rose-400" />
                <span>CONFIRMED DEFECT</span>
              </div>
              <p className="text-[10px] text-slate-400">Log defect and mandate CAPA</p>
            </button>

            {!isDisputed && (
              <>
                <button
                  type="button"
                  onClick={() => setDecision('DISPUTED')}
                  className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                    decision === 'DISPUTED'
                      ? 'bg-amber-500/15 border-amber-500 text-amber-200'
                      : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  <div className="flex items-center space-x-2 font-bold text-xs mb-1">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    <span>DISPUTE</span>
                  </div>
                  <p className="text-[10px] text-slate-400">Escalate to Quality Manager</p>
                </button>

                <button
                  type="button"
                  onClick={() => setDecision('REQUEST_ADDITIONAL_EVIDENCE')}
                  className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                    decision === 'REQUEST_ADDITIONAL_EVIDENCE'
                      ? 'bg-sky-500/15 border-sky-500 text-sky-200'
                      : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  <div className="flex items-center space-x-2 font-bold text-xs mb-1">
                    <HelpCircle className="w-4 h-4 text-sky-400" />
                    <span>NEED EVIDENCE</span>
                  </div>
                  <p className="text-[10px] text-slate-400">Request clearer photograph</p>
                </button>
              </>
            )}
          </div>
        </div>

        {/* Defect Details Form (if CONFIRMED_DEFECTIVE) */}
        {decision === 'CONFIRMED_DEFECTIVE' && (
          <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/30 space-y-4 animate-in fade-in">
            <div className="text-xs font-mono font-bold text-rose-300 uppercase flex items-center space-x-1.5">
              <ShieldAlert className="w-4 h-4 text-rose-400" />
              <span>Mandatory Defect Classification (9-Category Taxonomy)</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Defect Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value as DefectCategory)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white focus:outline-none focus:border-rose-500"
                >
                  {DEFECT_CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat.replace(/_/g, ' ')}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">Defect Severity</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value as DefectSeverity)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white focus:outline-none focus:border-rose-500"
                >
                  {DEFECT_SEVERITIES.map((sev) => (
                    <option key={sev} value={sev}>
                      {sev}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">Surface Location</label>
                <input
                  type="text"
                  value={surfaceLocation}
                  onChange={(e) => setSurfaceLocation(e.target.value)}
                  placeholder="e.g. SUCTION_EYE, SHROUD"
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white focus:outline-none focus:border-rose-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1">Defect Description & Extent</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe non-conformance size, depth, and geometry..."
                rows={2}
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-rose-500"
                required
              />
            </div>
          </div>
        )}

        {/* Review Notes */}
        <div>
          <label className="block text-xs font-mono font-bold text-slate-300 uppercase mb-1">
            Inspector Findings & Review Notes
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Record visual observations, reference drawing dimensions..."
            rows={2}
            className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500"
          />
        </div>

        {/* Submit Button */}
        <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800">
          <Button
            type="submit"
            variant={decision === 'CONFIRMED_DEFECTIVE' ? 'danger' : 'primary'}
            isLoading={isSubmitting}
            icon={isDisputed ? <Sparkles className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
          >
            {isDisputed ? 'Adjudicate Dispute as Quality Manager' : 'Submit Official Human Review'}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default ReviewPanel;
