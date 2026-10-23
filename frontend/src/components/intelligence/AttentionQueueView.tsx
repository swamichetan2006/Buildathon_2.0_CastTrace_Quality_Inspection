import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { intelligenceApi } from '../../api/intelligence';
import { Button } from '../common/Button';
import type { AttentionItem, AttentionPriority, Batch } from '../../types';
import {
  AlertOctagon,
  Clock,
  CheckCircle2,
  Filter,
  RefreshCw,
  ExternalLink,
  ShieldAlert,
  Wrench,
  FileCheck2,
  Cpu,
  Sparkles,
} from 'lucide-react';

interface AttentionQueueViewProps {
  batches: Batch[];
  selectedBatchIdentifier: string;
  onSelectBatch: (batchNumber: string) => void;
  onNavigate: (tab: string, contextId?: string, extraId?: string) => void;
}

export const AttentionQueueView: React.FC<AttentionQueueViewProps> = ({
  batches,
  selectedBatchIdentifier,
  onSelectBatch,
  onNavigate,
}) => {
  const [priorityFilter, setPriorityFilter] = useState<string>('ALL');

  const {
    data: attentionData,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ['attention-today', selectedBatchIdentifier, priorityFilter],
    queryFn: () =>
      intelligenceApi.getAttentionItems({
        batch_identifier: selectedBatchIdentifier || undefined,
        priority: priorityFilter !== 'ALL' ? priorityFilter : undefined,
        limit: 100,
      }),
  });

  const handleOpenItem = (item: AttentionItem) => {
    const entity = item.entity_type.toLowerCase();
    const id = item.entity_id;
    if (entity === 'batches') {
      onNavigate('batch', id);
    } else if (entity === 'inspections') {
      onNavigate('inspection', id);
    } else if (entity === 'defects') {
      onNavigate('defect', id);
    } else if (entity === 'corrective_actions') {
      onNavigate('capa', undefined, id);
    } else if (entity === 'inspection_items') {
      onNavigate('inspection', item.related_inspection_id || id);
    } else {
      onNavigate('batch', item.batch_id || id);
    }
  };

  const getPriorityBadgeClass = (priority: AttentionPriority) => {
    switch (priority) {
      case 'CRITICAL':
        return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
      case 'HIGH':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      case 'MEDIUM':
        return 'bg-sky-500/20 text-sky-300 border-sky-500/40';
      case 'LOW':
      default:
        return 'bg-slate-700/30 text-slate-300 border-slate-700/50';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'RELEASE_BLOCKER':
        return <ShieldAlert className="w-4 h-4 text-rose-400" />;
      case 'DEFECT':
        return <AlertOctagon className="w-4 h-4 text-rose-400" />;
      case 'CORRECTIVE_ACTION':
        return <Wrench className="w-4 h-4 text-amber-400" />;
      case 'INSPECTION':
        return <FileCheck2 className="w-4 h-4 text-sky-400" />;
      case 'REVIEW':
      default:
        return <Cpu className="w-4 h-4 text-purple-400" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Controls & Batch Filter */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 space-y-4 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-base font-mono font-bold text-white flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-400" />
              What Needs Attention Today?
            </h2>
            <p className="text-xs text-slate-400">
              Deterministic PostgreSQL factory queue across draft inspections, unreviewed items, defects, and overdue CAPAs.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Scope Filter */}
            <div className="flex items-center gap-2">
              <label htmlFor="attn-batch-selector" className="text-xs font-mono text-slate-400">
                Scope:
              </label>
              <select
                id="attn-batch-selector"
                value={selectedBatchIdentifier}
                onChange={(e) => onSelectBatch(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-amber-500 font-mono"
              >
                <option value="">All Monitored Production Batches</option>
                {batches.map((b) => (
                  <option key={b.id} value={b.batch_number}>
                    {b.batch_number} ({b.status})
                  </option>
                ))}
              </select>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              isLoading={isFetching}
              icon={<RefreshCw className="w-3.5 h-3.5" />}
              className="text-xs font-mono"
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Priority Filter Pills */}
        <div className="flex items-center gap-2 pt-2 border-t border-slate-800/80">
          <span className="text-xs font-mono text-slate-400 flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" /> Filter Priority:
          </span>
          {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((prio) => (
            <button
              key={prio}
              type="button"
              onClick={() => setPriorityFilter(prio)}
              className={`px-3 py-1 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer ${
                priorityFilter === prio
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm'
                  : 'bg-slate-950 text-slate-400 border border-slate-800 hover:text-white'
              }`}
            >
              {prio}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Counters Bar */}
      {attentionData && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="rounded-xl bg-slate-900 border border-slate-800 p-3.5 space-y-1">
            <div className="text-[10px] font-mono uppercase text-slate-400 font-bold">Total Items</div>
            <div className="text-2xl font-extrabold text-white">{attentionData.total_items}</div>
            <div className="text-[10px] text-slate-500 font-mono">Actionable records</div>
          </div>
          <div className="rounded-xl bg-slate-900 border border-rose-500/30 p-3.5 space-y-1">
            <div className="text-[10px] font-mono uppercase text-rose-400 font-bold">Critical</div>
            <div className="text-2xl font-extrabold text-rose-400">{attentionData.critical_count}</div>
            <div className="text-[10px] text-slate-500 font-mono">Blockers & overdue</div>
          </div>
          <div className="rounded-xl bg-slate-900 border border-amber-500/30 p-3.5 space-y-1">
            <div className="text-[10px] font-mono uppercase text-amber-400 font-bold">High Priority</div>
            <div className="text-2xl font-extrabold text-amber-300">{attentionData.high_count}</div>
            <div className="text-[10px] text-slate-500 font-mono">Defects & pending CAPA</div>
          </div>
          <div className="rounded-xl bg-slate-900 border border-slate-800 p-3.5 space-y-1">
            <div className="text-[10px] font-mono uppercase text-slate-400 font-bold">Overdue CAPAs</div>
            <div className="text-2xl font-extrabold text-rose-400">{attentionData.overdue_capas_count}</div>
            <div className="text-[10px] text-slate-500 font-mono">Past deadline</div>
          </div>
          <div className="rounded-xl bg-slate-900 border border-slate-800 p-3.5 space-y-1">
            <div className="text-[10px] font-mono uppercase text-slate-400 font-bold">Unresolved Defects</div>
            <div className="text-2xl font-extrabold text-white">{attentionData.unresolved_defects_count}</div>
            <div className="text-[10px] text-slate-500 font-mono">Confirmed open</div>
          </div>
          <div className="rounded-xl bg-slate-900 border border-slate-800 p-3.5 space-y-1">
            <div className="text-[10px] font-mono uppercase text-slate-400 font-bold">Release Blockers</div>
            <div className="text-2xl font-extrabold text-rose-400">{attentionData.active_release_blockers_count}</div>
            <div className="text-[10px] text-slate-500 font-mono">Gating release</div>
          </div>
        </div>
      )}

      {/* AI Synthesis Summary */}
      {attentionData?.ai_summary && (
        <div className="rounded-xl border border-teal-500/30 bg-teal-950/20 p-4 flex items-start gap-3 animate-in fade-in">
          <Sparkles className="w-5 h-5 text-teal-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="text-xs font-bold text-teal-300 font-mono uppercase tracking-wider">
              Quality Intelligence Synthesis
            </div>
            <p className="text-xs text-slate-200 leading-relaxed">{attentionData.ai_summary}</p>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-28 rounded-2xl bg-slate-900/60 border border-slate-800 p-5 space-y-3">
              <div className="h-4 bg-slate-800 rounded w-1/3"></div>
              <div className="h-3 bg-slate-850 rounded w-2/3"></div>
              <div className="h-3 bg-slate-850 rounded w-1/2"></div>
            </div>
          ))}
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="rounded-2xl border border-rose-800/50 bg-rose-950/20 p-6 space-y-2">
          <div className="flex items-center gap-2 text-rose-400 font-bold text-sm">
            <AlertOctagon className="w-5 h-5 flex-shrink-0" />
            <span>Failed to load Attention Queue</span>
          </div>
          <p className="text-xs text-rose-200 pl-7">
            {error instanceof Error ? error.message : 'Unknown communication error.'}
          </p>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && attentionData && attentionData.items.length === 0 && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
            Zero Immediate Quality Blockers
          </h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            {selectedBatchIdentifier
              ? `Batch ${selectedBatchIdentifier} has no draft inspections, unreviewed items, unresolved defects, or overdue CAPAs.`
              : 'All active manufacturing lots are in a compliant state with zero blocking release criteria or overdue corrective actions.'}
          </p>
        </div>
      )}

      {/* Action Items List */}
      {!isLoading && attentionData && attentionData.items.length > 0 && (
        <div className="space-y-3">
          {attentionData.items.map((item) => (
            <div
              key={item.item_id}
              className="rounded-2xl border border-slate-800 bg-slate-900/80 hover:border-slate-700 p-5 space-y-3.5 transition-all shadow-lg"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${getPriorityBadgeClass(
                      item.priority
                    )}`}
                  >
                    {item.priority}
                  </span>
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                    {getCategoryIcon(item.category)}
                    {item.category.replace('_', ' ')}
                  </span>
                  {item.batch_number && (
                    <button
                      type="button"
                      onClick={() => onNavigate('batch', item.batch_id || item.batch_number || '')}
                      className="text-[10px] font-mono text-teal-400 bg-teal-500/10 hover:bg-teal-500/20 px-2 py-0.5 rounded border border-teal-500/20 transition-colors cursor-pointer"
                    >
                      {item.batch_number}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => handleOpenItem(item)}
                    className="text-[10px] font-mono text-sky-400 bg-sky-500/10 hover:bg-sky-500/20 px-2 py-0.5 rounded border border-sky-500/20 transition-colors font-bold cursor-pointer"
                  >
                    {item.business_identifier}
                  </button>
                  {item.is_overdue && (
                    <span className="text-[10px] font-mono font-bold text-rose-400 bg-rose-500/20 border border-rose-500/30 px-2 py-0.5 rounded animate-pulse">
                      OVERDUE
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono text-slate-400">
                    Status: <span className="text-white font-bold">{item.current_status}</span>
                  </span>
                  {item.due_date && (
                    <span className="text-[11px] font-mono text-slate-400">
                      • Due: <span className={item.is_overdue ? 'text-rose-400 font-bold' : 'text-slate-300'}>{item.due_date}</span>
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => handleOpenItem(item)}
                    className="ml-2 inline-flex items-center text-xs font-mono text-teal-400 hover:text-teal-300 font-bold cursor-pointer"
                  >
                    <span>View Record</span>
                    <ExternalLink className="w-3 h-3 ml-1" />
                  </button>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-bold text-white font-mono">{item.title}</h4>
                <p className="text-xs text-slate-300 mt-1 leading-relaxed">{item.explanation}</p>
              </div>

              {/* Blocking / Attention Reasons */}
              {item.reasons.length > 0 && (
                <div className="rounded-xl bg-slate-950/70 border border-slate-800/80 p-3 space-y-1">
                  <span className="text-[10px] font-mono uppercase text-slate-500 font-bold tracking-wider">
                    Attention Triggers:
                  </span>
                  <ul className="space-y-0.5 text-xs text-slate-400 list-disc list-inside">
                    {item.reasons.map((r, idx) => (
                      <li key={idx} className="leading-snug">
                        {r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
