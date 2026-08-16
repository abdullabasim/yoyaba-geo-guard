/**
 * CSV parsing for the bulk upload component.
 *
 * Parsing happens in the browser so every row is validated and previewed
 * before anything is posted, and the user sees per-row errors immediately
 * instead of a single opaque server rejection.
 */
import Papa from 'papaparse';

import type { BulkRow, CheckInterval } from './types';

export const REQUIRED_COLUMNS = ['client_name', 'project_name', 'url', 'keyword'] as const;

export const OPTIONAL_COLUMNS = [
  'location_code',
  'language_code',
  'check_interval',
  'execution_time',
  'timezone',
] as const;

export const ALL_COLUMNS = [...REQUIRED_COLUMNS, ...OPTIONAL_COLUMNS];

const VALID_INTERVALS: CheckInterval[] = ['daily', 'weekly', 'monthly'];

export interface ParsedCsv {
  rows: BulkRow[];
  errors: string[];
  totalLines: number;
}

function normalizeTime(value: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  // Accept HH:MM and HH:MM:SS; the API expects a time string.
  if (/^\d{1,2}:\d{2}(:\d{2})?$/.test(trimmed)) {
    const [hours, minutes, seconds = '00'] = trimmed.split(':');
    return `${hours.padStart(2, '0')}:${minutes}:${seconds}`;
  }
  return undefined;
}

export function parseCsv(text: string): ParsedCsv {
  const result = Papa.parse<Record<string, string>>(text, {
    header: true,
    skipEmptyLines: 'greedy',
    transformHeader: (header) => header.trim().toLowerCase(),
  });

  const errors: string[] = result.errors
    .slice(0, 20)
    .map((error) => `line ${(error.row ?? 0) + 2}: ${error.message}`);

  const headers = result.meta.fields ?? [];
  const missing = REQUIRED_COLUMNS.filter((column) => !headers.includes(column));
  if (missing.length > 0) {
    return {
      rows: [],
      errors: [`Missing required column(s): ${missing.join(', ')}`],
      totalLines: result.data.length,
    };
  }

  const rows: BulkRow[] = [];

  result.data.forEach((raw, index) => {
    const lineNumber = index + 2;
    const clientName = (raw.client_name ?? '').trim();
    const projectName = (raw.project_name ?? '').trim();
    const url = (raw.url ?? '').trim();
    const keyword = (raw.keyword ?? '').trim();

    if (!clientName || !projectName || !url || !keyword) {
      errors.push(`line ${lineNumber}: missing a required value, row skipped`);
      return;
    }

    if (!/^https?:\/\//i.test(url)) {
      errors.push(`line ${lineNumber}: url must start with http:// or https://`);
      return;
    }

    const row: BulkRow = {
      client_name: clientName,
      project_name: projectName,
      url,
      keyword: keyword.replace(/\s+/g, ' ').toLowerCase(),
    };

    const locationCode = Number.parseInt((raw.location_code ?? '').trim(), 10);
    if (Number.isFinite(locationCode) && locationCode > 0) {
      row.location_code = locationCode;
    }

    const languageCode = (raw.language_code ?? '').trim().toLowerCase();
    if (languageCode) {
      row.language_code = languageCode;
    }

    const interval = (raw.check_interval ?? '').trim().toLowerCase() as CheckInterval;
    if (interval) {
      if (VALID_INTERVALS.includes(interval)) {
        row.check_interval = interval;
      } else {
        errors.push(
          `line ${lineNumber}: unknown check_interval "${interval}", using the default`,
        );
      }
    }

    const executionTime = normalizeTime(raw.execution_time ?? '');
    if (executionTime) {
      row.execution_time = executionTime;
    } else if ((raw.execution_time ?? '').trim()) {
      errors.push(`line ${lineNumber}: unreadable execution_time, using the default`);
    }

    const timezone = (raw.timezone ?? '').trim();
    if (timezone) {
      row.timezone = timezone;
    }

    rows.push(row);
  });

  return { rows, errors, totalLines: result.data.length };
}

export function buildTemplateCsv(): string {
  const header = ALL_COLUMNS.join(',');
  const example = [
    'Acme Inc,Acme Website,https://acme.example.com/pricing,project management pricing,2840,en,daily,03:00,UTC',
    'Acme Inc,Acme Website,https://acme.example.com/features,best project tool,2840,en,weekly,04:30,Europe/Berlin',
  ];
  return [header, ...example].join('\n');
}
