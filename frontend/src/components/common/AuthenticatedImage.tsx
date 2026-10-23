import React, { useState, useEffect } from 'react';
import { getAuthToken } from '../../api/client';
import { Loader2, ImageOff, ZoomIn, X } from 'lucide-react';

interface AuthenticatedImageProps {
  imageId: string;
  alt?: string;
  className?: string;
  allowZoom?: boolean;
}

interface LoadedState {
  imageId: string;
  src: string | null;
  error: boolean;
}

export const AuthenticatedImage: React.FC<AuthenticatedImageProps> = ({
  imageId,
  alt = 'Inspection specimen photograph',
  className,
  allowZoom = true,
}) => {
  const [loadedState, setLoadedState] = useState<LoadedState | null>(null);
  const [isZoomed, setIsZoomed] = useState<boolean>(false);

  const loading = loadedState?.imageId !== imageId;
  const src = loadedState?.imageId === imageId ? loadedState.src : null;
  const error = loadedState?.imageId === imageId ? loadedState.error : false;

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;

    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    fetch(`/api/v1/images/${imageId}/content`, { headers })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setLoadedState({ imageId, src: objectUrl, error: false });
      })
      .catch((err) => {
        if (!active) return;
        console.error('Failed to load image blob:', err);
        setLoadedState({ imageId, src: null, error: true });
      });

    return () => {
      active = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [imageId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center w-full h-full min-h-[220px] bg-slate-950/80 rounded-xl text-slate-500 space-y-2 p-6">
        <Loader2 className="w-7 h-7 animate-spin text-teal-400" />
        <span className="text-xs font-mono text-slate-400 tracking-wide">Loading surface photograph...</span>
      </div>
    );
  }

  if (error || !src) {
    return (
      <div className="flex flex-col items-center justify-center w-full h-full min-h-[220px] bg-slate-950/80 rounded-xl text-slate-500 space-y-2 p-6 border border-dashed border-slate-800">
        <ImageOff className="w-8 h-8 text-slate-600" />
        <span className="text-xs text-slate-400">Failed to render evidence photograph</span>
        <span className="text-[10px] font-mono text-slate-600">ID: {imageId.slice(0, 8)}...</span>
      </div>
    );
  }

  return (
    <>
      <div className="relative group w-full h-full flex items-center justify-center overflow-hidden rounded-xl bg-slate-950">
        <img
          src={src}
          alt={alt}
          className={className || 'max-h-[320px] w-auto max-w-full object-contain rounded-lg transition-transform duration-200 group-hover:scale-[1.01]'}
        />
        {allowZoom && (
          <button
            type="button"
            onClick={() => setIsZoomed(true)}
            title="Inspect high-resolution photo"
            className="absolute bottom-2 right-2 p-2 rounded-lg bg-slate-900/80 text-teal-300 hover:text-white hover:bg-slate-800 transition-all opacity-0 group-hover:opacity-100 shadow-md border border-slate-700/60 backdrop-blur-xs cursor-pointer flex items-center gap-1.5 text-xs font-mono"
          >
            <ZoomIn className="w-3.5 h-3.5" />
            <span>Enlarge</span>
          </button>
        )}
      </div>

      {/* Lightbox / High-Res Zoom Modal */}
      {isZoomed && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 sm:p-8"
          onClick={() => setIsZoomed(false)}
        >
          <div
            className="relative max-w-5xl max-h-[90vh] bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-950">
              <span className="text-xs font-mono font-semibold text-slate-300 truncate max-w-md">
                {alt}
              </span>
              <button
                type="button"
                onClick={() => setIsZoomed(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 flex items-center justify-center bg-slate-950 overflow-auto max-h-[calc(90vh-60px)]">
              <img
                src={src}
                alt={alt}
                className="max-h-[80vh] w-auto object-contain rounded-lg"
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default AuthenticatedImage;
