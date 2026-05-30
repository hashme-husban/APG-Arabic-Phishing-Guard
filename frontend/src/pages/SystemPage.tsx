import { useEffect, useState } from 'react';
import {
  Activity, CheckCircle2, Database, Download, FileDown,
  RefreshCw, Server, ShieldCheck, Zap,
} from 'lucide-react';
import {
  api,
  cleanupThreatIntelligenceMemory,
  getThreatIntelligenceIndicators,
  getThreatIntelligenceSummary,
} from '../api/client';
import LoadingSkeleton from '../components/LoadingSkeleton';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import StatusBadge from '../components/StatusBadge';
import ConfirmDialog from '../components/ConfirmDialog';
import { useI18n } from '../i18n';
import { useToast } from '../components/common/ToastProvider';
import type { DynamicUrlAnalysisStatus, ThreatIndicatorMemoryItem, ThreatIntelligenceSummary } from '../types';

const actionKey: Record<string, string> = {
  toggle_signal: 'audit.signalDisabled', edit_signal: 'audit.signalUpdated',
  add_signal: 'audit.signalAdded', mark_incident_resolved: 'audit.incidentResolved',
  review_false_positive: 'audit.reviewFalsePositive', review_false_negative: 'audit.reviewFalseNegative',
  review_mark_correct: 'audit.reviewCorrect', sync_rules: 'audit.rulesSynced',
  export_incidents: 'audit.csvExported', export_quality: 'audit.csvExported',
  export_signals: 'audit.csvExported', export_security_summary: 'audit.csvExported',
  export_incidents_csv: 'audit.csvExported', export_detection_quality_csv: 'audit.csvExported',
  export_threat_signals_csv: 'audit.csvExported', export_security_summary_csv: 'audit.csvExported',
  export_security_report_pdf: 'audit.pdfExported', test_connection: 'audit.connectionTested',
  signal_updated: 'audit.signalUpdated', incident_resolved: 'audit.incidentResolved',
  rules_synced: 'audit.rulesSynced', connection_tested: 'audit.connectionTested',
};

function filenameFromDisposition(header?: string) {
  const match = header?.match(/filename="?([^";]+)"?/i);
  return match?.[1] || `apg_export_${new Date().toISOString().slice(0, 10)}.csv`;
}

/** Format dates consistently: "2026-05-10 · 8:42 PM" regardless of locale */
function fmtDate(iso: string) {
  try {
    const d = new Date(iso);
    const date = d.toLocaleDateString('en-GB', { year: 'numeric', month: '2-digit', day: '2-digit' });
    const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    return `${date} · ${time}`;
  } catch {
    return iso;
  }
}

/** Mask raw server URL — show only sanitised label to avoid localhost leaks */
function maskUrl(url: string) {
  if (!url) return 'Configured';
  try {
    const u = new URL(url);
    // Hide localhost / private IPs; show only host for external endpoints
    if (u.hostname === 'localhost' || u.hostname.startsWith('127.') || u.hostname.startsWith('192.168.')) {
      return 'APG Analysis API (local)';
    }
    return `${u.hostname}${u.port ? `:${u.port}` : ''}`;
  } catch {
    return 'Configured';
  }
}

function SectionHeader({ icon: Icon, title, badge }: { icon: any; title: string; badge?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <h3 className="flex items-center gap-2 text-base font-semibold">
        <Icon size={15} className="text-slate-400" />
        {title}
      </h3>
      {badge}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 border-b border-slate-700/25 last:border-0">
      <span className="text-[12px] text-slate-500">{label}</span>
      <span className="text-[13px] text-slate-200 font-medium text-right max-w-[60%] break-all">{value}</span>
    </div>
  );
}

function firstDefined<T>(...values: Array<T | undefined | null>): T | undefined {
  return values.find((value) => value !== undefined && value !== null);
}

function formatSeconds(value: unknown, fallback: string) {
  return typeof value === 'number' ? String(value) : fallback;
}

function formatObservation(value: unknown, fallback: string) {
  return typeof value === 'number' ? `${value} ms` : fallback;
}

export default function SystemPage() {
  const { t } = useI18n();
  const { toast } = useToast();

  const [data, setData]         = useState<any>(null);
  const [audit, setAudit]       = useState<any[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [testing, setTesting]   = useState(false);
  const [syncing, setSyncing]   = useState(false);
  const [confirmSync, setConfirmSync] = useState(false);
  const [exporting, setExporting]     = useState<string>('');
  const [memoryItems, setMemoryItems] = useState<ThreatIndicatorMemoryItem[]>([]);
  const [memorySummary, setMemorySummary] = useState<ThreatIntelligenceSummary | null>(null);
  const [memoryType, setMemoryType] = useState('all');
  const [memoryMinSeen, setMemoryMinSeen] = useState(1);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [memoryWarning, setMemoryWarning] = useState('');
  const [memoryCleanupLoading, setMemoryCleanupLoading] = useState(false);
  const [memoryCleanupMessage, setMemoryCleanupMessage] = useState('');

  const loadMemory = async (type = memoryType, minSeen = memoryMinSeen) => {
    setMemoryLoading(true);
    try {
      const params = {
        type: type === 'all' ? undefined : type,
        min_seen_count: minSeen,
        limit: 8,
      };
      const [itemsRes, summaryRes] = await Promise.all([
        getThreatIntelligenceIndicators(params),
        getThreatIntelligenceSummary().catch(() => null),
      ]);
      setMemoryItems(itemsRes.items || []);
      setMemorySummary(summaryRes);
      setMemoryWarning('');
    } catch {
      setMemoryItems([]);
      setMemoryWarning(t('system.memoryEndpointWarning'));
    } finally {
      setMemoryLoading(false);
    }
  };

  const load = async () => {
    setLoading(true);
    try {
      const range = localStorage.getItem('apg_admin_range') || 'today';
      const [sys, auditRes] = await Promise.all([
        api.get('/admin/system/status', { params: { range } }),
        api.get('/admin/audit-log', { params: { limit: 8 } }),
      ]);
      setData(sys.data);
      setAudit(auditRes.data.items || []);
      setError('');
      await loadMemory();
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

  useEffect(() => {
    if (!loading) loadMemory(memoryType, memoryMinSeen);
  }, [memoryType, memoryMinSeen]);

  const test = async () => {
    setTesting(true);
    try {
      await api.post('/admin/system/test-connection');
      toast(t('system.connectionTested'), 'success');
      await load();
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setTesting(false);
    }
  };

  const syncRules = async () => {
    setConfirmSync(false);
    setSyncing(true);
    try {
      await api.post('/admin/system/sync-rules', { note: 'manual sync from web console' });
      toast(t('system.rulesSynced'), 'success');
      await load();
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setSyncing(false);
    }
  };

  const downloadFile = async (path: string, key: string, type: 'csv' | 'pdf') => {
    setExporting(key);
    try {
      const res = await api.get(path, { responseType: 'blob' });
      const mime = type === 'pdf' ? 'application/pdf' : 'text/csv;charset=utf-8';
      const blob = new Blob([res.data], { type: mime });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url;
      a.download = filenameFromDisposition(res.headers['content-disposition']);
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast(type === 'pdf' ? t('common.pdfDownloaded') : t('common.csvDownloaded'), 'success');
      await load();
    } catch {
      toast(t('common.exportFailed'), 'error');
    } finally {
      setExporting('');
    }
  };

  const downloadMemoryExport = async (format: 'json' | 'csv') => {
    setExporting(`memory-${format}`);
    try {
      const res = await api.get('/admin/intelligence/export', {
        responseType: 'blob',
        params: {
          format,
          type: memoryType === 'all' ? undefined : memoryType,
          min_seen_count: memoryMinSeen,
          limit: 1000,
        },
      });
      const mime = format === 'json' ? 'application/json;charset=utf-8' : 'text/csv;charset=utf-8';
      const blob = new Blob([res.data], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filenameFromDisposition(res.headers['content-disposition']);
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast(t('system.memoryExportStarted'), 'success');
    } catch {
      toast(t('common.exportFailed'), 'error');
    } finally {
      setExporting('');
    }
  };

  const runMemoryCleanupDryRun = async () => {
    setMemoryCleanupLoading(true);
    setMemoryCleanupMessage('');
    try {
      const result = await cleanupThreatIntelligenceMemory({ dry_run: true });
      setMemoryCleanupMessage(
        `${t('system.cleanupDryRunResult')}: ${result.matched_count} (${t('system.retentionDays')}: ${result.retention_days})`,
      );
    } catch {
      setMemoryCleanupMessage(t('system.memoryEndpointWarning'));
    } finally {
      setMemoryCleanupLoading(false);
    }
  };

  if (loading) return <LoadingSkeleton rows={6} />;
  if (error)   return <ErrorState message={error} onRetry={load} />;

  const privacy = [
    t('system.rawHidden'),
    t('system.sensitiveMasked'),
    t('system.rawApproval'),
    t('system.sensitiveLogged'),
  ];

  const dynamicSandboxRaw: DynamicUrlAnalysisStatus = data.dynamic_url_analysis || data.dynamic_url_sandbox || {};
  const sandboxEnabled = firstDefined(
    dynamicSandboxRaw.enabled,
  );
  const sandboxStatus =
    sandboxEnabled === undefined
      ? t('system.sandboxStatusNotConfigured')
      : sandboxEnabled
        ? t('common.enabled')
        : t('common.disabled');
  const sandboxBadgeValue =
    sandboxEnabled === undefined ? 'low' : sandboxEnabled ? 'active' : 'resolved';
  const sandboxMode = firstDefined(
    dynamicSandboxRaw.mode === 'shadow' ? t('system.sandboxModeShadow') : undefined,
    dynamicSandboxRaw.mode === 'evidence_ready' ? t('system.sandboxModeEvidenceReady') : undefined,
    dynamicSandboxRaw.mode === 'production_disabled' ? t('system.sandboxModeProductionDisabled') : undefined,
    dynamicSandboxRaw.mode,
    sandboxEnabled ? t('system.sandboxModeEvidenceReady') : t('system.sandboxModeProductionDisabled'),
  );
  const sandboxTimeout = firstDefined(
    dynamicSandboxRaw.timeout_seconds,
  );
  const sandboxObservation = firstDefined<unknown>(
    dynamicSandboxRaw.observation_ms,
    dynamicSandboxRaw.observation_window_ms,
    t('system.sandboxObservationConfigured'),
  );
  const sandboxTimeSimulation = firstDefined(
    dynamicSandboxRaw.time_simulation_enabled === true ? t('common.enabled') : undefined,
    dynamicSandboxRaw.time_simulation_enabled === false ? t('common.disabled') : undefined,
    t('common.disabled'),
  );
  const sandboxDefaultEnabled = firstDefined(dynamicSandboxRaw.default_enabled, false);
  const sandboxScoring = firstDefined(
    dynamicSandboxRaw.scoring_integration === 'conservative_evidence_mapping_available'
      ? t('system.sandboxScoringConservative')
      : undefined,
    dynamicSandboxRaw.scoring_integration,
    t('system.sandboxScoringConservative'),
  );
  const sandboxPlaywright = firstDefined(
    dynamicSandboxRaw.playwright_available === true ? t('common.enabled') : undefined,
    dynamicSandboxRaw.playwright_available === false ? t('common.disabled') : undefined,
    t('system.sandboxStatusNotConfigured'),
  );
  const safetyControls = dynamicSandboxRaw.safety_controls || {};
  const sandboxSafety: Array<[string, boolean | undefined]> = [
    [t('system.sandboxPrivateIpBlocking'), firstDefined(safetyControls.private_ip_blocking, true)],
    [t('system.sandboxLocalhostBlocking'), firstDefined(safetyControls.localhost_blocking, true)],
    [t('system.sandboxDangerousSchemesBlocked'), firstDefined(safetyControls.dangerous_schemes_blocked, true)],
    [t('system.sandboxNoFormSubmission'), firstDefined(safetyControls.no_form_submission, true)],
    [t('system.sandboxNoCredentialEntry'), firstDefined(safetyControls.no_credential_entry, true)],
    [t('system.sandboxNoScreenshotsStored'), firstDefined(safetyControls.screenshots_disabled, true)],
    [t('system.sandboxDisabledByDefault'), sandboxDefaultEnabled === false],
  ];
  return (
    <div className="grid gap-5">
      {/* Row 1 — API + Database */}
      <div className="grid gap-5 xl:grid-cols-2">
        {/* API Connection */}
        <div className="card p-5">
          <SectionHeader icon={Server} title={t('system.apiConnection')} badge={<StatusBadge value={data.server_status} />} />
          <div className="grid gap-0">
            <InfoRow label="API Endpoint" value={maskUrl(data.api_url)} />
            <InfoRow label={t('system.latency')} value={`${data.latency_ms} ms`} />
            <InfoRow label={t('system.lastCheck')} value={fmtDate(data.last_checked)} />
          </div>
          <button
            onClick={test}
            disabled={testing}
            className="enterprise-button mt-4 flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold disabled:opacity-60"
          >
            <RefreshCw size={14} className={testing ? 'animate-spin' : ''} />
            {testing ? t('common.loading') : t('system.testConnection')}
          </button>
        </div>

        {/* Database */}
        <div className="card p-5">
          <SectionHeader icon={Database} title={t('system.database')} badge={<StatusBadge value={data.database_status} />} />
          <div className="grid gap-0">
            <InfoRow label={t('system.currentRangeAnalyses')} value={String(data.database.current_range_analyses)} />
            <InfoRow label={t('system.storedAnalysisSamples')} value={String(data.database.stored_analysis_samples)} />
            <InfoRow label={t('system.totalReports')} value={String(data.database.total_reports)} />
            <InfoRow label={t('system.totalIncidents')} value={String(data.database.total_incidents)} />
            <InfoRow label={t('system.lastSync')} value={fmtDate(data.database.last_sync)} />
          </div>
        </div>
      </div>

      {/* Row 2 — AI/Rules + Feature Status + Privacy */}
      <div className="grid gap-5 xl:grid-cols-3">
        {/* Model & Rules */}
        <div className="card p-5">
          <SectionHeader icon={Zap} title={t('system.modelRules')} />
          <div className="grid gap-0">
            <InfoRow label={t('system.modelVersion')} value={data.model_version} />
            <InfoRow label={t('system.rulesVersion')} value={data.rules_version} />
          </div>
          <button
            onClick={() => setConfirmSync(true)}
            disabled={syncing}
            className="secondary-button mt-4 rounded-xl px-4 py-2 text-sm text-cyan-200 disabled:opacity-50"
          >
            {syncing ? t('common.loading') : t('system.syncRules')}
          </button>
        </div>

        {/* Feature Status */}
        <div className="card p-5">
          <SectionHeader icon={Activity} title={t('system.featureStatus')} />
          <div className="grid gap-2">
            {Object.entries(data.features).map(([k, v]: any) => (
              <div key={k} className="flex items-center justify-between gap-3 rounded-lg border border-slate-700/30 bg-slate-900/20 px-3 py-2">
                <span className="text-[13px] text-slate-300">{k.replaceAll('_', ' ')}</span>
                <StatusBadge value={v ? 'stable' : 'low'} label={v ? t('common.enabled') : t('common.disabled')} />
              </div>
            ))}
          </div>
        </div>

        {/* Privacy */}
        <div className="card p-5">
          <SectionHeader icon={ShieldCheck} title={t('system.privacy')} />
          <ul className="grid gap-2.5">
            {privacy.map((item) => (
              <li key={item} className="flex items-start gap-2 text-[13px] text-slate-300">
                <CheckCircle2 className="mt-0.5 shrink-0 text-emerald-300" size={14} />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="card p-5">
          <SectionHeader
            icon={ShieldCheck}
            title={t('system.dynamicUrlSandbox')}
            badge={<StatusBadge value={sandboxBadgeValue} label={sandboxStatus} />}
          />
          <div className="grid gap-0">
            <InfoRow label={t('system.status')} value={sandboxStatus} />
            <InfoRow label={t('system.mode')} value={String(sandboxMode)} />
            <InfoRow
              label={t('system.timeoutSeconds')}
              value={formatSeconds(sandboxTimeout, t('common.noData'))}
            />
            <InfoRow label={t('system.observationWindow')} value={formatObservation(sandboxObservation, String(sandboxObservation))} />
            <InfoRow label={t('system.timeSimulation')} value={String(sandboxTimeSimulation)} />
            <InfoRow label={t('system.simulatedMinutes')} value={String(firstDefined(dynamicSandboxRaw.simulated_minutes, 0))} />
            <InfoRow label={t('system.playwrightAvailable')} value={String(sandboxPlaywright)} />
            <InfoRow label={t('system.scoringIntegration')} value={String(sandboxScoring)} />
          </div>
          <div className="mt-4 rounded-lg border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-[12px] font-medium text-amber-100">
            {t('system.sandboxSafetyNote')}
          </div>
        </div>

        <div className="card p-5">
          <SectionHeader icon={ShieldCheck} title={t('system.sandboxSafetyControls')} />
          <ul className="grid gap-2.5 sm:grid-cols-2">
            {sandboxSafety.map(([item, enabled]) => (
              <li key={item} className="flex items-start justify-between gap-3 text-[13px] text-slate-300">
                <span className="flex min-w-0 items-start gap-2">
                  <CheckCircle2 className={`mt-0.5 shrink-0 ${enabled ? 'text-emerald-300' : 'text-slate-500'}`} size={14} />
                  {item}
                </span>
                <StatusBadge value={enabled ? 'stable' : 'low'} label={enabled ? t('common.enabled') : t('common.disabled')} />
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* OCR Image Analysis status — compact single card */}
      {data.ocr && (() => {
        const ocr = data.ocr;
        const activeEngine: string = ocr.active_engine || 'none';
        const ocrReady = ocr.enabled && activeEngine !== 'none';
        const badgeValue = ocrReady
          ? (activeEngine === 'paddle_microservice' ? 'stable' : 'medium')
          : ocr.enabled ? 'medium' : 'low';
        const badgeLabel = ocrReady
          ? t('common.enabled')
          : ocr.enabled ? 'مفعّل (لا محرك متاح)' : t('common.disabled');
        const engineConfigLabel =
          ocr.engine_config === 'paddle' || ocr.engine_config === 'paddle_microservice'
            ? 'PaddleOCR Microservice فقط'
            : ocr.engine_config === 'tesseract' ? 'Tesseract فقط'
            : 'تلقائي (PaddleOCR → Tesseract)';
        const activeEngineLabel =
          activeEngine === 'paddle_microservice' ? 'PaddleOCR (Microservice)' :
          activeEngine === 'paddle' ? 'PaddleOCR' :
          activeEngine === 'tesseract' ? 'Tesseract OCR' : 'لا محرك متاح';
        const paddleSvcValue =
          ocr.paddle_microservice_configured
            ? (ocr.paddle_microservice_available ? 'متاح ومتصل' : 'مُعَدّ — غير متصل')
            : 'غير مُعَدّ';
        return (
          <div className="card p-5">
            <SectionHeader
              icon={Activity}
              title="استخراج النص من الصور"
              badge={<StatusBadge value={badgeValue} label={badgeLabel} />}
            />
            <div className="grid gap-0 sm:grid-cols-2">
              <InfoRow label="الحالة" value={ocr.enabled ? 'مفعّل' : 'غير مفعّل'} />
              <InfoRow label="الإعداد" value={engineConfigLabel} />
              <InfoRow label="المحرك النشط" value={activeEngineLabel} />
              <InfoRow label="اللغات" value={ocr.languages || 'ara+eng'} />
              <InfoRow label="الحجم الأقصى" value={`${ocr.max_image_mb || 5} MB`} />
              <InfoRow label="PaddleOCR Microservice" value={paddleSvcValue} />
              <InfoRow
                label="Tesseract"
                value={ocr.tesseract_available ? `متاح — ${ocr.tesseract_version || ''}` : 'غير متاح'}
              />
            </div>
          </div>
        );
      })()}

      <div className="card p-5">
        <SectionHeader icon={ShieldCheck} title={t('system.threatIntelligenceMemory')} />
        <div className="mb-3 grid gap-2 lg:grid-cols-[minmax(0,1fr)_150px_130px_40px] lg:items-center">
          <div className="text-[12px] text-slate-500">
            {t('system.memoryPassiveNote')}
            {memorySummary ? (
              <span className="ms-2 text-slate-400">
                {t('system.totalIndicators')}: {memorySummary.total_indicators} · {t('system.topRepeated')}: {memorySummary.top_repeated}
              </span>
            ) : null}
          </div>
          <select
            value={memoryType}
            onChange={(event) => setMemoryType(event.target.value)}
            className="rounded-lg border border-slate-700/50 bg-slate-950/60 px-3 py-2 text-[12px] text-slate-200 outline-none"
            aria-label={t('system.memoryTypeFilter')}
          >
            {['all', 'domain', 'url_hash', 'path', 'sender', 'entity', 'signal'].map((type) => (
              <option key={type} value={type}>{t(`system.memoryType_${type}`)}</option>
            ))}
          </select>
          <select
            value={memoryMinSeen}
            onChange={(event) => setMemoryMinSeen(Number(event.target.value))}
            className="rounded-lg border border-slate-700/50 bg-slate-950/60 px-3 py-2 text-[12px] text-slate-200 outline-none"
            aria-label={t('system.memoryMinSeenFilter')}
          >
            {[1, 2, 5, 10].map((count) => (
              <option key={count} value={count}>{count}+</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => loadMemory(memoryType, memoryMinSeen)}
            disabled={memoryLoading}
            className="secondary-button inline-flex h-9 w-10 items-center justify-center rounded-lg text-cyan-200 disabled:opacity-50"
            aria-label={t('topbar.refresh')}
          >
            <RefreshCw size={14} className={memoryLoading ? 'animate-spin' : ''} />
          </button>
        </div>
        {memoryWarning ? (
          <div className="mb-3 rounded-lg border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-[12px] font-medium text-amber-100">
            {memoryWarning}
          </div>
        ) : null}
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => downloadMemoryExport('json')}
            disabled={exporting === 'memory-json'}
            className="secondary-button rounded-lg px-3 py-2 text-[12px] text-cyan-200 disabled:opacity-50"
          >
            {t('system.exportMemoryJson')}
          </button>
          <button
            type="button"
            onClick={() => downloadMemoryExport('csv')}
            disabled={exporting === 'memory-csv'}
            className="secondary-button rounded-lg px-3 py-2 text-[12px] text-cyan-200 disabled:opacity-50"
          >
            {t('system.exportMemoryCsv')}
          </button>
          <button
            type="button"
            onClick={runMemoryCleanupDryRun}
            disabled={memoryCleanupLoading}
            className="secondary-button rounded-lg px-3 py-2 text-[12px] text-amber-100 disabled:opacity-50"
          >
            {memoryCleanupLoading ? t('common.loading') : t('system.cleanupDryRun')}
          </button>
          {memoryCleanupMessage ? (
            <span className="text-[12px] text-slate-400">{memoryCleanupMessage}</span>
          ) : null}
        </div>
        {memoryItems.length === 0 ? (
          <EmptyState title={t('system.noMemoryIndicators')} description={t('system.noMemoryIndicatorsDescription')} />
        ) : (
          <div className="grid gap-2">
            {memoryItems.map((item, idx) => (
              <div
                key={`${item.indicator_type}-${item.display_value || idx}`}
                className="grid gap-2 rounded-xl border border-slate-700/35 bg-slate-900/20 px-3.5 py-2.5 md:grid-cols-[110px_minmax(0,1fr)_90px_90px_120px_150px] md:items-center"
              >
                <StatusBadge value="low" label={item.indicator_type.replace(/_/g, ' ')} />
                <span className="min-w-0 truncate text-[13px] font-medium text-slate-200" dir="auto">
                  {item.display_value || t('common.noData')}
                </span>
                <span className="text-[12px] text-slate-400">
                  {t('system.seenCount')}: <strong className="text-slate-200">{item.seen_count}</strong>
                </span>
                <span className="text-[12px] text-slate-400">
                  {t('system.maxRisk')}: <strong className="text-slate-200">{item.max_risk_score ?? '-'}</strong>
                </span>
                <span className="truncate text-[12px] text-slate-400">
                  {item.last_classification || t('common.noData')}
                </span>
                <span className="text-[11px] text-slate-500" dir="ltr">
                  {fmtDate(item.last_seen)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Analyzer Explain UI removed from admin dashboard.
      <div className="card p-5">
        <SectionHeader icon={Activity} title={t('system.analyzerExplain')} />
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="grid gap-3">
            <div className="rounded-lg border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-[12px] font-medium text-amber-100">
              {t('system.analyzerExplainSafety')}
            </div>
            <label className="grid gap-1.5">
              <span className="text-[12px] font-medium text-slate-500">{t('system.messageText')}</span>
              <textarea
                value={explainText}
                onChange={(e) => setExplainText(e.target.value)}
                rows={4}
                className="min-h-28 rounded-xl border border-white/10 bg-slate-950/35 px-3.5 py-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan-400/35"
                placeholder={t('system.messageTextPlaceholder')}
                dir="auto"
              />
            </label>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="grid gap-1.5">
                <span className="text-[12px] font-medium text-slate-500">{t('system.optionalSender')}</span>
                <input
                  value={explainSender}
                  onChange={(e) => setExplainSender(e.target.value)}
                  className="rounded-xl border border-white/10 bg-slate-950/35 px-3.5 py-2.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan-400/35"
                  placeholder="APG"
                  dir="auto"
                />
              </label>
              <label className="grid gap-1.5">
                <span className="text-[12px] font-medium text-slate-500">{t('system.optionalUrl')}</span>
                <input
                  value={explainUrl}
                  onChange={(e) => setExplainUrl(e.target.value)}
                  className="rounded-xl border border-white/10 bg-slate-950/35 px-3.5 py-2.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan-400/35"
                  placeholder="https://example.com"
                  dir="ltr"
                />
              </label>
            </div>
            {explainError && (
              <div className="rounded-xl border border-rose-400/20 bg-rose-400/10 px-3.5 py-2.5 text-sm text-rose-200">
                {explainError}
              </div>
            )}
            <button
              onClick={runExplain}
              disabled={!explainText.trim() || explainLoading}
              className="enterprise-button flex w-fit items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold disabled:opacity-60"
            >
              <Activity size={14} className={explainLoading ? 'animate-pulse' : ''} />
              {explainLoading ? t('common.loading') : t('system.runExplain')}
            </button>
          </div>

          <div className="rounded-xl border border-slate-700/40 bg-slate-900/25 p-4">
            <h4 className="mb-3 text-[13px] font-semibold text-slate-200">{t('system.explainSummary')}</h4>
            {explainResult ? (
              <div className="grid gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  {explainVerdict && <StatusBadge value={String(explainVerdict)} label={String(explainVerdict)} />}
                  {explainScore !== undefined && (
                    <span className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-2.5 py-0.5 text-[11px] font-semibold text-cyan-200">
                      {t('system.riskScore')}: {String(explainScore)}
                    </span>
                  )}
                </div>
                {explainEvidence.length > 0 ? (
                  <div className="grid gap-2">
                    {explainEvidence.map((item: any, idx: number) => (
                      <div key={item.id || item.name || idx} className="rounded-lg border border-slate-700/30 bg-slate-950/25 px-3 py-2">
                        <p className="text-[12px] font-medium text-slate-200">
                          {item.title || item.name || item.id || t('system.evidence')}
                        </p>
                        <p className="mt-0.5 line-clamp-2 text-[12px] text-slate-500">
                          {item.explanation_en || item.explanation_ar || item.description || item.reason || JSON.stringify(item)}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[12px] text-slate-500">{t('system.noEvidenceReturned')}</p>
                )}
                {!explainResult.dynamic_url_analysis && (
                  <p className="rounded-lg border border-slate-700/30 bg-slate-950/25 px-3 py-2 text-[12px] text-slate-500">
                    {t('system.noSandboxDetails')}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-[12px] leading-5 text-slate-500">{t('system.explainEmpty')}</p>
            )}
          </div>
        </div>

        {explainResult?.dynamic_url_analysis ? (
          <div className="mt-4">
            <DynamicSandboxResultCard result={explainResult.dynamic_url_analysis} compact />
          </div>
        ) : null}
      </div>
      */}

      {/* Row 3 — Exports + Version */}
      <div className="grid gap-5 xl:grid-cols-[1fr_280px]">
        {/* Operational Exports */}
        <div className="card p-5">
          <SectionHeader icon={Download} title={t('system.operationalExports')} />
          <p className="mb-4 text-[12px] text-slate-400">{t('system.exportDescription')}</p>
          <div className="grid gap-2.5 sm:grid-cols-2">
            <button
              onClick={() => downloadFile('/admin/export/incidents', 'incidents', 'csv')}
              disabled={!!exporting}
              className="enterprise-button flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold disabled:opacity-60"
            >
              <Download size={14} />
              {exporting === 'incidents' ? t('common.loading') : t('system.exportIncidents')}
            </button>
            <button
              onClick={() => downloadFile('/admin/export/detection-quality', 'quality', 'csv')}
              disabled={!!exporting}
              className="secondary-button flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm disabled:opacity-60"
            >
              <FileDown size={14} />
              {exporting === 'quality' ? t('common.loading') : t('system.exportQuality')}
            </button>
            <button
              onClick={() => downloadFile('/admin/export/threat-signals', 'signals', 'csv')}
              disabled={!!exporting}
              className="secondary-button flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm disabled:opacity-60"
            >
              <FileDown size={14} />
              {exporting === 'signals' ? t('common.loading') : t('system.exportSignals')}
            </button>
            <button
              onClick={() => downloadFile('/admin/export/security-summary', 'summary', 'csv')}
              disabled={!!exporting}
              className="secondary-button flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm disabled:opacity-60"
            >
              <Database size={14} />
              {exporting === 'summary' ? t('common.loading') : t('system.exportSummary')}
            </button>
            <button
              onClick={() => downloadFile('/admin/export/security-report-pdf', 'pdf', 'pdf')}
              disabled={!!exporting}
              className="enterprise-button flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold disabled:opacity-60 sm:col-span-2"
            >
              <FileDown size={14} />
              {exporting === 'pdf' ? t('common.loading') : t('system.exportPdf')}
            </button>
          </div>
        </div>

        {/* Version info */}
        <div className="card p-5">
          <SectionHeader icon={Activity} title={t('system.versionInfo')} />
          <div className="grid gap-0">
            {Object.entries(data.version).map(([k, v]: any) => (
              <InfoRow key={k} label={k} value={String(v)} />
            ))}
          </div>
        </div>
      </div>

      {/* Row 4 — Audit Log */}
      <div className="card p-5">
        <SectionHeader icon={Activity} title={t('system.auditLog')} />
        <div className="grid gap-2">
          {audit.length === 0 ? (
            <EmptyState title={t('states.noActivity')} description="No admin actions have been logged yet." />
          ) : (
            audit.map((a: any) => (
              <div
                key={a.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-700/35 bg-slate-900/20 px-3.5 py-2.5 transition hover:border-slate-600/50"
              >
                <div className="min-w-0">
                  <p className="text-[13px] font-medium text-slate-200">
                    {t(actionKey[a.action_type] || '') || a.action_title || a.action}
                  </p>
                  <p className="text-[12px] text-slate-500">
                    {a.actor_email || a.actor}
                    {(a.target_name || a.target) ? ` · ${a.target_name || a.target}` : ''}
                  </p>
                  {a.note && <p className="mt-0.5 text-[11px] text-slate-600">{a.note}</p>}
                </div>
                <span className="shrink-0 text-[11px] text-slate-600" dir="ltr">
                  {fmtDate(a.created_at)}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmSync}
        variant="positive"
        title={t('system.syncConfirm')}
        description={t('system.syncConfirmBody')}
        confirmLabel={t('system.syncRules')}
        cancelLabel={t('common.cancel')}
        onCancel={() => setConfirmSync(false)}
        onConfirm={syncRules}
      />
    </div>
  );
}
