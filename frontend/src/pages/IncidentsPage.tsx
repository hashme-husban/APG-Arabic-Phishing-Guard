import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutGrid, List } from 'lucide-react';
import { api } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import LoadingSkeleton from '../components/LoadingSkeleton';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import type { Incident } from '../types';
import { useI18n, labelFor } from '../i18n';

export default function IncidentsPage() {
  const { t } = useI18n();
  const location = useLocation();
  const queryFilter = useMemo(
    () => new URLSearchParams(location.search).get('severity') || 'all',
    [location.search],
  );
  const [items, setItems] = useState<Incident[]>([]);
  const [filter, setFilter] = useState(queryFilter);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [compact, setCompact] = useState(
    () => localStorage.getItem('apg_incident_density') === 'compact',
  );

  const filters = ['all', 'high', 'medium', 'low', 'active', 'resolved'];

  const setDensity = (next: boolean) => {
    setCompact(next);
    localStorage.setItem('apg_incident_density', next ? 'compact' : 'comfortable');
  };

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const params: any = { search };
      if (['high', 'medium', 'low'].includes(filter)) params.severity = filter;
      if (['active', 'resolved'].includes(filter))    params.status   = filter;
      const res = await api.get('/admin/incidents', { params });
      setItems(res.data.items);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { setFilter(queryFilter); }, [queryFilter]);
  useEffect(() => { load(); }, [filter]);

  return (
    <div className="grid gap-4">
      {/* Toolbar */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && load()}
          placeholder={t('incidents.search')}
          className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm md:max-w-sm"
        />
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-xl border border-white/10 bg-white/[0.03] p-0.5">
            <button
              onClick={() => setDensity(false)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] ${!compact ? 'bg-cyan-400 text-slate-950' : 'text-slate-300 hover:bg-white/5'}`}
            >
              <LayoutGrid size={13} />{t('sidebar.comfortable')}
            </button>
            <button
              onClick={() => setDensity(true)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] ${compact ? 'bg-cyan-400 text-slate-950' : 'text-slate-300 hover:bg-white/5'}`}
            >
              <List size={13} />{t('sidebar.compact')}
            </button>
          </div>
          {filters.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-full px-3.5 py-1.5 text-[13px] transition ${
                filter === f
                  ? 'bg-cyan-400 text-slate-950 font-semibold'
                  : 'border border-white/10 text-slate-300 hover:bg-white/5'
              }`}
            >
              {labelFor(f, t)}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingSkeleton rows={5} />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : items.length === 0 ? (
        <EmptyState title={t('incidents.noIncidents')} description={t('states.noIncidents')} />
      ) : compact ? (
        /* Compact view */
        <div className="grid gap-2">
          {items.map((i) => (
            <div
              key={i.id}
              className="card grid gap-3 p-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="truncate text-sm font-semibold">{i.title}</h3>
                  <StatusBadge value={i.severity} label={labelFor(i.severity, t)} />
                  <StatusBadge value={i.status}   label={labelFor(i.status, t)} />
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  {i.channel} · {i.cases_count} {t('common.cases')} · {i.affected_devices} {t('common.devices')} · {t('common.lastSeen')}: {new Date(i.last_seen).toLocaleDateString()}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {i.indicators.slice(0, 2).map((ind) => (
                    <span key={ind} className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-slate-300">{ind}</span>
                  ))}
                  {i.indicators.length > 2 && (
                    <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-slate-400">+{i.indicators.length - 2}</span>
                  )}
                </div>
              </div>
              <Link
                to={`/incidents/${i.id}`}
                className="rounded-xl bg-cyan-400 px-4 py-2 text-center text-sm font-semibold text-slate-950 hover:bg-cyan-300"
              >
                {t('common.details')}
              </Link>
            </div>
          ))}
        </div>
      ) : (
        /* Comfortable view */
        <div className="grid gap-4">
          {items.map((i) => (
            <div key={i.id} className="card animate-in p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-lg font-semibold">{i.title}</h3>
                    <StatusBadge value={i.severity} label={labelFor(i.severity, t)} />
                    <StatusBadge value={i.status}   label={labelFor(i.status, t)} />
                  </div>
                  <p className="mt-2 max-w-3xl text-sm text-slate-400">{i.description}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {i.indicators.map((ind) => (
                      <span key={ind} className="rounded-full border border-slate-700/50 bg-slate-900/40 px-2.5 py-0.5 text-xs text-slate-300">{ind}</span>
                    ))}
                  </div>
                </div>
                <div className="text-end">
                  <p className="text-3xl font-bold text-cyan-300">{i.cases_count}</p>
                  <p className="text-xs text-slate-500">{t('common.cases')}</p>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] pt-4 text-sm text-slate-400">
                <span>{i.channel} · {i.affected_devices} {t('common.devices')} · {t('common.lastSeen')}: {new Date(i.last_seen).toLocaleDateString()}</span>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-slate-500 text-xs">{i.recommended_action}</span>
                  <Link
                    to={`/incidents/${i.id}`}
                    className="rounded-xl bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-300"
                  >
                    {t('common.details')}
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
