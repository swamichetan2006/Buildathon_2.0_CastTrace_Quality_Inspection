import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import {
  Activity,
  CheckCircle2,
  XCircle,
  Database,
  Server,
  RefreshCw,
  ShieldCheck,
  Cpu,
  Layers,
  AlertTriangle,
  Clock,
  Code2,
} from 'lucide-react'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

interface HealthResponse {
  status: string
  app_name: string
  environment: string
  version: string
  database: string
  database_latency_ms: number | null
  timestamp: string
  details?: Record<string, unknown>
}

async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch('/health')
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null)
    throw new Error(
      errorBody?.details?.error ||
      `Health check failed with HTTP ${response.status}: ${response.statusText}`
    )
  }
  return response.json()
}

function HealthDashboard() {
  const { data, error, isLoading, isFetching, refetch } = useQuery<HealthResponse, Error>({
    queryKey: ['system-health'],
    queryFn: fetchHealth,
  })

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col font-sans selection:bg-teal-500 selection:text-black">
      {/* Top Banner */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-teal-600 to-emerald-400 p-0.5 shadow-lg shadow-teal-500/20">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Cpu className="w-5 h-5 text-teal-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-teal-200 to-white bg-clip-text text-transparent">
                  CastTrace AI
                </span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400 border border-teal-500/20 font-medium">
                  Phase 1B
                </span>
              </div>
              <p className="text-xs text-slate-400">Quality Inspection & Defect Tracking System</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/50 text-xs">
              <div
                className={`w-2.5 h-2.5 rounded-full ${
                  data?.status === 'healthy'
                    ? 'bg-emerald-500 animate-pulse'
                    : isLoading
                    ? 'bg-amber-400 animate-ping'
                    : 'bg-rose-500'
                }`}
              />
              <span className="text-slate-300 capitalize font-medium">
                {isLoading ? 'Checking...' : data?.status ?? 'Disconnected'}
              </span>
            </div>

            <button
              onClick={() => refetch()}
              disabled={isFetching}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 active:bg-teal-700 disabled:opacity-50 text-white text-xs font-semibold shadow-md shadow-teal-900/30 transition-all cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8 space-y-8">
        {/* Hero / System Status Bar */}
        <section className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-slate-850 to-slate-900 border border-slate-800 p-8 shadow-2xl">
          <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 bg-teal-500/5 rounded-full blur-3xl pointer-events-none" />

          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div>
              <div className="inline-flex items-center space-x-2 px-2.5 py-1 rounded-md bg-slate-800 text-teal-400 text-xs font-mono mb-3 border border-slate-700">
                <Activity className="w-3.5 h-3.5" />
                <span>REAL-TIME SYSTEM DIAGNOSTICS</span>
              </div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
                Project Foundation & Health Verification
              </h1>
              <p className="text-sm text-slate-400 mt-1 max-w-2xl">
                Connecting FastAPI backend, SQLite/SQLAlchemy 2 persistence, and React frontend.
                Live diagnostic probes verify real database connection and round-trip responsiveness.
              </p>
            </div>

            {/* Overall Status Badge */}
            <div className="flex items-center">
              {isLoading ? (
                <div className="flex items-center space-x-3 px-5 py-3 rounded-xl bg-slate-800 border border-slate-700">
                  <RefreshCw className="w-5 h-5 text-amber-400 animate-spin" />
                  <span className="text-sm font-medium text-slate-300">Probing backend & database...</span>
                </div>
              ) : data?.status === 'healthy' ? (
                <div className="flex items-center space-x-3 px-5 py-3 rounded-xl bg-emerald-950/40 border border-emerald-500/30 shadow-lg shadow-emerald-950/50">
                  <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                  <div>
                    <div className="text-sm font-bold text-emerald-300">System Fully Operational</div>
                    <div className="text-xs text-emerald-400/80 font-mono">Backend & Database Connected</div>
                  </div>
                </div>
              ) : (
                <div className="flex items-center space-x-3 px-5 py-3 rounded-xl bg-rose-950/50 border border-rose-500/40 shadow-lg shadow-rose-950/50">
                  <XCircle className="w-6 h-6 text-rose-400" />
                  <div>
                    <div className="text-sm font-bold text-rose-300">Service Degraded / Unavailable</div>
                    <div className="text-xs text-rose-400/80 font-mono">Database or Backend Offline</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Diagnostics Grid */}
        <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Card 1: Backend API */}
          <div className="rounded-xl bg-slate-900/80 border border-slate-800 p-5 space-y-3">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs uppercase font-bold tracking-wider">FastAPI Backend</span>
              <Server className="w-4 h-4 text-teal-400" />
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="text-xl font-bold text-white">
                {isLoading ? 'Checking...' : data ? 'Online' : 'Unreachable'}
              </span>
              {data && <span className="text-xs text-slate-400 font-mono">v{data.version}</span>}
            </div>
            <div className="text-xs text-slate-400 flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span>Route: /health & /api/v1</span>
            </div>
          </div>

          {/* Card 2: Database Connection */}
          <div className="rounded-xl bg-slate-900/80 border border-slate-800 p-5 space-y-3">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs uppercase font-bold tracking-wider">SQLAlchemy 2 DB</span>
              <Database className="w-4 h-4 text-teal-400" />
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="text-xl font-bold text-white">
                {isLoading ? 'Pinging...' : data?.database === 'connected' ? 'Connected' : 'Failed'}
              </span>
              <span className="text-xs text-slate-400 font-mono">SQLite (Local)</span>
            </div>
            <div className="text-xs text-slate-400 flex items-center space-x-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  data?.database === 'connected' ? 'bg-emerald-500' : 'bg-rose-500'
                }`}
              />
              <span>16 Core Tables Migrated</span>
            </div>
          </div>

          {/* Card 3: Round-Trip Latency */}
          <div className="rounded-xl bg-slate-900/80 border border-slate-800 p-5 space-y-3">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs uppercase font-bold tracking-wider">Database Ping</span>
              <Clock className="w-4 h-4 text-teal-400" />
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="text-xl font-bold text-white">
                {isLoading ? '...' : data?.database_latency_ms != null ? `${data.database_latency_ms} ms` : 'N/A'}
              </span>
            </div>
            <div className="text-xs text-slate-400 flex items-center space-x-1.5">
              <span>Active Query: SELECT 1</span>
            </div>
          </div>

          {/* Card 4: Environment */}
          <div className="rounded-xl bg-slate-900/80 border border-slate-800 p-5 space-y-3">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs uppercase font-bold tracking-wider">Environment</span>
              <Layers className="w-4 h-4 text-teal-400" />
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="text-xl font-bold text-white capitalize">
                {isLoading ? '...' : data?.environment ?? 'development'}
              </span>
            </div>
            <div className="text-xs text-slate-400">
              <span>App: {data?.app_name ?? 'CastTrace AI'}</span>
            </div>
          </div>
        </section>

        {/* Error Notification (If any) */}
        {error && (
          <div className="rounded-xl bg-rose-950/60 border border-rose-500/50 p-5 flex items-start space-x-4">
            <AlertTriangle className="w-5 h-5 text-rose-400 mt-0.5 flex-shrink-0" />
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-rose-200">Backend Communication Error</h3>
              <p className="text-xs text-rose-300/80 font-mono">{error.message}</p>
              <p className="text-xs text-slate-400 mt-2">
                Make sure the FastAPI backend is running via{' '}
                <code className="text-teal-400">uvicorn backend.app.main:app --reload</code> on port 8000.
              </p>
            </div>
          </div>
        )}

        {/* Raw Live Response & Seeded Accounts Showcase */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Actual JSON Payload */}
          <div className="rounded-xl bg-slate-900 border border-slate-800 p-6 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2 text-slate-300 font-semibold text-sm">
                <Code2 className="w-4 h-4 text-teal-400" />
                <span>Actual Backend Payload: GET /health</span>
              </div>
              <span className="text-xs font-mono text-slate-500">HTTP 200 / application/json</span>
            </div>
            <pre className="flex-1 bg-slate-950 p-4 rounded-lg font-mono text-xs text-teal-300/90 overflow-x-auto border border-slate-800/80 leading-relaxed">
              {isLoading
                ? '// Querying backend endpoint...'
                : data
                ? JSON.stringify(data, null, 2)
                : '// No data received from server.'}
            </pre>
          </div>

          {/* Right: Demo Seed Roles from Phase 1B */}
          <div className="rounded-xl bg-slate-900 border border-slate-800 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-slate-300 font-semibold text-sm">
                <ShieldCheck className="w-4 h-4 text-teal-400" />
                <span>Seeded Demo Personas (Phase 1B Foundation)</span>
              </div>
              <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400">Idempotent</span>
            </div>
            <p className="text-xs text-slate-400">
              Three authenticated roles have been seeded with bcrypt-hashed credentials into the SQLite database:
            </p>

            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between">
                <div>
                  <div className="text-xs font-bold text-white">David Chen</div>
                  <div className="text-xs text-slate-400 font-mono">inspector_chen</div>
                </div>
                <span className="text-xs px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-semibold">
                  INSPECTOR
                </span>
              </div>

              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between">
                <div>
                  <div className="text-xs font-bold text-white">Elena Torres</div>
                  <div className="text-xs text-slate-400 font-mono">supervisor_torres</div>
                </div>
                <span className="text-xs px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold">
                  SUPERVISOR
                </span>
              </div>

              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between">
                <div>
                  <div className="text-xs font-bold text-white">Dr. Edward Reynolds</div>
                  <div className="text-xs text-slate-400 font-mono">qm_reynolds</div>
                </div>
                <span className="text-xs px-2.5 py-1 rounded-full bg-teal-500/10 text-teal-400 border border-teal-500/20 font-semibold">
                  QUALITY_MANAGER
                </span>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-900/40 py-4 px-6 mt-auto">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-2">
          <span>CastTrace AI — Buildathon 2.0 (Problem Statement 1)</span>
          <span>FastAPI + SQLite + SQLAlchemy 2 + React + TanStack Query + Tailwind CSS</span>
        </div>
      </footer>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <HealthDashboard />
    </QueryClientProvider>
  )
}
