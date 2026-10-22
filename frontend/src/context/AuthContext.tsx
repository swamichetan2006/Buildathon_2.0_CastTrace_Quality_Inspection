import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { User, UserRole } from '../types';
import { authApi } from '../api/auth';
import { getAuthToken, setAuthToken } from '../api/client';
import { useNotification } from './NotificationContext';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<User>;
  logout: () => void;
  hasRole: (...roles: (UserRole | UserRole[])[]) => boolean;
  isInspector: boolean;
  isSupervisor: boolean;
  isQualityManager: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(getAuthToken());
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const { info, error } = useNotification();

  const logout = useCallback(() => {
    setAuthToken(null);
    setToken(null);
    setUser(null);
  }, []);

  // Initialize auth state
  useEffect(() => {
    async function initAuth() {
      const savedToken = getAuthToken();
      if (!savedToken) {
        setIsLoading(false);
        return;
      }

      try {
        const currentUser = await authApi.getMe();
        setUser(currentUser);
      } catch (err: any) {
        console.warn('Session verification failed:', err.message);
        logout();
      } finally {
        setIsLoading(false);
      }
    }

    initAuth();

    const handleExpired = () => {
      logout();
      info('Session Expired', 'Please log in again to continue.');
    };

    window.addEventListener('auth:expired', handleExpired);
    return () => window.removeEventListener('auth:expired', handleExpired);
  }, [logout, info]);

  const login = async (username: string, password: string): Promise<User> => {
    setIsLoading(true);
    try {
      const res = await authApi.login(username, password);
      setAuthToken(res.access_token);
      setToken(res.access_token);
      setUser(res.user);
      return res.user;
    } catch (err: any) {
      error('Login Failed', err.message || 'Invalid username or password.');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const hasRole = useCallback(
    (...roles: (UserRole | UserRole[])[]): boolean => {
      if (!user) return false;
      if (user.role === 'ADMIN') return true;
      const flatRoles = roles.flat();
      return flatRoles.includes(user.role);
    },
    [user]
  );

  const isInspector = user?.role === 'INSPECTOR';
  const isSupervisor = user?.role === 'SUPERVISOR';
  const isQualityManager = user?.role === 'QUALITY_MANAGER' || user?.role === 'ADMIN';

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        hasRole,
        isInspector,
        isSupervisor,
        isQualityManager,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

// oxlint-disable-next-line react/only-export-components
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
