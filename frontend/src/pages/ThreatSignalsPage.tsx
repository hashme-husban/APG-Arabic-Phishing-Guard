import { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { api } from '../api/client';
import type { ThreatSignal } from '../types';
import StatusBadge from '../components/StatusBadge';
import LoadingSkeleton from '../components/LoadingSkeleton';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import ConfirmDialog from '../components/ConfirmDialog';
import SignalEditorModal from '../components/SignalEditorModal';
import { useI18n, labelFor } from '../i18n';
import { useToast } from '../components/common/ToastProvider';

/* ── severity accent colours for left-border ─────────────────── */
const severityBorderColor: Record<string, string> = {
  high:   '#FB718566',
  medium: '#FACC1566',
  low:    '#94A3B830',
};

/* ── category chip styles ─────────────────────────────────────── */
const categoryStyle: Record<string, string> = {
  text:     'border-sky-400/25    bg-sky-400/8    text-sky-300',
  link:     'border-violet-400/25 bg-violet-400/8 text-violet-300',
  behavior: 'border-amber-400/25  bg-amber-400/8  text-amber-200',
  sender:   'border-emerald-400/25 bg-emerald-400/8 text-emerald-300',
};

/* ── FP-risk chip colour ──────────────────────────────────────── */
const fpRiskStyle: Record<string, string> = {
  high:   'border-rose-400/20   bg-rose-400/8   text-rose-300',
  medium: 'border-amber-400/20  bg-amber-400/8  text-amber-200',
  low:    'border-emerald-400/20 bg-emerald-400/8 text-emerald-300',
};

/* ── Weight confidence bar ────────────────────────────────────── */
function WeightBar({ value }: { value: number }) {
  const pct   = Math.max(0, Math.min(100, value));
  const color = pct >= 75 ? '#FB7185' : pct >= 40 ? '#FACC15' : '#22D3EE';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1 flex-1 rounded-full bg-slate-800">
        <div
          className="h-1 rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color, opacity: 0.7 }}
        />
      </div>
      <span className="w-6 text-right text-[11px] font-semibold text-slate-400" dir="ltr">{pct}</span>
    </div>
  );
}

/* ── Compact iOS-style toggle ─────────────────────────────────── */
function Toggle({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      onClick={onToggle}
      className={`relative h-5 w-9 shrink-0 rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-cyan-400/30 ${
        enabled ? 'bg-emerald-500' : 'bg-slate-700'
      }`}
    >
      <span
        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${
          enabled ? 'left-[18px]' : 'left-0.5'
        }`}
      />
    </button>
  );
}

export default function ThreatSignalsPage() {
  const { t } = useI18n();
  const { toast } = useToast();
  const cats = ['all', 'text', 'link', 'behavior', 'sender'];

  const [items, setItems]     = useState<ThreatSignal[]>([]);
  const [category, setCategory] = useState('all');
  const [search, setSearch]   = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [editing, setEditing] = useState<ThreatSignal | null>(null);
  const [open, setOpen]       = useState(false);
  const [confirm, setConfirm] = useState<ThreatSignal | null>(null);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/admin/threat-signals', { params: { category, search } });
      setItems(res.data.items);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [category]);

  const save = async (payload: any) => {
    if (editing) await api.patch(`/admin/threat-signals/${editing.id}`, payload);
    else         await api.post('/admin/threat-signals', payload);
    toast(t('signals.saved'), 'success');
    await load();
  };

  const toggle = async (signal: ThreatSignal, reason?: string) => {
    await api.patch(`/admin/threat-signals/${signal.id}/toggle`, { reason });
    toast(t('signals.disabled'), 'success');
    await load();
  };

  const openEdit = (s: ThreatSignal) => { setEditing(s); setOpen(true); };
  const openAdd  = ()              => { setEditing(null); setOpen(true); };

  return (
    <div className="grid gap-5">
      {/* ── Toolbar ────────────────────────────────────────────── */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-wrap gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && load()}
            placeholder={t('signals.search')}
            className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 placeholder-slate-500 outline-none focus:border-cyan-400/30"
          />
          {cats.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition capitalize ${
                category === c
                  ? 'bg-sky-400 text-slate-950'
                  : 'border border-slate-700/60 text-slate-300 hover:bg-slate-800/60'
              }`}
            >
              {c === 'all' ? t('common.all') : c}
            </button>
          ))}
        </div>
        <button
          onClick={openAdd}
          className="enterprise-button flex shrink-0 items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold"
        >
          <Plus size={16} /> {t('signals.add')}
        </button>
      </div>

      {/* ── Card grid ──────────────────────────────────────────── */}
      {loading ? (
        <LoadingSkeleton variant="list" rows={6} />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : items.length === 0 ? (
        <EmptyState
          title={t('states.noSignals')}
          description="No detection signals match the current filter."
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {items.map((s) => (
            <SignalCard
              key={s.id}
              signal={s}
              onEdit={() => openEdit(s)}
              onToggle={() => s.impact === 'high' && s.enabled ? setConfirm(s) : toggle(s)}
            />
          ))}
        </div>
      )}

      <SignalEditorModal
        open={open}
        signal={editing}
        onClose={() => setOpen(false)}
        onSave={save}
      />

      <ConfirmDialog
        open={!!confirm}
        variant="danger"
        title={t('signals.disableHighTitle')}
        description={t('signals.disableHighImpact')}
        confirmLabel={t('signals.disableSignal')}
        cancelLabel={t('common.cancel')}
        requireReason
        reasonPlaceholder={t('common.reasonForChange')}
        onCancel={() => setConfirm(null)}
        onConfirm={async (reason) => {
          if (confirm) { await toggle(confirm, reason); setConfirm(null); }
        }}
      />
    </div>
  );
}

/* ── Signal card extracted as a stable named component ───────── */
function SignalCard({
  signal: s,
  onEdit,
  onToggle,
}: {
  signal: ThreatSignal;
  onEdit: () => void;
  onToggle: () => void;
}) {
  const { t } = useI18n();
  return (
    <div
      className="card card-hover flex flex-col border-l-2 p-4"
      style={{ borderLeftColor: severityBorderColor[s.impact] || '#94A3B830' }}
    >
      {/* ── Header row: name + toggle ─────────────────────────── */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-semibold leading-snug text-slate-100">{s.name}</h3>
          <p className="mt-1 line-clamp-2 text-[12px] leading-5 text-slate-400">{s.description}</p>
        </div>
        <Toggle enabled={s.enabled} onToggle={onToggle} />
      </div>

      {/* ── Metadata chips — always LTR to prevent Arabic bidi mix ── */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5" dir="ltr">
        {/* Severity */}
        <StatusBadge value={s.impact} label={labelFor(s.impact, t)} />

        {/* Category */}
        <span
          className={`rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize ${
            categoryStyle[s.category] || 'border-slate-700/40 bg-slate-800/40 text-slate-400'
          }`}
        >
          {s.category}
        </span>

        {/* False-positive risk */}
        <span
          className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${
            fpRiskStyle[s.false_positive_risk] || 'border-slate-700/40 bg-slate-800/40 text-slate-400'
          }`}
        >
          FP · <span className="capitalize">{s.false_positive_risk}</span>
        </span>
      </div>

      {/* ── Weight bar ──────────────────────────────────────────── */}
      <div className="mt-3">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-widest text-slate-600">
            {t('signals.weight')}
          </span>
        </div>
        <WeightBar value={s.weight} />
      </div>

      {/* ── Footer: enabled state + edit button ─────────────────── */}
      <div className="mt-3 flex items-center justify-between border-t border-slate-700/25 pt-3">
        <span
          className={`flex items-center gap-1.5 text-[11px] font-medium ${
            s.enabled ? 'text-emerald-400' : 'text-slate-600'
          }`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${s.enabled ? 'bg-emerald-400' : 'bg-slate-600'}`} />
          {s.enabled ? t('common.enabled') : t('common.disabled')}
        </span>
        <button
          onClick={onEdit}
          className="rounded-lg border border-cyan-400/20 px-3 py-1.5 text-[12px] text-cyan-200 transition hover:bg-cyan-400/10"
        >
          {t('signals.edit')}
        </button>
      </div>
    </div>
  );
}
