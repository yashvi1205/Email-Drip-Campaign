import React, { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { RefreshCw } from 'lucide-react';

import LayoutShell from './LayoutShell.jsx';
import AppRoutes from './routes/AppRoutes.jsx';

import ToastContainer from '../shared/toast/ToastContainer.jsx';
import { useToasts } from '../shared/toast/useToasts.js';

import { fetchDashboardDrip, fetchProfilesRaw } from '../services/api/monitorApi.js';
import { triggerScrape } from '../services/api/scraperApi.js';
import { useScraperStatusPolling } from '../features/scraper/hooks/useScraperStatusPolling.js';

export default function LinkedInScraperApp() {
  const location = useLocation();
  const navigateView = location.pathname.startsWith('/drip') ? 'drip' : 'monitor';

  const { toasts, addToast } = useToasts();

  const [scraping, setScraping] = useState(false);
  const [filter, setFilter] = useState('all');

  const dashboardQuery = useQuery({
    queryKey: ['dashboardData'],
    queryFn: async ({ signal }) => {
      const profilesRes = await fetchProfilesRaw({ signal });
      const dripRes = await fetchDashboardDrip({ signal });
      return {
        profiles: profilesRes.data || [],
        dripData: dripRes.data || [],
        lastUpdated: new Date().toLocaleTimeString(),
      };
    },
    refetchInterval: 30000,
    staleTime: 25000,
  });

  useScraperStatusPolling({
    enabled: scraping,
    addToast,
    setScraping,
  });

  void motion;

  const profiles = useMemo(
    () => dashboardQuery.data?.profiles || [],
    [dashboardQuery.data]
  );
  const dripData = useMemo(
    () => dashboardQuery.data?.dripData || [],
    [dashboardQuery.data]
  );
  const lastUpdated = dashboardQuery.data?.lastUpdated || new Date().toLocaleTimeString();

  // Centralized API error toast (matches old UX: one toast per failed sync cycle).
  useEffect(() => {
    if (!dashboardQuery.isError) return;
    const err = dashboardQuery.error;
    const requestId = err?.requestId;
    const msg = requestId ? `Failed to sync with backend (request_id: ${requestId})` : 'Failed to sync with backend';
    addToast(msg, 'error');
  }, [dashboardQuery.isError, dashboardQuery.error, addToast]);

  const showSpinner = dashboardQuery.isFetching && profiles.length === 0;

  const refreshAll = () => dashboardQuery.refetch();

  const triggerScrapeNow = async () => {
    if (scraping) return;
    setScraping(true);
    addToast('Starting LinkedIn Scraper...', 'info');
    try {
      await triggerScrape();
      addToast('Scraper is now running in the background', 'success');
    } catch (error) {
      const requestId = error?.requestId;
      addToast(
        requestId ? `Failed to start scraper (request_id: ${requestId})` : 'Failed to start scraper',
        'error'
      );
      setScraping(false);
    }
  };

  const appProps = useMemo(() => ({ profiles, dripData, filter, setFilter }), [profiles, dripData, filter]);

  return (
    <>
      <ToastContainer toasts={toasts} />
      <LayoutShell
        profiles={profiles}
        view={navigateView}
        loading={dashboardQuery.isFetching}
        lastUpdated={lastUpdated}
        onRefresh={refreshAll}
        onRunScraper={triggerScrapeNow}
        scraping={scraping}
      >
        {showSpinner ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
            <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}>
              <RefreshCw size={40} color="#0a66c2" />
            </motion.div>
          </div>
        ) : (
          <AppRoutes appProps={appProps} />
        )}
      </LayoutShell>
    </>
  );
}

