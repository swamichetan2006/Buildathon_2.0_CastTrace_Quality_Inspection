import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { capaApi, reinspectionsApi } from '../api/capa';
import { defectsApi } from '../api/defects';
import type {
  CorrectiveAction,
  CAPAStatus,
  VerificationStatus,
  Defect,
  Reinspection,
} from '../types';
import { useAuth } from '../context/AuthContext';
import { useNotification } from '../context/NotificationContext';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Modal from '../components/common/Modal';
import CAPAWorkflowModal from '../components/domain/CAPAWorkflowModal';
import ReinspectionModal from '../components/domain/ReinspectionModal';

interface CAPAPageProps {
  initialDefectId?: string;
  onNavigateToDefect?: (defectId: string) => void;
}

export const CAPAPage: React.FC<CAPAPageProps> = ({
  initialDefectId,
  onNavigateToDefect,
}) => {
  const { user, hasRole } = useAuth();
  const { addToast } = useNotification();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<'CAPA' | 'REINSPECTIONS'>('CAPA');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [verificationFilter, setVerificationFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  // Modals state
  const [selectedCapa, setSelectedCapa] = useState<CorrectiveAction | null>(null);
  const [reinspectionDefectId, setReinspectionDefectId] = useState<string | null>(null);
  const [reinspectionCapaId, setReinspectionCapaId] = useState<string | null>(null);

  // Create CAPA modal state
  const [isCreateOpen, setIsCreateOpen] = useState(Boolean(initialDefectId));
  const [targetDefectId, setTargetDefectId] = useState(initialDefectId || '');
  const [title, setTitle] = useState('');
  const [actionType, setActionType] = useState<'REWORK' | 'SCRAP' | 'PROCESS_ADJUSTMENT' | 'TRAINING'>('REWORK');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    return d.toISOString().split('T')[0];
  });
  const [rootCause, setRootCause] = useState('');
  const [preventiveActionText, setPreventiveActionText] = useState('');
  const [assignedToUserId, setAssignedToUserId] = useState(user?.id || '');

  // Queries
  const { data: capasData, isLoading: capasLoading, refetch: refetchCapas } = useQuery<{ items: CorrectiveAction[]; total: number }>({
    queryKey: ['capas', statusFilter, verificationFilter],
    queryFn: () =>
      capaApi.list({
        status: statusFilter === 'ALL' ? undefined : (statusFilter as CAPAStatus),
        verification_status:
          verificationFilter === 'ALL' ? undefined : (verificationFilter as VerificationStatus),
      }),
  });

  const capas = capasData?.items || [];

  const { data: defectsData } = useQuery<{ items: Defect[]; total: number }>({
    queryKey: ['defects-for-capa'],
    queryFn: () => defectsApi.list(),
  });

  const defects = defectsData?.items || [];

  const { data: reinspectionsData, isLoading: reinspectionsLoading, refetch: refetchReinspections } = useQuery<{ items: Reinspection[]; total: number }>({
    queryKey: ['reinspections'],
    queryFn: () => reinspectionsApi.list(),
  });

  const reinspections = reinspectionsData?.items || [];

  // Create CAPA Mutation
  const createMutation = useMutation({
    mutationFn: (data: {
      defect_id: string;
      title: string;
      action_type: 'REWORK' | 'SCRAP' | 'PROCESS_ADJUSTMENT' | 'TRAINING';
      description: string;
      assigned_to: string;
      due_date: string;
      root_cause?: string;
      preventive_action?: string;
    }) => capaApi.create(data),
    onSuccess: (newCapa) => {
      addToast('success', 'Corrective and Preventive Action plan established');
      setIsCreateOpen(false);
      setTitle('');
      setDescription('');
      setRootCause('');
      setPreventiveActionText('');
      queryClient.invalidateQueries({ queryKey: ['capas'] });
      queryClient.invalidateQueries({ queryKey: ['defects'] });
      setSelectedCapa(newCapa);
    },
    onError: (err: any) => {
      addToast('error', err.message || 'Failed to create CAPA');
    },
  });

  const filteredCapas = capas.filter((c) => {
    return (
      c.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.action_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (c.root_cause && c.root_cause.toLowerCase().includes(searchTerm.toLowerCase())) ||
      c.defect_id.toLowerCase().includes(searchTerm.toLowerCase())
    );
  });

  const canCreate = hasRole('SUPERVISOR') || hasRole('QUALITY_MANAGER');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            CAPA & Independent Verification
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Root cause investigation, Four-Eyes separation of duties, and post-remediation reinspection.
          </p>
        </div>

        {canCreate && (
          <Button onClick={() => setIsCreateOpen(true)} className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            Create CAPA Plan
          </Button>
        )}
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-slate-200 flex gap-6">
        <button
          onClick={() => setActiveTab('CAPA')}
          className={`pb-3 text-sm font-semibold border-b-2 transition ${
            activeTab === 'CAPA'
              ? 'border-sky-600 text-sky-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          Corrective Actions ({capas.length})
        </button>
        <button
          onClick={() => setActiveTab('REINSPECTIONS')}
          className={`pb-3 text-sm font-semibold border-b-2 transition ${
            activeTab === 'REINSPECTIONS'
              ? 'border-sky-600 text-sky-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          Reinspection Records ({reinspections.length})
        </button>
      </div>

      {activeTab === 'CAPA' ? (
        <div className="space-y-4">
          {/* Filters */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <input
                type="text"
                placeholder="Search by ID, action #, defect or title..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white shadow-sm"
              />
            </div>

            <div>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="w-full px-3 py-2 text-sm font-medium border border-slate-300 rounded-lg bg-white shadow-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500"
              >
                <option value="ALL">All Implementation Statuses</option>
                <option value="OPEN">OPEN (Draft/Assigned)</option>
                <option value="IN_PROGRESS">IN_PROGRESS (Remediation active)</option>
                <option value="COMPLETED">COMPLETED (Implementation done)</option>
                <option value="CANCELLED">CANCELLED</option>
              </select>
            </div>

            <div>
              <select
                value={verificationFilter}
                onChange={(e) => setVerificationFilter(e.target.value)}
                className="w-full px-3 py-2 text-sm font-medium border border-slate-300 rounded-lg bg-white shadow-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500"
              >
                <option value="ALL">All Verification Statuses</option>
                <option value="PENDING">PENDING (Awaiting Independent Verification)</option>
                <option value="VERIFIED">VERIFIED (Four-Eyes Approved)</option>
                <option value="REJECTED">REJECTED (Returned for rework)</option>
              </select>
            </div>
          </div>

          {/* CAPA Table */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            {capasLoading ? (
              <div className="p-8 text-center text-slate-500">Loading CAPA records...</div>
            ) : filteredCapas.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                <p className="font-semibold text-slate-700">No CAPA records found</p>
                <p className="text-sm mt-1">Create a new CAPA plan or adjust filters.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-600">
                  <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                    <tr>
                      <th className="px-6 py-3">Action Number</th>
                      <th className="px-6 py-3">Title & Linked Defect</th>
                      <th className="px-6 py-3">Implementation Status</th>
                      <th className="px-6 py-3">Independent Verification</th>
                      <th className="px-6 py-3">Assignee</th>
                      <th className="px-6 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredCapas.map((capa) => (
                      <tr key={capa.id} className="hover:bg-slate-50 transition">
                        <td className="px-6 py-4 font-mono font-medium text-slate-900">
                          {capa.action_number || capa.id.slice(0, 10)}
                        </td>
                        <td className="px-6 py-4">
                          <span className="font-semibold text-slate-800">{capa.title}</span>
                          <div className="text-xs text-slate-400">
                            Defect:{' '}
                            <button
                              onClick={() => onNavigateToDefect && onNavigateToDefect(capa.defect_id)}
                              className="font-mono text-sky-700 hover:underline"
                            >
                              {capa.defect?.defect_number || capa.defect_id.slice(0, 10)}
                            </button>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <Badge status={capa.status} />
                        </td>
                        <td className="px-6 py-4">
                          <Badge status={capa.verification_status} />
                        </td>
                        <td className="px-6 py-4 font-mono text-xs text-slate-700">
                          {capa.assignee?.full_name || (capa.assigned_to ? capa.assigned_to.slice(0, 8) : 'Unassigned')}
                        </td>
                        <td className="px-6 py-4 text-right space-x-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setSelectedCapa(capa)}
                            className="text-xs"
                          >
                            Manage Workflow
                          </Button>
                          {capa.verification_status === 'VERIFIED' && (
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => {
                                setReinspectionDefectId(capa.defect_id);
                                setReinspectionCapaId(capa.id);
                              }}
                              className="text-xs text-emerald-700 bg-emerald-50 border-emerald-200 hover:bg-emerald-100"
                            >
                              Reinspect Unit
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Reinspections Tab */
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          {reinspectionsLoading ? (
            <div className="p-8 text-center text-slate-500">Loading reinspection history...</div>
          ) : reinspections.length === 0 ? (
            <div className="p-12 text-center text-slate-500">
              <p className="font-semibold text-slate-700">No reinspection records</p>
              <p className="text-sm mt-1">Reinspections are executed on verified CAPA remediation lots.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-600">
                <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-3">Reinspection Number</th>
                    <th className="px-6 py-3">Defect ID</th>
                    <th className="px-6 py-3">Outcome Result</th>
                    <th className="px-6 py-3">Inspector Notes</th>
                    <th className="px-6 py-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {reinspections.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50 transition">
                      <td className="px-6 py-4 font-mono font-medium text-slate-900">
                        {r.reinspection_number || r.id.slice(0, 10)}
                      </td>
                      <td className="px-6 py-4 font-mono text-xs text-slate-700">
                        {r.defect_id ? r.defect_id.slice(0, 10) : 'N/A'}
                      </td>
                      <td className="px-6 py-4">
                        <Badge status={r.outcome} />
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-600 max-w-sm truncate">
                        {r.notes || '—'}
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-500">
                        {new Date(r.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* CAPA Workflow Modal (Start, Complete, Four-Eyes Verification) */}
      {selectedCapa && (
        <CAPAWorkflowModal
          capa={selectedCapa}
          onClose={() => setSelectedCapa(null)}
          onSuccess={() => {
            refetchCapas();
            queryClient.invalidateQueries({ queryKey: ['defects'] });
          }}
        />
      )}

      {/* Reinspection Modal */}
      {reinspectionDefectId && reinspectionCapaId && (
        <ReinspectionModal
          defectId={reinspectionDefectId}
          capaId={reinspectionCapaId}
          onClose={() => {
            setReinspectionDefectId(null);
            setReinspectionCapaId(null);
          }}
          onSuccess={() => {
            refetchReinspections();
            refetchCapas();
            queryClient.invalidateQueries({ queryKey: ['defects'] });
          }}
        />
      )}

      {/* Create CAPA Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Establish Corrective & Preventive Action Plan"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!targetDefectId) {
              addToast('error', 'Target defect is required');
              return;
            }
            createMutation.mutate({
              defect_id: targetDefectId,
              title: title.trim(),
              action_type: actionType,
              description: description.trim(),
              assigned_to: assignedToUserId || user?.id || '',
              due_date: new Date(dueDate).toISOString(),
              root_cause: rootCause.trim() || undefined,
              preventive_action: preventiveActionText.trim() || undefined,
            });
          }}
          className="space-y-4"
        >
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Target Defect <span className="text-rose-500">*</span>
            </label>
            <select
              required
              value={targetDefectId}
              onChange={(e) => setTargetDefectId(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
            >
              <option value="" disabled>Select defect requiring CAPA...</option>
              {defects
                .filter((d) => d.status !== 'RESOLVED')
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.defect_number || d.id.slice(0, 10)} [{d.category}] — {d.severity}
                  </option>
                ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
                CAPA Plan Title <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Weld Repair and Radiographic Check"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
                Remediation Type
              </label>
              <select
                value={actionType}
                onChange={(e) => setActionType(e.target.value as any)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
              >
                <option value="REWORK">REWORK (Fettling / Weld overlay)</option>
                <option value="SCRAP">SCRAP (Part unrecoverable)</option>
                <option value="PROCESS_ADJUSTMENT">PROCESS_ADJUSTMENT (Furnace/Pour)</option>
                <option value="TRAINING">TRAINING (Operator technique)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
                Assigned Implementer ID <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={assignedToUserId}
                onChange={(e) => setAssignedToUserId(e.target.value)}
                placeholder="User UUID of implementer..."
                className="w-full px-3 py-2 text-sm font-mono border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
                Target Due Date
              </label>
              <input
                type="date"
                required
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Remediation Action Description <span className="text-rose-500">*</span>
            </label>
            <textarea
              required
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Step-by-step engineering instructions for repair/remediation..."
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Root Cause Analysis
            </label>
            <textarea
              rows={2}
              value={rootCause}
              onChange={(e) => setRootCause(e.target.value)}
              placeholder="Detailed metallurgic or procedural root cause findings (e.g. Mold degassing issue)..."
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Preventive Action (Systemic)
            </label>
            <textarea
              rows={2}
              value={preventiveActionText}
              onChange={(e) => setPreventiveActionText(e.target.value)}
              placeholder="Process modifications, tooling adjustments, or calibration changes to prevent recurrence..."
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button variant="secondary" onClick={() => setIsCreateOpen(false)} type="button">
              Cancel
            </Button>
            <Button type="submit" loading={createMutation.isPending}>
              Create CAPA Plan
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
export default CAPAPage;
