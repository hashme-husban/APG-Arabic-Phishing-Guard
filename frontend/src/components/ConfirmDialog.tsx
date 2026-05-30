import { useEffect, useState } from 'react';

type Variant = 'primary' | 'positive' | 'warning' | 'danger';
type Props = { open: boolean; title: string; description?: string; confirmLabel?: string; cancelLabel?: string; requireReason?: boolean; reasonPlaceholder?: string; variant?: Variant; onConfirm: (reason?: string) => void | Promise<void>; onCancel: () => void };

const variantClass: Record<Variant, string> = {
  primary: 'bg-sky-400 text-slate-950 hover:bg-sky-300',
  positive: 'bg-emerald-400 text-slate-950 hover:bg-emerald-300',
  warning: 'bg-amber-300 text-slate-950 hover:bg-amber-200',
  danger: 'bg-rose-500 text-white hover:bg-rose-400',
};

export default function ConfirmDialog({ open, title, description, confirmLabel = 'Confirm', cancelLabel = 'Cancel', requireReason = false, reasonPlaceholder = 'Reason', variant = 'primary', onConfirm, onCancel }: Props) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setReason(''); setBusy(false); } }, [open]);
  if (!open) return null;
  const submit = async () => {
    if (requireReason && !reason.trim()) return;
    setBusy(true);
    try { await onConfirm(reason); } finally { setBusy(false); }
  };
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"><div className="card w-full max-w-md p-6 animate-in"><h3 className="text-xl font-semibold text-slate-50">{title}</h3>{description && <p className="mt-2 text-sm leading-6 text-slate-300">{description}</p>}{requireReason && <label className="mt-4 grid gap-2 text-sm text-slate-300"><span>{reasonPlaceholder}</span><textarea value={reason} onChange={(e)=>setReason(e.target.value)} className="min-h-24 rounded-xl border border-slate-700/70 bg-slate-950/30 px-4 py-3 outline-none transition focus:border-sky-400/40" /></label>}<div className="mt-6 flex justify-end gap-3"><button onClick={onCancel} disabled={busy} className="secondary-button rounded-xl px-4 py-2 text-sm disabled:opacity-50">{cancelLabel}</button><button onClick={submit} disabled={busy || (requireReason && !reason.trim())} className={`rounded-xl px-4 py-2 text-sm font-semibold transition disabled:opacity-50 ${variantClass[variant]}`}>{busy ? '...' : confirmLabel}</button></div></div></div>;
}
