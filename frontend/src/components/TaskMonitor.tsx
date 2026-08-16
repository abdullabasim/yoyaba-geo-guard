'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { StatusBadge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader, StatCard } from '@/components/ui/Card';
import { Alert, Button, Input, Select, Spinner } from '@/components/ui/Form';
import { Pagination } from '@/components/ui/Pagination';
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table';
import { tasksApi } from '@/lib/api';
import { formatDateTime, formatDuration, truncate } from '@/lib/format';
import type { Page, TaskExecutionLog, TaskStats, TaskStatus } from '@/lib/types';

/**
 * Live task monitor. Polls on an interval; the poll is paused while the browser
 * tab is hidden so a forgotten dashboard tab does not hammer the API overnight.
 */

const REFRESH_OPTIONS = [
  { value: 0, label: 'Off' },
  { value: 5, label: '5 s' },
  { value: 15, label: '15 s' },
  { value: 60, label: '60 s' },
];

const ERROR_PREVIEW_CHARS = 140;

export function TaskMonitor({
  initialPage,
  initialStats,
}: {
  initialPage: Page<TaskExecutionLog>;
  initialStats: TaskStats;
}) {
  const [logs, setLogs] = useState<TaskExecutionLog[]>(initialPage.items);
  const [total, setTotal] = useState(initialPage.total);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPage.limit || 10);
  const [stats, setStats] = useState(initialStats);
  const [statusFilter, setStatusFilter] = useState<TaskStatus | ''>('');
  const [sortBy, setSortBy] = useState<string>('started_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [search, setSearch] = useState('');
  const [refreshSeconds, setRefreshSeconds] = useState(15);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const inFlight = useRef(false);

  const load = useCallback(
    async (targetPage = page, targetSize = pageSize, currentFilter = statusFilter) => {
      if (inFlight.current) return;
      inFlight.current = true;
      setLoading(true);
      try {
        const skip = (targetPage - 1) * targetSize;
        const [res, freshStats] = await Promise.all([
          tasksApi.list({
            status: currentFilter || undefined,
            skip,
            limit: targetSize,
          }),
          tasksApi.stats(24),
        ]);
        setLogs(res.items);
        setTotal(res.total);
        setPage(targetPage);
        setPageSize(targetSize);
        setStats(freshStats);
        setError(null);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : 'Failed to load task logs');
      } finally {
        setLoading(false);
        inFlight.current = false;
      }
    },
    [page, pageSize, statusFilter],
  );

  useEffect(() => {
    if (refreshSeconds === 0) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void load(page, pageSize, statusFilter);
      }
    }, refreshSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [refreshSeconds, load, page, pageSize, statusFilter]);

  const handleFilterChange = (newFilter: TaskStatus | '') => {
    setStatusFilter(newFilter);
    void load(1, pageSize, newFilter);
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Pending" value={stats.pending} tone="warning" hint="last 24 h" />
        <StatCard label="Success" value={stats.success} tone="success" hint="last 24 h" />
        <StatCard label="Failed" value={stats.failed} tone="danger" hint="last 24 h" />
        <StatCard label="Skipped" value={stats.skipped} hint="no action needed" />
      </div>

      <Card>
        <CardHeader
          title="Background task log"
          description="Every Celery execution, newest first"
          action={
            <div className="flex items-center gap-2">
              {loading ? <Spinner className="text-slate-400" /> : null}
              <Select
                value={statusFilter}
                onChange={(event) => handleFilterChange(event.target.value as TaskStatus | '')}
                className="w-36"
                aria-label="Filter by status"
              >
                <option value="">All statuses</option>
                <option value="PENDING">Pending</option>
                <option value="SUCCESS">Success</option>
                <option value="FAILED">Failed</option>
                <option value="SKIPPED">Skipped</option>
              </Select>

              <Select
                value={refreshSeconds}
                onChange={(event) => setRefreshSeconds(Number(event.target.value))}
                className="w-24"
                aria-label="Poll interval"
              >
                {REFRESH_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </Select>
            </div>
          }
        />
        <div className="border-b border-slate-200 dark:border-yoyaba-border bg-slate-50/80 dark:bg-slate-800/40 p-4">
          <div className="relative max-w-md">
            <Input
              type="text"
              placeholder="Search task logs by task name, URL, or error..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pr-8 text-xs"
            />
            {search ? (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs font-bold"
                aria-label="Clear search"
              >
                ✕
              </button>
            ) : null}
          </div>
        </div>
        <CardBody className="px-0 py-0">
          {error ? (
            <div className="px-5 py-4">
              <Alert tone="error">{error}</Alert>
            </div>
          ) : null}

          <Table className={loading ? 'opacity-50 pointer-events-none' : ''}>
            <THead>
              <TR>
                <TH sortable sortActive={sortBy === 'started_at'} sortOrder={sortOrder as any} onSort={() => setSortOrder(s => s === 'asc' ? 'desc' : 'asc')}>Started</TH>
                <TH sortable sortActive={sortBy === 'task_name'} sortOrder={sortOrder as any} onSort={() => setSortBy('task_name')}>Task</TH>
                <TH>Target URL / Keyword</TH>
                <TH align="right">Duration</TH>
                <TH sortable sortActive={sortBy === 'status'} sortOrder={sortOrder as any} onSort={() => setSortBy('status')}>Status</TH>
                <TH />
              </TR>
            </THead>
            <TBody>
              {logs
                .filter((item) => {
                  if (!search.trim()) return true;
                  const q = search.toLowerCase();
                  return (
                    item.task_name.toLowerCase().includes(q) ||
                    (item.error_message ?? '').toLowerCase().includes(q)
                  );
                })
                .length === 0 ? (
                <EmptyRow colSpan={6} message="No task logs match your search." />
              ) : (
                logs
                  .filter((item) => {
                    if (!search.trim()) return true;
                    const q = search.toLowerCase();
                    return (
                      item.task_name.toLowerCase().includes(q) ||
                      (item.error_message ?? '').toLowerCase().includes(q)
                    );
                  })
                  .map((log) => {
                  const isExpanded = expandedId === log.id;
                  const hasError = Boolean(log.error_message);
                  return (
                    <TR
                      key={log.id}
                      className={hasError ? 'cursor-pointer hover:bg-rose-50/50 dark:hover:bg-rose-900/30' : undefined}
                      onClick={hasError ? () => setExpandedId(isExpanded ? null : log.id) : undefined}
                    >
                      <TD className="whitespace-nowrap text-xs text-slate-500">
                        {formatDateTime(log.started_at)}
                      </TD>
                      <TD className="font-mono text-xs text-slate-800 dark:text-slate-200">{log.task_name}</TD>
                      <TD className="max-w-xs text-xs">
                        {log.target_url ? (
                          <a
                            href={log.target_url}
                            target="_blank"
                            rel="noreferrer"
                            className="block truncate font-medium text-brand-700 hover:underline"
                            title={log.target_url}
                          >
                            {log.target_url}
                          </a>
                        ) : null}
                        {log.keyword_text ? (
                          <div className="font-semibold text-slate-900 dark:text-slate-100">&quot;{log.keyword_text}&quot;</div>
                        ) : null}
                        {!log.target_url && !log.keyword_text ? (
                          <span className="inline-flex items-center gap-1 font-mono text-[11px] bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-600">
                            {log.task_name.includes('dispatch') ? '⚙️ System Scheduler (All URLs)' :
                             log.task_name.includes('health') ? '🩺 System Health Check' :
                             log.task_name.includes('resend') ? '📩 Slack Alert Resend' :
                             'System Task'}
                          </span>
                        ) : null}
                      </TD>
                      <TD align="right" className="whitespace-nowrap text-xs font-mono text-slate-600 dark:text-slate-400">
                        {formatDuration(log.duration_ms)}
                      </TD>
                      <TD>
                        <StatusBadge status={log.status} />
                      </TD>
                      <TD align="right">
                        {hasError ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(event) => {
                              event.stopPropagation();
                              setExpandedId(isExpanded ? null : log.id);
                            }}
                          >
                            {isExpanded ? 'Hide' : 'Error'}
                          </Button>
                        ) : null}
                      </TD>
                    </TR>
                  );
                })
              )}
            </TBody>
          </Table>

          {expandedId !== null ? (
            <div className="border-t border-slate-200 bg-slate-900 p-4 font-mono text-xs text-slate-200">
              <div className="flex items-center justify-between pb-2">
                <span className="font-semibold text-rose-400">Traceback for log #{expandedId}</span>
                <button
                  type="button"
                  onClick={() => setExpandedId(null)}
                  className="text-slate-400 hover:text-white"
                >
                  Close
                </button>
              </div>
              <pre className="whitespace-pre-wrap overflow-x-auto text-xs text-rose-200">
                {logs.find((l) => l.id === expandedId)?.error_message ?? 'No error recorded'}
              </pre>
            </div>
          ) : null}

          <Pagination
            page={page}
            pageSize={pageSize}
            total={total}
            onPageChange={(newPage) => void load(newPage, pageSize, statusFilter)}
            onPageSizeChange={(newSize) => void load(1, newSize, statusFilter)}
          />
        </CardBody>
      </Card>
    </div>
  );
}
