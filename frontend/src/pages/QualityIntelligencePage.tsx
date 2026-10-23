import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { batchesApi } from '../api/batches';
import { intelligenceApi } from '../api/intelligence';
import { ApiException } from '../api/client';
import { Button } from '../components/common/Button';
import { StatusBadge } from '../components/common/Badge';
import type {
  Batch,
  Citation,
  IntelligenceQueryResponse,
  SourceReference,
} from '../types';
import {

  Sparkles,
  Layers,
  ShieldCheck,
  AlertOctagon,
  AlertTriangle,
  Clock,
  ExternalLink,
  Info,
  Send,
  RotateCcw,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Cpu,
  FileCheck2,
  Wrench,
  ChevronRight,
  ShieldAlert,
  History,
} from 'lucide-react';

import SafeMarkdownViewer from '../components/common/SafeMarkdownViewer';
import { AttentionQueueView } from '../components/intelligence/AttentionQueueView';
import { HistoricalSimilarityView } from '../components/intelligence/HistoricalSimilarityView';

interface QualityIntelligencePageProps {
  initialBatchId?: string | null;
  initialView?: 'lot-summary' | 'attention' | 'recurrence';
  onNavigate: (tab: string, contextId?: string, extraId?: string) => void;
}

export const QualityIntelligencePage: React.FC<QualityIntelligencePageProps> = ({
  initialBatchId,
  initialView = 'lot-summary',
  onNavigate,
}) => {
  const [activeView, setActiveView] = useState<'lot-summary' | 'attention' | 'recurrence'>(initialView);
  const [selectedBatchIdentifier, setSelectedBatchIdentifier] = useState<string>('');
  const [displayedBatchIdentifier, setDisplayedBatchIdentifier] = useState<string | null>(null);
  const [question, setQuestion] = useState<string>('');
  const [queryResult, setQueryResult] = useState<IntelligenceQueryResponse | null>(null);
  const [queryError, setQueryError] = useState<ApiException | Error | null>(null);

  // Fetch authorized batches list for the selector
  const { data: batches = [], isLoading: isLoadingBatches } = useQuery({
    queryKey: ['batches-list-intelligence'],
    queryFn: () => batchesApi.list(),
  });

  // Derive effective selected batch identifier
  const effectiveBatchIdentifier =
    selectedBatchIdentifier ||
    (initialBatchId
      ? batches.find(
          (b) => b.id === initialBatchId || b.batch_number === initialBatchId
        )?.batch_number || initialBatchId
      : batches[0]?.batch_number || '');

  const handleBatchChange = (newBatch: string) => {
    setSelectedBatchIdentifier(newBatch);
    setQueryResult(null);
    setDisplayedBatchIdentifier(null);
    setQueryError(null);
  };

  // Query mutation
  const { mutate: executeQuery, isPending } = useMutation({
    mutationFn: (data: { batch_identifier: string; question: string }) =>
      intelligenceApi.query(data),
    onSuccess: (data, variables) => {
      setQueryResult(data);
      setDisplayedBatchIdentifier(variables.batch_identifier);
      setQueryError(null);
    },
    onError: (err: any) => {
      setQueryError(err);
      setQueryResult(null);
      setDisplayedBatchIdentifier(null);
    },
  });

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!effectiveBatchIdentifier.trim() || !question.trim() || isPending) return;

    // Immediately clear previous response or error to prevent stale batch metrics
    setQueryResult(null);
    setDisplayedBatchIdentifier(null);
    setQueryError(null);

    executeQuery({
      batch_identifier: effectiveBatchIdentifier.trim(),
      question: question.trim(),
    });
  };

  const handleApplyTemplate = (templateQuestion: string) => {
    setQuestion(templateQuestion);
  };

  const handleCitationClick = (citation: Citation) => {
    const entity = citation.entity?.toLowerCase();
    const id = citation.id || citation.source_reference;
    if (!entity) return;

    if (entity === 'batches') {
      onNavigate('batch', id);
    } else if (entity === 'inspections') {
      onNavigate('inspection', id);
    } else if (entity === 'defects') {
      onNavigate('defect', id);
    } else if (entity === 'corrective_actions') {
      onNavigate('capa', undefined, id);
    } else if (entity === 'batch_decisions' || entity === 'release_gates') {
      onNavigate('release-gates', effectiveBatchIdentifier);
    }
  };

  const handleSourceClick = (src: SourceReference) => {
    const entity = src.entity.toLowerCase();
    const id = src.id || src.reference;
    if (entity === 'batches') {
      onNavigate('batch', id);
    } else if (entity === 'inspections') {
      onNavigate('inspection', id);
    } else if (entity === 'defects') {
      onNavigate('defect', id);
    } else if (entity === 'corrective_actions') {
      onNavigate('capa', undefined, id);
    } else if (entity === 'batch_decisions' || entity === 'release_gates') {
      onNavigate('release-gates', effectiveBatchIdentifier);
    }
  };

  const activeBatchObj: Batch | undefined = batches.find(
    (b) =>
      b.batch_number === effectiveBatchIdentifier || b.id === effectiveBatchIdentifier
  );

  return (
    <div className="space-y-6 animate-in fade-in pb-12">
      {/* Top Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border border-slate-800 p-6 md:p-8 shadow-2xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center space-x-2 px-2.5 py-1 rounded-md bg-teal-500/10 text-teal-400 text-xs font-mono mb-2 border border-teal-500/20">
              <Sparkles className="w-3.5 h-3.5" />
              <span>EVIDENCE-GROUNDED QUALITY ASSISTANT</span>
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
              CastTrace Quality Intelligence
            </h1>
            <p className="text-sm text-slate-400 mt-1 max-w-3xl">
              Real-time generative intelligence strictly grounded in verified PostgreSQL inspection records,
              human review outcomes, and corrective actions. Deterministic counts are calculated in SQL;
              GenAI has zero authority to alter lot status or release batches.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-700 text-xs font-mono text-slate-300">
              <Cpu className="w-3.5 h-3.5 text-teal-400" />
              <span>Model: {queryResult?.model_name || 'gemini-flash-lite-latest'}</span>
            </span>
          </div>
        </div>
      </div>

      {/* Feature Navigation Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 pb-3">
        <button
          type="button"
          onClick={() => setActiveView('lot-summary')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-bold transition-all cursor-pointer ${
            activeView === 'lot-summary'
              ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40 shadow-lg'
              : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>1. Lot Quality Assistant</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveView('attention')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-bold transition-all cursor-pointer ${
            activeView === 'attention'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-lg'
              : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
          }`}
        >
          <Clock className="w-3.5 h-3.5 text-amber-400" />
          <span>2. What Needs Attention Today?</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveView('recurrence')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-bold transition-all cursor-pointer ${
            activeView === 'recurrence'
              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-lg'
              : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
          }`}
        >
          <History className="w-3.5 h-3.5 text-purple-400" />
          <span>3. Have We Seen This Issue Before?</span>
        </button>
      </div>

      {/* Feature A: Attention Today View */}
      {activeView === 'attention' && (
        <AttentionQueueView
          batches={batches}
          selectedBatchIdentifier={effectiveBatchIdentifier}
          onSelectBatch={handleBatchChange}
          onNavigate={onNavigate}
        />
      )}

      {/* Feature B: Historical Defect Similarity View */}
      {activeView === 'recurrence' && (
        <HistoricalSimilarityView
          batches={batches}
          initialBatchIdentifier={effectiveBatchIdentifier}
          onNavigate={onNavigate}
        />
      )}

      {/* Main Lot Summary View */}
      {activeView === 'lot-summary' && (
        <div className="space-y-6">
          {/* Query Form Panel */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 space-y-5 shadow-lg">
            <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Batch Selector */}
            <div className="space-y-1.5">
              <label
                htmlFor="batch-selector"
                className="block text-xs font-mono font-bold text-slate-300 uppercase tracking-wider"
              >
                Target Production Batch <span className="text-rose-400">*</span>
              </label>
              <div className="relative">
                <select
                  id="batch-selector"
                  value={effectiveBatchIdentifier}
                  onChange={(e) => handleBatchChange(e.target.value)}
                  disabled={isLoadingBatches || isPending}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-teal-500 font-mono disabled:opacity-50 cursor-pointer"
                >
                  <option value="">-- Select a Production Batch --</option>
                  {batches.map((b) => (
                    <option key={b.id} value={b.batch_number}>
                      {b.batch_number} ({b.status} • Qty: {b.declared_quantity})
                    </option>
                  ))}
                </select>
              </div>
              {activeBatchObj && (
                <div className="flex items-center gap-2 pt-1">
                  <StatusBadge status={activeBatchObj.status} size="sm" />
                  <span className="text-[11px] text-slate-500 font-mono">
                    Heat: {activeBatchObj.heat_number || 'N/A'} • Declared: {activeBatchObj.declared_quantity}
                  </span>
                </div>
              )}
            </div>

            {/* Quick Templates */}
            <div className="md:col-span-2 space-y-1.5">
              <label className="block text-xs font-mono font-bold text-slate-300 uppercase tracking-wider">
                Quick Inquiry Templates
              </label>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={isPending}
                  onClick={() =>
                    handleApplyTemplate(
                      'Summarise this batch, including inspection coverage, confirmed defects, pending reviews, open corrective actions, and release blockers.'
                    )
                  }
                  className="text-xs text-left px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-teal-500/50 text-slate-300 hover:text-white transition-all disabled:opacity-50 cursor-pointer"
                >
                  Full Batch Quality Summary
                </button>
                <button
                  type="button"
                  disabled={isPending}
                  onClick={() =>
                    handleApplyTemplate(
                      'What are the active release blockers and open corrective actions preventing batch release?'
                    )
                  }
                  className="text-xs text-left px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-teal-500/50 text-slate-300 hover:text-white transition-all disabled:opacity-50 cursor-pointer"
                >
                  Release Gate Blockers & CAPAs
                </button>
                <button
                  type="button"
                  disabled={isPending}
                  onClick={() =>
                    handleApplyTemplate(
                      'Detail all human-confirmed defects versus unreviewed AI suggestions on this casting lot.'
                    )
                  }
                  className="text-xs text-left px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-teal-500/50 text-slate-300 hover:text-white transition-all disabled:opacity-50 cursor-pointer"
                >
                  Confirmed Defects vs AI Flags
                </button>
              </div>
            </div>
          </div>

          {/* Question Textarea */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label
                htmlFor="intelligence-question"
                className="block text-xs font-mono font-bold text-slate-300 uppercase tracking-wider"
              >
                Inquiry Question <span className="text-rose-400">*</span>
              </label>
              <span className="text-[11px] font-mono text-slate-500">
                {question.length} / 1500 characters
              </span>
            </div>
            <textarea
              id="intelligence-question"
              rows={3}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask an evidence-grounded question regarding batch defects, inspections, CAPAs, or release readiness..."
              disabled={isPending}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-teal-500 disabled:opacity-50 transition-colors"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-between pt-1">
            <div className="flex items-center text-xs text-slate-500 gap-1.5 font-mono">
              <Info className="w-3.5 h-3.5 text-teal-400 flex-shrink-0" />
              <span>
                Evidence is fetched deterministically from PostgreSQL; mutation commands (e.g. release, close) are rejected.
              </span>
            </div>

            <div className="flex items-center gap-3">
              {question && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setQuestion('')}
                  disabled={isPending}
                >
                  <RotateCcw className="w-3.5 h-3.5 mr-1" />
                  Clear
                </Button>
              )}
              <Button
                type="submit"
                variant="primary"
                size="md"
                isLoading={isPending}
                disabled={!selectedBatchIdentifier.trim() || !question.trim() || isPending}
                icon={<Send className="w-4 h-4" />}
              >
                {isPending ? 'Grounding with Gemini...' : 'Ask Quality Assistant'}
              </Button>
            </div>
          </div>
        </form>
      </div>

      {/* Loading Skeleton */}
      {isPending && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-8 space-y-6 animate-pulse">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-teal-500/20 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-teal-400 animate-spin" />
            </div>
            <div className="space-y-1">
              <div className="h-4 w-48 bg-slate-800 rounded"></div>
              <div className="h-3 w-72 bg-slate-850 rounded"></div>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="h-20 bg-slate-950/80 rounded-xl"></div>
            <div className="h-20 bg-slate-950/80 rounded-xl"></div>
            <div className="h-20 bg-slate-950/80 rounded-xl"></div>
            <div className="h-20 bg-slate-950/80 rounded-xl"></div>
          </div>
          <div className="space-y-2.5 pt-2">
            <div className="h-4 bg-slate-800 rounded w-full"></div>
            <div className="h-4 bg-slate-800 rounded w-5/6"></div>
            <div className="h-4 bg-slate-800 rounded w-4/6"></div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {queryError && (
        <div className="rounded-2xl border border-rose-800/50 bg-rose-950/20 p-6 space-y-3 animate-in fade-in">
          <div className="flex items-center gap-2.5 text-rose-400">
            <AlertOctagon className="w-5 h-5 flex-shrink-0" />
            <h3 className="font-bold text-sm">
              {queryError instanceof ApiException
                ? `Inquiry Error (${queryError.code})`
                : 'Request Failed'}
            </h3>
            {queryError instanceof ApiException && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/20 text-rose-300">
                HTTP {queryError.status}
              </span>
            )}
          </div>
          <p className="text-sm text-rose-200/90 pl-7">{queryError.message}</p>
          {queryError instanceof ApiException && queryError.status === 400 && (
            <div className="pl-7 pt-1 text-xs text-rose-300/80">
              Note: I can answer questions about production batches, inspections, confirmed defects, CAPAs, and release-gate evidence. Please ask a quality-related question.
            </div>
          )}
        </div>
      )}

      {/* Query Result Section */}
      {queryResult && !isPending && displayedBatchIdentifier === effectiveBatchIdentifier && (
        <div className="space-y-6 animate-in fade-in">
          {/* Fallback Banner if applicable */}
          {queryResult.is_fallback && (
            <div className="rounded-xl border border-amber-600/40 bg-amber-950/20 p-4 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-bold text-amber-300 font-mono uppercase tracking-wide">
                  Deterministic Fallback Mode
                </div>
                <div className="text-xs text-slate-300 mt-0.5">
                  Live Gemini API inference was offline or unconfigured. The results below were compiled
                  strictly deterministically from active PostgreSQL inspection and quality records.
                </div>
              </div>
            </div>
          )}

          {/* Section 1: Ground Truth Deterministic Metrics Dashboard */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/95 p-6 space-y-5 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center space-x-2.5">
                <ShieldCheck className="w-5 h-5 text-teal-400" />
                <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                  Deterministic PostgreSQL Quality Metrics
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-400 font-mono">
                  Calculated in SQL • 0 Hallucination
                </span>
                {queryResult.deterministic_metrics.is_release_eligible ? (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-xs font-bold font-mono">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    RELEASE ELIGIBLE
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-400 text-xs font-bold font-mono">
                    <XCircle className="w-3.5 h-3.5" />
                    RELEASE BLOCKED ({queryResult.deterministic_metrics.release_blockers_count})
                  </span>
                )}
              </div>
            </div>

            {/* KPI Metrics Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* Inspection Coverage */}
              <div className="rounded-xl bg-slate-950 border border-slate-800 p-4 space-y-1.5">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="text-[11px] font-mono uppercase font-bold">Coverage</span>
                  <FileCheck2 className="w-4 h-4 text-sky-400" />
                </div>
                <div className="text-xl font-extrabold text-white">
                  {queryResult.deterministic_metrics.inspected_items} / {queryResult.deterministic_metrics.total_declared_quantity}
                </div>
                <div className="text-xs text-slate-400 font-mono">
                  {queryResult.deterministic_metrics.inspection_coverage_pct}% of lot imaged
                </div>
              </div>

              {/* Confirmed Defects */}
              <div className="rounded-xl bg-slate-950 border border-slate-800 p-4 space-y-1.5">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="text-[11px] font-mono uppercase font-bold">Confirmed Defects</span>
                  <AlertOctagon className="w-4 h-4 text-rose-400" />
                </div>
                <div className="text-xl font-extrabold text-rose-400">
                  {queryResult.deterministic_metrics.confirmed_defects_count}
                </div>
                <div className="text-xs text-slate-400 font-mono">
                  {queryResult.deterministic_metrics.open_defects_count} open • {queryResult.deterministic_metrics.resolved_defects_count} resolved
                </div>
              </div>

              {/* AI Flags vs Human Review */}
              <div className="rounded-xl bg-slate-950 border border-slate-800 p-4 space-y-1.5">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="text-[11px] font-mono uppercase font-bold">Unreviewed AI Flags</span>
                  <Cpu className="w-4 h-4 text-purple-400" />
                </div>
                <div className="text-xl font-extrabold text-amber-300">
                  {queryResult.deterministic_metrics.unreviewed_ai_flagged_items}
                </div>
                <div className="text-[10px] text-slate-400 font-mono">
                  Suggestions only (NOT confirmed)
                </div>
              </div>

              {/* Corrective Actions */}
              <div className="rounded-xl bg-slate-950 border border-slate-800 p-4 space-y-1.5">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="text-[11px] font-mono uppercase font-bold">Active CAPAs</span>
                  <Wrench className="w-4 h-4 text-amber-400" />
                </div>
                <div className="text-xl font-extrabold text-white">
                  {queryResult.deterministic_metrics.active_capas_count}
                </div>
                <div className="text-xs text-slate-400 font-mono">
                  {queryResult.deterministic_metrics.overdue_capas_count > 0 ? (
                    <span className="text-rose-400 font-bold">
                      {queryResult.deterministic_metrics.overdue_capas_count} Overdue
                    </span>
                  ) : (
                    <span>0 Overdue</span>
                  )}
                </div>
              </div>
            </div>

            {/* Active Release Blockers list if any */}
            {queryResult.deterministic_metrics.release_blockers.length > 0 && (
              <div className="rounded-xl bg-rose-950/20 border border-rose-900/40 p-4 space-y-2">
                <div className="flex items-center gap-2 text-rose-300 font-mono font-bold text-xs uppercase">
                  <ShieldAlert className="w-4 h-4 text-rose-400" />
                  <span>
                    Release Gate Blockers ({queryResult.deterministic_metrics.release_blockers.length})
                  </span>
                </div>
                <ul className="space-y-1.5 pl-6 list-disc text-xs text-rose-200/90 font-mono">
                  {queryResult.deterministic_metrics.release_blockers.map((blocker, idx) => (
                    <li key={idx}>{blocker}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Section 2: Evidence-Grounded Generative Explanation */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/95 p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center space-x-2.5">
                <Sparkles className="w-5 h-5 text-teal-400" />
                <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                  Grounded Intelligence Synthesis
                </h3>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-400 font-mono">
                <span>Provider: {queryResult.model_provider}</span>
                {queryResult.latency_ms && (
                  <span className="flex items-center gap-1 text-slate-500">
                    <Clock className="w-3.5 h-3.5" />
                    {queryResult.latency_ms} ms
                  </span>
                )}
              </div>
            </div>

            {/* Answer Text Display (Safe, formatted markdown rendering without dangerouslySetInnerHTML) */}
            <div className="p-5 rounded-xl bg-slate-950/80 border border-slate-800/80 text-sm leading-relaxed text-slate-200">
              <SafeMarkdownViewer
                content={queryResult.answer}
                citations={queryResult.citations}
                onCitationClick={handleCitationClick}
              />
            </div>

            {/* Verified Citations Links */}
            {queryResult.citations.length > 0 && (
              <div className="space-y-2 pt-2">
                <span className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-teal-400" />
                  Verified Evidence Citations (Click to drill down)
                </span>
                <div className="flex flex-wrap gap-2">
                  {queryResult.citations.map((c, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleCitationClick(c)}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-300 hover:bg-teal-500/20 text-xs font-mono transition-colors cursor-pointer"
                    >
                      <span className="font-bold">{c.source_reference}</span>
                      {c.entity && (
                        <span className="text-[10px] text-teal-400/80">({c.entity})</span>
                      )}
                      <ExternalLink className="w-3 h-3 text-teal-400" />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Warning for unverified citations if present */}
            {queryResult.unverified_citations.length > 0 && (
              <div className="rounded-xl bg-amber-950/20 border border-amber-600/30 p-3.5 flex items-start gap-2.5 text-xs text-amber-300">
                <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Unverified Citations Filtered: </span>
                  The model output contained reference(s) {queryResult.unverified_citations.join(', ')} which
                  could not be substantiated against retrieved database records.
                </div>
              </div>
            )}
          </div>

          {/* Section 3: Retrieved Source References & Audit Scope */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <span className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-slate-400" />
                Database Evidence Retrieved ({queryResult.retrieved_source_ids.length} records)
              </span>
              <span className="text-[11px] text-slate-500 font-mono">
                Logged to genai_queries & audit_log
              </span>
            </div>

            <div className="flex flex-wrap gap-2">
              {queryResult.retrieved_source_ids.map((src, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSourceClick(src)}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-950 border border-slate-800 hover:border-slate-700 text-xs text-slate-300 font-mono cursor-pointer transition-colors"
                >
                  <span className="text-slate-500">{src.entity}:</span>
                  <span className="font-semibold text-slate-200">{src.reference}</span>
                  <ChevronRight className="w-3 h-3 text-slate-600" />
                </button>
              ))}
            </div>

            {/* Limitations & Disclaimer */}
            <div className="pt-2 border-t border-slate-800/80 space-y-1.5 text-xs text-slate-500 font-mono">
              <div className="flex items-start gap-1.5">
                <HelpCircle className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 mt-0.5" />
                <span>{queryResult.disclaimer}</span>
              </div>
              {queryResult.limitations.map((lim, idx) => (
                <div key={idx} className="pl-5 text-slate-500">
                  • {lim}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      </div>
      )}
    </div>
  );
};

export default QualityIntelligencePage;
