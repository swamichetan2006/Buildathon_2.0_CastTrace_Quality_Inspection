import { api } from './client';
import type { Defect } from '../types';

export const defectsApi = {
  list: async (params?: {
    status?: string;
    category?: string;
    severity?: string;
    inspection_item_id?: string;
  }): Promise<{ items: Defect[]; total: number }> => {
    const query = new URLSearchParams();
    if (params?.status) query.append('status', params.status);
    if (params?.category) query.append('category', params.category);
    if (params?.severity) query.append('severity', params.severity);
    if (params?.inspection_item_id) query.append('inspection_item_id', params.inspection_item_id);
    const qs = query.toString();
    return api.get<{ items: Defect[]; total: number }>(qs ? `/defects?${qs}` : '/defects');
  },

  get: async (id: string): Promise<Defect> => {
    return api.get<Defect>(`/defects/${id}`);
  },

  update: async (
    id: string,
    data: { severity?: string; surface_location?: string; description?: string }
  ): Promise<Defect> => {
    return api.patch<Defect>(`/defects/${id}`, data);
  },

  reopen: async (id: string, reason: string): Promise<Defect> => {
    return api.post<Defect>(`/defects/${id}/reopen`, { reason });
  },

  getRecurrenceHistory: async (id: string): Promise<{ defect: Defect; lineage: Defect[] }> => {
    return api.get<{ defect: Defect; lineage: Defect[] }>(`/defects/${id}/recurrence-history`);
  },
};
