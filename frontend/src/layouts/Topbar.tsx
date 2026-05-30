import { Languages, LogOut, RefreshCw } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../store/AuthContext';
import { useI18n } from '../i18n';
import StatusBadge from '../components/StatusBadge';

export default function Topbar() {
  const { pathname } = useLocation();
  const { logout } = useAuth();
  const { t, lang, setLang } = useI18n();

  const titles: Record<string, string> = {
    '/monitoring':        t('nav.monitoring'),
    '/incidents':         t('nav.incidents'),
    '/threat-signals':    t('nav.threatSignals'),
    '/detection-quality': t('nav.detectionQuality'),
    '/system':            t('nav.system'),
  };
  const title =
    titles[pathname] ||
    (pathname.startsWith('/incidents/') ? t('common.details') : t('app.title'));

  return (
    <header className="sticky top-0 z-30 border-b border-slate-700/25 bg-[var(--bg-main)]/92 px-4 py-2.5 backdrop-blur-xl lg:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight">{title}</h2>
          <p className="text-[12px] text-slate-500">{t('app.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge value="stable" label={t('topbar.systemStable')} />

          <select
            aria-label="time range"
            onChange={(e) => {
              localStorage.setItem('apg_admin_range', e.target.value);
              window.dispatchEvent(new Event('apg:refresh'));
            }}
            className="rounded-xl border border-slate-700/50 bg-slate-900/70 px-3 py-1.5 text-[13px] text-slate-200"
          >
            <option value="today">{t('topbar.today')}</option>
            <option value="7d">{t('topbar.sevenDays')}</option>
            <option value="30d">{t('topbar.thirtyDays')}</option>
          </select>

          <button
            onClick={() => window.dispatchEvent(new Event('apg:refresh'))}
            title={t('topbar.refresh')}
            className="motion-button rounded-xl border border-slate-700/50 p-1.5 text-slate-400 hover:bg-slate-800/70 hover:text-slate-200"
          >
            <RefreshCw size={16} />
          </button>

          <label className="flex items-center gap-1.5 rounded-xl border border-slate-700/50 bg-slate-900/50 px-2.5 py-1.5 text-[13px] text-slate-200">
            <Languages size={14} />
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value as 'en' | 'ar')}
              className="bg-transparent"
            >
              <option value="en">English</option>
              <option value="ar">العربية</option>
            </select>
          </label>

          <button
            onClick={logout}
            title={t('topbar.logout')}
            className="motion-button rounded-xl border border-rose-400/20 p-1.5 text-rose-300 hover:bg-rose-400/10"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </header>
  );
}
