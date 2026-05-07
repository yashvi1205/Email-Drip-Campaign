import axios from 'axios';
import { API_BASE_URL, API_KEY } from './apiConfig';
import { fromAxiosError } from './apiError';

export function createHttpClient() {
  const instance = axios.create({
    baseURL: API_BASE_URL,
    timeout: 15000,
  });

  instance.interceptors.request.use((config) => {
    // Backward compatibility: only attach API key header when provided.
    if (API_KEY) {
      config.headers = config.headers || {};
      config.headers['X-API-Key'] = API_KEY;
    }
    // Allow request deduplication by keeping idempotency for GETs; no change in semantics.
    return config;
  });

  instance.interceptors.response.use(
    (response) => response,
    (error) => Promise.reject(fromAxiosError(error))
  );

  return instance;
}

export const httpClient = createHttpClient();

