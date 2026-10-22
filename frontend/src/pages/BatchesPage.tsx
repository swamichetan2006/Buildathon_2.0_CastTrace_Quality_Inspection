import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { batchesApi } from '../api/batches';
import { productsApi } from '../api/products';
import type { Batch, Product } from '../types';
import { useAuth } from '../context/AuthContext';
import { useNotification } from '../context/NotificationContext';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Modal from '../components/common/Modal';
import ConfirmDialog from '../components/common/ConfirmDialog';

interface BatchesPageProps {
  onSelectBatch: (batchId: string) => void;
  selectedProductId?: string;
}

export const BatchesPage: React.FC<BatchesPageProps> = ({ onSelectBatch, selectedProductId }) => {
  const { hasRole } = useAuth();
  const { addToast } = useNotification();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newBatchNumber, setNewBatchNumber] = useState('');
  const [newProductId, setNewProductId] = useState(selectedProductId || '');
  const [newQuantity, setNewQuantity] = useState(50);
  const [newHeatNumber, setNewHeatNumber] = useState('');
  const [newNotes, setNewNotes] = useState('');

  // Hold dialog state
  const [holdBatch, setHoldBatch] = useState<Batch | null>(null);
  const [holdReason, setHoldReason] = useState('');

  const { data: batches = [], isLoading, refetch } = useQuery<Batch[]>({
    queryKey: ['batches', statusFilter, selectedProductId],
    queryFn: () =>
      batchesApi.list({
        status: statusFilter === 'ALL' ? undefined : statusFilter,
        product_id: selectedProductId,
      }),
  });

  const { data: products = [] } = useQuery<Product[]>({
    queryKey: ['products'],
    queryFn: () => productsApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: (data: {
      batch_number: string;
      product_id: string;
      manufacture_date: string;
      declared_quantity: number;
      heat_number?: string;
      notes?: string;
    }) => batchesApi.create(data),
    onSuccess: (newBatch) => {
      addToast('success', `Batch ${newBatch.batch_number} created successfully`);
      setIsCreateOpen(false);
      setNewBatchNumber('');
      setNewHeatNumber('');
      setNewNotes('');
      queryClient.invalidateQueries({ queryKey: ['batches'] });
      onSelectBatch(newBatch.id);
    },
    onError: (err: any) => {
      addToast('error', err.message || 'Failed to create production batch');
    },
  });

  const holdMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      batchesApi.placeHold(id, reason),
    onSuccess: () => {
      addToast('warning', `Containment hold placed on batch ${holdBatch?.batch_number}`);
      setHoldBatch(null);
      setHoldReason('');
      queryClient.invalidateQueries({ queryKey: ['batches'] });
    },
    onError: (err: any) => {
      addToast('error', err.message || 'Failed to apply containment hold');
    },
  });

  const filteredBatches = batches.filter(
    (b) =>
      b.batch_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (b.product?.name && b.product.name.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const canManage = hasRole('SUPERVISOR') || hasRole('QUALITY_MANAGER');

  return (
    <div className="space-y-6">
      {/* Top bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Casting Batches</h1>
          <p className="text-sm text-slate-500 mt-1">
            Manufacturing production runs, containment states, and quality gates.
          </p>
        </div>
        {canManage && (
          <Button onClick={() => setIsCreateOpen(true)} className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            Create Production Batch
          </Button>
        )}
      </div>

      {/* Filters and controls */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <input
            type="text"
            placeholder="Search by batch number or product name..."
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
          <option value="ALL">All Lifecycle Statuses</option>
          <option value="PENDING">Pending Inspection</option>
          <option value="IN_PRODUCTION">In Production</option>
          <option value="ON_HOLD">On Hold (Containment)</option>
          <option value="RELEASED">Released</option>
          <option value="SCRAPPED">Scrapped / Rejected</option>
          <option value="ARCHIVED">Archived</option>
        </select>

        <button
          onClick={() => refetch()}
          className="px-3 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm transition"
        >
          Refresh
        </button>
      </div>

      {/* Batch Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-500">Loading production batches...</div>
        ) : filteredBatches.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <p className="font-semibold text-slate-700">No batches found</p>
            <p className="text-sm mt-1">Adjust the status filter or create a new batch.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3">Batch Number</th>
                  <th className="px-6 py-3">Product Model</th>
                  <th className="px-6 py-3">Declared Lot Size</th>
                  <th className="px-6 py-3">Quality Status</th>
                  <th className="px-6 py-3">Heat / Melt</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredBatches.map((b) => (
                  <tr key={b.id} className="hover:bg-slate-50 transition">
                    <td className="px-6 py-4">
                      <button
                        onClick={() => onSelectBatch(b.id)}
                        className="font-mono font-semibold text-sky-700 hover:text-sky-900 hover:underline"
                      >
                        {b.batch_number}
                      </button>
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-medium text-slate-900">{b.product?.name || 'Impeller'}</span>
                      {b.product?.sku && (
                        <span className="ml-2 text-xs font-mono text-slate-400">
                          ({b.product.sku})
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 font-mono text-slate-700">
                      {b.declared_quantity} physical units
                    </td>
                    <td className="px-6 py-4">
                      <Badge status={b.status} />
                    </td>
                    <td className="px-6 py-4 text-xs font-mono text-slate-500">
                      {b.heat_number || '—'}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      {b.status !== 'ON_HOLD' &&
                        b.status !== 'RELEASED' &&
                        b.status !== 'SCRAPPED' && (
                          <button
                            onClick={() => {
                              setHoldBatch(b);
                              setHoldReason('');
                            }}
                            className="text-xs font-semibold px-2 py-1 bg-amber-50 text-amber-700 hover:bg-amber-100 rounded border border-amber-200"
                          >
                            Place Hold
                          </button>
                        )}
                      <button
                        onClick={() => onSelectBatch(b.id)}
                        className="text-xs font-semibold px-2.5 py-1 bg-sky-50 text-sky-700 hover:bg-sky-100 rounded border border-sky-200"
                      >
                        Inspect & Govern →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Batch Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Create New Production Batch"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate({
              batch_number: newBatchNumber.trim(),
              product_id: newProductId,
              manufacture_date: new Date().toISOString(),
              declared_quantity: Number(newQuantity),
              heat_number: newHeatNumber.trim() || undefined,
              notes: newNotes.trim() || undefined,
            });
          }}
          className="space-y-4"
        >
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Batch / Lot Identifier <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="e.g. BATCH-2026-IMP-001"
              value={newBatchNumber}
              onChange={(e) => setNewBatchNumber(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 font-mono"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Impeller Product Model <span className="text-rose-500">*</span>
            </label>
            <select
              required
              value={newProductId}
              onChange={(e) => setNewProductId(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
            >
              <option value="" disabled>Select product model...</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sku} — {p.name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
                Declared Lot Quantity <span className="text-rose-500">*</span>
              </label>
              <input
                type="number"
                min={1}
                required
                value={newQuantity}
                onChange={(e) => setNewQuantity(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
                Foundry Heat Number
              </label>
              <input
                type="text"
                placeholder="e.g. HEAT-9942"
                value={newHeatNumber}
                onChange={(e) => setNewHeatNumber(e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
              Production Notes / Shift
            </label>
            <textarea
              rows={2}
              value={newNotes}
              onChange={(e) => setNewNotes(e.target.value)}
              placeholder="Furnace notes, mold preparation..."
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button variant="secondary" onClick={() => setIsCreateOpen(false)} type="button">
              Cancel
            </Button>
            <Button type="submit" loading={createMutation.isPending}>
              Create Batch
            </Button>
          </div>
        </form>
      </Modal>

      {/* Hold Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(holdBatch)}
        onClose={() => setHoldBatch(null)}
        title={`Place Containment Hold: ${holdBatch?.batch_number}`}
        message="Placing an operational hold halts further downstream movement until investigated. Please document the operational hold justification."
        confirmText="Confirm Containment Hold"
        variant="warning"
        loading={holdMutation.isPending}
        onConfirm={() => {
          if (!holdReason.trim()) {
            addToast('error', 'Hold reason is required');
            return;
          }
          if (holdBatch) {
            holdMutation.mutate({ id: holdBatch.id, reason: holdReason.trim() });
          }
        }}
      >
        <div className="mt-3">
          <label className="block text-xs font-semibold uppercase text-slate-600 mb-1">
            Operational Hold Reason <span className="text-rose-500">*</span>
          </label>
          <textarea
            required
            rows={2}
            value={holdReason}
            onChange={(e) => setHoldReason(e.target.value)}
            placeholder="e.g. Cluster of surface porosity detected on suction vanes during shift 1..."
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
        </div>
      </ConfirmDialog>
    </div>
  );
};
export default BatchesPage;
