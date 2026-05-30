import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './store/AuthContext';
import DashboardLayout from './layouts/DashboardLayout';
import LoginPage from './pages/LoginPage';
import LoadingSkeleton from './components/LoadingSkeleton';

const MonitoringPage      = lazy(() => import('./pages/MonitoringPage'));
const IncidentsPage       = lazy(() => import('./pages/IncidentsPage'));
const IncidentDetailsPage = lazy(() => import('./pages/IncidentDetailsPage'));
const ThreatSignalsPage   = lazy(() => import('./pages/ThreatSignalsPage'));
const DetectionQualityPage = lazy(() => import('./pages/DetectionQualityPage'));
const SystemPage          = lazy(() => import('./pages/SystemPage'));
const NotFoundPage        = lazy(() => import('./pages/NotFoundPage'));

function PageFallback({ variant }: { variant?: 'cards' | 'rows' }) {
  return (
    <div className="p-6">
      <LoadingSkeleton variant={variant ?? 'rows'} />
    </div>
  );
}

function Protected({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen p-8"><LoadingSkeleton rows={8} /></div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/monitoring" replace /> : <LoginPage />} />
      <Route path="/" element={<Protected><DashboardLayout /></Protected>}>
        <Route index element={<Navigate to="/monitoring" replace />} />
        <Route path="monitoring" element={<Suspense fallback={<PageFallback variant="cards" />}><MonitoringPage /></Suspense>} />
        <Route path="incidents" element={<Suspense fallback={<PageFallback variant="rows" />}><IncidentsPage /></Suspense>} />
        <Route path="incidents/:id" element={<Suspense fallback={<PageFallback variant="rows" />}><IncidentDetailsPage /></Suspense>} />
        <Route path="threat-signals" element={<Suspense fallback={<PageFallback variant="rows" />}><ThreatSignalsPage /></Suspense>} />
        <Route path="detection-quality" element={<Suspense fallback={<PageFallback variant="cards" />}><DetectionQualityPage /></Suspense>} />
        <Route path="system" element={<Suspense fallback={<PageFallback variant="rows" />}><SystemPage /></Suspense>} />
      </Route>
      <Route path="*" element={<Suspense fallback={null}><NotFoundPage /></Suspense>} />
    </Routes>
  );
}
