import { api } from './client';
import type {
  IntelligenceQueryRequest,
  IntelligenceQueryResponse,
  AttentionResponse,
  HistoricalSimilarityResponse,
  BatchDefectOption,
} from '../types';

export const intelligenceApi = {
  query: async (data: IntelligenceQueryRequest): Promise<IntelligenceQueryResponse> => {
    return api.post<IntelligenceQueryResponse>('/intelligence/query', data);
  },

  getAttentionItems: async (params?: {
    batch_identifier?: string;
    priority?: string;
    limit?: number;
    offset?: number;
  }): Promise<AttentionResponse> => {
    const query = new URLSearchParams();
    if (params?.batch_identifier) query.append('batch_identifier', params.batch_identifier);
    if (params?.priority && params.priority !== 'ALL') query.append('priority', params.priority);
    if (params?.limit) query.append('limit', String(params.limit));
    if (params?.offset) query.append('offset', String(params.offset));
    const qs = query.toString();
    return api.get<AttentionResponse>(`/intelligence/attention${qs ? `?${qs}` : ''}`);
  },

  getHistoricalSimilarity: async (params: {
    defect_id: string;
    limit?: number;
    include_cross_product?: boolean;
  }): Promise<HistoricalSimilarityResponse> => {
    const query = new URLSearchParams({ defect_id: params.defect_id });
    if (params.limit) query.append('limit', String(params.limit));
    if (params.include_cross_product !== undefined) {
      query.append('include_cross_product', String(params.include_cross_product));
    }
    return api.get<HistoricalSimilarityResponse>(`/intelligence/historical-similarity?${query.toString()}`);
  },

  getBatchDefects: async (batchIdentifier: string): Promise<BatchDefectOption[]> => {
    return api.get<BatchDefectOption[]>(
      `/intelligence/batch-defects?batch_identifier=${encodeURIComponent(batchIdentifier)}`
    );
  },
};

