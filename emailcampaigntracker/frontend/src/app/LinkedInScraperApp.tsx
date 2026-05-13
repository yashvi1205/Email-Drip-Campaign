import React, { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { RefreshCw } from 'lucide-react';

import LayoutShell from './LayoutShell';
import AppRoutes from './routes/AppRoutes';

import ToastContainer from '@shared/toast/ToastContainer';
import { useToasts } from '@shared/toast/useToasts';

import {
  fetchDashboardDrip,
  fetchProfilesRaw,
} from '@services/api/monitorApi';
import { triggerScrape } from '@services/api/scraperApi';
import { useScraperStatusPolling } from '@hooks/useScraperStatusPolling';
import { Profile, DripStats } from '@types/index';

interface AppPropsType {
  profiles: Profile[];
  dripData: DripStats[];
  filter: string;
  setFilter: (filter: string) => void;
}

interface DashboardData {
  profiles: Profile[];
  dripData: DripStats[];
  lastUpdated: string;
}

export default function LinkedInScraperApp() {
  const location = useLocation();
  const navigateView = location.pathname.startsWith('/drip') ? 'drip' : 'monitor';

  const { toasts, addToast } = useToasts();

  const [scraping, setScraping] = useState(false);
  const [filter, setFilter] = useState('all');

  const dashboardQuery = useQuery<DashboardData>({
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
  const lastUpdated =
    dashboardQuery.data?.lastUpdated || new Date().toLocaleTimeString();

  useEffect(() => {
    if (!dashboardQuery.isError) return;
    const err = dashboardQuery.error as any;
    const requestId = err?.requestId;
    const msg = requestId
      ? `Failed to sync with backend (request_id: ${requestId})`
      : 'Failed to sync with backend';
    addToast(msg, 'error');
  }, [dashboardQuery.isError, dashboardQuery.error, addToast]);

  const showSpinner =
    dashboardQuery.isFetching && profiles.length === 0;

  const refreshAll = () => dashboardQuery.refetch();

  const triggerScrapeNow = async () => {
    if (scraping) return;
    setScraping(true);
    addToast('Starting LinkedIn Scraper...', 'info');
    try {
      await triggerScrape();
      addToast('Scraper is now running in the background', 'success');
    } catch (error) {
      const apiError = error as any;
      const requestId = apiError?.requestId;
      addToast(
        requestId
          ? `Failed to start scraper (request_id: ${requestId})`
          : 'Failed to start scraper',
        'error'
      );
      setScraping(false);
    }
  };

  const appProps: AppPropsType = useMemo(
    () => ({ profiles, dripData, filter, setFilter }),
    [profiles, dripData, filter]
  );

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
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: '50vh',
            }}
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{
                duration: 1,
                repeat: Infinity,
                ease: 'linear',
              }}
            >
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
