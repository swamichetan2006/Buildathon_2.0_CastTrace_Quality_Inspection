import React, { useState } from 'react';
import type { ImageEvidence, ModelRun } from '../../types';
import { StatusBadge, Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { Cpu, RefreshCw, Hash, Eye, Sparkles } from 'lucide-react';
import { inspectionsApi } from '../../api/inspections';
import { useNotification } from '../../context/NotificationContext';
import { AuthenticatedImage } from '../common/AuthenticatedImage';

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
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);
  const [runningInferId, setRunningInferId] = useState<string | null>(null);
  const { addToast } = useNotification();

  // Active image is derived directly during render without cascading setState
  const activeImage =
    (selectedImageId ? images.find((img) => img.id === selectedImageId) : null) ||
    images[0] ||
    null;

  const handleTriggerInference = async (imageId: string) => {
    setRunningInferId(imageId);
    try {
      await inspectionsApi.triggerInference(imageId);
      addToast('success', 'ML inference run enqueued. Processing tensor forward pass.');
      onImageUpdated?.();
      onRefresh?.();
    } catch (err: any) {
      addToast('error', err.message || 'Could not enqueue inference run.');
    } finally {
      setRunningInferId(null);
    }
  };

  const handleRetryInference = async (modelRunId: string) => {
    setRunningInferId(modelRunId);
    try {
      await inspectionsApi.retryInference(modelRunId);
      addToast('success', 'New inference attempt enqueued with incremented attempt counter.');
      onImageUpdated?.();
      onRefresh?.();
    } catch (err: any) {
      addToast('error', err.message || 'Could not retry inference run.');
    } finally {
      setRunningInferId(null);
    }
  };

  if (images.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-700/60 p-8 text-center space-y-2 bg-slate-900/40">
        <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-500">
          <Eye className="w-5 h-5" />
        </div>
        <p className="text-xs text-slate-400 font-medium">No photographic evidence registered for this item yet.</p>
        <p className="text-[11px] text-slate-500">Use &ldquo;Upload Surface Photo&rdquo; above to attach visual casting specimens.</p>
      </div>
    );
  }

  // Find latest model run for active image
  const modelRuns = activeImage?.model_runs || [];
  const latestRun: ModelRun | null = modelRuns.length > 0 ? modelRuns[0] : null;

  const formatModelVersion = (verId?: string | null) => {
    if (!verId) return 'ResNet-18 (v1.0.0)';
    if (verId.length === 36 && verId.includes('-')) {
      return 'ResNet-18 (v1.0.0)';
    }
    return verId;
  };

  const isRunActive = latestRun?.status === 'QUEUED' || latestRun?.status === 'PROCESSING';

  return (
    <div className="space-y-4">
      {/* Multi-Image Thumbnails Selector */}
      {images.length > 1 && (
        <div className="flex items-center space-x-2 overflow-x-auto pb-1">
          {images.map((img, idx) => {
            const isSelected = img.id === activeImage?.id;
            const imgRuns = img.model_runs || [];
            const imgRun = imgRuns[0];
            return (
              <button
                key={img.id}
                onClick={() => setSelectedImageId(img.id)}
                className={`flex-shrink-0 px-3.5 py-2 rounded-xl border text-xs font-mono transition-all cursor-pointer flex items-center space-x-2 ${
                  isSelected
                    ? 'bg-teal-600 text-white font-bold border-teal-400 shadow-md shadow-teal-950/40 ring-1 ring-teal-400/50'
                    : 'bg-slate-800 border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700'
                }`}
              >
                <span className={isSelected ? 'text-teal-100 font-medium' : 'text-slate-400'}>
                  Image {idx + 1}:
                </span>
                <span className="font-bold uppercase tracking-wider">
                  {img.surface_location || img.image_scope}
                </span>
                {imgRun?.status === 'SUCCEEDED' && (
                  <span
                    className={`w-2 h-2 rounded-full ${
                      imgRun.predicted_label === 'DEFECTIVE' ? 'bg-rose-400' : 'bg-emerald-400'
                    }`}
                    title={`Classification: ${imgRun.predicted_label}`}
                  />
                )}
                {(imgRun?.status === 'QUEUED' || imgRun?.status === 'PROCESSING') && (
                  <span title="Processing inference...">
                    <RefreshCw className="w-2.5 h-2.5 animate-spin text-amber-300" />
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Main Image & AI Diagnostic Card */}
      {activeImage && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900 overflow-hidden shadow-xl">
          {/* Diagnostic Header */}
          <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-950/80">
            <div className="flex items-center space-x-2.5">
              <span className="text-xs font-mono font-bold text-white tracking-wide">
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

            {/* Inference Actions & Refresh */}
            <div className="flex items-center space-x-2">
              {onRefresh && (
                <button
                  type="button"
                  onClick={onRefresh}
                  title="Refresh ML diagnostics and status"
                  className="p-1.5 rounded-lg border border-slate-700 bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition-colors cursor-pointer flex items-center gap-1 text-xs"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isRunActive ? 'animate-spin text-teal-400' : ''}`} />
                  <span className="text-[11px] font-mono">Sync</span>
                </button>
              )}

              {canTriggerInference && !latestRun && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => handleTriggerInference(activeImage.id)}
                  loading={runningInferId === activeImage.id}
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
                  loading={runningInferId === latestRun.id}
                  icon={<RefreshCw className="w-3.5 h-3.5" />}
                >
                  Retry Inference (Attempt {latestRun.attempt_number + 1})
                </Button>
              )}
            </div>
          </div>

          {/* Photo Display & ML Diagnostic Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-5">
            {/* Left: Authentic Image Container */}
            <div className="rounded-xl border border-slate-800 bg-slate-950 flex flex-col p-4 space-y-3 relative overflow-hidden">
              <div className="w-full flex-1 min-h-[240px] flex items-center justify-center bg-slate-900/60 rounded-lg overflow-hidden border border-slate-800/80 p-2 relative">
                <AuthenticatedImage
                  imageId={activeImage.id}
                  alt={`${activeImage.original_filename} - ${activeImage.surface_location || activeImage.image_scope}`}
                  className="max-h-[300px] w-auto max-w-full object-contain rounded-md"
                />
              </div>

              {/* Image Metadata Bar */}
              <div className="space-y-1.5 pt-1 border-t border-slate-800/80">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 font-medium">
                    Surface Specimen: <span className="text-teal-400 font-bold uppercase">{activeImage.surface_location || 'Impeller Casting View'}</span>
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">
                    {(activeImage.file_size_bytes / 1024).toFixed(1)} KB
                  </span>
                </div>

                <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
                  <span className="truncate max-w-[180px]" title={activeImage.original_filename}>
                    {activeImage.original_filename}
                  </span>
                  {/* SHA-256 Badge */}
                  <div
                    className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px] text-slate-400"
                    title={`SHA-256 Hash: ${activeImage.sha256_hash}`}
                  >
                    <Hash className="w-2.5 h-2.5 text-teal-400 shrink-0" />
                    <span>SHA256: {activeImage.sha256_hash.substring(0, 12)}...</span>
                  </div>
                </div>

                {activeImage.is_superseded && (
                  <div className="p-2 rounded bg-amber-950/40 border border-amber-800/60 text-[10px] text-amber-300 font-mono flex items-center gap-1.5">
                    <span>⚠️</span>
                    <span>Marked as SUPERSEDED: {activeImage.supersede_reason || 'Replaced by newer photograph'}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Right: ML Inference Diagnostics */}
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 flex flex-col justify-between space-y-4">
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center space-x-2">
                    <Sparkles className="w-4 h-4 text-teal-400" />
                    <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                      ML Prediction Diagnostic
                    </span>
                  </div>
                  {latestRun && <StatusBadge status={latestRun.status} size="sm" />}
                </div>

                {isRunActive && (
                  <div className="p-3 rounded-lg bg-teal-950/40 border border-teal-800/60 text-xs text-teal-300 flex items-center gap-2.5">
                    <RefreshCw className="w-4 h-4 animate-spin text-teal-400 shrink-0" />
                    <div>
                      <div className="font-semibold">Tensor inference active</div>
                      <div className="text-[11px] text-teal-400/80">Worker is executing forward pass on ResNet-18...</div>
                    </div>
                  </div>
                )}

                {latestRun ? (
                  <div className="space-y-3.5 text-xs">
                    <div className="flex justify-between items-center py-1 border-b border-slate-800/50">
                      <span className="text-slate-400 font-medium">Predicted Class:</span>
                      <div>
                        {latestRun.predicted_label ? (
                          <StatusBadge status={latestRun.predicted_label} size="sm" />
                        ) : isRunActive ? (
                          <span className="inline-flex items-center gap-1.5 text-amber-400 font-mono text-[11px]">
                            <RefreshCw className="w-3 h-3 animate-spin" /> PENDING INFERENCE
                          </span>
                        ) : (
                          <span className="text-slate-500 font-mono">PENDING</span>
                        )}
                      </div>
                    </div>

                    <div className="flex justify-between items-center py-1 border-b border-slate-800/50">
                      <span className="text-slate-400 font-medium">Defect Probability:</span>
                      <div>
                        {latestRun.score !== null && latestRun.score !== undefined ? (
                          <div className="flex items-center gap-2.5">
                            <span className="font-mono font-bold text-white text-sm">
                              {(Number(latestRun.score) * 100).toFixed(2)}%
                            </span>
                            <div className="w-20 h-2 bg-slate-800 rounded-full overflow-hidden">
                              <div
                                className={`h-full transition-all duration-500 ${
                                  Number(latestRun.score) >= 0.5 ? 'bg-rose-500' : 'bg-emerald-500'
                                }`}
                                style={{
                                  width: `${Math.min(100, Math.max(0, Number(latestRun.score) * 100))}%`,
                                }}
                              />
                            </div>
                          </div>
                        ) : isRunActive ? (
                          <span className="text-amber-400 font-mono text-[11px]">Computing tensor...</span>
                        ) : (
                          <span className="text-slate-500 font-mono">N/A</span>
                        )}
                      </div>
                    </div>

                    <div className="flex justify-between items-center py-1 border-b border-slate-800/50">
                      <span className="text-slate-400 font-medium">Routing Safeguard:</span>
                      <div>
                        {latestRun.routing_outcome ? (
                          <StatusBadge status={latestRun.routing_outcome} size="sm" />
                        ) : isRunActive ? (
                          <span className="text-amber-400 font-mono text-[11px]">Evaluating gate...</span>
                        ) : (
                          <span className="text-slate-500 font-mono">N/A</span>
                        )}
                      </div>
                    </div>

                    <div className="flex justify-between items-center py-1 border-b border-slate-800/50">
                      <span className="text-slate-400 font-medium">Model Architecture:</span>
                      <span
                        className="font-mono text-teal-300 font-semibold cursor-help"
                        title={latestRun.model_version_id ? `Model Version ID: ${latestRun.model_version_id}` : undefined}
                      >
                        {formatModelVersion(latestRun.model_version_id)}
                      </span>
                    </div>

                    {latestRun.processing_latency_ms !== null && latestRun.processing_latency_ms !== undefined && (
                      <div className="flex justify-between items-center py-1 border-b border-slate-800/50">
                        <span className="text-slate-400 font-medium">Inference Latency:</span>
                        <span className="font-mono text-slate-300">{latestRun.processing_latency_ms} ms</span>
                      </div>
                    )}

                    {latestRun.attempt_number > 1 && (
                      <div className="flex justify-between items-center py-1 border-b border-slate-800/50">
                        <span className="text-slate-400 font-medium">Attempt Counter:</span>
                        <span className="font-mono text-slate-300">Attempt #{latestRun.attempt_number}</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="py-8 text-center space-y-2">
                    <p className="text-xs text-slate-500 font-mono">No ML inference run executed for this photograph.</p>
                    {canTriggerInference && (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleTriggerInference(activeImage.id)}
                        loading={runningInferId === activeImage.id}
                        icon={<Cpu className="w-3.5 h-3.5" />}
                      >
                        Run ML Classifier Now
                      </Button>
                    )}
                  </div>
                )}
              </div>

              {/* Informational Quality Disclaimer */}
              <div className="text-[10px] text-slate-500 font-mono pt-3 border-t border-slate-800/80 leading-relaxed">
                <span className="text-slate-400 font-semibold">Quality Safeguard:</span> AI suggestion assists inspection triage; mandatory human inspector sign-off and four-eyes verification required before release.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ImageEvidenceViewer;
