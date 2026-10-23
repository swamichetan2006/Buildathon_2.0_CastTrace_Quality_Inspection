import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { intelligenceApi } from '../../api/intelligence';
import { Button } from '../common/Button';
import { StatusBadge } from '../common/Badge';
import type { Batch, IntelligenceQueryResponse } from '../../types';
import {
  Sparkles,
  ArrowRight,
  Clock,
  Cpu,
} from 'lucide-react';
import SafeMarkdownViewer from '../common/SafeMarkdownViewer';

interface QualityIntelligencePanelProps {
  batches: Batch[];
  onNavigateToIntelligence: (batchNumber?: string, initialView?: 'lot-summary' | 'attention' | 'recurrence') => void;
  onNavigate?: (tab: string, contextId?: string) => void;
}

export const QualityIntelligencePanel: React.FC<QualityIntelligencePanelProps> = ({
  batches,
  onNavigateToIntelligence,
  onNavigate,
}) => {
  const [selectedBatch, setSelectedBatch] = useState<string>(
    batches.length > 0 ? batches[0].batch_number : ''
  );
  const [previewResult, setPreviewResult] = useState<IntelligenceQueryResponse | null>(null);

  const { mutate: runSummary, isPending } = useMutation({
    mutationFn: (batchNum: string) =>
      intelligenceApi.query({
        batch_identifier: batchNum,
        question:
          'Summarise this batch, including inspection coverage, confirmed defects, pending reviews, open corrective actions, and release blockers.',
      }),
    onSuccess: (data) => {
      setPreviewResult(data);
    },
  });

  const handleRunSummary = () => {
    if (!selectedBatch) return;
    runSummary(selectedBatch);
  };

  const activeBatchObj = batches.find(
    (b) => b.batch_number === selectedBatch || b.id === selectedBatch
  );

  return (
    <div className="rounded-2xl border border-teal-500/30 bg-gradient-to-b from-slate-900/95 to-slate-950/95 p-6 space-y-5 shadow-2xl relative overflow-hidden">
      {/* Decorative accent glow */}
      <div className="absolute top-0 right-0 w-64 h-64 bg-teal-500/5 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-teal-500/15 border border-teal-500/30 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-teal-400" />
          </div>
          <div>
            <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider flex items-center gap-2">
              Quality Intelligence Assistant
            </h3>
            <p className="text-xs text-slate-400">
              Deterministic PostgreSQL evidence synthesis via Gemini 2.5 Flash
            </p>
          </div>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => onNavigateToIntelligence(selectedBatch)}
          className="self-start sm:self-auto text-xs font-mono"
        >
          <span>Open Full Assistant</span>
          <ArrowRight className="w-3.5 h-3.5 ml-1 text-teal-400" />
        </Button>
      </div>

      {/* Batch Selector & Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
        {/* Lot Selector */}
        <div className="space-y-1">
          <label
            htmlFor="dashboard-intel-batch"
            className="block text-[11px] font-mono uppercase font-bold text-slate-400"
          >
            Target Production Lot
          </label>
          <select
            id="dashboard-intel-batch"
            value={selectedBatch}
            onChange={(e) => {
              setSelectedBatch(e.target.value);
              setPreviewResult(null);
            }}
            disabled={isPending}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-teal-500 font-mono"
          >
            {batches.map((b) => (
              <option key={b.id} value={b.batch_number}>
                {b.batch_number} ({b.status})
              </option>
            ))}
          </select>
          {activeBatchObj && (
            <div className="flex items-center gap-2 pt-0.5">
              <StatusBadge status={activeBatchObj.status} size="sm" />
              <span className="text-[10px] text-slate-500 font-mono">
                Qty: {activeBatchObj.declared_quantity}
              </span>
            </div>
          )}
        </div>

        {/* Quick Actions (3 cards) */}
        <div className="md:col-span-2 grid grid-cols-1 sm:grid-cols-3 gap-2">
          {/* Action 1: Summarise Selected Lot (Supported & Connected) */}
          <button
            type="button"
            disabled={!selectedBatch || isPending}
            onClick={handleRunSummary}
            className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-teal-500/50 text-left transition-all group disabled:opacity-50 cursor-pointer flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between text-xs font-bold text-white font-mono">
                <span>1. Summarise Lot</span>
                <Sparkles className="w-3.5 h-3.5 text-teal-400 group-hover:scale-110 transition-transform" />
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Grounded coverage, defect counts & blockers
              </p>
            </div>
            <span className="text-[10px] font-mono text-teal-400 font-bold mt-2 flex items-center">
              {isPending ? 'Computing...' : 'Run Query →'}
            </span>
          </button>

          {/* Action 2: What needs attention today? (Enabled & Connected) */}
          <button
            type="button"
            onClick={() => onNavigateToIntelligence(selectedBatch, 'attention')}
            className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-amber-500/50 text-left transition-all group cursor-pointer flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between text-xs font-bold text-white font-mono">
                <span>2. Attention Today?</span>
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Factory triage queue: blockers & overdue CAPAs
              </p>
            </div>
            <span className="text-[10px] font-mono text-amber-400 font-bold mt-2 flex items-center group-hover:translate-x-0.5 transition-transform">
              Open Queue →
            </span>
          </button>

          {/* Action 3: Have we seen this issue before? (Enabled & Connected) */}
          <button
            type="button"
            onClick={() => onNavigateToIntelligence(selectedBatch, 'recurrence')}
            className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-purple-500/50 text-left transition-all group cursor-pointer flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between text-xs font-bold text-white font-mono">
                <span>3. Recurrence Match</span>
                <span className="w-2 h-2 rounded-full bg-purple-400" />
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Multi-factor defect similarity radar
              </p>
            </div>
            <span className="text-[10px] font-mono text-purple-400 font-bold mt-2 flex items-center group-hover:translate-x-0.5 transition-transform">
              Search Similar →
            </span>
          </button>
        </div>
      </div>

      {/* In-Panel Quick Preview */}
      {previewResult && (
        <div className="rounded-xl bg-slate-950/90 border border-slate-800 p-4 space-y-3 animate-in fade-in">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-slate-200">
                Summary for {selectedBatch}
              </span>
              {previewResult.deterministic_metrics.is_release_eligible ? (
                <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 text-[10px] font-mono font-bold">
                  RELEASE ELIGIBLE
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => onNavigate && onNavigate('release-gates')}
                  className="px-2 py-0.5 rounded bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 text-[10px] font-mono font-bold cursor-pointer transition-colors"
                >
                  RELEASE BLOCKED ({previewResult.deterministic_metrics.release_blockers_count})
                </button>
              )}
            </div>

            <div className="flex items-center gap-2 text-[10px] font-mono text-slate-500">
              <Cpu className="w-3 h-3 text-teal-400" />
              <span>{previewResult.model_provider}</span>
              {previewResult.latency_ms && (
                <span className="flex items-center gap-0.5">
                  <Clock className="w-2.5 h-2.5" />
                  {previewResult.latency_ms}ms
                </span>
              )}
            </div>
          </div>

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
            <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-800/80">
              <span className="text-[10px] text-slate-500 block">Coverage</span>
              <span className="font-bold text-white">
                {previewResult.deterministic_metrics.inspected_items} / {previewResult.deterministic_metrics.total_declared_quantity} ({previewResult.deterministic_metrics.inspection_coverage_pct}%)
              </span>
            </div>
            <div
              onClick={() => onNavigate && onNavigate('defects')}
              className="p-2 rounded-lg bg-slate-900/60 border border-slate-800/80 hover:border-slate-700 cursor-pointer transition-colors"
            >
              <span className="text-[10px] text-slate-500 block">Confirmed Defects</span>
              <span className="font-bold text-rose-400">
                {previewResult.deterministic_metrics.confirmed_defects_count}
              </span>
            </div>
            <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-800/80">
              <span className="text-[10px] text-slate-500 block">AI Flagged</span>
              <span className="font-bold text-amber-300">
                {previewResult.deterministic_metrics.unreviewed_ai_flagged_items} (unreviewed)
              </span>
            </div>
            <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-800/80">
              <span className="text-[10px] text-slate-500 block">Active CAPAs</span>
              <span className="font-bold text-white">
                {previewResult.deterministic_metrics.active_capas_count}
              </span>
            </div>
          </div>

          {/* Generative Synthesis Snippet */}
          <div className="text-xs text-slate-300 leading-relaxed max-h-24 overflow-hidden">
            <SafeMarkdownViewer
              content={previewResult.answer}
              citations={previewResult.citations}
            />
          </div>

          {/* Verified Citations Snippet */}
          {previewResult.citations.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[10px] font-mono text-slate-500 uppercase">Citations:</span>
              {previewResult.citations.map((c, idx) => (
                <span
                  key={idx}
                  className="px-2 py-0.5 rounded bg-teal-500/10 border border-teal-500/20 text-teal-300 text-[10px] font-mono font-bold"
                >
                  {c.source_reference}
                </span>
              ))}
            </div>
          )}

          {/* Action Link to Full Investigation */}
          <div className="pt-2 flex justify-end">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onNavigateToIntelligence(selectedBatch)}
              className="text-xs"
            >
              <span>Examine Full Investigation & Source Citations</span>
              <ArrowRight className="w-3.5 h-3.5 ml-1 text-teal-400" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default QualityIntelligencePanel;
