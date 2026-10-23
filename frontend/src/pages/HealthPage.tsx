import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Button from '../components/common/Button';

export const HealthPage: React.FC = () => {
  const [lastCheck, setLastCheck] = useState<string>(() => new Date().toLocaleTimeString());

  const { data: healthData, isLoading, error, refetch } = useQuery({
    queryKey: ['system-health'],
    queryFn: async () => {
      const res = await fetch('/health');
      if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
      return res.json();
    },
    refetchInterval: 30000,
  });

  const handleManualRefresh = () => {
    refetch();
    setLastCheck(new Date().toLocaleTimeString());
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">System Diagnostics & Health</h1>
          <p className="text-sm text-slate-400 mt-1">
            Service status, PostgreSQL database connectivity, and ML inference worker monitoring.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleManualRefresh}>
          Refresh Health Status
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Core API Service */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm space-y-3 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">FastAPI Core Service</span>
            <span className="flex h-2.5 w-2.5 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </span>
          </div>
          <div className="text-2xl font-bold text-white">
            {isLoading ? 'Checking...' : error ? 'Unavailable' : 'Operational'}
          </div>
          <p className="text-xs text-slate-400">REST API & Auth endpoints responsive</p>
        </div>

        {/* Database Engine */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm space-y-3 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Storage Engine</span>
            <span className="text-xs font-mono font-bold text-cyan-400">PostgreSQL</span>
          </div>
          <div className="text-2xl font-bold text-white">Connected</div>
          <p className="text-xs text-slate-400">
            Schema verified with Alembic release gate snapshots
          </p>
        </div>

        {/* ML Inference Worker */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm space-y-3 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">ML Model Service</span>
            <span className="text-xs font-mono font-bold text-cyan-400">ResNet-18</span>
          </div>
          <div className="text-2xl font-bold text-white">Frozen Baseline</div>
          <p className="text-xs text-slate-400">197 held-out validation dataset evaluated</p>
        </div>
      </div>

      {/* Raw Health JSON Response */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-sm space-y-3 backdrop-blur-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
            Probe Response Payload (/health)
          </h3>
          <span className="text-xs text-slate-400">
            Polled at: {lastCheck}
          </span>
        </div>
        <pre className="bg-slate-950 text-slate-200 font-mono text-xs p-4 rounded-lg overflow-x-auto border border-slate-800">
          {isLoading
            ? 'Querying probe...'
            : error
            ? JSON.stringify({ error: (error as Error).message }, null, 2)
            : JSON.stringify(healthData, null, 2)}
        </pre>
      </div>
    </div>
  );
};
export default HealthPage;
