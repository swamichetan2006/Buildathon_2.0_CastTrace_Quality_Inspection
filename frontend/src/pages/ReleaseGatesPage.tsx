import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { batchesApi } from '../api/batches';
import type { Batch } from '../types';
import ReleaseGateCard from '../components/domain/ReleaseGateCard';
import Badge from '../components/common/Badge';

interface ReleaseGatesPageProps {
  onSelectBatch: (batchId: string) => void;
  onNavigateToInspection?: (inspectionId: string) => void;
  onNavigateToDefect?: (defectId: string) => void;
  onNavigateToCapa?: (capaId: string) => void;
}

export const ReleaseGatesPage: React.FC<ReleaseGatesPageProps> = ({
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

  const activeBatchId = selectedBatchId || (batches.length > 0 ? batches[0].id : '');
  const activeBatch = batches.find((b) => b.id === activeBatchId);

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Batch Release Governance Portal
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Phase 4C Release Gates, automated blocker verification, Four-Eyes audit checks, and official Quality Manager decisions.
        </p>
      </div>

      {/* Lot selector bar */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex-1 max-w-md">
          <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
            Select Production Lot / Batch
          </label>
          <select
            value={activeBatchId}
            onChange={(e) => setSelectedBatchId(e.target.value)}
            className="w-full px-3 py-2 text-sm font-semibold border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
          >
            {batches.map((b) => (
              <option key={b.id} value={b.id}>
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
              className="text-xs font-semibold px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg border border-slate-300 transition"
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
        <div className="p-12 text-center text-slate-400 bg-white border border-slate-200 rounded-xl">
          {isLoading ? 'Loading batches...' : 'No batches available for release evaluation.'}
        </div>
      )}
    </div>
  );
};
export default ReleaseGatesPage;
