import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { inspectionsApi } from '../api/inspections';
import type { Inspection } from '../types';
import { useAuth } from '../context/AuthContext';
import { useNotification } from '../context/NotificationContext';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Modal from '../components/common/Modal';
import ConfirmDialog from '../components/common/ConfirmDialog';
import ImageEvidenceViewer from '../components/domain/ImageEvidenceViewer';
import ReviewPanel from '../components/domain/ReviewPanel';

interface InspectionDetailPageProps {
  inspectionId: string;
  onBack: () => void;
  onNavigateToBatch?: (batchId: string) => void;
  onNavigateToDefect?: (defectId: string) => void;
}

export const InspectionDetailPage: React.FC<InspectionDetailPageProps> = ({
  inspectionId,
  onBack,
  onNavigateToBatch,
  onNavigateToDefect: _onNavigateToDefect,
}) => {
  const { hasRole } = useAuth();
  const { addToast } = useNotification();
  const queryClient = useQueryClient();

  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);

  // Register item modal state
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [itemIdentifier, setItemIdentifier] = useState('');
  const [cavityNumber, setCavityNumber] = useState<number | undefined>(undefined);

  // Upload image modal state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadScope, setUploadScope] = useState<'ITEM' | 'SURFACE' | 'BATCH_SAMPLE'>('SURFACE');
  const [uploadLocation, setUploadLocation] = useState('SUCTION_EYE');

  // Submit confirmation dialog state
  const [isSubmitOpen, setIsSubmitOpen] = useState(false);

  // Cancel dialog state
  const [isCancelOpen, setIsCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('');

  // Query
  const { data: inspection, isLoading, refetch } = useQuery<Inspection>({
    queryKey: ['inspection', inspectionId],
    queryFn: () => inspectionsApi.get(inspectionId),
    refetchInterval: (query) => {
      const currentInspection = query.state.data;
      if (!currentInspection) return false;
      const allItems = currentInspection.items || [];
      const hasPendingRuns = allItems.some((item) =>
        item.images?.some((img) =>
          img.model_runs?.some((run) => run.status === 'QUEUED' || run.status === 'PROCESSING')
        )
      );
      return hasPendingRuns ? 1500 : false;
    },
  });

  // Selected item
  const items = inspection?.items || [];
  const activeItem = items.find((it) => it.id === selectedItemId) || items[0] || null;

  // Register Items Mutation
  const registerMutation = useMutation({
    mutationFn: (data: { item_identifier: string; cavity_number?: number }) =>
      inspectionsApi.registerItems(inspectionId, [data]),
    onSuccess: (updatedItems) => {
      addToast('success', 'Physical item registered for inspection');
      setIsRegisterOpen(false);
      setItemIdentifier('');
      setCavityNumber(undefined);
      queryClient.invalidateQueries({ queryKey: ['inspection', inspectionId] });
      if (updatedItems && updatedItems.length > 0) {
        setSelectedItemId(updatedItems[updatedItems.length - 1].id);
      }
    },
    onError: (err: any) => {
      addToast('error', err.message || 'Failed to register inspection item');
    },
  });

  // Upload Evidence Mutation
  const uploadMutation = useMutation({
    mutationFn: (data: { file: File; scope: 'ITEM' | 'SURFACE' | 'BATCH_SAMPLE'; surface_location: string }) => {
      if (!activeItem || !inspection) throw new Error('No physical item selected');
      const formData = new FormData();
      formData.append('file', data.file);
      formData.append('batch_id', inspection.batch_id);
      formData.append('inspection_item_id', activeItem.id);
      formData.append('image_scope', data.scope);
      formData.append('surface_location', data.surface_location);
      return inspectionsApi.uploadEvidence(formData);
    },
    onSuccess: () => {
      addToast('success', 'Photographic evidence uploaded and SHA-256 hashed');
      setIsUploadOpen(false);
      setUploadFile(null);
      queryClient.invalidateQueries({ queryKey: ['inspection', inspectionId] });
    },
    onError: (err: any) => {
      addToast('error', err.message || 'Image upload failed');
    },
  });

  // Submit Inspection Mutation
  const submitMutation = useMutation({
    mutationFn: () => inspectionsApi.submit(inspectionId),
    onSuccess: () => {
      addToast('success', 'Inspection submitted for quality review');
      setIsSubmitOpen(false);
      queryClient.invalidateQueries({ queryKey: ['inspection', inspectionId] });
      queryClient.invalidateQueries({ queryKey: ['inspections'] });
    },
    onError: (err: any) => {
      addToast('error', err.message || 'Failed to submit inspection');
    },
  });

  // Cancel Inspection Mutation
  const cancelMutation = useMutation({
    mutationFn: (reason: string) => inspectionsApi.cancel(inspectionId, reason),
    onSuccess: () => {
      addToast('warning', 'Inspection session cancelled');
      setIsCancelOpen(false);
      setCancelReason('');
      queryClient.invalidateQueries({ queryKey: ['inspection', inspectionId] });
      queryClient.invalidateQueries({ queryKey: ['inspections'] });
    },
    onError: (err: any) => {
      addToast('error', err.message || 'Failed to cancel inspection');
    },
  });

  if (isLoading) {
    return <div className="p-12 text-center text-slate-500">Loading inspection workspace...</div>;
  }

  if (!inspection) {
    return (
      <div className="p-8 text-center text-rose-600">
        Inspection record not found.{' '}
        <button onClick={onBack} className="text-sky-600 underline">
          Return to Inspections
        </button>
      </div>
    );
  }

  const isEditable = inspection.status === 'DRAFT';
  const canAct = hasRole('INSPECTOR') || hasRole('SUPERVISOR') || hasRole('QUALITY_MANAGER');

  return (
    <div className="space-y-6">
      {/* Top action bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-800 transition"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Inspections
        </button>

        <div className="flex items-center gap-2">
          {inspection.batch_id && onNavigateToBatch && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigateToBatch(inspection.batch_id)}
              className="text-xs font-mono"
            >
              Batch: {inspection.batch_id.slice(0, 8)}... →
            </Button>
          )}

          {isEditable && canAct && (
            <>
              <Button
                variant="danger"
                size="sm"
                onClick={() => setIsCancelOpen(true)}
                className="text-xs"
              >
                Cancel Session
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsSubmitOpen(true)}
                className="text-xs"
              >
                Submit Inspection
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Header Banner */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-sm backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold font-mono text-white">
                Inspection {inspection.inspection_number || inspection.id.slice(0, 10)}
              </h1>
              <Badge status={inspection.status} />
            </div>
            <p className="text-sm text-slate-400 mt-1">
              Registered Physical Units:{' '}
              <span className="font-semibold text-white">{items.length} item(s)</span>
              <span className="mx-2">•</span>
              Multiple photographic surfaces per physical impeller are grouped and aggregated.
            </p>
          </div>
          <div className="text-xs text-slate-400">
            Stage: <span className="font-semibold text-slate-300">{inspection.stage}</span> • Created:{' '}
            {new Date(inspection.created_at).toLocaleString()}
          </div>
        </div>
      </div>

      {/* Main Inspection Workspace Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Column: Physical Items List */}
        <div className="lg:col-span-1 bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm space-y-4 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
              Physical Items
            </h2>
            {isEditable && canAct && (
              <button
                onClick={() => setIsRegisterOpen(true)}
                className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                </svg>
                Add Unit
              </button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-400 border border-dashed border-slate-800 rounded-lg bg-slate-950/40">
              No physical units registered yet.{' '}
              {isEditable && canAct && (
                <button
                  onClick={() => setIsRegisterOpen(true)}
                  className="text-cyan-400 hover:text-cyan-300 underline block mt-2 font-medium"
                >
                  Register first unit
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {items.map((item, idx) => {
                const isSelected = activeItem?.id === item.id;
                const imagesCount = item.images?.length || 0;
                return (
                  <div
                    key={item.id}
                    onClick={() => setSelectedItemId(item.id)}
                    className={`p-3 rounded-lg border text-left cursor-pointer transition ${
                      isSelected
                        ? 'border-cyan-500 bg-cyan-950/40 shadow-sm'
                        : 'border-slate-800 bg-slate-950/40 hover:border-slate-700 hover:bg-slate-800/50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-white">
                        #{idx + 1} {item.item_identifier}
                      </span>
                      <Badge status={item.status} size="sm" />
                    </div>
                    <div className="mt-1 flex items-center justify-between text-xs text-slate-400">
                      <span>{imagesCount} surface photo{imagesCount === 1 ? '' : 's'}</span>
                      {item.cavity_number && (
                        <span className="font-mono text-[10px] text-slate-400">
                          Cavity: {item.cavity_number}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Physical Item Workspace */}
        <div className="lg:col-span-3 space-y-6">
          {activeItem ? (
            <>
              {/* Active Item Header */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm space-y-3 backdrop-blur-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-3">
                      <h2 className="text-lg font-bold font-mono text-white">
                        Unit Identifier: {activeItem.item_identifier}
                      </h2>
                      <Badge status={activeItem.status} />
                    </div>
                    <p className="text-xs text-slate-400 mt-1">
                      System Item ID: <span className="font-mono text-slate-300">{activeItem.id}</span>
                      {activeItem.cavity_number && (
                        <>
                          <span className="mx-2">•</span>
                          Mold Cavity Index: <span className="font-mono text-slate-300">{activeItem.cavity_number}</span>
                        </>
                      )}
                    </p>
                  </div>

                  {canAct && (
                    <Button
                      size="sm"
                      onClick={() => setIsUploadOpen(true)}
                      className="text-xs flex items-center gap-1.5"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                      </svg>
                      Upload Surface Photo
                    </Button>
                  )}
                </div>
              </div>

              {/* Multi-Surface Image Evidence Gallery */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4 backdrop-blur-sm">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                    Photographic Evidence & ML Inference Diagnostics
                  </h3>
                  <span className="text-xs text-slate-400">
                    {activeItem.images?.length || 0} surface photo(s)
                  </span>
                </div>

                <ImageEvidenceViewer
                  images={activeItem.images || []}
                  onRefresh={() => refetch()}
                />
              </div>

              {/* Human Review & Adjudication Workspace */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm backdrop-blur-sm">
                <ReviewPanel
                  item={activeItem}
                  onReviewSubmitted={() => {
                    refetch();
                    queryClient.invalidateQueries({ queryKey: ['defects'] });
                  }}
                  onDisputeSubmitted={() => refetch()}
                />
              </div>
            </>
          ) : (
            <div className="p-12 text-center text-slate-400 bg-slate-900/90 border border-slate-800 rounded-xl backdrop-blur-sm">
              Register or select a physical unit from the list to begin inspection.
            </div>
          )}
        </div>
      </div>

      {/* Register Physical Item Modal */}
      <Modal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        title="Register Physical Impeller Unit"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            registerMutation.mutate({
              item_identifier: itemIdentifier.trim(),
              cavity_number: cavityNumber ? Number(cavityNumber) : undefined,
            });
          }}
          className="space-y-4"
        >
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-300 mb-1">
              Part Identifier / Casting Tag <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              value={itemIdentifier}
              onChange={(e) => setItemIdentifier(e.target.value)}
              placeholder="e.g. SN-IMP-2026-081"
              className="w-full px-3 py-2 text-sm font-mono border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-slate-950 text-white placeholder-slate-500"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-300 mb-1">
              Die Cavity Number (Optional)
            </label>
            <input
              type="number"
              min={1}
              value={cavityNumber || ''}
              onChange={(e) => setCavityNumber(e.target.value ? Number(e.target.value) : undefined)}
              placeholder="e.g. 2"
              className="w-full px-3 py-2 text-sm border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-slate-950 text-white placeholder-slate-500"
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
            <Button variant="secondary" onClick={() => setIsRegisterOpen(false)} type="button">
              Cancel
            </Button>
            <Button type="submit" loading={registerMutation.isPending}>
              Register Unit
            </Button>
          </div>
        </form>
      </Modal>

      {/* Upload Photographic Evidence Modal */}
      <Modal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        title="Upload Inspection Photographic Evidence"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!uploadFile) {
              addToast('error', 'Please choose an image file');
              return;
            }
            uploadMutation.mutate({
              file: uploadFile,
              scope: uploadScope,
              surface_location: uploadLocation,
            });
          }}
          className="space-y-4"
        >
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-300 mb-1">
              Select Photographic Evidence <span className="text-rose-400">*</span>
            </label>
            <input
              type="file"
              accept="image/png,image/jpeg"
              required
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  setUploadFile(e.target.files[0]);
                }
              }}
              className="w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border file:border-cyan-800 file:text-xs file:font-semibold file:bg-cyan-950 file:text-cyan-300 hover:file:bg-cyan-900 cursor-pointer"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-300 mb-1">
                Imaging Scope
              </label>
              <select
                value={uploadScope}
                onChange={(e) => setUploadScope(e.target.value as 'ITEM' | 'SURFACE' | 'BATCH_SAMPLE')}
                className="w-full px-3 py-2 text-sm border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-slate-950 text-white"
              >
                <option value="SURFACE">Surface Detailed</option>
                <option value="ITEM">Full Component (Item)</option>
                <option value="BATCH_SAMPLE">Batch Sample</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-300 mb-1">
                Surface Location
              </label>
              <select
                value={uploadLocation}
                onChange={(e) => setUploadLocation(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-slate-950 text-white"
              >
                <option value="SUCTION_EYE">Suction Eye</option>
                <option value="VANES">Impeller Vanes</option>
                <option value="HUB_SHROUD">Hub & Shroud</option>
                <option value="OUTLET_TIPS">Outlet Tips</option>
                <option value="BORE">Drive Bore</option>
                <option value="KEYWAY">Keyway</option>
                <option value="OTHER">Other Surface</option>
              </select>
            </div>
          </div>

          <p className="text-xs text-slate-400 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800">
            Uploaded images are immediately hashed via SHA-256 for chain-of-custody verification
            and sent to the ML inference pipeline.
          </p>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
            <Button variant="secondary" onClick={() => setIsUploadOpen(false)} type="button">
              Cancel
            </Button>
            <Button type="submit" loading={uploadMutation.isPending}>
              Upload Evidence
            </Button>
          </div>
        </form>
      </Modal>

      {/* Submit Inspection Confirmation Dialog */}
      <ConfirmDialog
        isOpen={isSubmitOpen}
        onClose={() => setIsSubmitOpen(false)}
        title="Submit Inspection for Review"
        message="Submitting locks the physical item registration and triggers final quality routing evaluation. Are you sure you wish to submit?"
        confirmText="Confirm Submission"
        variant="primary"
        loading={submitMutation.isPending}
        onConfirm={() => submitMutation.mutate()}
      />

      {/* Cancel Inspection Dialog */}
      <ConfirmDialog
        isOpen={isCancelOpen}
        onClose={() => setIsCancelOpen(false)}
        title="Cancel Inspection Session"
        message="Cancelling terminates this inspection session. Please document the reason for cancellation."
        confirmText="Confirm Cancellation"
        variant="danger"
        loading={cancelMutation.isPending}
        onConfirm={() => {
          if (!cancelReason.trim()) {
            addToast('error', 'Cancellation reason is required');
            return;
          }
          cancelMutation.mutate(cancelReason.trim());
        }}
      >
        <div className="mt-3">
          <label className="block text-xs font-semibold uppercase text-slate-300 mb-1">
            Reason for Cancellation <span className="text-rose-400">*</span>
          </label>
          <textarea
            required
            rows={2}
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            placeholder="e.g. Test aborted due to camera calibration error..."
            className="w-full px-3 py-2 text-sm border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500 bg-slate-950 text-white placeholder-slate-500"
          />
        </div>
      </ConfirmDialog>
    </div>
  );
};
export default InspectionDetailPage;
