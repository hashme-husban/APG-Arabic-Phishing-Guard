import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ArrowLeft, Download, Radio, ShieldAlert, Zap } from 'lucide-react';
import { api } from '../api/client';
import LoadingSkeleton from '../components/LoadingSkeleton';
import ErrorState from '../components/ErrorState';
import StatusBadge from '../components/StatusBadge';
import ConfirmDialog from '../components/ConfirmDialog';
import { useI18n, labelFor } from '../i18n';
import { useToast } from '../components/common/ToastProvider';

export default function IncidentDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t } = useI18n();
  const { toast } = useToast();

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [confirmResolved, setConfirmResolved] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/admin/incidents/${id}`);
      setData(res.data);
      setError('');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);

  const update = async (status: string) => {
    await api.patch(`/admin/incidents/${id}`, { status });
    toast(
      status === 'resolved' ? t('incidents.incidentResolved') : t('incidents.incidentMonitoring'),
      'success',
    );
    await load();
  };

  const exportIncident = async () => {
    try {
      const res = await api.get('/admin/export/incidents', { responseType: 'blob' });
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `apg_incidents_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast(t('common.csvDownloaded'), 'success');
    } catch {
      toast(t('common.csvFailed'), 'error');
    }
  };

  if (loading) return <LoadingSkeleton rows={6} />;
  if (error)   return <ErrorState message={error} onRetry={load} />;

  const incident = data.incident;

  return (
    <div className="grid gap-5">
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="flex w-fit items-center gap-1.5 text-sm text-cyan-300 hover:text-cyan-200"
      >
        <ArrowLeft size={14} /> {t('common.back')}
      </button>

      {/* Header card */}
      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ShieldAlert size={18} className="text-rose-400 shrink-0" />
              <h2 className="text-2xl font-bold">{incident.title}</h2>
            </div>
            <p className="mt-1.5 max-w-2xl text-sm text-slate-400">{incident.description}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <StatusBadge value={incident.severity} label={labelFor(incident.severity, t)} />
              <StatusBadge value={incident.status}   label={labelFor(incident.status, t)} />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => update('monitoring')}
              className="rounded-xl border border-white/10 bg-white/[0.04] px-3.5 py-2 text-sm hover:bg-white/[0.07]"
            >
              <Radio size={13} className="inline mr-1.5 text-violet-300" />
              {t('common.markMonitoring')}
            </button>
            <button
              onClick={() => setConfirmResolved(true)}
              className="rounded-xl bg-emerald-400 px-3.5 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300"
            >
              {t('common.markResolved')}
            </button>
            <button
              onClick={exportIncident}
              className="rounded-xl border border-cyan-400/25 px-3.5 py-2 text-sm text-cyan-200 hover:bg-cyan-400/10"
            >
              <Download size={13} className="inline mr-1.5" />
              {t('incidents.exportIncident')}
            </button>
          </div>
        </div>
      </div>

      {/* Chart + Recommendation */}
      <div className="grid gap-5 xl:grid-cols-2">
        <div className="card p-5">
          <h3 className="mb-4 flex items-center gap-2 text-base font-semibold">
            <span className="h-3.5 w-0.5 rounded-full bg-cyan-400/70" />
            {t('incidents.casesOverTime')}
          </h3>
          <div className="h-56">
            <ResponsiveContainer>
              <LineChart data={data.cases_over_time}>
                <XAxis dataKey="day" stroke="#64748B" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis stroke="#64748B" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} width={30} />
                <Tooltip
                  contentStyle={{
                    background: '#0B1220',
                    border: '1px solid rgba(255,255,255,.1)',
                    borderRadius: 12,
                    fontSize: 13,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="cases"
                  stroke="#22D3EE"
                  strokeWidth={2.5}
                  dot={{ fill: '#22D3EE', r: 3, strokeWidth: 0 }}
                  activeDot={{ r: 5, fill: '#22D3EE' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <h3 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <span className="h-3.5 w-0.5 rounded-full bg-cyan-400/70" />
            {t('common.recommendedAction')}
          </h3>
          <p className="text-sm leading-6 text-slate-300">{incident.recommended_action}</p>

          <h3 className="mt-5 mb-3 flex items-center gap-2 text-base font-semibold">
            <span className="h-3.5 w-0.5 rounded-full bg-violet-400/70" />
            {t('incidents.topIndicators')}
          </h3>
          <div className="flex flex-wrap gap-2">
            {data.top_indicators.map((x: string) => (
              <button
                key={x}
                onClick={() => navigate('/threat-signals')}
                className="flex items-center gap-1.5 rounded-full border border-violet-400/25 bg-violet-400/10 px-3 py-1 text-xs text-violet-200 hover:bg-violet-400/20"
              >
                <Zap size={11} />
                {x}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Related masked cases */}
      <div className="card p-5">
        <h3 className="mb-4 flex items-center gap-2 text-base font-semibold">
          <span className="h-3.5 w-0.5 rounded-full bg-cyan-400/70" />
          {t('incidents.relatedMaskedCases')}
        </h3>
        <div className="grid gap-3">
          {data.related_results.map((r: any) => (
            <div
              key={r.id}
              className="rounded-xl border border-slate-700/50 bg-slate-900/30 p-4 transition hover:border-slate-600/60"
            >
              <div className="flex items-center justify-between gap-3 mb-2">
                <StatusBadge value={r.classification} label={labelFor(r.classification, t)} />
                <span className="text-sm font-bold text-slate-100">{r.risk_score}<span className="text-xs text-slate-500 font-normal">/100</span></span>
              </div>
              <p className="text-sm leading-6 text-slate-300">{r.masked_text}</p>
              <p className="mt-2 text-xs text-slate-500" dir="ltr">{r.source} · {r.created_at ? new Date(r.created_at).toLocaleDateString('en-GB') + ' ' + new Date(r.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }) : ''}</p>
            </div>
          ))}
        </div>
      </div>

      <ConfirmDialog
        open={confirmResolved}
        variant="positive"
        title={t('incidents.markResolvedQuestion')}
        description={t('incidents.markResolvedBody')}
        confirmLabel={t('common.markResolved')}
        cancelLabel={t('common.cancel')}
        onCancel={() => setConfirmResolved(false)}
        onConfirm={async () => { setConfirmResolved(false); await update('resolved'); }}
      />
    </div>
  );
}
