import { api } from './client';
import type { Batch, BatchDecision, ReleaseGateResponse } from '../types';

export interface BatchCreateData {
  batch_number: string;
  product_id: string;
  manufacture_date: string;
  heat_number?: string;
  declared_quantity: number;
  notes?: string;
}

export interface BatchDecisionCreateData {
  decision: 'RELEASE' | 'HOLD' | 'REJECT_SCRAP' | 'CONCESSION_DEVIATION';
  reason: string;
  is_concession?: boolean;
  concession_justification?: string;
  conditions?: string;
}

export const batchesApi = {
  list: async (params?: { product_id?: string; status?: string; include_archived?: boolean }): Promise<Batch[]> => {
    const query = new URLSearchParams();
    if (params?.product_id) query.append('product_id', params.product_id);
    if (params?.status) query.append('status', params.status);
    if (params?.include_archived) query.append('include_archived', 'true');
    const qs = query.toString();
    return api.get<Batch[]>(qs ? `/batches?${qs}` : '/batches');
  },

  get: async (id: string): Promise<Batch> => {
    return api.get<Batch>(`/batches/${id}`);
  },

  create: async (data: BatchCreateData, idempotencyKey?: string): Promise<Batch> => {
    return api.post<Batch>('/batches', data, { idempotencyKey });
  },

  placeHold: async (id: string, reason: string): Promise<Batch> => {
    return api.post<Batch>(`/batches/${id}/hold`, { reason });
  },

  getReleaseGate: async (id: string): Promise<ReleaseGateResponse> => {
    return api.get<ReleaseGateResponse>(`/batches/${id}/release-gate`);
  },

  listDecisions: async (id: string): Promise<{ items: BatchDecision[]; total: number; batch_id: string }> => {
    return api.get<{ items: BatchDecision[]; total: number; batch_id: string }>(`/batches/${id}/decisions`);
  },

  createDecision: async (id: string, data: BatchDecisionCreateData, idempotencyKey?: string): Promise<BatchDecision> => {
    return api.post<BatchDecision>(`/batches/${id}/decisions`, data, { idempotencyKey });
  },
};
