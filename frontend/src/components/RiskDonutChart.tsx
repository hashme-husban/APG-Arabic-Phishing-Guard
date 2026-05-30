import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { useI18n } from '../i18n';

const COLORS: Record<string, string> = { safe: '#22C55E', suspicious: '#FACC15', dangerous: '#FB7185' };

export default function RiskDonutChart({ data, title = 'Risk Distribution' }: { data: any[]; title?: string }) {
  const { lang, t } = useI18n();
  const total = data.reduce((sum, item) => sum + Number(item.value || 0), 0) || 1;
  const risk = data.find((item) => item.key === 'dangerous')?.value || 0;
  const riskPercent = Math.round((Number(risk) / total) * 100);

  return (
    <div className="card card-hover p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">{title}</h3>
        <span className="rounded-full border border-slate-700/50 bg-slate-900/40 px-3 py-1 text-xs text-slate-400">
          {total.toLocaleString(lang === 'ar' ? 'ar' : 'en')} {lang === 'ar' ? 'تحليل' : 'analyses'}
        </span>
      </div>
      <div className="grid gap-5 md:grid-cols-[1fr_196px]">
        <div className="relative h-52">
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius={58}
                outerRadius={88}
                paddingAngle={3}
                cornerRadius={6}
                isAnimationActive
                animationDuration={1100}
                animationEasing="ease-out"
              >
                {data.map((entry, index) => (
                  <Cell
                    key={index}
                    fill={COLORS[entry.key] || '#22D3EE'}
                    stroke="rgba(15,23,42,.9)"
                    strokeWidth={2}
                  />
                ))}
              </Pie>
              <Tooltip
                formatter={(value: any, name: any) => [Number(value).toLocaleString(), name]}
                contentStyle={{
                  background: '#0D1724',
                  border: '1px solid rgba(148,163,184,.18)',
                  borderRadius: 12,
                  color: '#F8FAFC',
                  fontSize: 13,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            <div className="rounded-xl border border-slate-700/40 bg-slate-950/65 px-3 py-2 text-center">
              <p className="text-xl font-bold leading-none text-slate-50">{riskPercent}%</p>
              <p className="mt-0.5 text-[11px] text-slate-400">{t('monitoring.highRisk')}</p>
            </div>
          </div>
        </div>
        <div className="grid content-center gap-2.5">
          {data.map((item: any) => {
            const pct = Math.round((Number(item.value || 0) / total) * 100);
            const color = COLORS[item.key] || '#22D3EE';
            return (
              <div
                key={item.key || item.name}
                className="rounded-xl border border-slate-700/40 bg-slate-900/30 px-3 py-2.5 transition hover:border-slate-600/60 hover:bg-slate-800/40"
              >
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2 text-[13px] text-slate-300">
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
                    {item.name}
                  </span>
                  <span className="text-[13px] font-semibold text-slate-100">{pct}%</span>
                </div>
                <div className="h-1 rounded-full bg-slate-800">
                  <div
                    className="h-1 rounded-full transition-all duration-700"
                    style={{ width: `${pct}%`, background: color, opacity: 0.65 }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
