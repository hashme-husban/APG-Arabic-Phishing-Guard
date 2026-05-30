const styles: Record<string, string> = {
  connected:      'bg-emerald-400/10 text-emerald-300 border-emerald-400/25',
  stable:         'bg-emerald-400/10 text-emerald-300 border-emerald-400/25',
  safe:           'bg-emerald-400/10 text-emerald-300 border-emerald-400/25',
  high:           'bg-rose-400/10    text-rose-300    border-rose-400/25',
  danger:         'bg-rose-400/10    text-rose-300    border-rose-400/25',
  dangerous:      'bg-rose-400/10    text-rose-300    border-rose-400/25',
  medium:         'bg-amber-400/10   text-amber-200   border-amber-400/25',
  suspicious:     'bg-amber-400/10   text-amber-200   border-amber-400/25',
  active:         'bg-sky-400/10     text-sky-200     border-sky-400/25',
  monitoring:     'bg-violet-400/10  text-violet-200  border-violet-400/25',
  resolved:       'bg-slate-400/10   text-slate-300   border-slate-400/20',
  low:            'bg-slate-400/10   text-slate-300   border-slate-400/20',
  reviewed:       'bg-emerald-400/10 text-emerald-300 border-emerald-400/25',
  false_positive: 'bg-amber-400/10   text-amber-200   border-amber-400/25',
  false_negative: 'bg-rose-400/10    text-rose-300    border-rose-400/25',
};

const dots: Record<string, string> = {
  connected: 'bg-emerald-400', stable: 'bg-emerald-400', safe: 'bg-emerald-400', reviewed: 'bg-emerald-400',
  high: 'bg-rose-400', danger: 'bg-rose-400', dangerous: 'bg-rose-400', false_negative: 'bg-rose-400',
  medium: 'bg-amber-400', suspicious: 'bg-amber-400', false_positive: 'bg-amber-400',
  active: 'bg-sky-400',
  monitoring: 'bg-violet-400',
  resolved: 'bg-slate-400', low: 'bg-slate-400',
};

export default function StatusBadge({ value, label }: { value: string; label?: string }) {
  const key = (value || '').toLowerCase();
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-wide ${styles[key] || styles.low}`}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dots[key] || 'bg-slate-400'}`} />
      {label || value}
    </span>
  );
}
