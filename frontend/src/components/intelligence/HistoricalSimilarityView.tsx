import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { intelligenceApi } from '../../api/intelligence';
import { Button } from '../common/Button';
import type {
  Batch,
  HistoricalSimilarityResponse,
} from '../../types';
import {
  History,
  Search,
  Sparkles,
  AlertOctagon,
  CheckCircle2,
  ExternalLink,
  Wrench,
  Info,
  Tag,
} from 'lucide-react';

interface HistoricalSimilarityViewProps {
  batches: Batch[];
  initialBatchIdentifier?: string;
  onNavigate: (tab: string, contextId?: string, extraId?: string) => void;
}

export const HistoricalSimilarityView: React.FC<HistoricalSimilarityViewProps> = ({
  batches,
  initialBatchIdentifier,
  onNavigate,
}) => {
  const [selectedBatch, setSelectedBatch] = useState<string>(initialBatchIdentifier || '');
  const [selectedDefectId, setSelectedDefectId] = useState<string>('');
  const [manualDefectInput, setManualDefectInput] = useState<string>('');
  const [includeCrossProduct, setIncludeCrossProduct] = useState<boolean>(true);
  const [similarityResult, setSimilarityResult] = useState<HistoricalSimilarityResponse | null>(null);

  // Fetch defects for the selected batch
  const { data: batchDefects = [], isLoading: isLoadingDefects } = useQuery({
    queryKey: ['batch-defects', selectedBatch],
    queryFn: () => intelligenceApi.getBatchDefects(selectedBatch),
    enabled: Boolean(selectedBatch),
  });

  // Execute similarity search mutation
  const { mutate: runSimilaritySearch, isPending, error: mutationError } = useMutation({
    mutationFn: (targetDefectId: string) =>
      intelligenceApi.getHistoricalSimilarity({
        defect_id: targetDefectId,
        limit: 5,
        include_cross_product: includeCrossProduct,
      }),
    onSuccess: (data) => {
      setSimilarityResult(data);
    },
    onError: () => {
      setSimilarityResult(null);
    },
  });

  const activeDefectId = selectedDefectId || (batchDefects[0]?.id ?? '');
  const effectiveDefectIdentifier = manualDefectInput.trim() || activeDefectId;

  const handleSearch = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!effectiveDefectIdentifier || isPending) return;
    setSimilarityResult(null);
    runSimilaritySearch(effectiveDefectIdentifier);
  };

  const handleBatchChange = (newBatch: string) => {
    setSelectedBatch(newBatch);
    setSelectedDefectId('');
    setManualDefectInput('');
    setSimilarityResult(null);
  };

  const getTierClass = (tier: string) => {
    switch (tier) {
      case 'HIGH':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
      case 'MODERATE':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      case 'LOW':
      default:
        return 'bg-slate-700/30 text-slate-300 border-slate-700/50';
    }
  };

  return (
    <div className="space-y-6">
      {/* Search & Selector Card */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-4 shadow-xl">
        <div className="space-y-1">
          <h2 className="text-base font-mono font-bold text-white flex items-center gap-2">
            <History className="w-4 h-4 text-purple-400" />
            Have We Seen This Issue Before? (Defect Recurrence & Similarity Radar)
          </h2>
          <p className="text-xs text-slate-400">
            Multi-factor similarity retrieval comparing historical casting lot defects across product, category, severity, surface location, and CAPA resolutions.
          </p>
        </div>

        <form onSubmit={handleSearch} className="space-y-4 pt-2 border-t border-slate-800/80">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Step 1: Batch */}
            <div className="space-y-1.5">
              <label htmlFor="sim-batch-select" className="block text-xs font-mono font-bold text-slate-300 uppercase">
                1. Target Production Batch
              </label>
              <select
                id="sim-batch-select"
                value={selectedBatch}
                onChange={(e) => handleBatchChange(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-purple-500 font-mono"
              >
                <option value="">-- Choose a Production Batch --</option>
                {batches.map((b) => (
                  <option key={b.id} value={b.batch_number}>
                    {b.batch_number} ({b.status})
                  </option>
                ))}
              </select>
            </div>

            {/* Step 2: Target Defect Selection */}
            <div className="space-y-1.5">
              <label htmlFor="sim-defect-select" className="block text-xs font-mono font-bold text-slate-300 uppercase">
                2. Select Confirmed Defect <span className="text-rose-400">*</span>
              </label>
              <select
                id="sim-defect-select"
                value={activeDefectId}
                onChange={(e) => {
                  setSelectedDefectId(e.target.value);
                  setManualDefectInput('');
                  setSimilarityResult(null);
                }}
                disabled={isLoadingDefects || batchDefects.length === 0}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-purple-500 font-mono disabled:opacity-50"
              >
                {batchDefects.length === 0 ? (
                  <option value="">
                    {selectedBatch ? 'No confirmed defects in this batch' : '-- Select a batch first --'}
                  </option>
                ) : (
                  batchDefects.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.defect_number} • {d.category} ({d.severity}) — Status: {d.status} {d.review_decision ? `[Decision: ${d.review_decision}]` : ''} - {d.surface_location || 'General'}
                    </option>
                  ))
                )}
              </select>
            </div>

            {/* Manual Defect ID Override */}
            <div className="space-y-1.5">
              <label htmlFor="manual-defect-input" className="block text-xs font-mono font-bold text-slate-300 uppercase">
                Or Enter Defect ID (DEF-...)
              </label>
              <input
                id="manual-defect-input"
                type="text"
                placeholder="e.g. DEF-20261022-0009"
                value={manualDefectInput}
                onChange={(e) => {
                  setManualDefectInput(e.target.value);
                  setSimilarityResult(null);
                }}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-purple-500 font-mono"
              />
            </div>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
            <label className="flex items-center gap-2 text-xs font-mono text-slate-400 cursor-pointer">
              <input
                type="checkbox"
                checked={includeCrossProduct}
                onChange={(e) => setIncludeCrossProduct(e.target.checked)}
                className="rounded border-slate-800 bg-slate-950 text-purple-600 focus:ring-purple-500"
              />
              <span>Include cross-product candidates (broad casting domain comparison)</span>
            </label>

            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isPending}
              disabled={!effectiveDefectIdentifier || isPending}
              icon={<Search className="w-3.5 h-3.5" />}
              className="text-xs font-mono self-end sm:self-auto"
            >
              {isPending ? 'Searching Candidates...' : 'Find Historical Matches'}
            </Button>
          </div>
        </form>
      </div>

      {/* Loading Skeleton */}
      {isPending && (
        <div className="space-y-4 animate-pulse">
          <div className="h-32 rounded-2xl bg-slate-900/60 border border-slate-800 p-5 space-y-3">
            <div className="h-4 bg-slate-800 rounded w-1/4"></div>
            <div className="h-3 bg-slate-850 rounded w-1/2"></div>
          </div>
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-40 rounded-2xl bg-slate-900/60 border border-slate-800 p-5 space-y-3">
                <div className="h-4 bg-slate-800 rounded w-1/3"></div>
                <div className="h-3 bg-slate-850 rounded w-3/4"></div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error Banner */}
      {mutationError && (
        <div className="rounded-2xl border border-rose-800/50 bg-rose-950/20 p-6 space-y-2">
          <div className="flex items-center gap-2 text-rose-400 font-bold text-sm">
            <AlertOctagon className="w-5 h-5 flex-shrink-0" />
            <span>Similarity Search Failed</span>
          </div>
          <p className="text-xs text-rose-200 pl-7">
            {mutationError instanceof Error ? mutationError.message : 'Defect not found or error communicating with API.'}
          </p>
        </div>
      )}

      {/* Similarity Results */}
      {!isPending && similarityResult && (
        <div className="space-y-6 animate-in fade-in">
          {/* Source Defect Card */}
          <div className="rounded-2xl border border-purple-500/30 bg-purple-950/15 p-5 space-y-3 shadow-xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-purple-500/20">
              <div className="flex items-center gap-2">
                <Tag className="w-4 h-4 text-purple-400" />
                <h3 className="text-xs font-mono font-bold text-purple-200 uppercase tracking-wider">
                  Source Defect Under Analysis
                </h3>
              </div>
              <span className="text-[11px] font-mono text-purple-300">
                Lot: {similarityResult.source_defect.batch_number || 'N/A'} • Product: {similarityResult.source_defect.product_sku || 'N/A'}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => onNavigate('defect', similarityResult.source_defect.id)}
                className="text-sm font-mono font-bold text-white bg-purple-500/20 hover:bg-purple-500/30 px-2.5 py-1 rounded-lg border border-purple-500/40 cursor-pointer flex items-center gap-1.5"
              >
                <span>{similarityResult.source_defect.defect_number}</span>
                <ExternalLink className="w-3.5 h-3.5 text-purple-300" />
              </button>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-200 font-bold">
                Category: {similarityResult.source_defect.category}
              </span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-200">
                Severity: {similarityResult.source_defect.severity}
              </span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-200">
                Status: <span className="font-bold text-sky-300">{similarityResult.source_defect.status}</span>
              </span>
              {similarityResult.source_defect.review_decision && (
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/60 text-emerald-300">
                  Decision: <span className="font-bold">{similarityResult.source_defect.review_decision}</span>
                </span>
              )}
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-200">
                Location: {similarityResult.source_defect.surface_location || 'General'}
              </span>
            </div>

            {similarityResult.source_defect.description && (
              <p className="text-xs text-slate-300 italic pl-1">
                "{similarityResult.source_defect.description}"
              </p>
            )}
          </div>

          {/* AI Synthesis Summary */}
          {similarityResult.ai_synthesis && (
            <div className="rounded-xl border border-teal-500/30 bg-teal-950/20 p-4 flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-teal-400 flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="text-xs font-bold text-teal-300 font-mono uppercase tracking-wider">
                  Historical Recurrence Synthesis
                </div>
                <p className="text-xs text-slate-200 leading-relaxed">{similarityResult.ai_synthesis}</p>
              </div>
            </div>
          )}

          {/* Disclaimers & Methodology */}
          <div className="flex items-center gap-2 text-[11px] font-mono text-slate-500 px-1">
            <Info className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            <span>
              Match score represents relative multi-factor ranking, not a statistical probability of identical root cause.
            </span>
          </div>

          {/* Empty Match Result */}
          {similarityResult.matches.length === 0 && (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-12 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                No Comparable Historical Defects Found
              </h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                Evaluated {similarityResult.total_candidates_evaluated} historical defects in PostgreSQL. No records met the minimum similarity threshold. This appears to be an isolated or novel defect condition.
              </p>
            </div>
          )}

          {/* Ranked Historical Matches List */}
          {similarityResult.matches.length > 0 && (
            <div className="space-y-4">
              <h3 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                <span>Top Ranked Historical Candidates ({similarityResult.matches.length} of {similarityResult.total_candidates_evaluated} evaluated)</span>
              </h3>

              {similarityResult.matches.map((cand) => (
                <div
                  key={cand.defect_id}
                  className="rounded-2xl border border-slate-800 bg-slate-900/90 hover:border-slate-700 p-5 space-y-4 transition-all shadow-xl"
                >
                  {/* Match Header */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
                    <div className="flex flex-wrap items-center gap-2.5">
                      {/* Match Score Badge */}
                      <span className="text-xs font-mono font-extrabold px-2.5 py-1 rounded-lg bg-purple-500/20 text-purple-300 border border-purple-500/40">
                        {cand.match_score}% MATCH
                      </span>
                      <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${getTierClass(cand.confidence_tier)}`}>
                        {cand.confidence_tier} CONFIDENCE
                      </span>
                      {cand.is_cross_product ? (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-400">
                          Cross-Product ({cand.product_sku || 'N/A'})
                        </span>
                      ) : (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 font-bold">
                          Same Product ({cand.product_sku})
                        </span>
                      )}
                      {cand.has_prior_link && (
                        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                          DIRECT RECURRENCE LINK
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono text-slate-400">
                        Recorded: {new Date(cand.created_at).toLocaleDateString()}
                      </span>
                      <button
                        type="button"
                        onClick={() => onNavigate('defect', cand.defect_id)}
                        className="inline-flex items-center text-xs font-mono text-teal-400 hover:text-teal-300 font-bold cursor-pointer ml-2"
                      >
                        <span>View Defect</span>
                        <ExternalLink className="w-3.5 h-3.5 ml-1" />
                      </button>
                    </div>
                  </div>

                  {/* Candidate Attributes */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div className="space-y-1">
                      <div className="text-slate-400 font-mono">
                        Defect: <button type="button" onClick={() => onNavigate('defect', cand.defect_id)} className="text-sky-400 font-bold hover:underline cursor-pointer">{cand.defect_number}</button> • Category: <span className="text-white font-bold">{cand.category}</span>
                      </div>
                      <div className="text-slate-400 font-mono">
                        Severity: <span className="text-white">{cand.severity}</span> • Status: <span className="text-sky-300 font-bold">{cand.status}</span>
                        {cand.review_decision && (
                          <span className="ml-1.5 text-[11px] text-emerald-400 font-bold">[{cand.review_decision}]</span>
                        )}
                      </div>
                      <div className="text-slate-400 font-mono">
                        Location: <span className="text-white">{cand.surface_location || 'General'}</span>
                      </div>
                      {cand.batch_number && (
                        <div className="text-slate-400 font-mono">
                          Batch Lot: <button type="button" onClick={() => onNavigate('batch', cand.batch_id || '')} className="text-teal-400 font-bold hover:underline cursor-pointer">{cand.batch_number}</button>
                        </div>
                      )}
                    </div>

                    <div className="space-y-1">
                      <span className="text-[10px] font-mono uppercase text-slate-500 font-bold">Match Rationale:</span>
                      <div className="flex flex-wrap gap-1.5">
                        {cand.matching_reasons.map((r, idx) => (
                          <span key={idx} className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                            {r}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Description */}
                  {cand.description && (
                    <p className="text-xs text-slate-300 italic bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60">
                      "{cand.description}"
                    </p>
                  )}

                  {/* Prior Corrective Actions & Resolution Outcomes */}
                  {cand.corrective_actions.length > 0 && (
                    <div className="rounded-xl bg-slate-950/70 border border-slate-800 p-3 space-y-2">
                      <div className="flex items-center justify-between text-xs font-mono font-bold text-amber-300">
                        <span className="flex items-center gap-1.5">
                          <Wrench className="w-3.5 h-3.5 text-amber-400" />
                          Recorded Corrective Actions ({cand.corrective_actions.length})
                        </span>
                      </div>

                      <div className="space-y-2">
                        {cand.corrective_actions.map((c, idx) => (
                          <div key={idx} className="text-xs space-y-1 pl-2 border-l-2 border-amber-500/40">
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => onNavigate('capa', undefined, c.action_number)}
                                className="font-mono font-bold text-amber-300 hover:underline cursor-pointer"
                              >
                                {c.action_number}
                              </button>
                              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 text-slate-300">
                                {c.status} • Verification: {c.verification_status}
                              </span>
                            </div>
                            {c.root_cause && (
                              <p className="text-slate-300 text-[11px]">
                                <span className="font-bold text-slate-400">Root Cause:</span> {c.root_cause}
                              </p>
                            )}
                            {c.preventive_action && (
                              <p className="text-slate-300 text-[11px]">
                                <span className="font-bold text-slate-400">Preventive Action:</span> {c.preventive_action}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Recorded Reinspection Outcomes */}
                  {cand.reinspections.length > 0 && (
                    <div className="rounded-xl bg-slate-950/70 border border-slate-800 p-3 space-y-1">
                      <span className="text-[10px] font-mono uppercase text-teal-400 font-bold">
                        Reinspection Verification Outcomes:
                      </span>
                      {cand.reinspections.map((r, idx) => (
                        <div key={idx} className="text-xs text-slate-300 flex items-center gap-2">
                          <span className={`font-mono font-bold text-[11px] ${r.outcome === 'DEFECT_RESOLVED' ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {r.outcome}
                          </span>
                          {r.notes && <span className="text-slate-400 text-[11px]">— {r.notes}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
