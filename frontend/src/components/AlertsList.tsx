'use client';

import clsx from 'clsx';
import Link from 'next/link';
import { useState } from 'react';

import { Badge, DeltaBadge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Alert, Button, Input, Select } from '@/components/ui/Form';
import { Pagination } from '@/components/ui/Pagination';
import { Table, TH, THead, TR } from '@/components/ui/Table';
import { alertsApi } from '@/lib/api';
import {
  formatConfidence,
  formatDateTime,
  formatIssueType,
  formatRank,
  rankDelta,
} from '@/lib/format';
import type { AiAlert, IssueType, Page, User } from '@/lib/types';

const ISSUE_TYPES: IssueType[] = [
  'INTENT_SHIFT',
  'NEW_COMPETITOR',
  'SERP_FEATURE_CHANGE',
  'CONTENT_FRESHNESS',
  'ALGORITHM_UPDATE',
  'NO_SIGNIFICANT_CHANGE',
  'UNKNOWN',
];

function issueTone(issueType: IssueType) {
  if (issueType === 'INTENT_SHIFT') return 'danger' as const;
  if (issueType === 'NEW_COMPETITOR') return 'warning' as const;
  if (issueType === 'NO_SIGNIFICANT_CHANGE') return 'neutral' as const;
  return 'brand' as const;
}

function renderParts(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, pIdx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={pIdx} className="font-bold text-slate-900">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={pIdx}
          className="font-mono text-[11px] bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded font-semibold text-slate-900"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

function FormattedParagraphs({ text, className }: { text: string; className?: string }) {
  if (!text) return null;
  const lines = text.split('\n').filter((l) => l.trim().length > 0);
  return (
    <div className={`space-y-1.5 text-xs ${className || 'text-slate-700'}`}>
      {lines.map((line, idx) => (
        <p key={idx} className="leading-relaxed">
          {renderParts(line.trim())}
        </p>
      ))}
    </div>
  );
}

function FormattedList({ text, className }: { text: string; className?: string }) {
  if (!text) return null;
  const lines = text.split('\n').filter((l) => l.trim().length > 0);
  return (
    <div className={`space-y-2 text-xs ${className || 'text-slate-700'}`}>
      {lines.map((line, idx) => {
        // Strip out leading numbers if the LLM happened to output them anyway
        const content = line.replace(/^(\(\d+\)|\d+[\.\)])\s*/, '').trim();
        return (
          <div
            key={idx}
            className="flex items-start gap-2.5 p-2.5 rounded-md bg-white border border-slate-200/80 shadow-2xs mt-1.5"
          >
            <span className="shrink-0 font-bold text-[11px] bg-brand-700 text-white px-2 py-0.5 rounded-full font-mono shadow-2xs">
              {idx + 1}
            </span>
            <div className="leading-relaxed min-w-0 flex-1 text-slate-800">
              {renderParts(content)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function AlertsList({
  initialPage,
  currentUser,
  initialSearch = '',
}: {
  initialPage: Page<AiAlert>;
  currentUser?: User;
  initialSearch?: string;
}) {
  const [alerts, setAlerts] = useState<AiAlert[]>(initialPage.items);
  const [total, setTotal] = useState(initialPage.total);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPage.limit || 10);
  const [filter, setFilter] = useState<IssueType | ''>('');
  const [search, setSearch] = useState(initialSearch);
  const [sortBy, setSortBy] = useState<'created_at' | 'keyword' | 'url' | 'confidence' | 'issue_type'>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const isReadOnly = currentUser?.role === 'read_only' || (!currentUser?.is_superuser && currentUser?.role !== 'read_write');

  async function fetchPage(
    targetPage: number,
    targetSize: number,
    currentFilter: IssueType | '',
    currentSearch: string = search,
    currentSortBy: string = sortBy,
    currentSortOrder: 'asc' | 'desc' = sortOrder,
  ) {
    setLoading(true);
    setError(null);
    try {
      const skip = (targetPage - 1) * targetSize;
      const res = await alertsApi.list({
        issue_type: currentFilter || undefined,
        search: currentSearch.trim() || undefined,
        sort_by: currentSortBy,
        sort_order: currentSortOrder,
        skip,
        limit: targetSize,
      });
      setAlerts(res.items);
      setTotal(res.total);
      setPage(targetPage);
      setPageSize(targetSize);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to load alerts');
    } finally {
      setLoading(false);
    }
  }

  async function applyFilter(next: IssueType | '') {
    setFilter(next);
    await fetchPage(1, pageSize, next, search, sortBy, sortOrder);
  }

  async function handleSort(field: 'created_at' | 'keyword' | 'url' | 'confidence' | 'issue_type') {
    let nextOrder: 'asc' | 'desc' = 'desc';
    if (sortBy === field) {
      nextOrder = sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
      nextOrder = field === 'created_at' || field === 'confidence' ? 'desc' : 'asc';
    }
    setSortBy(field);
    setSortOrder(nextOrder);
    await fetchPage(1, pageSize, filter, search, field, nextOrder);
  }

  async function handleSearchSubmit(event?: React.FormEvent) {
    if (event) event.preventDefault();
    await fetchPage(1, pageSize, filter, search, sortBy, sortOrder);
  }

  async function handleClearSearch() {
    setSearch('');
    await fetchPage(1, pageSize, filter, '', sortBy, sortOrder);
  }

  async function handleResend(alert: AiAlert) {
    if (isReadOnly) return;
    setError(null);
    setNotice(null);
    try {
      await alertsApi.resend(alert.id);
      setNotice('Slack re-delivery queued.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to queue re-delivery');
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="AI Diagnoses"
          description="Generated when a tracked page drops by the configured threshold"
        />

        {/* Backend Search & Filter Header Bar */}
        <div className="tour-alerts-filters border-b border-slate-200 dark:border-yoyaba-border bg-slate-50/80 dark:bg-slate-800/40 p-4">
          <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
            <form onSubmit={handleSearchSubmit} className="relative flex-1 w-full sm:max-w-md flex gap-2">
              <div className="relative flex-1">
                <Input
                  type="text"
                  placeholder="Search across all pages (keyword, URL, client, diagnosis)..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pr-8 text-xs"
                />
                {search ? (
                  <button
                    type="button"
                    onClick={() => void handleClearSearch()}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs font-bold"
                    aria-label="Clear search"
                  >
                    ✕
                  </button>
                ) : null}
              </div>
              <Button type="submit" variant="secondary" size="sm">
                Search
              </Button>
            </form>

            <div className="flex items-center gap-2 w-full sm:w-auto shrink-0">
              <Select
                value={filter}
                onChange={(event) => void applyFilter(event.target.value as IssueType | '')}
                className="w-full sm:w-48 text-xs"
                aria-label="Filter by issue type"
              >
                <option value="">All issue types</option>
                {ISSUE_TYPES.map((issueType) => (
                  <option key={issueType} value={issueType}>
                    {formatIssueType(issueType)}
                  </option>
                ))}
              </Select>
              
              <Select
                value={`${sortBy}-${sortOrder}`}
                onChange={(event) => {
                  const [newSortBy, newSortOrder] = event.target.value.split('-');
                  setSortBy(newSortBy as 'created_at' | 'keyword' | 'url' | 'confidence' | 'issue_type');
                  setSortOrder(newSortOrder as 'asc' | 'desc');
                  void fetchPage(1, pageSize, filter, search, newSortBy as any, newSortOrder as any);
                }}
                className="w-full sm:w-48 text-xs"
                aria-label="Sort by"
              >
                <option value="created_at-desc">Date (Newest)</option>
                <option value="created_at-asc">Date (Oldest)</option>
                <option value="issue_type-asc">Issue Type</option>
                <option value="keyword-asc">Keyword (A-Z)</option>
                <option value="confidence-desc">Confidence (High-Low)</option>
              </Select>
            </div>
          </div>
        </div>

        {/* Items List */}
        <div className="bg-slate-50/30 dark:bg-transparent">
          {error ? (
            <div className="px-5 py-4">
              <Alert tone="error">{error}</Alert>
            </div>
          ) : null}
          {notice ? (
            <div className="px-5 py-4">
              <Alert tone="success">{notice}</Alert>
            </div>
          ) : null}

          {loading ? (
            <div className="px-5 py-4">
              <p className="text-sm text-slate-500">Loading...</p>
            </div>
          ) : null}

          {!loading && alerts.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-400">
              No AI alerts match your search/filter criteria.
            </p>
          ) : null}

          <div className={`tour-alerts-list space-y-6 px-4 py-6 md:px-6 ${loading ? 'opacity-50 pointer-events-none' : ''}`}>
            {alerts.map((alert, idx) => {
              const delta = rankDelta(alert.previous_rank, alert.current_rank);
              return (
                <div key={alert.id} className={`${idx === 0 ? 'tour-alert-card' : ''} bg-white dark:bg-[#0B0F19]/50 border border-slate-200 dark:border-yoyaba-border shadow-sm rounded-xl p-5 md:p-6 transition-all hover:shadow-md`}>
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={issueTone(alert.issue_type)}>
                            {formatIssueType(alert.issue_type)}
                          </Badge>
                          <span className="text-sm font-semibold text-slate-900 dark:text-white">
                            &quot;{alert.keyword_text}&quot;
                          </span>
                          <DeltaBadge direction={delta.direction} label={delta.label} />
                          <span className="text-xs text-slate-500 dark:text-slate-400">
                            {formatRank(alert.previous_rank)} &rarr; {formatRank(alert.current_rank)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                          {alert.client_name} / {alert.project_name} ·{' '}
                          <a
                            href={alert.url ?? '#'}
                            target="_blank"
                            rel="noreferrer"
                            className="text-brand-700 dark:text-yoyaba-yellow hover:underline"
                          >
                            {alert.url}
                          </a>
                        </p>
                      </div>

                      <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                        <span>Confidence {formatConfidence(alert.confidence)}</span>
                        <Badge tone={alert.slack_sent ? 'success' : 'warning'}>
                          {alert.slack_sent ? 'Slack sent' : 'Not sent'}
                        </Badge>
                        {!isReadOnly ? (
                          <Button variant="ghost" size="sm" onClick={() => handleResend(alert)}>
                            Resend
                          </Button>
                        ) : null}
                      </div>
                    </div>

                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-50/50 dark:bg-slate-800/40 p-4 rounded-xl border border-slate-200/60 dark:border-yoyaba-border">
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
                          Diagnosis Summary
                        </p>
                        <p className="text-sm text-slate-700 dark:text-slate-300 line-clamp-2">
                          {alert.ai_diagnosis}
                        </p>
                      </div>
                      <Link
                        href={`/alerts/${alert.id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="shrink-0 px-4 py-2 bg-white dark:bg-transparent border border-slate-300 dark:border-slate-500 hover:border-brand-400 dark:hover:border-yoyaba-yellow hover:text-brand-700 dark:hover:text-yoyaba-yellow text-slate-700 dark:text-slate-300 text-sm font-semibold rounded-lg shadow-xs transition-colors"
                      >
                        View Full Report ↗
                      </Link>
                    </div>

                    <p className="text-xs text-slate-400">
                      {formatDateTime(alert.created_at)}
                      {alert.model_used ? ` · ${alert.model_used}` : ''}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          <Pagination
            page={page}
            pageSize={pageSize}
            total={total}
            onPageChange={(newPage) => fetchPage(newPage, pageSize, filter, search, sortBy, sortOrder)}
            onPageSizeChange={(newSize) => fetchPage(1, newSize, filter, search, sortBy, sortOrder)}
          />
        </div>
      </Card>
    </div>
  );
}
