import { api } from './client';
import type { ImageEvidence, Inspection, InspectionItem, ModelRun } from '../types';

export interface InspectionCreateData {
  batch_id: string;
  stage: string;
  sampling_plan: string;
  notes?: string;
}

export interface InspectionItemRegisterData {
  item_identifier: string;
  cavity_number?: number;
}

export const inspectionsApi = {
  list: async (params?: { batch_id?: string; status?: string; stage?: string }): Promise<Inspection[]> => {
    const query = new URLSearchParams();
    if (params?.batch_id) query.append('batch_id', params.batch_id);
    if (params?.status) query.append('status', params.status);
    if (params?.stage) query.append('stage', params.stage);
    const qs = query.toString();
    return api.get<Inspection[]>(qs ? `/inspections?${qs}` : '/inspections');
  },

  get: async (id: string): Promise<Inspection> => {
    return api.get<Inspection>(`/inspections/${id}`);
  },

  create: async (data: InspectionCreateData, idempotencyKey?: string): Promise<Inspection> => {
    return api.post<Inspection>('/inspections', data, { idempotencyKey });
  },

  registerItems: async (inspectionId: string, items: InspectionItemRegisterData[]): Promise<InspectionItem[]> => {
    return api.post<InspectionItem[]>(`/inspections/${inspectionId}/items`, { items });
  },

  submit: async (inspectionId: string): Promise<Inspection> => {
    return api.post<Inspection>(`/inspections/${inspectionId}/submit`);
  },

  cancel: async (inspectionId: string, reason: string): Promise<Inspection> => {
    return api.post<Inspection>(`/inspections/${inspectionId}/cancel`, { reason });
  },

  uploadEvidence: async (formData: FormData, idempotencyKey?: string): Promise<ImageEvidence> => {
    return api.post<ImageEvidence>('/images/upload', formData, { idempotencyKey });
  },

  supersedeImage: async (imageId: string, reason: string, replacementImageId?: string): Promise<ImageEvidence> => {
    return api.post<ImageEvidence>(`/images/${imageId}/supersede`, {
      reason,
      replacement_image_id: replacementImageId,
    });
  },

  triggerInference: async (imageId: string, idempotencyKey?: string): Promise<ModelRun> => {
    return api.post<ModelRun>(`/images/${imageId}/infer`, undefined, { idempotencyKey });
  },

  retryInference: async (modelRunId: string): Promise<ModelRun> => {
    return api.post<ModelRun>(`/model-runs/${modelRunId}/retry`);
  },
};
