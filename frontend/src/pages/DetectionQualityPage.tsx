import { useEffect, useState } from 'react';
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api/client';
import LoadingSkeleton from '../components/LoadingSkeleton';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import MetricCard from '../components/MetricCard';
import StatusBadge from '../components/StatusBadge';
import ConfirmDialog from '../components/ConfirmDialog';
import { useI18n, labelFor } from '../i18n';
import { useToast } from '../components/common/ToastProvider';

const perfColors = ['#22D3EE', '#38BDF8', '#8B5CF6', '#FACC15', '#FB7185'];

export default function DetectionQualityPage() {
  const { t } = useI18n();
  const { toast } = useToast();

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<'queue' | 'reports' | 'resolved'>('queue');
  const [confirm, setConfirm] = useState<{
    id: number; status: string; title: string; description?: string; variant: 'positive' | 'warning';
  } | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const range = localStorage.getItem('apg_admin_range') || 'today';
      const res = await api.get('/admin/detection-quality', { params: { range } });
      setData(res.data);
      setError('');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    window.addEventListener('apg:refresh', load);
    return () => window.removeEventListener('apg:refresh', load);
  }, []);

  const review = async (id: number, status: string) => {
    await api.patch(`/admin/analysis/${id}/review`, { review_status: status });
    toast(t('quality.updateReview'), 'success');
    await load();
  };

  if (loading) return <LoadingSkeleton variant="cards" />;
  if (error)   return <ErrorState message={error} onRetry={load} />;

  const metricNames: Record<string, string> = {
    'Confirmed Correct':         t('quality.confirmedCorrect'),
    'Needs Review':              t('quality.needsReview'),
    'Estimated False Positive':  t('quality.estimatedFP'),
    'Estimated False Negative':  t('quality.estimatedFN'),
  };
  const metrics = data.metrics.map((m: any) => ({
    ...m,
    label: metricNames[m.label] || m.label,
    tone: 'cyan',
  }));

  const reports = (data.reports || []).filter((r: any) =>
    tab === 'resolved'
      ? ['resolved', 'rejected'].includes(r.status)
      : !['resolved', 'rejected'].includes(r.status),
  );

  const tabClass = (active: boolean) =>
    `rounded-full px-3.5 py-1.5 text-[13px] transition ${
      active ? 'bg-sky-400 text-slate-950 font-semibold' : 'border border-slate-700/60 text-slate-300 hover:bg-slate-800/40'
    }`;

  return (
    <div className="grid gap-5">
      {/* Metric cards */}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map((m: any) => <MetricCard key={m.label} metric={m} />)}
      </div>
      <p className="-mt-2 text-[12px] text-slate-500">{t('quality.note')}</p>

      {/* Charts */}
      <div className="grid gap-5 xl:grid-cols-2">
        <div className="card p-5">
          <h3 className="mb-4 flex items-center gap-2 text-base font-semibold">
            <span className="h-3.5 w-0.5 rounded-full bg-cyan-400/70" />
            {t('quality.performanceOverview')}
          </h3>
          <div className="h-52">
            <ResponsiveContainer>
              <BarChart data={data.performance} barCategoryGap="38%">
                <XAxis dataKey="name" stroke="#64748B" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis stroke="#64748B" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} width={30} />
                <Tooltip
                  contentStyle={{
                    background: '#0B1220',
                    border: '1px solid rgba(255,255,255,.1)',
                    borderRadius: 12,
                    fontSize: 13,
                  }}
                  cursor={{ fill: 'rgba(148,163,184,.05)' }}
                />
                <Bar dataKey="value" radius={[6, 6, 0, 0]} isAnimationActive animationDuration={900} maxBarSize={56}>
                  {data.performance.map((_: any, i: number) => (
                    <Cell key={i} fill={perfColors[i % perfColors.length]} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <h3 className="mb-4 flex items-center gap-2 text-base font-semibold">
            <span className="h-3.5 w-0.5 rounded-full bg-cyan-400/70" />
            {t('quality.userFeedback')}
          </h3>
          <div className="grid grid-cols-2 gap-2.5">
            {Object.entries(data.feedback_summary).map(([k, v]: any) => (
              <div key={k} className="rounded-xl border border-slate-700/40 bg-slate-900/30 p-3.5">
                <p className="text-xl font-bold text-cyan-300">{v}</p>
                <p className="mt-0.5 text-[12px] text-slate-400">{k.replaceAll('_', ' ')}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Where to improve */}
      <div className="grid gap-3 lg:grid-cols-4">
        {data.where_to_improve.map((x: any) => (
          <button
            key={x.title}
            onClick={() => setTab('queue')}
            className="card card-hover p-4 text-start"
          >
            <StatusBadge value={x.severity} label={labelFor(x.severity, t)} />
            <h3 className="mt-3 text-[13px] font-semibold leading-snug">{x.title}</h3>
            <p className="mt-1.5 text-[12px] leading-5 text-slate-400">{x.description}</p>
            <p className="mt-2.5 text-[11px] text-cyan-200">{x.suggested_improvement}</p>
          </button>
        ))}
      </div>

      {/* Review queue / reports */}
      <div className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-base font-semibold">
            {tab === 'queue' ? t('quality.reviewQueue') : tab === 'reports' ? t('quality.userReports') : t('quality.resolvedFeedback')}
          </h3>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => setTab('queue')}    className={tabClass(tab === 'queue')}>{t('quality.reviewQueue')}</button>
            <button onClick={() => setTab('reports')}  className={tabClass(tab === 'reports')}>{t('quality.userReports')}</button>
            <button onClick={() => setTab('resolved')} className={tabClass(tab === 'resolved')}>{t('quality.resolvedFeedback')}</button>
          </div>
        </div>

        {tab === 'queue' ? (
          <div className="mt-4 grid gap-2.5">
            {data.review_queue.length === 0 ? (
              <EmptyState title={t('states.noReview')} description={t('common.noData')} />
            ) : (
              data.review_queue.map((r: any) => (
                <div
                  key={r.id}
                  className="grid gap-3 rounded-xl border border-slate-700/50 bg-slate-900/30 p-4 transition hover:border-slate-600/60 xl:grid-cols-[100px_minmax(0,1fr)_120px_340px] xl:items-center"
                >
                  <div>
                    <p className="text-xl font-bold text-slate-50 leading-none">{r.risk_score}<span className="text-xs text-slate-500 font-normal">/100</span></p>
                    <p className="mt-1 text-[11px] text-slate-500" dir="ltr">{r.report_count} {t('quality.reports')}</p>
                  </div>
                  <div className="min-w-0">
                    <p className="line-clamp-2 text-sm leading-5 text-slate-200">{r.masked_text}</p>
                    <p className="mt-1 text-[12px] text-slate-400">{r.reason}</p>
                  </div>
                  <div className="xl:justify-self-center">
                    <StatusBadge value={r.classification} label={labelFor(r.classification, t)} />
                  </div>
                  <div className="flex flex-wrap gap-2 xl:justify-end">
                    <button
                      onClick={() => setConfirm({ id: r.id, status: 'reviewed', title: t('quality.confirmCorrect'), description: t('quality.confirmCorrectBody'), variant: 'positive' })}
                      className="rounded-xl bg-emerald-400 px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-emerald-300"
                    >
                      {t('quality.markCorrect')}
                    </button>
                    <button
                      onClick={() => setConfirm({ id: r.id, status: 'false_positive', title: t('quality.confirmFP'), variant: 'warning' })}
                      className="rounded-xl border border-slate-700/60 px-3 py-1.5 text-xs hover:bg-slate-800/50"
                    >
                      {t('quality.falsePositive')}
                    </button>
                    <button
                      onClick={() => setConfirm({ id: r.id, status: 'false_negative', title: t('quality.confirmFN'), variant: 'warning' })}
                      className="rounded-xl border border-slate-700/60 px-3 py-1.5 text-xs hover:bg-slate-800/50"
                    >
                      {t('quality.falseNegative')}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        ) : (
          <div className="mt-4 grid gap-2.5">
            {reports.length === 0 ? (
              <EmptyState title={t('states.noReview')} description={t('common.noData')} />
            ) : (
              reports.map((r: any) => (
                <div key={r.id} className="rounded-xl border border-slate-700/50 bg-slate-900/30 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <strong className="text-[13px]">{r.report_type?.replaceAll('_', ' ')}</strong>
                    <StatusBadge value={r.status} />
                  </div>
                  <p className="mt-2 text-sm text-slate-300">{r.message}</p>
                  <p className="mt-2 text-xs text-slate-500" dir="ltr">#{r.id} · {new Date(r.created_at).toLocaleDateString('en-GB')} {new Date(r.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })}</p>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!confirm}
        variant={confirm?.variant || 'primary'}
        title={confirm?.title || ''}
        description={confirm?.description}
        confirmLabel={confirm?.status === 'reviewed' ? t('quality.markCorrect') : t('common.confirm')}
        cancelLabel={t('common.cancel')}
        onCancel={() => setConfirm(null)}
        onConfirm={async () => {
          if (confirm) { await review(confirm.id, confirm.status); setConfirm(null); }
        }}
      />
    </div>
  );
}
