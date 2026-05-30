import { Clock, ExternalLink, ShieldCheck } from 'lucide-react';
import StatusBadge from './StatusBadge';
import { useI18n } from '../i18n';
import type { DynamicSandboxExplainResult } from '../types';

function valueText(value: unknown, fallback: string) {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (value === undefined || value === null || value === '') return fallback;
  return String(value);
}

function boolLabel(value: boolean | undefined, t: (key: string) => string) {
  if (value === undefined) return t('common.noData');
  return value ? t('common.enabled') : t('common.disabled');
}

function boolTone(value: boolean | undefined) {
  return value ? 'active' : 'low';
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-700/25 py-1.5 last:border-0">
      <span className="text-[12px] text-slate-500">{label}</span>
      <span className="max-w-[62%] break-words text-right text-[13px] font-medium text-slate-200" dir="auto">
        {value}
      </span>
    </div>
  );
}

export default function DynamicSandboxResultCard({
  result,
  compact = false,
}: {
  result?: DynamicSandboxExplainResult | null;
  compact?: boolean;
}) {
  const { t } = useI18n();
  const data = result || {};
  const status = data.status || (data.enabled === false ? 'disabled' : 'not_configured');
  const disabled = status === 'disabled' || data.enabled === false;
  const statusLabel =
    status === 'disabled'
      ? t('common.disabled')
      : status === 'completed'
        ? t('sandboxResult.completed')
        : status === 'failed'
          ? t('sandboxResult.failed')
          : valueText(status, t('system.sandboxStatusNotConfigured'));

  const booleans = [
    [t('sandboxResult.loginForm'), data.has_login_form],
    [t('sandboxResult.passwordField'), data.has_password_field],
    [t('sandboxResult.otpField'), data.has_otp_field],
    [t('sandboxResult.delayedUrlChange'), data.delayed_url_change],
    [t('sandboxResult.delayedTitleChange'), data.delayed_title_change],
    [t('sandboxResult.delayedFormChange'), data.delayed_form_change],
    [t('sandboxResult.delayedSensitiveField'), data.delayed_sensitive_field_appeared],
    [t('system.timeSimulation'), data.time_simulation_enabled],
  ] as const;

  return (
    <div className={`card p-5 ${disabled ? 'border-slate-700/45 bg-slate-950/20' : ''}`}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-base font-semibold">
          <ShieldCheck size={15} className="text-slate-400" />
          {t('sandboxResult.title')}
        </h3>
        <StatusBadge value={disabled ? 'resolved' : status === 'failed' ? 'high' : 'active'} label={statusLabel} />
      </div>

      <div className="mb-4 rounded-lg border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-[12px] font-medium text-amber-100">
        {t('sandboxResult.advisoryNote')}
      </div>

      <div className={`grid gap-4 ${compact ? '' : 'xl:grid-cols-2'}`}>
        <div>
          <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-slate-500">
            <ExternalLink size={13} />
            {t('sandboxResult.navigation')}
          </div>
          <div className="grid gap-0">
            <DetailRow label={t('system.status')} value={statusLabel} />
            <DetailRow label={t('sandboxResult.finalUrl')} value={valueText(data.final_url, t('common.noData'))} />
            <DetailRow label={t('sandboxResult.redirectChainLength')} value={String(data.redirect_chain?.length || 0)} />
            <DetailRow label={t('sandboxResult.pageTitle')} value={valueText(data.page_title, t('common.noData'))} />
            <DetailRow label={t('sandboxResult.elapsedMs')} value={data.elapsed_ms === undefined ? t('common.noData') : `${data.elapsed_ms} ms`} />
            {data.error && <DetailRow label={t('sandboxResult.error')} value={data.error} />}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-slate-500">
            <Clock size={13} />
            {t('sandboxResult.signals')}
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {booleans.map(([label, value]) => (
              <div
                key={label}
                className="flex items-center justify-between gap-3 rounded-lg border border-slate-700/30 bg-slate-900/20 px-3 py-2"
              >
                <span className="text-[12px] text-slate-400">{label}</span>
                <StatusBadge value={boolTone(value)} label={boolLabel(value, t)} />
              </div>
            ))}
          </div>
          <div className="mt-3 grid gap-0">
            <DetailRow label={t('sandboxResult.formCount')} value={String(data.form_count ?? 0)} />
            <DetailRow label={t('sandboxResult.externalRequests')} value={String(data.external_request_count ?? 0)} />
            <DetailRow label={t('sandboxResult.suspiciousRequests')} value={String(data.suspicious_request_count ?? 0)} />
            <DetailRow label={t('system.simulatedMinutes')} value={String(data.simulated_minutes ?? 0)} />
          </div>
        </div>
      </div>
    </div>
  );
}
