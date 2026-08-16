/** Shared formatting helpers used across tables and charts. */
import { format, formatDistanceToNow, parseISO } from 'date-fns';

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '-';
  try {
    return format(parseISO(value), 'yyyy-MM-dd HH:mm');
  } catch {
    return value;
  }
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '-';
  try {
    return format(parseISO(value), 'MMM d');
  } catch {
    return value;
  }
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return 'never';
  try {
    return `${formatDistanceToNow(parseISO(value))} ago`;
  } catch {
    return value;
  }
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '-';
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}

/** A rank of null means "not found in results", never zero. */
export function formatRank(rank: number | null | undefined): string {
  return rank === null || rank === undefined ? 'not ranking' : `#${rank}`;
}

export function formatConfidence(value: number | null | undefined): string {
  return value === null || value === undefined ? '-' : `${Math.round(value * 100)}%`;
}

export function formatIssueType(value: string): string {
  return value
    .split('_')
    .map((part) => part.charAt(0) + part.slice(1).toLowerCase())
    .join(' ');
}

export interface RankDelta {
  label: string;
  direction: 'up' | 'down' | 'flat' | 'unknown';
}

export function rankDelta(
  previous: number | null | undefined,
  current: number | null | undefined,
): RankDelta {
  if (previous === null || previous === undefined || current === null || current === undefined) {
    return { label: '-', direction: 'unknown' };
  }
  const delta = current - previous;
  if (delta === 0) return { label: 'no change', direction: 'flat' };
  return {
    label: delta > 0 ? `-${delta}` : `+${Math.abs(delta)}`,
    direction: delta > 0 ? 'down' : 'up',
  };
}

export function truncate(value: string | null | undefined, max = 120): string {
  if (!value) return '';
  return value.length <= max ? value : `${value.slice(0, max)}...`;
}
