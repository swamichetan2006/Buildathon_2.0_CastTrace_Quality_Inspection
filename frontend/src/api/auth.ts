import { api } from './client';
import type { AuthResponse, User } from '../types';

export const authApi = {
  login: async (username: string, password: string): Promise<AuthResponse> => {
    return api.post<AuthResponse>('/auth/login', { username, password });
  },

  getMe: async (): Promise<User> => {
    return api.get<User>('/auth/me');
  },

  logout: async (): Promise<void> => {
    try {
      await api.post('/auth/logout');
    } catch {
      // Best-effort server notification
    }
  },
};
