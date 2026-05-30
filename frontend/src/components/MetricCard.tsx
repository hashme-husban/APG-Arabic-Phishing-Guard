import { ArrowDownRight, ArrowUpRight, TrendingDown, TrendingUp } from 'lucide-react';
import type { Metric } from '../types';

const toneMap: Record<string, { badge: string; accent: string }> = {
  cyan:    { badge: 'text-cyan-300    bg-cyan-400/10    border-cyan-400/20',    accent: '#22D3EE' },
  purple:  { badge: 'text-violet-300  bg-violet-400/10  border-violet-400/20',  accent: '#8B5CF6' },
  success: { badge: 'text-emerald-300 bg-emerald-400/10 border-emerald-400/20', accent: '#22C55E' },
  warning: { badge: 'text-yellow-200  bg-yellow-400/10  border-yellow-400/20',  accent: '#FACC15' },
  danger:  { badge: 'text-rose-300    bg-rose-400/10    border-rose-400/20',    accent: '#FB7185' },
};

export default function MetricCard({ metric, onClick }: { metric: Metric; onClick?: () => void }) {
  const isUp = (metric.change ?? 0) >= 0;
  const tone = toneMap[metric.tone || 'cyan'] || toneMap.cyan;
  const Comp: any = onClick ? 'button' : 'div';
  return (
    <Comp
      onClick={onClick}
      style={{ borderLeftColor: tone.accent + 'AA' }}
      className={`card animate-in w-full border-l-2 p-4 text-start transition ${onClick ? 'hover:bg-[var(--bg-elevated)] cursor-pointer' : ''}`}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-[13px] font-medium text-slate-400">{metric.label}</p>
        <div className={`rounded-lg border p-1.5 ${tone.badge}`}>
          {isUp ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
        </div>
      </div>
      <div className="mt-3 flex items-end justify-between gap-2">
        <h3 className="text-2xl font-bold leading-none tracking-tight">
          {Number(metric.value).toLocaleString()}{metric.suffix || ''}
        </h3>
        {metric.change !== undefined && (
          <span className={`flex items-center gap-0.5 text-xs font-medium ${isUp ? 'text-emerald-300' : 'text-rose-300'}`}>
            {isUp ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            {isUp ? '+' : ''}{metric.change}%
          </span>
        )}
      </div>
    </Comp>
  );
}
