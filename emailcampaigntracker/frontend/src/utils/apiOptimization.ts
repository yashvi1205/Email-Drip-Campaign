"""API request/response optimization utilities

Reduces payload sizes and optimizes API communication.
"""

import { Profile, DripStats } from '@types/index';

/**
 * Deduplicate array items by property
 */
export function deduplicateBy<T>(
  items: T[],
  keyFn: (item: T) => any
): T[] {
  const seen = new Set();
  return items.filter((item) => {
    const key = keyFn(item);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/**
 * Batch API requests to reduce network calls
 */
export async function batchRequests<T>(
  requests: Promise<T>[],
  batchSize: number = 5
): Promise<T[]> {
  const results: T[] = [];

  for (let i = 0; i < requests.length; i += batchSize) {
    const batch = requests.slice(i, i + batchSize);
    const batchResults = await Promise.all(batch);
    results.push(...batchResults);
  }

  return results;
}

/**
 * Request debouncing for frequent API calls
 */
export function createDebouncedRequest<T extends any[], R>(
  fn: (...args: T) => Promise<R>,
  delayMs: number = 300
): (...args: T) => Promise<R> {
  let timeoutId: NodeJS.Timeout | null = null;
  let lastResult: Promise<R> | null = null;

  return (...args: T) => {
    return new Promise((resolve, reject) => {
      if (timeoutId) clearTimeout(timeoutId);

      timeoutId = setTimeout(async () => {
        try {
          lastResult = fn(...args);
          const result = await lastResult;
          resolve(result);
        } catch (error) {
          reject(error);
        }
      }, delayMs);
    });
  };
}

/**
 * Compress profile data by removing unnecessary fields
 */
export function compressProfile(profile: Profile): Partial<Profile> {
  return {
    name: profile.name,
    profileUrl: profile.profileUrl,
    ...(profile.headline && { headline: profile.headline }),
    ...(profile.location && { location: profile.location }),
  };
}

/**
 * Compress drip stats by removing unnecessary fields
 */
export function compressDripStats(stats: DripStats): Partial<DripStats> {
  return {
    id: stats.id,
    lead_id: stats.lead_id,
    name: stats.name,
    email: stats.email,
    sequences_sent: stats.sequences_sent,
    sequences_opened: stats.sequences_opened,
    sequences_replied: stats.sequences_replied,
  };
}

/**
 * Cache key generator for React Query
 */
export const cacheKeys = {
  profiles: () => ['profiles'],
  profilesRaw: () => ['profiles', 'raw'],
  dripData: () => ['dripData'],
  dripDataDashboard: () => ['dripData', 'dashboard'],
  scraperStatus: () => ['scraperStatus'],
  dashboardData: () => ['dashboardData'],
};

/**
 * Request memoization for preventing duplicate calls
 */
export function memoizeRequest<T extends any[], R>(
  fn: (...args: T) => Promise<R>
): (...args: T) => Promise<R> {
  const cache = new Map<string, Promise<R>>();

  return (...args: T) => {
    const key = JSON.stringify(args);
    if (cache.has(key)) {
      return cache.get(key)!;
    }

    const promise = fn(...args);
    cache.set(key, promise);

    // Clean up cache after completion
    promise.finally(() => {
      // Keep cache for 5 seconds
      setTimeout(() => cache.delete(key), 5000);
    });

    return promise;
  };
}

/**
 * Calculate estimated data transfer size
 */
export function estimatePayloadSize(data: any): number {
  return new Blob([JSON.stringify(data)]).size;
}

/**
 * Log payload sizes for monitoring
 */
export function logPayloadSize(
  name: string,
  data: any,
  maxSizeKb: number = 100
): void {
  const sizeBytes = estimatePayloadSize(data);
  const sizeKb = sizeBytes / 1024;

  if (sizeKb > maxSizeKb) {
    console.warn(
      `${name} payload is large: ${sizeKb.toFixed(2)}KB (threshold: ${maxSizeKb}KB)`
    );
  } else {
    console.debug(`${name} payload: ${sizeKb.toFixed(2)}KB`);
  }
}
