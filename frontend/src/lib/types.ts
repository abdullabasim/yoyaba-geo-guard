/**
 * Types mirroring the backend Pydantic schemas.
 *
 * Kept hand-written rather than generated so the frontend has no build-time
 * dependency on a running backend.
 */

export type CheckInterval = 'daily' | 'weekly' | 'monthly';

export type TaskStatus = 'PENDING' | 'SUCCESS' | 'FAILED' | 'SKIPPED';

export type IssueType =
  | 'INTENT_SHIFT'
  | 'SERP_FEATURE_CHANGE'
  | 'NEW_COMPETITOR'
  | 'CONTENT_FRESHNESS'
  | 'ALGORITHM_UPDATE'
  | 'NO_SIGNIFICANT_CHANGE'
  | 'UNKNOWN';

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface MessageResponse {
  detail: string;
}

export type UserRole = 'read_write' | 'read_only';

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  role: UserRole;
  is_main_account?: boolean;
  created_at?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Client {
  id: number;
  name: string;
  company_name: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  project_count: number;
  active_project_count: number;
}

export interface Project {
  id: number;
  client_id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  default_check_interval: CheckInterval;
  default_execution_time: string;
  default_timezone: string;
  rank_drop_threshold: number;
  dataforseo_depth: number;
  created_at: string;
  updated_at: string;
  client_name: string | null;
  url_count: number;
  active_url_count: number;
  inheriting_url_count: number;
}

export interface ProjectSchedule {
  project_id: number;
  default_check_interval: CheckInterval;
  default_execution_time: string;
  default_timezone: string;
  rank_drop_threshold: number;
  dataforseo_depth: number;
  inheriting_url_count: number;
  overriding_url_count: number;
}

export interface TargetUrl {
  id: number;
  project_id: number;
  url: string;
  check_interval: CheckInterval;
  execution_time: string;
  timezone: string;
  rank_drop_threshold: number | null;
  dataforseo_depth: number | null;
  inherit_schedule: boolean;
  last_checked_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  project_name: string | null;
  client_name: string | null;
  keyword_count: number;
  active_keyword_count: number;
  /** What the scheduler will actually obey, after inheritance is resolved. */
  effective_check_interval: CheckInterval | null;
  effective_execution_time: string | null;
  effective_timezone: string | null;
  effective_rank_drop_threshold: number | null;
  effective_dataforseo_depth: number | null;
}

export type ServiceKey =
  | 'SCHEDULER'
  | 'SERP_FETCH'
  | 'AI_ANALYSIS'
  | 'SLACK_ALERTS'
  | 'ERROR_ALERTS'
  | 'HEALTH_MONITOR';

export interface ServiceControl {
  id: number;
  service_key: ServiceKey;
  is_enabled: boolean;
  paused_reason: string | null;
  paused_by: string | null;
  paused_at: string | null;
  updated_at: string;
  display_name: string;
  summary: string;
  impact: string;
}

export interface ServiceControlSummary {
  total: number;
  enabled: number;
  paused: number;
  scheduler_paused: boolean;
  paused_keys: ServiceKey[];
}

export interface ContainerStatus {
  name: string;
  role: string;
  status: string;
  detail: string;
  controllable: boolean;
}

export interface SystemStatus {
  controls: ServiceControl[];
  summary: ServiceControlSummary;
  containers: ContainerStatus[];
}

export interface SystemHealth {
  healthy: boolean;
  database: string;
  redis: string;
  serp_credentials: string;
  llm_credentials: string;
  slack_webhook: string;
}

export interface SeedResult {
  seeded: boolean;
  detail: string;
  counts: Record<string, number>;
}

export interface Keyword {
  id: number;
  target_url_id: number;
  keyword_text: string;
  location_code: number;
  language_code: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  url: string | null;
  current_rank: number | null;
  previous_rank: number | null;
  last_check_date: string | null;
}

export interface SerpResultItem {
  position: number;
  title: string | null;
  url: string | null;
  domain: string | null;
  description: string | null;
}

export interface RankPoint {
  check_date: string;
  rank: number | null;
  history_id: number;
}

export interface RankSeries {
  keyword_id: number;
  keyword_text: string;
  url: string;
  location_code: number;
  language_code: string;
  points: RankPoint[];
  best_rank: number | null;
  worst_rank: number | null;
  latest_rank: number | null;
}

export interface RankingsHistory {
  id: number;
  keyword_id: number;
  current_rank: number | null;
  previous_rank: number | null;
  top_10_serp_snapshot: SerpResultItem[];
  total_results_checked: number | null;
  serp_url: string | null;
  check_date: string;
}

export interface TaskExecutionLog {
  id: number;
  task_name: string;
  target_url: string | null;
  keyword_text: string | null;
  status: TaskStatus;
  error_message: string | null;
  celery_task_id: string | null;
  payload: Record<string, unknown> | null;
  duration_ms: number | null;
  started_at: string;
  completed_at: string | null;
}

export interface TaskStats {
  pending: number;
  success: number;
  failed: number;
  skipped: number;
  total: number;
  window_hours: number;
}

export interface AiAlert {
  id: number;
  history_id: number;
  issue_type: IssueType;
  ai_diagnosis: string;
  actionable_advice: string;
  confidence: number | null;
  competitor_signals: Array<Record<string, unknown>> | null;
  model_used: string | null;
  slack_sent: boolean;
  created_at: string;
  keyword_text: string | null;
  url: string | null;
  project_name: string | null;
  client_name: string | null;
  current_rank: number | null;
  previous_rank: number | null;
  check_date: string | null;
}

export interface AlertStats {
  total: number;
  by_issue_type: Record<string, number>;
  unsent: number;
  window_days: number;
}

export interface BulkRow {
  client_name: string;
  project_name: string;
  url: string;
  keyword: string;
  location_code?: number;
  language_code?: string;
  check_interval?: CheckInterval;
  execution_time?: string;
  timezone?: string;
}

export interface BulkUploadResponse {
  clients_created: number;
  projects_created: number;
  urls_created: number;
  keywords_created: number;
  rows_processed: number;
  rows_skipped: number;
  errors: string[];
}

export interface ManualRunResponse {
  dispatched: number;
  celery_task_ids: string[];
}
