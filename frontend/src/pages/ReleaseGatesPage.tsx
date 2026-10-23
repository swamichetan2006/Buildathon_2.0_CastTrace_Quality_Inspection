import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { batchesApi } from '../api/batches';
import type { Batch } from '../types';
import ReleaseGateCard from '../components/domain/ReleaseGateCard';
import Badge from '../components/common/Badge';

interface ReleaseGatesPageProps {
  initialBatchId?: string;
  onSelectBatch: (batchId: string) => void;
  onNavigateToInspection?: (inspectionId: string) => void;
  onNavigateToDefect?: (defectId: string) => void;
  onNavigateToCapa?: (capaId: string) => void;
}

export const ReleaseGatesPage: React.FC<ReleaseGatesPageProps> = ({
  initialBatchId,
  onSelectBatch,
  onNavigateToInspection,
  onNavigateToDefect,
  onNavigateToCapa,
}) => {
  const [selectedBatchId, setSelectedBatchId] = useState<string>('');

  const { data: batches = [], isLoading } = useQuery<Batch[]>({
    queryKey: ['batches-release-portal'],
    queryFn: () => batchesApi.list(),
  });

  const activeBatch =
    batches.find(
      (b) =>
        b.id === selectedBatchId ||
        b.batch_number === selectedBatchId ||
        (initialBatchId && (b.id === initialBatchId || b.batch_number === initialBatchId))
    ) || (batches.length > 0 ? batches[0] : undefined);

  const activeBatchId = activeBatch ? activeBatch.id : '';

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">
          Batch Release Governance Portal
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Phase 4C Release Gates, automated blocker verification, Four-Eyes audit checks, and official Quality Manager decisions.
        </p>
      </div>

      {/* Lot selector bar */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex-1 max-w-md">
          <label className="block text-xs font-mono font-bold uppercase text-slate-300 mb-1.5 tracking-wider">
            Select Production Lot / Batch
          </label>
          <select
            value={activeBatchId}
            onChange={(e) => setSelectedBatchId(e.target.value)}
            className="w-full px-3.5 py-2.5 text-sm font-semibold font-mono border border-slate-700 rounded-xl focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 bg-slate-950 text-white cursor-pointer shadow-inner"
          >
            {batches.map((b) => (
              <option key={b.id} value={b.id} className="bg-slate-900 text-white py-1">
                {b.batch_number} — {b.product?.name || 'Impeller'} ({b.status})
              </option>
            ))}
          </select>
        </div>

        {activeBatch && (
          <div className="flex items-center gap-3">
            <Badge status={activeBatch.status} />
            <button
              onClick={() => onSelectBatch(activeBatch.id)}
              className="text-xs font-semibold px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl border border-slate-700 transition cursor-pointer"
            >
              Full Batch Details →
            </button>
          </div>
        )}
      </div>

      {/* Release Gate Live Evaluation Card */}
      {activeBatchId ? (
        <ReleaseGateCard
          batchId={activeBatchId}
          onNavigateToInspection={onNavigateToInspection}
          onNavigateToDefect={onNavigateToDefect}
          onNavigateToCapa={onNavigateToCapa}
        />
      ) : (
        <div className="p-12 text-center text-slate-400 bg-slate-900/50 border border-slate-800 rounded-2xl font-mono">
          {isLoading ? 'Loading batches...' : 'No batches available for release evaluation.'}
        </div>
      )}
    </div>
  );
};
export default ReleaseGatesPage;
