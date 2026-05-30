import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, ArrowUpRight, ShieldCheck, Zap } from 'lucide-react';
import { api } from '../api/client';
import MetricCard from '../components/MetricCard';
import RiskDonutChart from '../components/RiskDonutChart';
import ChannelBarChart from '../components/ChannelBarChart';
import LoadingSkeleton from '../components/LoadingSkeleton';
import ErrorState from '../components/ErrorState';
import StatusBadge from '../components/StatusBadge';
import { useI18n } from '../i18n';

const indicatorLabel: Record<string, string> = {
  'OTP request': 'OTP request',
  'Shortened URL': 'Shortened URL',
  'Login/verify path': 'Login/verify path',
  'Bank impersonation': 'Bank impersonation',
};

function SectionHeader({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h3 className="flex items-center gap-2 text-base font-semibold">
        <span className="h-4 w-0.5 rounded-full bg-cyan-400/70" />
        {title}
      </h3>
      {action}
    </div>
  );
}

export default function MonitoringPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { t, lang } = useI18n();
  const navigate = useNavigate();

  const load = async () => {
    const range = localStorage.getItem('apg_admin_range') || 'today';
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/admin/monitoring', { params: { range } });
      setData(res.data);
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

  if (loading) return <LoadingSkeleton variant="cards" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const translatedMetrics = data.metrics.map((m: any) => ({
    ...m,
    label:
      m.label === 'Total Analyses' ? t('monitoring.totalAnalyses') :
      m.label === 'High Risk'       ? t('monitoring.highRisk') :
      m.label === 'Suspicious'      ? t('monitoring.suspicious') :
      m.label === 'Safe'            ? t('monitoring.safe') :
      m.label,
  }));

  const riskData = data.risk_distribution.map((x: any) => ({
    ...x,
    name:
      x.key === 'safe'       ? t('monitoring.safeLegend') :
      x.key === 'suspicious' ? t('monitoring.suspiciousLegend') :
      x.key === 'dangerous'  ? t('monitoring.highRiskLegend') :
      x.name,
  }));

  const localizeAttention = (item: any) => {
    if (lang !== 'ar') return item;
    if (item.title.includes('OTP'))     return { ...item, title: 'ارتفاع رسائل OTP', detail: 'زادت طلبات رموز التحقق عبر حملات SMS.' };
    if (item.title.includes('login'))   return { ...item, title: 'روابط تسجيل دخول متكررة', detail: 'تستخدم عدة روابط مشبوهة مسارات /verify أو /login.' };
    if (item.title.includes('reports')) return { ...item, title: 'بلاغات مستخدمين معلّقة', detail: 'توجد بلاغات تحتاج مراجعة من الأدمن.' };
    return { ...item, title: 'حالة API', detail: 'الخادم مستقر حاليًا.' };
  };

  return (
    <div className="grid gap-5">
      {/* Seed data banner */}
      {data.seed_data && (
        <div className="flex justify-end">
          <StatusBadge value="active" label={t('app.seedData')} />
        </div>
      )}

      {/* Metric cards */}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {translatedMetrics.map((m: any, idx: number) => (
          <MetricCard
            key={m.label}
            metric={m}
            onClick={
              idx === 1 ? () => navigate('/incidents?severity=high') :
              idx === 2 ? () => navigate('/incidents?severity=medium') :
              idx === 0 ? () => navigate('/incidents') :
              undefined
            }
          />
        ))}
      </div>

      {/* Charts row */}
      <div className="grid gap-5 xl:grid-cols-2">
        <RiskDonutChart data={riskData} title={t('monitoring.riskDistribution')} />
        <ChannelBarChart data={data.channel_breakdown} title={t('monitoring.channelBreakdown')} />
      </div>

      {/* Attention / Activity / Threat story */}
      <div className="grid gap-5 xl:grid-cols-3">
        {/* Needs attention */}
        <div className="card p-4 xl:col-span-1">
          <SectionHeader title={t('monitoring.needsAttention')} />
          <div className="mt-3 grid gap-2">
            {data.needs_attention.map((raw: any) => {
              const item = localizeAttention(raw);
              return (
                <button
                  key={item.title}
                  onClick={() => navigate(item.path || '/incidents')}
                  className="card-hover rounded-xl border border-slate-700/40 bg-slate-900/30 p-3.5 text-start"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-[13px] font-medium">{item.title}</p>
                    <span className="flex items-center gap-1.5">
                      <StatusBadge value={item.severity} />
                      <ArrowUpRight size={13} className="text-slate-500" />
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">{item.detail}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Recent activity */}
        <div className="card p-4">
          <SectionHeader title={t('monitoring.recentActivity')} />
          <div className="mt-3 grid gap-2">
            {(data.recent_activity || []).map((a: any, idx: number) => (
              <div
                key={a.id || a.event || idx}
                className="flex items-center justify-between rounded-xl border border-slate-700/30 bg-slate-900/30 px-3 py-2.5"
              >
                <span className="flex items-center gap-2 text-[13px]">
                  <Activity size={14} className="shrink-0 text-cyan-300" />
                  {a.event || a.action_title || a.action}
                </span>
                <span className="text-xs text-slate-500">
                  {a.time || new Date(a.created_at || Date.now()).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Threat story */}
        <div className="card p-4">
          <SectionHeader title={t('monitoring.threatStory')} />
          <p className="mt-3 text-[13px] leading-6 text-slate-300">
            {lang === 'ar' ? t('monitoring.storyText') : data.threat_story}
          </p>
          <button
            onClick={() => navigate('/incidents?severity=high')}
            className="secondary-button mt-4 flex items-center gap-2 rounded-xl px-3.5 py-2 text-[13px] text-cyan-200"
          >
            <ShieldCheck size={14} /> {t('common.openRelatedCases')}
          </button>
        </div>
      </div>

      {/* Top indicators */}
      <div className="card p-4">
        <SectionHeader title={t('monitoring.topIndicators')} />
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {data.top_indicators.map((x: any) => (
            <button
              key={x.name}
              onClick={() =>
                x.target_type === 'incident' && x.target_id
                  ? navigate(`/incidents/${x.target_id}`)
                  : navigate('/threat-signals')
              }
              className="card-hover rounded-xl border border-slate-700/40 bg-slate-900/30 p-4 text-start"
            >
              <Zap className="mb-2.5 text-cyan-300" size={16} />
              <p className="text-[13px] font-semibold">{indicatorLabel[x.name] || x.name}</p>
              <p className="mt-1 text-2xl font-bold text-cyan-300">{x.count}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
