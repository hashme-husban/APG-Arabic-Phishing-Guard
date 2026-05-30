import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import { useI18n } from '../i18n';

export default function DashboardLayout() {
  const { dir } = useI18n();
  return (
    <div dir={dir} className="flex min-h-screen bg-[var(--bg-main)]">
      <Sidebar />
      <main className="min-w-0 flex-1">
        <Topbar />
        <div className="page-motion p-4 lg:p-5 2xl:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
