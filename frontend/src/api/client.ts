import axios from 'axios';
import type {
  ThreatIndicatorMemoryItem,
  ThreatIntelligenceCleanupResult,
  ThreatIntelligenceSummary,
} from '../types';

export class ApiRequestError extends Error {
  status?: number;
  isNetworkError: boolean;

  constructor(message: string, status?: number, isNetworkError = false) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.isNetworkError = isNetworkError;
  }
}

const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api';
export const API_BASE_URL = rawApiBaseUrl.replace(/\/+$/, '') || '/api';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
});

export async function getThreatIntelligenceIndicators(params?: {
  type?: string;
  min_seen_count?: number;
  limit?: number;
}): Promise<{ items: ThreatIndicatorMemoryItem[]; limit: number }> {
  const { data } = await api.get('/admin/intelligence/indicators', { params });
  return data;
}

export async function getThreatIntelligenceSummary(): Promise<ThreatIntelligenceSummary> {
  const { data } = await api.get('/admin/intelligence/summary');
  return data;
}

export async function cleanupThreatIntelligenceMemory(params?: {
  dry_run?: boolean;
  retention_days?: number;
}): Promise<ThreatIntelligenceCleanupResult> {
  const { data } = await api.post('/admin/intelligence/cleanup', null, { params });
  return data;
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('apg_admin_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    if (status === 401) {
      localStorage.removeItem('apg_admin_token');
      localStorage.removeItem('apg_admin_user');
      if (!window.location.pathname.includes('/login')) window.location.href = '/login';
    }
    const message = error?.response?.data?.detail || error?.message || 'Request failed';
    const cleanMessage = Array.isArray(message) ? message[0]?.msg : message;
    return Promise.reject(new ApiRequestError(cleanMessage, status, !error?.response));
  }
);
