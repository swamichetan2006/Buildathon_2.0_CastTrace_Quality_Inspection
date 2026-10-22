import { api } from './client';
import type { CorrectiveAction, Reinspection } from '../types';

export interface CAPACreateData {
  defect_id: string;
  title: string;
  action_type: 'REWORK' | 'SCRAP' | 'PROCESS_ADJUSTMENT' | 'TRAINING';
  description: string;
  assigned_to: string;
  due_date: string;
  root_cause?: string;
  preventive_action?: string;
}

export interface CAPACompleteData {
  completion_notes: string;
  evidence_image_id?: string;
}

export interface CAPAVerifyData {
  decision: 'APPROVED' | 'REJECTED';
  notes: string;
}

export const capaApi = {
  list: async (params?: {
    defect_id?: string;
    status?: string;
    verification_status?: string;
    assigned_to?: string;
  }): Promise<{ items: CorrectiveAction[]; total: number }> => {
    const query = new URLSearchParams();
    if (params?.defect_id) query.append('defect_id', params.defect_id);
    if (params?.status) query.append('status', params.status);
    if (params?.verification_status) query.append('verification_status', params.verification_status);
    if (params?.assigned_to) query.append('assigned_to', params.assigned_to);
    const qs = query.toString();
    return api.get<{ items: CorrectiveAction[]; total: number }>(qs ? `/corrective-actions?${qs}` : '/corrective-actions');
  },

  get: async (id: string): Promise<CorrectiveAction> => {
    return api.get<CorrectiveAction>(`/corrective-actions/${id}`);
  },

  create: async (data: CAPACreateData, idempotencyKey?: string): Promise<CorrectiveAction> => {
    return api.post<CorrectiveAction>('/corrective-actions', data, { idempotencyKey });
  },

  start: async (id: string): Promise<CorrectiveAction> => {
    return api.post<CorrectiveAction>(`/corrective-actions/${id}/start`);
  },

  complete: async (id: string, data: CAPACompleteData): Promise<CorrectiveAction> => {
    return api.post<CorrectiveAction>(`/corrective-actions/${id}/complete`, data);
  },

  verify: async (id: string, data: CAPAVerifyData): Promise<CorrectiveAction> => {
    return api.post<CorrectiveAction>(`/corrective-actions/${id}/verify`, data);
  },

  cancel: async (id: string, reason: string): Promise<CorrectiveAction> => {
    return api.post<CorrectiveAction>(`/corrective-actions/${id}/cancel`, { reason });
  },
};

export interface ReinspectionCreateData {
  defect_id: string;
  corrective_action_id?: string;
  outcome: 'DEFECT_RESOLVED' | 'DEFECT_RECURRED_REOPENED';
  notes: string;
  evidence_image_id?: string;
}

export const reinspectionsApi = {
  list: async (params?: { defect_id?: string; outcome?: string }): Promise<{ items: Reinspection[]; total: number }> => {
    const query = new URLSearchParams();
    if (params?.defect_id) query.append('defect_id', params.defect_id);
    if (params?.outcome) query.append('outcome', params.outcome);
    const qs = query.toString();
    return api.get<{ items: Reinspection[]; total: number }>(qs ? `/reinspections?${qs}` : '/reinspections');
  },

  create: async (data: ReinspectionCreateData, idempotencyKey?: string): Promise<Reinspection> => {
    return api.post<Reinspection>('/reinspections', data, { idempotencyKey });
  },
};
