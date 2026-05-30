export type User = { id: number; name?: string; email: string; role: string };
export type Tone = 'cyan' | 'purple' | 'success' | 'warning' | 'danger' | 'muted';
export type Metric = { label: string; value: number; change?: number; tone?: string; suffix?: string };
export type Incident = {
  id: number;
  title: string;
  severity: 'high' | 'medium' | 'low';
  status: 'active' | 'monitoring' | 'resolved';
  channel: string;
  cases_count: number;
  affected_devices: number;
  indicators: string[];
  description: string;
  recommended_action: string;
  first_seen: string;
  last_seen: string;
};
export type ThreatSignal = {
  id: number;
  name: string;
  category: 'text' | 'link' | 'behavior' | 'sender';
  description: string;
  impact: 'high' | 'medium' | 'low';
  enabled: boolean;
  weight: number;
  false_positive_risk: string;
  created_at: string;
  updated_at: string;
};

export type DynamicUrlAnalysisStatus = {
  enabled?: boolean;
  mode?: 'production_disabled' | 'shadow' | 'evidence_ready' | string;
  timeout_seconds?: number;
  observation_ms?: number;
  observation_window_ms?: number;
  time_simulation_enabled?: boolean;
  simulated_minutes?: number;
  scoring_integration?: string;
  default_enabled?: boolean;
  playwright_available?: boolean;
  safety_controls?: {
    private_ip_blocking?: boolean;
    localhost_blocking?: boolean;
    dangerous_schemes_blocked?: boolean;
    no_form_submission?: boolean;
    no_credential_entry?: boolean;
    screenshots_disabled?: boolean;
  };
};

export type DynamicSandboxExplainResult = {
  enabled?: boolean;
  status?: string;
  final_url?: string | null;
  redirect_chain?: string[];
  page_title?: string | null;
  has_login_form?: boolean;
  has_password_field?: boolean;
  has_otp_field?: boolean;
  form_count?: number;
  external_request_count?: number;
  suspicious_request_count?: number;
  delayed_url_change?: boolean;
  delayed_title_change?: boolean;
  delayed_form_change?: boolean;
  delayed_sensitive_field_appeared?: boolean;
  time_simulation_enabled?: boolean;
  simulated_minutes?: number;
  elapsed_ms?: number;
  error?: string | null;
};

export type AdminExplainPayload = {
  text: string;
  sender?: string;
  urls?: string[];
};

export type AdminExplainResponse = {
  engine?: string;
  message_category?: string | null;
  evidence?: Array<Record<string, any>>;
  dynamic_url_analysis?: DynamicSandboxExplainResult;
  final_internal_result?: {
    verdict?: string;
    risk_score?: number;
    final_score?: number;
    [key: string]: any;
  };
  backward_compatible_result?: {
    classification?: string;
    risk_score?: number;
    final_score?: number;
    matched_signals?: any[];
    reasons?: string[];
    recommendation?: string;
    [key: string]: any;
  };
};

export type ThreatIndicatorMemoryItem = {
  indicator_type: string;
  display_value?: string | null;
  seen_count: number;
  first_seen: string;
  last_seen: string;
  max_risk_score?: number | null;
  last_classification?: string | null;
  last_source?: string | null;
  tags?: string[];
  metadata?: Record<string, any>;
};

export type ThreatIntelligenceSummary = {
  total_indicators: number;
  top_types: Array<{ type: string; count: number }>;
  top_repeated: number;
  latest_seen?: string | null;
};

export type ThreatIntelligenceCleanupResult = {
  dry_run: boolean;
  retention_days: number;
  cutoff_date: string;
  matched_count: number;
  deleted_count: number;
};
