import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchScraperStatus } from '../../../services/api/scraperApi';

export function useScraperStatusPolling({ enabled, addToast, setScraping }) {
  const queryClient = useQueryClient();

  const scraperStatusQuery = useQuery({
    queryKey: ['scraperStatus'],
    queryFn: async ({ signal }) => fetchScraperStatus({ signal }),
    enabled,
    refetchInterval: enabled ? 5000 : false,
    staleTime: 0,
    retry: 0,
  });

  useEffect(() => {
    if (!enabled) return;
    const data = scraperStatusQuery.data?.data || scraperStatusQuery.data; // axios vs query normalization
    if (!data || !data.status) return;

    const { status, timestamp, new_posts_found, error } = data;
    const now = Date.now() / 1000;
    const tsNum = typeof timestamp === 'number' ? timestamp : Number(timestamp || 0);
    const isStale = status === 'running' && tsNum && now - tsNum > 45;

    if (status === 'completed' || isStale || status === 'error') {
      queueMicrotask(() => setScraping(false));

      if (status === 'completed') {
        if (new_posts_found === 0) {
          addToast('Scraping completed: No new posts found', 'info');
        } else {
          addToast(`Scraping completed: Found ${new_posts_found} new posts!`, 'success');
        }
      } else if (isStale) {
        addToast('Scraper seems to have stopped or was closed', 'error');
      } else if (status === 'error') {
        addToast(`Scraper error: ${error || 'Unknown error'}`, 'error');
      }

      queryClient.invalidateQueries({ queryKey: ['dashboardData'] });
    }
  }, [enabled, scraperStatusQuery.data, addToast, setScraping, queryClient]);

  return scraperStatusQuery;
}

