import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useI18n } from '../i18n';

const channelKey: Record<string, string> = {
  SMS: 'monitoring.channelSms',
  Email: 'monitoring.channelEmail',
  WhatsApp: 'monitoring.channelWhatsapp',
  Notification: 'monitoring.channelNotification',
  Manual: 'monitoring.channelManual',
};

const channelColors: Record<string, string> = {
  SMS: '#22D3EE',
  Email: '#38BDF8',
  WhatsApp: '#22C55E',
  Notification: '#FACC15',
  Manual: '#94A3B8',
};

export default function ChannelBarChart({ data, title = 'Channel Breakdown' }: { data: any[]; title?: string }) {
  const { t } = useI18n();
  const mapped = data.map((item) => ({
    ...item,
    label: t(channelKey[item.channel] || item.channel),
    color: channelColors[item.channel] || '#38BDF8',
  }));

  return (
    <div className="card p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">{title}</h3>
        <span className="text-xs text-slate-500 uppercase tracking-wide">{t('common.cases')}</span>
      </div>
      <div className="h-52">
        <ResponsiveContainer>
          <BarChart data={mapped} barCategoryGap="38%">
            <CartesianGrid stroke="rgba(148,163,184,.07)" vertical={false} />
            <XAxis
              dataKey="label"
              stroke="#64748B"
              tick={{ fontSize: 12, fill: '#94A3B8' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              stroke="#64748B"
              tick={{ fontSize: 12, fill: '#94A3B8' }}
              axisLine={false}
              tickLine={false}
              width={30}
            />
            <Tooltip
              formatter={(value: any) => [value, t('common.cases')]}
              labelFormatter={(label) => label}
              contentStyle={{
                background: '#0D1724',
                border: '1px solid rgba(148,163,184,.18)',
                borderRadius: 12,
                color: '#F8FAFC',
                fontSize: 13,
              }}
              cursor={{ fill: 'rgba(148,163,184,.05)' }}
            />
            <Bar dataKey="count" radius={[6, 6, 0, 0]} isAnimationActive maxBarSize={52}>
              {mapped.map((entry, index) => (
                <Cell key={index} fill={entry.color} fillOpacity={0.82} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
