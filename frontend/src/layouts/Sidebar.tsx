import {
  Activity, AlertTriangle, BarChart3, ChevronLeft, ChevronRight,
  LogOut, Menu, Radar, Server,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useAuth } from '../store/AuthContext';
import { useI18n } from '../i18n';

export default function Sidebar() {
  const { user, logout } = useAuth();
  const { t, dir } = useI18n();
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('apg_sidebar_collapsed') === 'true',
  );

  useEffect(() => {
    localStorage.setItem('apg_sidebar_collapsed', String(collapsed));
  }, [collapsed]);

  const links = [
    { to: '/monitoring',         label: t('nav.monitoring'),       icon: Activity },
    { to: '/incidents',          label: t('nav.incidents'),        icon: AlertTriangle },
    { to: '/threat-signals',     label: t('nav.threatSignals'),    icon: Radar },
    { to: '/detection-quality',  label: t('nav.detectionQuality'), icon: BarChart3 },
    { to: '/system',             label: t('nav.system'),           icon: Server },
  ];

  const ToggleIcon =
    dir === 'rtl'
      ? collapsed ? ChevronLeft : ChevronRight
      : collapsed ? ChevronRight : ChevronLeft;

  const initials = (user?.email ?? 'AD').slice(0, 2).toUpperCase();

  return (
    <aside
      className={`hidden shrink-0 border-e border-slate-700/25 bg-[var(--bg-sidebar)] transition-[width] duration-300 ease-out lg:sticky lg:top-0 lg:flex lg:h-screen lg:max-h-screen lg:flex-col lg:overflow-hidden ${
        collapsed ? 'w-[68px] p-2.5' : 'w-[252px] p-3.5'
      }`}
    >
      {/* Brand header */}
      <div className={`flex h-[68px] shrink-0 items-center ${collapsed ? 'justify-center' : 'justify-between gap-2'}`}>
        {collapsed ? (
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-cyan-400/25 bg-cyan-400/10">
            <img
              src="/branding/apg_logo_transparent.png?v=2"
              alt="APG"
              className="h-9 w-9 object-contain"
              draggable={false}
            />
          </div>
        ) : (
          <>
            <img
              src="/branding/apg_brand_horizontal.png?v=2"
              alt="APG"
              className="h-[52px] w-auto max-w-[190px] object-contain object-left"
              draggable={false}
            />
            <button
              onClick={() => setCollapsed(true)}
              className="motion-button shrink-0 rounded-lg border border-slate-700/50 p-1.5 text-slate-500 hover:bg-slate-800/60 hover:text-slate-300"
              title={t('sidebar.collapse')}
            >
              <ToggleIcon size={15} />
            </button>
          </>
        )}
      </div>

      {collapsed && (
        <button
          onClick={() => setCollapsed(false)}
          className="motion-button mx-auto mb-1.5 grid h-9 w-9 place-items-center rounded-lg border border-slate-700/50 text-slate-400 hover:bg-slate-800/60"
          title={t('sidebar.expand')}
        >
          <Menu size={15} />
        </button>
      )}

      {/* Navigation */}
      <nav className="min-h-0 flex-1 overflow-y-auto overflow-x-visible py-1 sidebar-scrollbar">
        <div className="grid gap-0.5">
          {links.map(({ to, label, icon: Icon }, idx) => (
            <NavLink
              key={to}
              to={to}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                `group relative flex h-10 items-center rounded-xl text-sm transition-all duration-200 ease-out ${
                  collapsed ? 'justify-center px-0' : 'gap-3 px-3'
                } ${
                  isActive
                    ? 'border border-cyan-400/20 bg-gradient-to-r from-cyan-400/12 to-cyan-400/4 text-cyan-100'
                    : 'border border-transparent text-slate-400 hover:bg-slate-800/40 hover:text-slate-200'
                }`
              }
              style={{ animationDelay: `${idx * 30}ms` }}
            >
              {({ isActive }) => (
                <>
                  <span
                    className={`absolute top-2.5 bottom-2.5 w-0.5 rounded-full bg-cyan-300 transition-opacity ${
                      isActive ? 'opacity-100' : 'opacity-0'
                    } ${dir === 'rtl' ? 'right-0' : 'left-0'}`}
                  />
                  <Icon
                    className={`shrink-0 transition-all duration-200 ${
                      isActive ? 'scale-105 text-cyan-300' : 'group-hover:scale-105'
                    }`}
                    size={17}
                  />
                  {!collapsed && (
                    <span className="truncate text-[13.5px] font-medium">{label}</span>
                  )}
                  {collapsed && (
                    <span
                      className={`pointer-events-none absolute top-1/2 z-50 -translate-y-1/2 whitespace-nowrap rounded-lg border border-slate-700/60 bg-slate-950 px-2 py-1 text-xs text-slate-100 opacity-0 shadow-xl transition group-hover:opacity-100 ${
                        dir === 'rtl' ? 'right-[50px]' : 'left-[50px]'
                      }`}
                    >
                      {label}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Watermark — subtle white logo above profile section */}
      {!collapsed && (
        <div className="mb-2 flex items-center justify-center px-2">
          <img
            src="/branding/apg_logo_white.png?v=2"
            alt=""
            aria-hidden="true"
            className="h-6 w-6 object-contain opacity-[0.14]"
            draggable={false}
          />
        </div>
      )}

      {/* Admin profile */}
      <div
        className={`shrink-0 border border-slate-700/35 bg-slate-900/40 ${
          collapsed ? 'rounded-xl p-2 text-center' : 'rounded-xl p-3'
        }`}
      >
        {!collapsed ? (
          <>
            <div className="flex items-center gap-2.5">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-cyan-400/20 bg-cyan-400/10 text-xs font-bold text-cyan-300">
                {initials}
              </div>
              <div className="min-w-0">
                <p className="truncate text-[13px] font-semibold leading-tight">{user?.email}</p>
                <p className="text-[10px] uppercase tracking-widest text-cyan-300/80">{user?.role}</p>
              </div>
            </div>
            <button
              onClick={logout}
              className="motion-button mt-3 flex items-center gap-1.5 text-xs text-rose-300 hover:text-rose-200"
            >
              <LogOut size={13} /> {t('topbar.logout')}
            </button>
          </>
        ) : (
          <button
            onClick={logout}
            title={t('topbar.logout')}
            className="motion-button mx-auto grid h-9 w-9 place-items-center rounded-lg text-rose-300 hover:bg-rose-400/10"
          >
            <LogOut size={16} />
          </button>
        )}
      </div>
    </aside>
  );
}
