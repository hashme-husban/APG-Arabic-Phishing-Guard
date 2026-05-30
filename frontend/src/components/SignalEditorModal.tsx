import { useEffect, useState } from 'react';
import type { ThreatSignal } from '../types';
import { useI18n } from '../i18n';

type Props = {
  open: boolean;
  signal?: ThreatSignal | null;
  onClose: () => void;
  onSave: (payload: any) => Promise<void>;
};

type FieldProps = { label: string; help?: string; children: React.ReactNode };

/**
 * Defined at module scope so React never unmounts/remounts inputs on keystroke.
 * Defining this inside the modal component function would recreate it on every
 * render, causing React to treat it as a new component type and destroy focus.
 */
function ModalField({ label, help, children }: FieldProps) {
  return (
    <label className="grid gap-1.5 text-sm text-slate-300">
      <span className="text-[13px] font-medium text-slate-300">{label}</span>
      {children}
      {help && <span className="text-[11px] text-slate-500">{help}</span>}
    </label>
  );
}

const inputCls =
  'w-full rounded-xl border border-white/10 bg-white/5 px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 outline-none transition focus:border-cyan-400/40 focus:ring-1 focus:ring-cyan-400/20';
const selectCls =
  'w-full rounded-xl border border-white/10 bg-[#0B1220] px-3.5 py-2.5 text-sm text-slate-100 outline-none transition focus:border-cyan-400/40';

const defaultForm = {
  name: '',
  category: 'text',
  description: '',
  impact: 'medium',
  enabled: true,
  weight: 50,
  false_positive_risk: 'medium',
};

export default function SignalEditorModal({ open, signal, onClose, onSave }: Props) {
  const { t } = useI18n();
  const [form, setForm] = useState<any>(defaultForm);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  useEffect(() => {
    if (open) {
      setForm(signal ? { ...signal } : { ...defaultForm });
      setSaveError('');
    }
  }, [signal, open]);

  if (!open) return null;

  const valid =
    form.name.trim().length >= 2 &&
    form.description.trim().length >= 4 &&
    Number(form.weight) >= 0 &&
    Number(form.weight) <= 100;

  const submit = async () => {
    if (!valid) return;
    setSaving(true);
    setSaveError('');
    try {
      await onSave({ ...form, weight: Number(form.weight) });
      onClose();
    } catch (e: any) {
      setSaveError(e?.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const set = (key: string, value: any) => setForm((prev: any) => ({ ...prev, [key]: value }));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="card w-full max-w-2xl animate-in overflow-hidden p-6">
        <h3 className="text-lg font-bold">
          {signal ? t('signals.edit') : t('signals.add')}
        </h3>
        <p className="mt-0.5 text-[12px] text-slate-500">
          {signal ? `Editing: ${signal.name}` : 'Configure a new detection signal'}
        </p>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {/* Name */}
          <ModalField label={t('signals.name')}>
            <input
              className={inputCls}
              placeholder="e.g. Suspicious Login Path"
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
              autoFocus
            />
          </ModalField>

          {/* Category */}
          <ModalField label={t('signals.category')}>
            <select
              className={selectCls}
              value={form.category}
              onChange={(e) => set('category', e.target.value)}
            >
              <option value="text">Text</option>
              <option value="link">Link</option>
              <option value="behavior">Behavior</option>
              <option value="sender">Sender</option>
            </select>
          </ModalField>

          {/* Impact / Severity */}
          <ModalField label={t('signals.impact')}>
            <select
              className={selectCls}
              value={form.impact}
              onChange={(e) => set('impact', e.target.value)}
            >
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </ModalField>

          {/* Weight */}
          <ModalField label={`${t('signals.weight')} (0–100)`} help={t('signals.weightHelp')}>
            <input
              type="number"
              min={0}
              max={100}
              className={inputCls}
              value={form.weight}
              onChange={(e) => set('weight', e.target.value)}
            />
          </ModalField>

          {/* Description — full width */}
          <div className="md:col-span-2">
            <ModalField label={t('signals.description')}>
              <textarea
                className={`${inputCls} min-h-[90px] resize-none`}
                placeholder="Describe what this signal detects..."
                value={form.description}
                onChange={(e) => set('description', e.target.value)}
              />
            </ModalField>
          </div>

          {/* False-positive risk */}
          <ModalField label={t('signals.fpRisk')} help={t('signals.fpHelp')}>
            <select
              className={selectCls}
              value={form.false_positive_risk}
              onChange={(e) => set('false_positive_risk', e.target.value)}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </ModalField>

          {/* Enabled toggle */}
          <div className="flex items-center gap-3 pt-1">
            <button
              type="button"
              role="switch"
              aria-checked={form.enabled}
              onClick={() => set('enabled', !form.enabled)}
              className={`relative h-5 w-9 shrink-0 rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-cyan-400/40 ${
                form.enabled ? 'bg-emerald-500' : 'bg-slate-700'
              }`}
            >
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${
                  form.enabled ? 'left-[18px]' : 'left-0.5'
                }`}
              />
            </button>
            <span className={`text-[13px] font-medium ${form.enabled ? 'text-emerald-300' : 'text-slate-500'}`}>
              {form.enabled ? t('common.enabled') : t('common.disabled')}
            </span>
          </div>
        </div>

        {saveError && (
          <p className="mt-3 rounded-xl border border-rose-400/25 bg-rose-400/8 px-3 py-2 text-[12px] text-rose-300">
            {saveError}
          </p>
        )}

        <div className="mt-5 flex items-center justify-between gap-3 border-t border-slate-700/30 pt-4">
          <p className="text-[12px] text-slate-500">
            {!valid && form.name.length > 0 ? 'Fill in all required fields' : ' '}
          </p>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-sm hover:bg-white/[0.07]"
            >
              {t('common.cancel')}
            </button>
            <button
              onClick={submit}
              disabled={saving || !valid}
              className="rounded-xl bg-cyan-400 px-5 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
            >
              {saving ? t('common.loading') : t('common.save')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
