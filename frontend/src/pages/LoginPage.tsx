import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Cpu, ShieldCheck, Wrench, Eye, ArrowRight, Lock, User as UserIcon } from 'lucide-react';
import { Button } from '../components/common/Button';

export const LoginPage: React.FC = () => {
  const { login, isLoading } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;
    try {
      await login(username, password);
    } catch {
      // Error handled by AuthContext
    }
  };

  const handleQuickLogin = async (user: string, pass: string) => {
    setUsername(user);
    setPassword(pass);
    try {
      await login(user, pass);
    } catch {
      // Error handled by AuthContext
    }
  };

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col justify-center items-center p-6 selection:bg-teal-500 selection:text-black">
      {/* Background glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-gradient-to-tr from-teal-500/10 to-emerald-500/5 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md space-y-8 relative z-10">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex w-14 h-14 rounded-2xl bg-gradient-to-tr from-teal-600 to-emerald-400 p-0.5 shadow-xl shadow-teal-500/20 mb-2">
            <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center">
              <Cpu className="w-7 h-7 text-teal-400" />
            </div>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-teal-200 via-white to-slate-200 bg-clip-text text-transparent">
            CastTrace AI
          </h1>
          <p className="text-sm text-slate-400">
            Industrial Quality Inspection & Batch Release Governance System
          </p>
          <div className="text-[11px] text-teal-400 font-mono tracking-widest uppercase">
            Pump Impeller Manufacturing QA
          </div>
        </div>

        {/* Login Form Box */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-7 shadow-2xl backdrop-blur-md space-y-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 font-mono">
                Username
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <UserIcon className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. qm_reynolds"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700/80 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-colors"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 font-mono">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700/80 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-colors"
                  required
                />
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              className="w-full mt-2"
              isLoading={isLoading}
              icon={<ArrowRight className="w-4 h-4" />}
            >
              Sign In to QA Station
            </Button>
          </form>

          {/* Seed Roles Quick Sign-In */}
          <div className="pt-4 border-t border-slate-800 space-y-3">
            <div className="text-[11px] font-mono text-slate-400 text-center uppercase tracking-wider">
              Quick Sign-In by Persona
            </div>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => handleQuickLogin('inspector_chen', 'Password123!')}
                className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 hover:border-teal-500/50 hover:bg-slate-800/60 text-left transition-all group cursor-pointer"
              >
                <div className="flex items-center space-x-1.5 text-teal-400 mb-1">
                  <Eye className="w-3.5 h-3.5" />
                  <span className="text-[11px] font-bold">Inspector</span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono truncate">chen</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('supervisor_torres', 'Password123!')}
                className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 hover:border-amber-500/50 hover:bg-slate-800/60 text-left transition-all group cursor-pointer"
              >
                <div className="flex items-center space-x-1.5 text-amber-400 mb-1">
                  <Wrench className="w-3.5 h-3.5" />
                  <span className="text-[11px] font-bold">Supervisor</span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono truncate">torres</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('qm_reynolds', 'Password123!')}
                className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 hover:border-purple-500/50 hover:bg-slate-800/60 text-left transition-all group cursor-pointer"
              >
                <div className="flex items-center space-x-1.5 text-purple-400 mb-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span className="text-[11px] font-bold">Quality Mgr</span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono truncate">reynolds</div>
              </button>
            </div>
          </div>
        </div>

        {/* Security & System Info */}
        <div className="text-center text-xs text-slate-500 font-mono">
          FastAPI & SQLAlchemy 2 • Role-Based Access Control • Local SQLite
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
