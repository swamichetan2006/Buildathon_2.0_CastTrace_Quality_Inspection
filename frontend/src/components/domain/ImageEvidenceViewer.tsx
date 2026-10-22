import React, { useState } from 'react';
import type { ImageEvidence, ModelRun } from '../../types';
import { StatusBadge, Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { Cpu, RefreshCw, Hash, Layers } from 'lucide-react';
import { inspectionsApi } from '../../api/inspections';
import { useNotification } from '../../context/NotificationContext';

interface ImageEvidenceViewerProps {
  images: ImageEvidence[];
  onImageUpdated?: () => void;
  onRefresh?: () => void;
  canTriggerInference?: boolean;
}

export const ImageEvidenceViewer: React.FC<ImageEvidenceViewerProps> = ({
  images,
  onImageUpdated,
  onRefresh,
  canTriggerInference = true,
}) => {
  const [selectedImageId, setSelectedImageId] = useState<string | null>(
    images.length > 0 ? images[0].id : null
  );
  const [runningInferId, setRunningInferId] = useState<string | null>(null);
  const { success, error } = useNotification();

  const activeImage = images.find((img) => img.id === selectedImageId) || images[0] || null;

  const handleTriggerInference = async (imageId: string) => {
    setRunningInferId(imageId);
    try {
      await inspectionsApi.triggerInference(imageId);
      success('Inference Enqueued', 'ML model run enqueued. Processing tensor forward pass.');
      onImageUpdated?.();
      onRefresh?.();
    } catch (err: any) {
      error('Inference Failed', err.message || 'Could not enqueue inference run.');
    } finally {
      setRunningInferId(null);
    }
  };

  const handleRetryInference = async (modelRunId: string) => {
    setRunningInferId(modelRunId);
    try {
      await inspectionsApi.retryInference(modelRunId);
      success('Inference Retried', 'New model run created with incremented attempt counter.');
      onImageUpdated?.();
      onRefresh?.();
    } catch (err: any) {
      error('Retry Failed', err.message || 'Could not retry inference run.');
    } finally {
      setRunningInferId(null);
    }
  };

  if (images.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center space-y-2 bg-slate-950/40">
        <Layers className="w-8 h-8 text-slate-600 mx-auto" />
        <p className="text-xs text-slate-400">No photographic evidence registered for this item yet.</p>
      </div>
    );
  }

  // Find latest model run for active image
  const modelRuns = activeImage?.model_runs || [];
  const latestRun: ModelRun | null = modelRuns.length > 0 ? modelRuns[0] : null;

  return (
    <div className="space-y-4">
      {/* Multi-Image Thumbnails Selector */}
      {images.length > 1 && (
        <div className="flex items-center space-x-2 overflow-x-auto pb-2">
          {images.map((img, idx) => (
            <button
              key={img.id}
              onClick={() => setSelectedImageId(img.id)}
              className={`flex-shrink-0 px-3 py-2 rounded-xl border text-xs font-mono transition-all cursor-pointer flex items-center space-x-2 ${
                img.id === activeImage?.id
                  ? 'bg-teal-500/20 border-teal-500/50 text-teal-200'
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              <span>Image {idx + 1}:</span>
              <span className="font-bold text-white uppercase">{img.surface_location || img.image_scope}</span>
            </button>
          ))}
        </div>
      )}

      {/* Main Image & AI Diagnostic Card */}
      {activeImage && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900 overflow-hidden shadow-xl">
          {/* Diagnostic Header */}
          <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-950/60">
            <div className="flex items-center space-x-3">
              <span className="text-xs font-mono font-bold text-white">
                {activeImage.original_filename}
              </span>
              <Badge variant="teal" size="sm">
                SCOPE: {activeImage.image_scope}
              </Badge>
              {activeImage.surface_location && (
                <Badge variant="neutral" size="sm">
                  SURFACE: {activeImage.surface_location}
                </Badge>
              )}
            </div>

            {/* Inference Actions */}
            <div className="flex items-center space-x-2">
              {canTriggerInference && !latestRun && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => handleTriggerInference(activeImage.id)}
                  isLoading={runningInferId === activeImage.id}
                  icon={<Cpu className="w-3.5 h-3.5" />}
                >
                  Run ML Classifier
                </Button>
              )}

              {canTriggerInference && latestRun?.status === 'FAILED' && (
                <Button
                  variant="warning"
                  size="sm"
                  onClick={() => handleRetryInference(latestRun.id)}
                  isLoading={runningInferId === latestRun.id}
                  icon={<RefreshCw className="w-3.5 h-3.5" />}
                >
                  Retry Inference (Attempt {latestRun.attempt_number + 1})
                </Button>
              )}
            </div>
          </div>

          {/* Photo Display Placeholder & Info */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-5">
            {/* Left: Image Container */}
            <div className="rounded-xl border border-slate-800 bg-slate-950 flex flex-col items-center justify-center min-h-[220px] p-6 text-center space-y-3 relative overflow-hidden">
              <div className="w-12 h-12 rounded-xl bg-slate-800/80 border border-slate-700 flex items-center justify-center text-teal-400">
                <Layers className="w-6 h-6" />
              </div>
              <div className="text-xs text-slate-300 font-medium">
                Surface Specimen: {activeImage.surface_location || 'Impeller Casting View'}
              </div>
              <div className="text-[11px] text-slate-500 font-mono">
                {activeImage.original_filename} ({(activeImage.file_size_bytes / 1024).toFixed(1)} KB)
              </div>

              {/* SHA-256 Badge */}
              <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-400">
                <Hash className="w-3 h-3 text-teal-400" />
                <span className="truncate max-w-[200px]" title={activeImage.sha256_hash}>
                  SHA256: {activeImage.sha256_hash.substring(0, 16)}...
                </span>
              </div>
            </div>

            {/* Right: ML Inference Diagnostics */}
            <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4 flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center space-x-2">
                    <Cpu className="w-4 h-4 text-teal-400" />
                    <span className="text-xs font-mono font-bold text-white uppercase">ML Prediction Diagnostic</span>
                  </div>
                  {latestRun && <StatusBadge status={latestRun.status} size="sm" />}
                </div>

                {latestRun ? (
                  <div className="mt-3 space-y-3 text-xs">
                    <div className="flex justify-between items-center">
                      <span className="text-slate-400">Predicted Class:</span>
                      <span className="font-extrabold text-white">
                        {latestRun.predicted_label ? (
                          <StatusBadge status={latestRun.predicted_label} size="sm" />
                        ) : (
                          <span className="text-slate-500 font-mono">PENDING</span>
                        )}
                      </span>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-slate-400">Defect Probability:</span>
                      <span className="font-mono font-bold text-white">
                        {latestRun.score !== null && latestRun.score !== undefined
                          ? `${(Number(latestRun.score) * 100).toFixed(2)}%`
                          : 'N/A'}
                      </span>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-slate-400">Routing Safeguard:</span>
                      {latestRun.routing_outcome ? (
                        <StatusBadge status={latestRun.routing_outcome} size="sm" />
                      ) : (
                        <span className="text-slate-500">N/A</span>
                      )}
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-slate-400">Model Version:</span>
                      <span className="font-mono text-teal-300">{latestRun.model_version_id || 'ResNet-18-v1'}</span>
                    </div>

                    {latestRun.processing_latency_ms && (
                      <div className="flex justify-between items-center">
                        <span className="text-slate-400">Inference Latency:</span>
                        <span className="font-mono text-slate-300">{latestRun.processing_latency_ms} ms</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="py-8 text-center space-y-2">
                    <p className="text-xs text-slate-500">No ML inference run executed for this photograph.</p>
                  </div>
                )}
              </div>

              {/* Informational Disclaimer */}
              <div className="text-[10px] text-slate-500 font-mono pt-2 border-t border-slate-800/80">
                AI suggestion assists triage; mandatory human inspector sign-off required.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ImageEvidenceViewer;
