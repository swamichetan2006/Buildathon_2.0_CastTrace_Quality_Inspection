import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { defectsApi } from '../api/defects';
import type { Defect, DefectCategory, DefectSeverity, DefectStatus } from '../types';
import { DEFECT_CATEGORIES } from '../types';
import { useAuth } from '../context/AuthContext';
import { useNotification } from '../context/NotificationContext';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Modal from '../components/common/Modal';
import ConfirmDialog from '../components/common/ConfirmDialog';

interface DefectsPageProps {
  onNavigateToCapa?: (defectId?: string) => void;
  onNavigateToBatch?: (batchId: string) => void;
}

export const DefectsPage: React.FC<DefectsPageProps> = ({
  onNavigateToCapa,
  onNavigateToBatch: _onNavigateToBatch,
}) => {
  const { hasRole } = useAuth();
  const { addToast } = useNotification();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  // Lineage modal state
  const [lineageDefect, setLineageDefect] = useState<Defect | null>(null);

  // Reopen modal state
  const [reopenDefect, setReopenDefect] = useState<Defect | null>(null);
  const [reopenReason, setReopenReason] = useState('');

  // Update modal state
  const [updateDefect, setUpdateDefect] = useState<Defect | null>(null);
  const [editSeverity, setEditSeverity] = useState<DefectSeverity>('MAJOR');
  const [editLocation, setEditLocation] = useState('');
  const [editDescription, setEditDescription] = useState('');

  // Queries
  const { data: defectsData, isLoading } = useQuery<{ items: Defect[]; total: number }>({
    queryKey: ['defects', statusFilter, severityFilter, categoryFilter],
    queryFn: () =>
      defectsApi.list({
        status: statusFilter === 'ALL' ? undefined : (statusFilter as DefectStatus),
        severity: severityFilter === 'ALL' ? undefined : (severityFilter as DefectSeverity),
        category: categoryFilter === 'ALL' ? undefined : (categoryFilter as DefectCategory),
      }),
  });

  const defects = defectsData?.items || [];

  const { data: lineageData } = useQuery<{ defect: Defect; lineage: Defect[] }>({
    queryKey: ['defect-lineage', lineageDefect?.id],
    queryFn: () => (lineageDefect ? defectsApi.getRecurrenceHistory(lineageDefect.id) : Promise.reject('No ID')),
    enabled: Boolean(lineageDefect),
  });

  const lineageHistory = lineageData?.lineage || [];

  // Reopen Mutation
  const reopenMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      defectsApi.reopen(id, reason),
    onSuccess: (updated) => {
      addToast('warning', `Defect ${updated.defect_number || updated.id.slice(0, 8)} reopened with incremented recurrence count`);
      setReopenDefect(null);
      setReopenReason('');
      queryClient.invalidateQueries({ queryKey: ['defects'] });
    },
    onError: (err: any) => {
      addToast('error', err.message || 'Failed to reopen defect');
    },
  });

  // Update Mutation
  const updateMutation = useMutation({
    mutationFn: ({
      id,
      severity,
      surface_location,
      description,
    }: {
      id: string;
      severity: string;
      surface_location?: string;
      description?: string;
    }) => defectsApi.update(id, { severity, surface_location, description }),
    onSuccess: () => {
      addToast('success', 'Defect details updated');
      setUpdateDefect(null);
      queryClient.invalidateQueries({ queryKey: ['defects'] });
    },
    onError: (err: any) => {
      addToast('error', err.message || 'Update rejected');
    },
  });

  const filteredDefects = defects.filter((d) => {
    return (
      d.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.defect_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.category.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (d.description && d.description.toLowerCase().includes(searchTerm.toLowerCase()))
    );
  });

  const canReopen = hasRole('QUALITY_MANAGER') || hasRole('SUPERVISOR');

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Defect Tracking & Lineage</h1>
          <p className="text-sm text-slate-500 mt-1">
            Authoritative 9-category taxonomy, recurrence chains, and root-cause linkage.
          </p>
        </div>
      </div>

      {/* Filter Row */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <div className="sm:col-span-1">
          <input
            type="text"
            placeholder="Search defect ID, number or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white shadow-sm"
          />
        </div>

        <div>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="w-full px-3 py-2 text-sm font-medium border border-slate-300 rounded-lg bg-white shadow-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="ALL">All Categories</option>
            {DEFECT_CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>

        <div>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="w-full px-3 py-2 text-sm font-medium border border-slate-300 rounded-lg bg-white shadow-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="MAJOR">Major</option>
            <option value="MINOR">Minor</option>
          </select>
        </div>

        <div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full px-3 py-2 text-sm font-medium border border-slate-300 rounded-lg bg-white shadow-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="OPEN">Open</option>
            <option value="ACTION_ASSIGNED">Action Assigned</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="PENDING_REINSPECTION">Pending Reinspection</option>
            <option value="RESOLVED">Resolved</option>
            <option value="REOPENED">Reopened</option>
          </select>
        </div>
      </div>

      {/* Defects Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-500">Loading defect records...</div>
        ) : filteredDefects.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <p className="font-semibold text-slate-700">No defects found</p>
            <p className="text-sm mt-1">All criteria satisfied or no matching defects in this view.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3">Defect Number</th>
                  <th className="px-6 py-3">Taxonomy Category</th>
                  <th className="px-6 py-3">Severity</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Recurrence Chain</th>
                  <th className="px-6 py-3">Logged Date</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredDefects.map((def) => {
                  const hasLineage = Boolean(def.prior_defect_id);
                  return (
                    <tr key={def.id} className="hover:bg-slate-50 transition">
                      <td className="px-6 py-4 font-mono font-medium text-slate-900">
                        {def.defect_number || def.id.slice(0, 10)}
                      </td>
                      <td className="px-6 py-4 font-semibold text-slate-800">
                        {def.category.replace(/_/g, ' ')}
                      </td>
                      <td className="px-6 py-4">
                        <Badge status={def.severity} />
                      </td>
                      <td className="px-6 py-4">
                        <Badge status={def.status} />
                      </td>
                      <td className="px-6 py-4">
                        {hasLineage ? (
                          <button
                            onClick={() => setLineageDefect(def)}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-800 hover:bg-amber-200"
                          >
                            <span>🔁 Recurrent Chain</span>
                          </button>
                        ) : (
                          <span className="text-xs text-slate-400 font-mono">Original Instance</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-500">
                        {new Date(def.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-right space-x-2">
                        {/* Open Lineage */}
                        <button
                          onClick={() => setLineageDefect(def)}
                          className="text-xs font-semibold text-slate-600 hover:text-slate-900"
                        >
                          Lineage
                        </button>

                        {/* Assign CAPA */}
                        {onNavigateToCapa && def.status !== 'RESOLVED' && (
                          <button
                            onClick={() => onNavigateToCapa(def.id)}
                            className="text-xs font-semibold text-sky-600 hover:text-sky-800"
                          >
                            Assign CAPA
                          </button>
                        )}

                        {/* Edit metadata */}
                        {def.status !== 'RESOLVED' && (
                          <button
                            onClick={() => {
                              setUpdateDefect(def);
                              setEditSeverity(def.severity);
                              setEditLocation(def.surface_location || '');
                              setEditDescription(def.description || '');
                            }}
                            className="text-xs font-semibold px-2 py-1 bg-slate-100 hover:bg-slate-200 rounded text-slate-700"
                          >
                            Edit
                          </button>
                        )}

                        {/* Reopen Defect */}
                        {def.status === 'RESOLVED' && canReopen && (
                          <button
                            onClick={() => {
                              setReopenDefect(def);
                              setReopenReason('');
                            }}
                            className="text-xs font-semibold px-2 py-1 bg-rose-50 text-rose-700 hover:bg-rose-100 rounded border border-rose-200"
                          >
                            Reopen Defect
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Recurrence Lineage Modal */}
      {lineageDefect && (
        <Modal
          isOpen={Boolean(lineageDefect)}
          onClose={() => setLineageDefect(null)}
          title={`Defect Lineage & History: ${lineageDefect.defect_number || lineageDefect.id.slice(0, 10)}`}
        >
          <div className="space-y-4">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs">
              <span className="font-semibold text-slate-700 block">Category & Severity:</span>
              <div className="flex items-center gap-2 mt-1">
                <span className="font-bold text-slate-900">{lineageDefect.category}</span>
                <Badge status={lineageDefect.severity} size="sm" />
                <Badge status={lineageDefect.status} size="sm" />
              </div>
              {lineageDefect.description && (
                <p className="mt-2 text-slate-600">{lineageDefect.description}</p>
              )}
            </div>

            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                Recurrence Ancestry Chain
              </h4>
              {lineageHistory.length === 0 ? (
                <p className="text-xs text-slate-400">
                  No ancestor records found in recurrence chain. This is the root instance.
                </p>
              ) : (
                <div className="space-y-2">
                  {lineageHistory.map((item, idx) => (
                    <div
                      key={item.id}
                      className="p-3 bg-white border border-slate-200 rounded-lg text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between font-mono font-medium">
                        <span>
                          #{idx + 1} {item.defect_number || item.id.slice(0, 10)}
                        </span>
                        <Badge status={item.status} size="sm" />
                      </div>
                      <div className="text-slate-500">
                        Category: {item.category} • Logged:{' '}
                        {new Date(item.created_at).toLocaleDateString()}
                      </div>
                      {item.resolution_notes && (
                        <div className="text-slate-700 bg-slate-50 p-2 rounded">
                          <span className="font-semibold">Resolution Notes:</span>{' '}
                          {item.resolution_notes}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end pt-3 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setLineageDefect(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Reopen Defect Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(reopenDefect)}
        onClose={() => setReopenDefect(null)}
        title="Reopen Resolved Defect"
        message="Reopening increments the recurrence count and re-flags the linked batch as non-compliant in the release gate."
        confirmText="Confirm Reopen"
        variant="danger"
        loading={reopenMutation.isPending}
        onConfirm={() => {
          if (!reopenReason.trim()) {
            addToast('error', 'Reopening reason is required');
            return;
          }
          if (reopenDefect) {
            reopenMutation.mutate({ id: reopenDefect.id, reason: reopenReason.trim() });
          }
        }}
      >
        <div className="mt-3">
          <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
            Reason for Reopening <span className="text-rose-500">*</span>
          </label>
          <textarea
            required
            rows={2}
            value={reopenReason}
            onChange={(e) => setReopenReason(e.target.value)}
            placeholder="Explain why the previously resolved defect has re-emerged..."
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
          />
        </div>
      </ConfirmDialog>

      {/* Update Metadata Modal */}
      <Modal
        isOpen={Boolean(updateDefect)}
        onClose={() => setUpdateDefect(null)}
        title="Update Defect Details"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (updateDefect) {
              updateMutation.mutate({
                id: updateDefect.id,
                severity: editSeverity,
                surface_location: editLocation.trim() || undefined,
                description: editDescription.trim() || undefined,
              });
            }
          }}
          className="space-y-4"
        >
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Severity Level
            </label>
            <select
              value={editSeverity}
              onChange={(e) => setEditSeverity(e.target.value as DefectSeverity)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
            >
              <option value="CRITICAL">CRITICAL</option>
              <option value="MAJOR">MAJOR</option>
              <option value="MINOR">MINOR</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Surface Location
            </label>
            <input
              type="text"
              value={editLocation}
              onChange={(e) => setEditLocation(e.target.value)}
              placeholder="e.g. SUCTION_EYE"
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Description Notes
            </label>
            <textarea
              rows={3}
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              placeholder="Visual or metallurgical defect description..."
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button variant="secondary" onClick={() => setUpdateDefect(null)} type="button">
              Cancel
            </Button>
            <Button type="submit" loading={updateMutation.isPending}>
              Save Updates
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
export default DefectsPage;
