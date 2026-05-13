"""Lazy loading utilities for React components

Provides code splitting for better initial load performance.
"""

import { lazy, LazyExoticComponent, ReactNode, Suspense } from 'react';

const LoadingFallback = () => (
  <div style={{ padding: '2rem', textAlign: 'center' }}>
    <p>Loading...</p>
  </div>
);

interface LazyComponentConfig {
  component: LazyExoticComponent<any>;
  fallback?: ReactNode;
}

/**
 * Create a lazy-loaded component with fallback UI
 */
export function createLazyComponent(
  importFunc: () => Promise<{ default: React.ComponentType<any> }>,
  fallback?: ReactNode
): React.ComponentType<any> {
  const Component = lazy(importFunc);

  return (props) => (
    <Suspense fallback={fallback || <LoadingFallback />}>
      <Component {...props} />
    </Suspense>
  );
}

/**
 * Lazy load pages with code splitting
 * Each route becomes a separate chunk
 */
export const lazyPages = {
  MonitorPage: () =>
    import('../../features/socialMonitor/MonitorPage').then((m) => ({
      default: m.default,
    })),
  DripDashboardPage: () =>
    import('../../features/dripDashboard/DripDashboardPage').then((m) => ({
      default: m.default,
    })),
};

/**
 * Prefetch a lazy component for faster loading
 */
export function prefetchComponent(
  importFunc: () => Promise<any>
): Promise<void> {
  return importFunc()
    .then(() => {
      console.debug('Component prefetched');
    })
    .catch((err) => {
      console.warn('Failed to prefetch component:', err);
    });
}

/**
 * Performance hint for route-based code splitting
 * Call on route change to prefetch next likely pages
 */
export function prefetchRoute(routeName: string): void {
  const prefetchMap: Record<string, () => Promise<any>> = {
    monitor: lazyPages.MonitorPage,
    drip: lazyPages.DripDashboardPage,
  };

  const importFunc = prefetchMap[routeName];
  if (importFunc) {
    prefetchComponent(importFunc);
  }
}
