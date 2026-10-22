import { api } from './client';
import type { Review, ReviewDecision } from '../types';

export interface DefectPayloadForReview {
  category: string;
  severity: string;
  surface_location?: string;
  description: string;
  prior_defect_id?: string;
  prior_corrective_action_id?: string;
}

export interface ReviewCreateData {
  inspection_item_id: string;
  decision: ReviewDecision;
  notes?: string;
  defect?: DefectPayloadForReview;
}

export const reviewsApi = {
  list: async (params?: { inspection_id?: string; item_id?: string; decision?: string; model_disagreement?: boolean }): Promise<{ items: Review[]; total: number }> => {
    const query = new URLSearchParams();
    if (params?.inspection_id) query.append('inspection_id', params.inspection_id);
    if (params?.item_id) query.append('item_id', params.item_id);
    if (params?.decision) query.append('decision', params.decision);
    if (params?.model_disagreement !== undefined) query.append('model_disagreement', String(params.model_disagreement));
    const qs = query.toString();
    return api.get<{ items: Review[]; total: number }>(qs ? `/reviews?${qs}` : '/reviews');
  },

  create: async (data: ReviewCreateData, idempotencyKey?: string): Promise<Review> => {
    return api.post<Review>('/reviews', data, { idempotencyKey });
  },

  dispute: async (reviewId: string, notes: string): Promise<Review> => {
    return api.post<Review>(`/reviews/${reviewId}/dispute`, { notes });
  },

  adjudicate: async (
    reviewId: string,
    decision: 'CONFIRMED_GOOD' | 'CONFIRMED_DEFECTIVE',
    notes: string,
    defect?: DefectPayloadForReview
  ): Promise<{ review: Review; defect?: any }> => {
    return api.post<{ review: Review; defect?: any }>(`/reviews/${reviewId}/adjudicate`, {
      decision,
      notes,
      defect,
    });
  },
};
