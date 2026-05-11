import { httpClient } from './httpClient';

export function fetchProfilesRaw({ signal } = {}) {
  const t = Date.now();
  return httpClient.get(`profiles/raw?t=${t}`, { signal });
}

export function fetchDashboardDrip({ signal } = {}) {
  const t = Date.now();
  return httpClient.get(`dashboard/drip?t=${t}`, { signal });
}

