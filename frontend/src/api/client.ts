import type { ApiError } from '../types';

const API_BASE = '/api/v1';

export class ApiException extends Error {
  public code: string;
  public status: number;
  public details?: Record<string, any> | null;
  public requestId?: string;

  constructor(status: number, code: string, message: string, details?: Record<string, any> | null, requestId?: string) {
    super(message);
    this.name = 'ApiException';
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

export function getAuthToken(): string | null {
  return localStorage.getItem('casttrace_token');
}

export function setAuthToken(token: string | null): void {
  if (token) {
    localStorage.setItem('casttrace_token', token);
  } else {
    localStorage.removeItem('casttrace_token');
  }
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  idempotencyKey?: string;
}

export async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 30000, idempotencyKey, headers = {}, ...rest } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const token = getAuthToken();
  const requestHeaders: Record<string, string> = {
    Accept: 'application/json',
    ...(headers as Record<string, string>),
  };

  if (token) {
    requestHeaders['Authorization'] = `Bearer ${token}`;
  }

  if (idempotencyKey) {
    requestHeaders['Idempotency-Key'] = idempotencyKey;
  }

  // Only set Content-Type if body is not FormData
  if (!(rest.body instanceof FormData) && !requestHeaders['Content-Type']) {
    requestHeaders['Content-Type'] = 'application/json';
  }

  const url = endpoint.startsWith('/') ? `${API_BASE}${endpoint}` : `${API_BASE}/${endpoint}`;

  try {
    const response = await fetch(url, {
      ...rest,
      headers: requestHeaders,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (response.status === 401) {
      // Discard invalid token
      setAuthToken(null);
      window.dispatchEvent(new CustomEvent('auth:expired'));
    }

    if (!response.ok) {
      let errorPayload: ApiError | null = null;
      try {
        errorPayload = await response.json();
      } catch {
        // Response wasn't valid JSON
      }

      const code = errorPayload?.error?.code || `HTTP_${response.status}`;
      const message = errorPayload?.error?.message || response.statusText || 'An unexpected error occurred';
      const details = errorPayload?.error?.details || null;
      const requestId = errorPayload?.error?.request_id;

      throw new ApiException(response.status, code, message, details, requestId);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return await response.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new ApiException(408, 'REQUEST_TIMEOUT', 'Request timed out. Please try again.');
    }
    if (err instanceof ApiException) {
      throw err;
    }
    throw new ApiException(0, 'NETWORK_ERROR', err.message || 'Network connection failed. Verify server status.');
  }
}

export const api = {
  get: <T>(url: string, options?: RequestOptions) => request<T>(url, { method: 'GET', ...options }),
  post: <T>(url: string, body?: any, options?: RequestOptions) =>
    request<T>(url, {
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body),
      ...options,
    }),
  patch: <T>(url: string, body?: any, options?: RequestOptions) =>
    request<T>(url, {
      method: 'PATCH',
      body: body instanceof FormData ? body : JSON.stringify(body),
      ...options,
    }),
  delete: <T>(url: string, options?: RequestOptions) => request<T>(url, { method: 'DELETE', ...options }),
};
