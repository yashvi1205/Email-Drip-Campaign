import React, { Suspense, lazy } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Profile, DripStats } from '@types/index';

const MonitorPage = lazy(
  () => import('../../features/socialMonitor/MonitorPage')
);
const DripPage = lazy(
  () => import('../../features/dripDashboard/DripDashboardPage')
);

interface AppRoutesProps {
  appProps: {
    profiles: Profile[];
    dripData: DripStats[];
    filter: string;
    setFilter: (filter: string) => void;
  };
}

export default function AppRoutes({ appProps }: AppRoutesProps) {
  const location = useLocation();
  return (
    <Suspense fallback={<div style={{ padding: '2rem' }}>Loading...</div>}>
      <Routes location={location}>
        <Route path="/" element={<Navigate to="/monitor" replace />} />
        <Route path="/monitor" element={<MonitorPage {...appProps} />} />
        <Route path="/drip" element={<DripPage {...appProps} />} />
        <Route path="*" element={<Navigate to="/monitor" replace />} />
      </Routes>
    </Suspense>
  );
}
