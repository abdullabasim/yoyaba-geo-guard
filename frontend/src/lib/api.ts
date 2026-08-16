/**
 * Typed API client.
 *
 * Two execution contexts need different base URLs and different credential
 * handling:
 *
 *  - Browser (client components): hits NEXT_PUBLIC_API_URL with
 *    `credentials: 'include'` so the httpOnly cookie rides along.
 *  - Server (server components / route handlers): hits INTERNAL_API_URL,
 *    which resolves inside the Docker network, and must forward the incoming
 *    cookie header manually because server fetches carry no cookie jar.
 */
import type {
  AiAlert,
  AlertStats,
  BulkRow,
  BulkUploadResponse,
  CheckInterval,
  Client,
  Keyword,
  ManualRunResponse,
  MessageResponse,
  Page,
  Project,
  ProjectSchedule,
  RankSeries,
  RankingsHistory,
  SeedResult,
  ServiceControl,
  ServiceControlSummary,
  ServiceKey,
  SystemHealth,
  SystemStatus,
  TargetUrl,
  TaskExecutionLog,
  TaskStats,
  TaskStatus,
  TokenResponse,
  User,
  UserRole,
} from './types';

const API_V1 = '/api/v1';

export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors?: Record<string, string>;

  constructor(status: number, message: string, fieldErrors?: Record<string, string>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

function browserBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8100';
}

function serverBaseUrl(): string {
  return process.env.INTERNAL_API_URL ?? browserBaseUrl();
}

async function parseError(response: Response): Promise<{ message: string; fieldErrors?: Record<string, string> }> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') return { message: body.detail };
    if (Array.isArray(body?.detail)) {
      // FastAPI validation errors arrive as a list of objects.
      const fieldErrors: Record<string, string> = {};
      const msg = body.detail
        .map((item: { loc?: string[]; msg?: string }) => {
          const field = item.loc?.slice(1).join('.') ?? 'field';
          fieldErrors[field] = item.msg ?? 'invalid';
          return `${field}: ${item.msg ?? 'invalid'}`;
        })
        .join('; ');
      return { message: msg, fieldErrors };
    }
    return { message: JSON.stringify(body).slice(0, 300) };
  } catch {
    return { message: response.statusText || `HTTP ${response.status}` };
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Raw cookie header, required for server-side calls. */
  cookieHeader?: string;
  /** Bypass the Next.js fetch cache for live data. */
  noStore?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const isServer = typeof window === 'undefined';
  const baseUrl = isServer ? serverBaseUrl() : browserBaseUrl();

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (options.cookieHeader) {
    headers.Cookie = options.cookieHeader;
  }

  const response = await fetch(`${baseUrl}${API_V1}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    credentials: isServer ? undefined : 'include',
    cache: options.noStore === false ? 'default' : 'no-store',
  });

  if (!response.ok) {
    const errorData = await parseError(response);
    throw new ApiError(response.status, errorData.message, errorData.fieldErrors);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value));
    }
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : '';
}

/* ------------------------------------------------------------------ */
/* Auth                                                                */
/* ------------------------------------------------------------------ */
export const authApi = {
  login: (email: string, password: string) =>
    request<TokenResponse>('/auth/login', { method: 'POST', body: { email, password } }),

  logout: () => request<MessageResponse>('/auth/logout', { method: 'POST' }),

  me: (cookieHeader?: string) => request<User>('/auth/me', { cookieHeader }),

  changePassword: (currentPassword: string, newPassword: string) =>
    request<MessageResponse>('/auth/change-password', {
      method: 'POST',
      body: { current_password: currentPassword, new_password: newPassword },
    }),
};

/* ------------------------------------------------------------------ */
/* Users                                                               */
/* ------------------------------------------------------------------ */
export const usersApi = {
  list: (skip = 0, limit = 50, cookieHeader?: string) =>
    request<Page<User>>(`/users${query({ skip, limit })}`, { cookieHeader }),

  create: (payload: {
    email: string;
    password: string;
    full_name?: string | null;
    role?: UserRole;
  }) => request<User>('/users', { method: 'POST', body: payload }),

  update: (
    id: number,
    payload: {
      email?: string;
      full_name?: string | null;
      password?: string;
      role?: UserRole;
      is_active?: boolean;
    },
  ) => request<User>(`/users/${id}`, { method: 'PATCH', body: payload }),

  toggle: (id: number, isActive: boolean) =>
    request<User>(`/users/${id}/toggle`, { method: 'PATCH', body: { is_active: isActive } }),

  remove: (id: number) => request<MessageResponse>(`/users/${id}`, { method: 'DELETE' }),
};

/* ------------------------------------------------------------------ */
/* Clients                                                             */
/* ------------------------------------------------------------------ */
export const clientsApi = {
  list: (skip = 0, limit = 50, cookieHeader?: string) =>
    request<Page<Client>>(`/clients${query({ skip, limit })}`, { cookieHeader }),

  create: (payload: { name: string; company_name?: string | null }) =>
    request<Client>('/clients', { method: 'POST', body: payload }),

  update: (id: number, payload: { name?: string; company_name?: string | null }) =>
    request<Client>(`/clients/${id}`, { method: 'PATCH', body: payload }),

  toggle: (id: number, isActive: boolean) =>
    request<Client>(`/clients/${id}/toggle`, { method: 'PATCH', body: { is_active: isActive } }),

  remove: (id: number) => request<MessageResponse>(`/clients/${id}`, { method: 'DELETE' }),
};

/* ------------------------------------------------------------------ */
/* Projects                                                            */
/* ------------------------------------------------------------------ */
export const projectsApi = {
  list: (clientId?: number, skip = 0, limit = 50, cookieHeader?: string) =>
    request<Page<Project>>(`/projects${query({ client_id: clientId, skip, limit })}`, {
      cookieHeader,
    }),

  create: (payload: {
    client_id: number;
    name: string;
    description?: string | null;
    default_check_interval?: CheckInterval;
    default_execution_time?: string;
    default_timezone?: string;
    rank_drop_threshold?: number;
    dataforseo_depth?: number;
  }) => request<Project>('/projects', { method: 'POST', body: payload }),

  update: (id: number, payload: { name?: string; description?: string | null; rank_drop_threshold?: number; dataforseo_depth?: number }) =>
    request<Project>(`/projects/${id}`, { method: 'PATCH', body: payload }),

  getSchedule: (id: number, cookieHeader?: string) =>
    request<ProjectSchedule>(`/projects/${id}/schedule`, { cookieHeader }),

  updateSchedule: (
    id: number,
    payload: {
      default_check_interval: CheckInterval;
      default_execution_time: string;
      default_timezone: string;
      rank_drop_threshold?: number;
      dataforseo_depth?: number;
      apply_to_all_urls?: boolean;
    },
  ) => request<ProjectSchedule>(`/projects/${id}/schedule`, { method: 'PUT', body: payload }),

  toggle: (id: number, isActive: boolean) =>
    request<Project>(`/projects/${id}/toggle`, { method: 'PATCH', body: { is_active: isActive } }),

  remove: (id: number) => request<MessageResponse>(`/projects/${id}`, { method: 'DELETE' }),
};

/* ------------------------------------------------------------------ */
/* Target URLs                                                         */
/* ------------------------------------------------------------------ */
export const urlsApi = {
  list: (projectId?: number, skip = 0, limit = 50, cookieHeader?: string) =>
    request<Page<TargetUrl>>(`/urls${query({ project_id: projectId, skip, limit })}`, {
      cookieHeader,
    }),

  create: (payload: {
    project_id: number;
    url: string;
    check_interval?: CheckInterval;
    execution_time?: string;
    timezone?: string;
    rank_drop_threshold?: number | null;
    dataforseo_depth?: number | null;
    inherit_schedule?: boolean;
    initial_keywords?: string[];
  }) => request<TargetUrl>('/urls', { method: 'POST', body: payload }),

  update: (id: number, payload: { url?: string; rank_drop_threshold?: number | null; dataforseo_depth?: number | null }) =>
    request<TargetUrl>(`/urls/${id}`, { method: 'PATCH', body: payload }),

  updateSchedule: (
    id: number,
    payload: {
      check_interval: CheckInterval;
      execution_time: string;
      timezone: string;
      rank_drop_threshold?: number | null;
      dataforseo_depth?: number | null;
      inherit_schedule?: boolean;
    },
  ) => request<TargetUrl>(`/urls/${id}/schedule`, { method: 'PUT', body: payload }),

  setInheritSchedule: (id: number, inherit: boolean) =>
    request<TargetUrl>(`/urls/${id}/inherit-schedule`, {
      method: 'PATCH',
      body: { inherit_schedule: inherit },
    }),

  toggle: (id: number, isActive: boolean) =>
    request<TargetUrl>(`/urls/${id}/toggle`, { method: 'PATCH', body: { is_active: isActive } }),

  remove: (id: number) => request<MessageResponse>(`/urls/${id}`, { method: 'DELETE' }),

  due: (windowMinutes = 30) =>
    request<TargetUrl[]>(`/urls/due${query({ window_minutes: windowMinutes })}`),
};

/* ------------------------------------------------------------------ */
/* Keywords                                                            */
/* ------------------------------------------------------------------ */
export const keywordsApi = {
  list: (targetUrlId?: number, skip = 0, limit = 50, cookieHeader?: string) =>
    request<Page<Keyword>>(`/keywords${query({ target_url_id: targetUrlId, skip, limit })}`, {
      cookieHeader,
    }),

  create: (payload: {
    target_url_id: number;
    keyword_text: string;
    location_code?: number;
    language_code?: string;
  }) => request<Keyword>('/keywords', { method: 'POST', body: payload }),

  update: (id: number, payload: { keyword_text?: string; location_code?: number }) =>
    request<Keyword>(`/keywords/${id}`, { method: 'PATCH', body: payload }),

  toggle: (id: number, isActive: boolean) =>
    request<Keyword>(`/keywords/${id}/toggle`, { method: 'PATCH', body: { is_active: isActive } }),

  remove: (id: number) => request<MessageResponse>(`/keywords/${id}`, { method: 'DELETE' }),
};

/* ------------------------------------------------------------------ */
/* Rankings                                                            */
/* ------------------------------------------------------------------ */
export const rankingsApi = {
  history: (keywordId: number, skip = 0, limit = 100, cookieHeader?: string) =>
    request<RankingsHistory[]>(`/rankings/keyword/${keywordId}${query({ skip, limit })}`, {
      cookieHeader,
    }),

  series: (keywordId: number, days = 90, cookieHeader?: string) =>
    request<RankSeries>(`/rankings/keyword/${keywordId}/series${query({ days })}`, {
      cookieHeader,
    }),

  entry: (historyId: number) => request<RankingsHistory>(`/rankings/${historyId}`),
};

/* ------------------------------------------------------------------ */
/* Tasks                                                               */
/* ------------------------------------------------------------------ */
export const tasksApi = {
  list: (
    params: { status?: TaskStatus; task_name?: string; skip?: number; limit?: number } = {},
    cookieHeader?: string,
  ) =>
    request<Page<TaskExecutionLog>>(
      `/tasks${query({
        status: params.status,
        task_name: params.task_name,
        skip: params.skip ?? 0,
        limit: params.limit ?? 50,
      })}`,
      { cookieHeader },
    ),

  stats: (windowHours = 24, cookieHeader?: string) =>
    request<TaskStats>(`/tasks/stats${query({ window_hours: windowHours })}`, { cookieHeader }),

  run: (payload: { target_url_id: number; keyword_id?: number; force_analysis?: boolean }) =>
    request<ManualRunResponse>('/tasks/run', { method: 'POST', body: payload }),
};

/* ------------------------------------------------------------------ */
/* Alerts                                                              */
/* ------------------------------------------------------------------ */
export const alertsApi = {
  get: (id: number, cookieHeader?: string) =>
    request<AiAlert>(`/alerts/${id}`, { cookieHeader }),

  list: (
    params: {
      issue_type?: string;
      client_id?: number;
      search?: string;
      sort_by?: string;
      sort_order?: 'asc' | 'desc';
      skip?: number;
      limit?: number;
    } = {},
    cookieHeader?: string,
  ) =>
    request<Page<AiAlert>>(
      `/alerts${query({
        issue_type: params.issue_type,
        client_id: params.client_id,
        search: params.search,
        sort_by: params.sort_by,
        sort_order: params.sort_order,
        skip: params.skip ?? 0,
        limit: params.limit ?? 50,
      })}`,
      { cookieHeader },
    ),

  stats: (windowDays = 30, cookieHeader?: string) =>
    request<AlertStats>(`/alerts/stats${query({ window_days: windowDays })}`, { cookieHeader }),

  resend: (id: number) => request<MessageResponse>(`/alerts/${id}/resend`, { method: 'POST' }),
};

/* ------------------------------------------------------------------ */
/* Service controls and system diagnostics                             */
/* ------------------------------------------------------------------ */
export const controlsApi = {
  list: (cookieHeader?: string) =>
    request<ServiceControl[]>('/controls', { cookieHeader }),

  summary: (cookieHeader?: string) =>
    request<ServiceControlSummary>('/controls/summary', { cookieHeader }),

  status: (cookieHeader?: string) =>
    request<SystemStatus>('/controls/status', { cookieHeader }),

  setEnabled: (key: ServiceKey, isEnabled: boolean, reason?: string) =>
    request<ServiceControl>(`/controls/${key}`, {
      method: 'PATCH',
      body: { is_enabled: isEnabled, reason },
    }),
};

export const systemApi = {
  health: (cookieHeader?: string) =>
    request<SystemHealth>('/system/health', { cookieHeader }),

  testAlert: (category: string) =>
    request<{ sent: boolean; category: string; severity: string; note: string }>(
      `/system/alerts/test${query({ category })}`,
      { method: 'POST' },
    ),

  alertCatalog: (cookieHeader?: string) =>
    request<
      Array<{
        category: string;
        severity: string;
        title: string;
        remediation: string;
        systemic: boolean;
      }>
    >('/system/alerts/catalog', { cookieHeader }),

  seedDemoData: (withHistory = true) =>
    request<SeedResult>(`/system/seed-demo-data${query({ with_history: withHistory })}`, {
      method: 'POST',
    }),
};

/* ------------------------------------------------------------------ */
/* Bulk upload                                                         */
/* ------------------------------------------------------------------ */
export const bulkApi = {
  insertRows: (rows: BulkRow[]) =>
    request<BulkUploadResponse>('/bulk/rows', {
      method: 'POST',
      body: { rows, upsert_parents: true },
    }),

  template: () =>
    request<{ columns: string[]; example_rows: Array<Record<string, string>> }>('/bulk/template'),

  /** Raw multipart upload for files too large to parse in the browser. */
  uploadCsv: async (file: File): Promise<BulkUploadResponse> => {
    const form = new FormData();
    form.append('file', file);

    const response = await fetch(`${browserBaseUrl()}${API_V1}/bulk/csv`, {
      method: 'POST',
      body: form,
      credentials: 'include',
    });

    if (!response.ok) {
      const errorData = await parseError(response);
      throw new ApiError(response.status, errorData.message, errorData.fieldErrors);
    }
    return (await response.json()) as BulkUploadResponse;
  },
};
