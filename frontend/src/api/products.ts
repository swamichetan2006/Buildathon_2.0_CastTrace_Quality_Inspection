import { api } from './client';
import type { Product } from '../types';

export interface ProductCreateData {
  sku: string;
  name: string;
  description?: string;
  material?: string;
  nominal_dimensions?: string;
  drawing_number?: string;
}

export const productsApi = {
  list: async (params?: { include_archived?: boolean; search?: string }): Promise<Product[]> => {
    const query = new URLSearchParams();
    if (params?.include_archived) query.append('include_archived', 'true');
    if (params?.search) query.append('search', params.search);
    const qs = query.toString();
    return api.get<Product[]>(qs ? `/products?${qs}` : '/products');
  },

  get: async (id: string): Promise<Product> => {
    return api.get<Product>(`/products/${id}`);
  },

  create: async (data: ProductCreateData): Promise<Product> => {
    return api.post<Product>('/products', data);
  },

  archive: async (id: string): Promise<Product> => {
    return api.delete<Product>(`/products/${id}`);
  },
};
