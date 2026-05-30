import { AlertTriangle } from 'lucide-react';
import { useI18n } from '../i18n';
export default function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useI18n();
  return <div className="soft-card p-6 text-rose-200"><div className="flex items-center gap-2 font-semibold"><AlertTriangle size={18} /> {t('states.failedLoad')}</div><p className="mt-2 text-sm text-slate-300">{message}</p>{onRetry && <button onClick={onRetry} className="mt-4 rounded-xl bg-rose-400/10 px-4 py-2 text-sm text-rose-200 hover:bg-rose-400/20">{t('common.retry')}</button>}</div>;
}
