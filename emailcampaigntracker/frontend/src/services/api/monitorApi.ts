import { httpClient } from './httpClient';
import { Profile, DripStats, ApiResponse } from '@types/index';

export interface FetchOptions {
  signal?: AbortSignal;
}

export async function fetchProfilesRaw(
  options?: FetchOptions
): Promise<ApiResponse<Profile[]>> {
  const t = Date.now();
  const response = await httpClient.get<Profile[]>(`profiles/raw?t=${t}`, {
    signal: options?.signal,
  });
  return {
    data: response.data,
    status: response.status,
  };
}

export async function fetchDashboardDrip(
  options?: FetchOptions
): Promise<ApiResponse<DripStats[]>> {
  const t = Date.now();
  const response = await httpClient.get<DripStats[]>(`dashboard/drip?t=${t}`, {
    signal: options?.signal,
  });
  return {
    data: response.data,
    status: response.status,
  };
}
