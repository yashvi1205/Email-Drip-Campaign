import { httpClient } from './httpClient';
import { ScraperStatus, ApiResponse } from '@types/index';

export interface FetchOptions {
  signal?: AbortSignal;
}

export async function triggerScrape(): Promise<ApiResponse<{ message: string }>> {
  const response = await httpClient.post<{ message: string }>(`scrape`);
  return {
    data: response.data,
    status: response.status,
  };
}

export async function fetchScraperStatus(
  options?: FetchOptions
): Promise<ApiResponse<ScraperStatus>> {
  const response = await httpClient.get<ScraperStatus>(
    `scraper-status?t=${Date.now()}`,
    {
      signal: options?.signal,
    }
  );
  return {
    data: response.data,
    status: response.status,
  };
}
