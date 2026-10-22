import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { inspectionsApi } from '../api/inspections';
import { batchesApi } from '../api/batches';
import type { Batch, Inspection } from '../types';
import { useAuth } from '../context/AuthContext';
import { useNotification } from '../context/NotificationContext';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Modal from '../components/common/Modal';

interface InspectionsPageProps {
  onSelectInspection: (inspectionId: string) => void;
  selectedBatchId?: string;
}

export const InspectionsPage: React.FC<InspectionsPageProps> = ({
  onSelectInspection,
  selectedBatchId,
}) => {
  const { hasRole } = useAuth();
  const { addToast } = useNotification();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newBatchId, setNewBatchId] = useState(selectedBatchId || '');
  const [newStage, setNewStage] = useState('FINAL_VISUAL');
  const [newSamplingPlan, setNewSamplingPlan] = useState('AQL_LEVEL_II');
  const [newNotes, setNewNotes] = useState('');

  const { data: inspections = [], isLoading, refetch } = useQuery<Inspection[]>({
    queryKey: ['inspections', statusFilter, selectedBatchId],
    queryFn: () =>
      inspectionsApi.list({
        status: statusFilter === 'ALL' ? undefined : statusFilter,
        batch_id: selectedBatchId,
      }),
  });

  const { data: batches = [] } = useQuery<Batch[]>({
    queryKey: ['batches-lookup'],
    queryFn: () => batchesApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: (data: { batch_id: string; stage: string; sampling_plan: string; notes?: string }) =>
      inspectionsApi.create(data),
    onSuccess: (newInspection) => {
      addToast('success', 'Inspection session initiated');
      setIsCreateOpen(false);
      queryClient.invalidateQueries({ queryKey: ['inspections'] });
      onSelectInspection(newInspection.id);
    },
    onError: (err: any) => {
      addToast('error', err.message || 'Failed to start inspection');
    },
  });

  const filteredInspections = inspections.filter(
    (ins) =>
      ins.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ins.inspection_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ins.batch_id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const canInspect = hasRole('INSPECTOR') || hasRole('SUPERVISOR') || hasRole('QUALITY_MANAGER');

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Physical Inspections</h1>
          <p className="text-sm text-slate-500 mt-1">
            Inspection lots, physical items registration, evidence photography, and AI routing.
          </p>
        </div>

        {canInspect && (
          <Button onClick={() => setIsCreateOpen(true)} className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            Start Inspection Session
          </Button>
        )}
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <input
            type="text"
            placeholder="Search by inspection ID, number, or batch ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white shadow-sm"
          />
          <svg
            className="w-4 h-4 text-slate-400 absolute left-3 top-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 text-sm font-medium border border-slate-300 rounded-lg bg-white shadow-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500"
        >
          <option value="ALL">All Inspection Statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="SUBMITTED">Submitted</option>
          <option value="IN_REVIEW">In Review</option>
          <option value="COMPLETED">Completed</option>
          <option value="CANCELLED">Cancelled</option>
        </select>

        <button
          onClick={() => refetch()}
          className="px-3 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition shadow-sm"
        >
          Refresh
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-500">Loading inspections...</div>
        ) : filteredInspections.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <p className="font-semibold text-slate-700">No inspections found</p>
            <p className="text-sm mt-1">Select a different filter or initiate an inspection session.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3">Inspection Number</th>
                  <th className="px-6 py-3">Batch ID</th>
                  <th className="px-6 py-3">Stage / Plan</th>
                  <th className="px-6 py-3">Physical Units</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredInspections.map((ins) => (
                  <tr key={ins.id} className="hover:bg-slate-50 transition">
                    <td className="px-6 py-4 font-mono font-medium text-slate-900">
                      {ins.inspection_number || ins.id.slice(0, 8)}
                    </td>
                    <td className="px-6 py-4 font-mono text-slate-700">
                      {ins.batch_id.slice(0, 8)}...
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      <span className="font-medium text-slate-800">{ins.stage}</span>{' '}
                      <span className="text-xs text-slate-400">({ins.sampling_plan})</span>
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      {ins.items?.length || 0} registered unit(s)
                    </td>
                    <td className="px-6 py-4">
                      <Badge status={ins.status} />
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onSelectInspection(ins.id)}
                        className="text-xs"
                      >
                        Open Workspace →
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Start Inspection Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Start Inspection Session"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!newBatchId) {
              addToast('error', 'Please select a production batch');
              return;
            }
            createMutation.mutate({
              batch_id: newBatchId,
              stage: newStage,
              sampling_plan: newSamplingPlan,
              notes: newNotes.trim() || undefined,
            });
          }}
          className="space-y-4"
        >
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Select Production Batch <span className="text-rose-500">*</span>
            </label>
            <select
              required
              value={newBatchId}
              onChange={(e) => setNewBatchId(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
            >
              <option value="" disabled>Select target batch...</option>
              {batches
                .filter((b) => b.status !== 'RELEASED' && b.status !== 'SCRAPPED')
                .map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.batch_number} — {b.product?.name || 'Impeller'} ({b.declared_quantity} units)
                  </option>
                ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
                Inspection Stage
              </label>
              <select
                value={newStage}
                onChange={(e) => setNewStage(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
              >
                <option value="FINAL_VISUAL">FINAL_VISUAL</option>
                <option value="RECEIVING">RECEIVING</option>
                <option value="POST_FETTLING">POST_FETTLING</option>
                <option value="MACHINED">MACHINED</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
                Sampling Plan
              </label>
              <select
                value={newSamplingPlan}
                onChange={(e) => setNewSamplingPlan(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
              >
                <option value="AQL_LEVEL_II">AQL_LEVEL_II (Standard)</option>
                <option value="100_PERCENT">100_PERCENT (Full Population)</option>
                <option value="SPOT_CHECK">SPOT_CHECK (Triage)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Inspection Shift Notes
            </label>
            <textarea
              rows={2}
              value={newNotes}
              onChange={(e) => setNewNotes(e.target.value)}
              placeholder="Inspection workstation, lighting conditions, calibrated optical setup..."
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button variant="secondary" onClick={() => setIsCreateOpen(false)} type="button">
              Cancel
            </Button>
            <Button type="submit" loading={createMutation.isPending}>
              Create Session
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
export default InspectionsPage;
