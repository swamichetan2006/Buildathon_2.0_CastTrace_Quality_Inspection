import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { productsApi } from '../api/products';
import type { Product } from '../types';
import { useAuth } from '../context/AuthContext';
import { useNotification } from '../context/NotificationContext';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Modal from '../components/common/Modal';

interface ProductsPageProps {
  onSelectProduct?: (productId: string) => void;
}

export const ProductsPage: React.FC<ProductsPageProps> = ({ onSelectProduct }) => {
  const { hasRole } = useAuth();
  const { addToast } = useNotification();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newSku, setNewSku] = useState('');
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newMaterial, setNewMaterial] = useState('Stainless Steel 316');
  const [newDrawingNumber, setNewDrawingNumber] = useState('');

  const { data: products = [], isLoading, error, refetch } = useQuery<Product[]>({
    queryKey: ['products'],
    queryFn: () => productsApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: (data: {
      sku: string;
      name: string;
      description?: string;
      material?: string;
      drawing_number?: string;
    }) => productsApi.create(data),
    onSuccess: () => {
      addToast('success', 'Product registered successfully');
      setIsCreateOpen(false);
      setNewSku('');
      setNewName('');
      setNewDescription('');
      setNewDrawingNumber('');
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
    onError: (err: any) => {
      addToast('error', err.message || 'Failed to register product');
    },
  });

  const filteredProducts = products.filter(
    (p) =>
      p.sku.toLowerCase().includes(search.toLowerCase()) ||
      p.name.toLowerCase().includes(search.toLowerCase())
  );

  const canManage = hasRole('SUPERVISOR') || hasRole('QUALITY_MANAGER');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Product Catalog</h1>
          <p className="text-sm text-slate-400 mt-1">
            Registered pump impeller models, casting alloys, drawings, and specifications.
          </p>
        </div>
        {canManage && (
          <Button onClick={() => setIsCreateOpen(true)} className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            Register Product
          </Button>
        )}
      </div>

      {/* Filter and stats */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <input
            type="text"
            placeholder="Search by SKU or model name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 text-sm border border-slate-700 rounded-xl focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 bg-slate-900 text-white placeholder-slate-500 shadow-sm"
          />
          <svg
            className="w-4 h-4 text-slate-500 absolute left-3.5 top-3.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <button
          onClick={() => refetch()}
          className="px-4 py-2.5 text-sm font-medium text-slate-300 bg-slate-800 border border-slate-700 rounded-xl hover:bg-slate-700 hover:text-white shadow-sm transition cursor-pointer"
        >
          Refresh
        </button>
      </div>

      {/* Table */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl shadow-xl overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-400 font-mono text-sm">Loading catalog...</div>
        ) : error ? (
          <div className="p-8 text-center text-rose-400 font-mono">Failed to load product catalog.</div>
        ) : filteredProducts.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <p className="font-semibold text-slate-300 text-base">No products found</p>
            <p className="text-sm mt-1 text-slate-500">Try adjusting your search criteria or register a new product.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/70 text-xs uppercase font-mono font-semibold text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-6 py-3.5">SKU / Model</th>
                  <th className="px-6 py-3.5">Part Name</th>
                  <th className="px-6 py-3.5">Material</th>
                  <th className="px-6 py-3.5">Drawing #</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {filteredProducts.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-800/50 transition">
                    <td className="px-6 py-4 font-mono font-semibold text-teal-400">{p.sku}</td>
                    <td className="px-6 py-4 font-medium text-white">{p.name}</td>
                    <td className="px-6 py-4 text-slate-300">{p.material || 'Cast Bronze / SS'}</td>
                    <td className="px-6 py-4 font-mono text-xs text-slate-400">{p.drawing_number || '—'}</td>
                    <td className="px-6 py-4">
                      <Badge status={p.is_archived ? 'ARCHIVED' : 'ACTIVE'} />
                    </td>
                    <td className="px-6 py-4 text-right">
                      {onSelectProduct && (
                        <button
                          onClick={() => onSelectProduct(p.id)}
                          className="text-xs font-semibold text-teal-400 hover:text-teal-300 cursor-pointer"
                        >
                          View Batches →
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Register Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Register New Impeller Product"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate({
              sku: newSku.trim(),
              name: newName.trim(),
              description: newDescription.trim() || undefined,
              material: newMaterial.trim() || undefined,
              drawing_number: newDrawingNumber.trim() || undefined,
            });
          }}
          className="space-y-4"
        >
          <div>
            <label className="block text-xs font-mono font-semibold uppercase text-slate-300 mb-1.5 tracking-wider">
              Product SKU / Part Number <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              value={newSku}
              onChange={(e) => setNewSku(e.target.value)}
              placeholder="e.g. CPI-65-200"
              className="w-full px-3.5 py-2.5 text-sm font-mono border border-slate-700 rounded-xl focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 bg-slate-950 text-white placeholder-slate-500"
            />
          </div>
          <div>
            <label className="block text-xs font-mono font-semibold uppercase text-slate-300 mb-1.5 tracking-wider">
              Model Name <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Closed Impeller 200mm"
              className="w-full px-3.5 py-2.5 text-sm border border-slate-700 rounded-xl focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 bg-slate-950 text-white placeholder-slate-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-mono font-semibold uppercase text-slate-300 mb-1.5 tracking-wider">
                Alloy / Material
              </label>
              <input
                type="text"
                value={newMaterial}
                onChange={(e) => setNewMaterial(e.target.value)}
                placeholder="e.g. CF8M Stainless"
                className="w-full px-3.5 py-2.5 text-sm border border-slate-700 rounded-xl focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 bg-slate-950 text-white placeholder-slate-500"
              />
            </div>
            <div>
              <label className="block text-xs font-mono font-semibold uppercase text-slate-300 mb-1.5 tracking-wider">
                Engineering Drawing #
              </label>
              <input
                type="text"
                value={newDrawingNumber}
                onChange={(e) => setNewDrawingNumber(e.target.value)}
                placeholder="e.g. DWG-2026-04"
                className="w-full px-3.5 py-2.5 text-sm font-mono border border-slate-700 rounded-xl focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 bg-slate-950 text-white placeholder-slate-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-mono font-semibold uppercase text-slate-300 mb-1.5 tracking-wider">
              Description / Casting Spec
            </label>
            <textarea
              rows={2}
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              placeholder="Casting alloy, tolerance specs, surface finish standards..."
              className="w-full px-3.5 py-2.5 text-sm border border-slate-700 rounded-xl focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 bg-slate-950 text-white placeholder-slate-500"
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
            <Button variant="secondary" onClick={() => setIsCreateOpen(false)} type="button">
              Cancel
            </Button>
            <Button type="submit" loading={createMutation.isPending}>
              Register Model
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
export default ProductsPage;
