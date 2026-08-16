import clsx from 'clsx';

import type { TaskStatus } from '@/lib/types';

/** Task status badge. Pending=yellow, Success=green, Failed=red. */
export function StatusBadge({ status }: { status: TaskStatus }) {
  const styles: Record<TaskStatus, string> = {
    PENDING: 'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400 ring-amber-200 dark:ring-amber-700/50',
    SUCCESS: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-400 ring-emerald-200 dark:ring-emerald-700/50',
    FAILED: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400 ring-red-200 dark:ring-red-700/50',
    SKIPPED: 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 ring-slate-200 dark:ring-slate-700',
  };

  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        styles[status],
      )}
    >
      {status}
    </span>
  );
}

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: React.ReactNode;
  tone?: 'neutral' | 'brand' | 'success' | 'warning' | 'danger';
}) {
  const styles = {
    neutral: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 ring-slate-200 dark:ring-slate-700',
    brand: 'bg-brand-50 dark:bg-yoyaba-yellow/10 text-brand-700 dark:text-yoyaba-yellow ring-brand-200 dark:ring-yoyaba-yellow/30',
    success: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-400 ring-emerald-200 dark:ring-emerald-700/50',
    warning: 'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400 ring-amber-200 dark:ring-amber-700/50',
    danger: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400 ring-red-200 dark:ring-red-700/50',
  }[tone];

  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        styles,
      )}
    >
      {children}
    </span>
  );
}

export function ActiveBadge({ isActive }: { isActive: boolean }) {
  return (
    <Badge tone={isActive ? 'success' : 'neutral'}>{isActive ? 'Active' : 'Paused'}</Badge>
  );
}

/** Rank movement indicator. A positive number means the rank got worse. */
export function DeltaBadge({
  direction,
  label,
}: {
  direction: 'up' | 'down' | 'flat' | 'unknown';
  label: string;
}) {
  const styles = {
    up: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-400 ring-emerald-200 dark:ring-emerald-700/50',
    down: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400 ring-red-200 dark:ring-red-700/50',
    flat: 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 ring-slate-200 dark:ring-slate-700',
    unknown: 'bg-slate-50 dark:bg-slate-800/50 text-slate-400 dark:text-slate-500 ring-slate-200 dark:ring-slate-700/50',
  }[direction];

  return (
    <span
      className={clsx(
        'inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium tabular-nums ring-1 ring-inset',
        styles,
      )}
    >
      {label}
    </span>
  );
}
