'use client';

import { useState } from 'react';

import { ScheduleForm } from '@/components/ScheduleForm';
import { ActiveBadge, Badge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Alert, Button, FieldError, Input, Label, Select } from '@/components/ui/Form';
import { Modal } from '@/components/ui/Modal';
import { Pagination } from '@/components/ui/Pagination';
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table';
import { ToggleSwitch } from '@/components/ui/ToggleSwitch';
import { ApiError, tasksApi, urlsApi } from '@/lib/api';
import { formatRelative } from '@/lib/format';
import type { CheckInterval, Page, Project, TargetUrl, User } from '@/lib/types';

const COMMON_TIMEZONES = [
  'Europe/Berlin',
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Asia/Dubai',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Sydney',
];

export function UrlsTable({
  initialPage,
  projects,
  currentUser,
}: {
  initialPage: Page<TargetUrl>;
  projects: Project[];
  currentUser?: User;
}) {
  const [urls, setUrls] = useState<TargetUrl[]>(initialPage.items);
  const [total, setTotal] = useState(initialPage.total);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPage.limit || 10);
  const [loading, setLoading] = useState(false);

  const [sortBy, setSortBy] = useState<string>('url');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [search, setSearch] = useState('');

  function handleSort(field: string) {
    let nextOrder: 'asc' | 'desc' = 'asc';
    if (sortBy === field) {
      nextOrder = sortOrder === 'asc' ? 'desc' : 'asc';
    }
    setSortBy(field);
    setSortOrder(nextOrder);
  }

  const [creating, setCreating] = useState(false);
  const [editingUrl, setEditingUrl] = useState<TargetUrl | null>(null);
  const [scheduling, setScheduling] = useState<TargetUrl | null>(null);
  const [projectId, setProjectId] = useState<number | ''>(projects[0]?.id ?? '');
  const [url, setUrl] = useState('');
  const [interval, setInterval] = useState<CheckInterval>('daily');
  const [executionTime, setExecutionTime] = useState('03:00');
  const [timezone, setTimezone] = useState('Europe/Berlin');
  const [rankDropThreshold, setRankDropThreshold] = useState('');
  const [depth, setDepth] = useState('');
  const [initialKeywords, setInitialKeywords] = useState('');
  const [inheritSchedule, setInheritSchedule] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const isReadOnly = currentUser?.role === 'read_only' || (!currentUser?.is_superuser && currentUser?.role !== 'read_write');

  async function fetchPage(targetPage: number, targetSize: number) {
    setLoading(true);
    try {
      const skip = (targetPage - 1) * targetSize;
      const res = await urlsApi.list(undefined, skip, targetSize);
      setUrls(res.items);
      setTotal(res.total);
      setPage(targetPage);
      setPageSize(targetSize);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to fetch URLs');
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle(target: TargetUrl, isActive: boolean) {
    if (isReadOnly) return;
    await urlsApi.toggle(target.id, isActive);
    setUrls((current) =>
      current.map((item) => (item.id === target.id ? { ...item, is_active: isActive } : item)),
    );
  }

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    if (isReadOnly || projectId === '') return;
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      const keywordList = initialKeywords
        .split(/[\n,]+/)
        .map((k) => k.trim())
        .filter(Boolean);

      await urlsApi.create({
        project_id: Number(projectId),
        url,
        check_interval: interval,
        execution_time: `${executionTime}:00`,
        timezone,
        rank_drop_threshold: rankDropThreshold.trim() ? Number(rankDropThreshold) : null,
        dataforseo_depth: depth.trim() ? Number(depth) : null,
        inherit_schedule: inheritSchedule,
        initial_keywords: keywordList,
      });
      setUrl('');
      setRankDropThreshold('');
      setDepth('');
      setInitialKeywords('');
      setCreating(false);
      await fetchPage(1, pageSize);
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        setFieldErrors(caught.fieldErrors);
      }
      setError(caught instanceof Error ? caught.message : 'Failed to add URL');
    } finally {
      setSaving(false);
    }
  }

  function openEdit(target: TargetUrl) {
    if (isReadOnly) return;
    setEditingUrl(target);
    setUrl(target.url);
    setRankDropThreshold(target.rank_drop_threshold ? String(target.rank_drop_threshold) : '');
    setDepth(target.dataforseo_depth ? String(target.dataforseo_depth) : '');
    setError(null);
    setFieldErrors({});
  }

  async function handleUpdate(event: React.FormEvent) {
    event.preventDefault();
    if (isReadOnly || !editingUrl) return;
    setSaving(true);
    setError(null);
    try {
      await urlsApi.update(editingUrl.id, {
        url,
        rank_drop_threshold: rankDropThreshold.trim() ? Number(rankDropThreshold) : null,
        dataforseo_depth: depth.trim() ? Number(depth) : null,
      });
      setEditingUrl(null);
      setUrl('');
      setRankDropThreshold('');
      setDepth('');
      await fetchPage(page, pageSize);
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        setFieldErrors(caught.fieldErrors);
      }
      setError(caught instanceof Error ? caught.message : 'Failed to update URL');
    } finally {
      setSaving(false);
    }
  }

  async function handleRunNow(target: TargetUrl) {
    if (isReadOnly) return;
    setError(null);
    setNotice(null);
    try {
      const response = await tasksApi.run({ target_url_id: target.id });
      setNotice(
        `Dispatched ${response.dispatched} keyword check${response.dispatched === 1 ? '' : 's'}. Watch the Task Monitor for progress.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to dispatch check');
    }
  }

  async function handleDelete(target: TargetUrl) {
    if (isReadOnly) return;
    const confirmed = window.confirm(
      `Delete ${target.url}? This also deletes its keywords, history and alerts.`,
    );
    if (!confirmed) return;
    try {
      await urlsApi.remove(target.id);
      await fetchPage(page, pageSize);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to delete URL');
    }
  }

  const colSpan = isReadOnly ? 6 : 8;

  return (
    <Card>
      <CardHeader
        title="Target URLs"
        description="Monitored pages, each with its own schedule"
        action={
          !isReadOnly ? (
            <Button size="sm" onClick={() => setCreating(true)} disabled={projects.length === 0}>
              Add URL
            </Button>
          ) : undefined
        }
      />
      <div className="border-b border-slate-200 dark:border-yoyaba-border bg-slate-50/80 dark:bg-slate-800/40 p-4">
        <div className="relative max-w-md">
          <Input
            type="text"
            placeholder="Search URLs, accounts, schedules..."
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
        {notice ? (
          <div className="px-5 py-4">
            <Alert tone="success">{notice}</Alert>
          </div>
        ) : null}

        <Table className={loading ? 'opacity-50 pointer-events-none' : ''}>
          <THead>
            <TR>
              <TH sortable sortActive={sortBy === 'url'} sortOrder={sortOrder} onSort={() => handleSort('url')}>URL</TH>
              <TH sortable sortActive={sortBy === 'client'} sortOrder={sortOrder} onSort={() => handleSort('client')}>Account</TH>
              <TH sortable sortActive={sortBy === 'check_interval'} sortOrder={sortOrder} onSort={() => handleSort('check_interval')}>Schedule</TH>
              <TH sortable sortActive={sortBy === 'keyword_count'} sortOrder={sortOrder} onSort={() => handleSort('keyword_count')} align="right">Keywords</TH>
              <TH sortable sortActive={sortBy === 'last_checked_at'} sortOrder={sortOrder} onSort={() => handleSort('last_checked_at')}>Last checked</TH>
              <TH sortable sortActive={sortBy === 'is_active'} sortOrder={sortOrder} onSort={() => handleSort('is_active')}>State</TH>
              {!isReadOnly ? <TH align="right">Enabled</TH> : null}
              {!isReadOnly ? <TH /> : null}
            </TR>
          </THead>
          <TBody>
            {urls
              .filter((item) => {
                if (!search.trim()) return true;
                const q = search.toLowerCase();
                return (
                  item.url.toLowerCase().includes(q) ||
                  (item.project_name ?? '').toLowerCase().includes(q) ||
                  (item.client_name ?? '').toLowerCase().includes(q) ||
                  item.check_interval.toLowerCase().includes(q)
                );
              })
              .length === 0 ? (
              <EmptyRow colSpan={colSpan} message="No target URLs match your search." />
            ) : (
              urls
                .filter((item) => {
                  if (!search.trim()) return true;
                  const q = search.toLowerCase();
                  return (
                    item.url.toLowerCase().includes(q) ||
                    (item.project_name ?? '').toLowerCase().includes(q) ||
                    (item.client_name ?? '').toLowerCase().includes(q) ||
                    item.check_interval.toLowerCase().includes(q)
                  );
                })
                .map((target) => (
                <TR key={target.id}>
                  <TD className="max-w-xs">
                    <a
                      href={target.url}
                      target="_blank"
                      rel="noreferrer"
                      className="block truncate text-xs font-medium text-brand-700 dark:text-yoyaba-yellow hover:underline"
                      title={target.url}
                    >
                      {target.url}
                    </a>
                  </TD>
                  <TD className="text-xs">
                    {target.client_name ?? '-'}
                    <span className="text-slate-400 dark:text-slate-500"> / </span>
                    {target.project_name ?? '-'}
                  </TD>
                  <TD className="text-xs">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge tone="brand">
                        {target.effective_check_interval ?? target.check_interval}
                      </Badge>
                      <Badge tone="warning">
                        Drop &ge; {target.effective_rank_drop_threshold ?? target.rank_drop_threshold ?? 3}
                      </Badge>
                      <Badge tone="neutral">
                        Depth: {target.effective_dataforseo_depth ?? target.dataforseo_depth ?? 10}
                      </Badge>
                      <span className="tabular-nums">
                        {(target.effective_execution_time ?? target.execution_time).slice(0, 5)}{' '}
                        {target.effective_timezone ?? target.timezone}
                      </span>
                      <Badge tone={target.inherit_schedule ? 'neutral' : 'warning'}>
                        {target.inherit_schedule ? 'project' : 'custom'}
                      </Badge>
                    </div>
                  </TD>
                  <TD align="right" className="tabular-nums text-xs">
                    {target.active_keyword_count} / {target.keyword_count}
                  </TD>
                  <TD className="whitespace-nowrap text-xs">
                    {formatRelative(target.last_checked_at)}
                  </TD>
                  <TD>
                    <ActiveBadge isActive={target.is_active} />
                  </TD>
                  {!isReadOnly ? (
                    <TD align="right">
                      <div className="flex justify-end">
                        <ToggleSwitch
                          checked={target.is_active}
                          onChange={(next) => handleToggle(target, next)}
                        />
                      </div>
                    </TD>
                  ) : null}
                  {!isReadOnly ? (
                    <TD align="right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => setScheduling(target)}
                        >
                          Schedule
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleRunNow(target)}>
                          Run now
                        </Button>
                        <Button variant="secondary" size="sm" onClick={() => openEdit(target)}>
                          Edit
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(target)}>
                          Delete
                        </Button>
                      </div>
                    </TD>
                  ) : null}
                </TR>
              ))
            )}
          </TBody>
        </Table>

        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={(newPage) => fetchPage(newPage, pageSize)}
          onPageSizeChange={(newSize) => fetchPage(1, newSize)}
        />
      </CardBody>

      {!isReadOnly ? (
        <>
          <Modal
            open={creating}
            title="Add target URL"
            onClose={() => setCreating(false)}
            footer={
              <>
                <Button variant="secondary" onClick={() => setCreating(false)}>
                  Cancel
                </Button>
                <Button form="create-url-form" type="submit" disabled={saving || !url}>
                  {saving ? 'Saving...' : 'Create'}
                </Button>
              </>
            }
          >
            <form id="create-url-form" onSubmit={handleCreate} className="space-y-4" noValidate>
              <div>
                <Label htmlFor="url-project" required>Project</Label>
                <Select
                  id="url-project"
                  name="project_id"
                  value={projectId}
                  onChange={(event) => setProjectId(Number(event.target.value))}
                  error={!!fieldErrors.project_id}
                  className="mt-1"
                >
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.client_name} / {project.name}
                    </option>
                  ))}
                </Select>
                <FieldError message={fieldErrors.project_id} />
              </div>
              <div>
                <Label htmlFor="url-value" required>URL</Label>
                <Input
                  id="url-value"
                  name="url"
                  type="url"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://example.com/pricing"
                  required
                  error={!!fieldErrors.url}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.url} />
              </div>
              <div>
                <Label htmlFor="url-keywords">Initial Keywords (Optional)</Label>
                <Input
                  id="url-keywords"
                  name="initial_keywords"
                  type="text"
                  value={initialKeywords}
                  onChange={(event) => setInitialKeywords(event.target.value)}
                  placeholder="e.g. flex shorthand css, css flex property (comma or newline separated)"
                  error={!!fieldErrors.initial_keywords}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.initial_keywords} />
                <p className="mt-1 text-xs text-slate-500">
                  Separate multiple keywords with commas or new lines. They will be linked to this URL automatically.
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-5">
                <div>
                  <Label htmlFor="url-interval">Interval</Label>
                  <Select
                    id="url-interval"
                    name="check_interval"
                    value={interval}
                    onChange={(event) => setInterval(event.target.value as CheckInterval)}
                    className="mt-1"
                    disabled={inheritSchedule}
                    error={!!fieldErrors.check_interval}
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </Select>
                  <FieldError message={fieldErrors.check_interval} />
                </div>
                <div>
                  <Label htmlFor="url-time">Execution time</Label>
                  <Input
                    id="url-time"
                    name="execution_time"
                    type="time"
                    value={executionTime}
                    onChange={(event) => setExecutionTime(event.target.value)}
                    className="mt-1"
                    disabled={inheritSchedule}
                    error={!!fieldErrors.execution_time}
                  />
                  <FieldError message={fieldErrors.execution_time} />
                </div>
                <div>
                  <Label htmlFor="url-tz">Timezone</Label>
                  <Select
                    id="url-tz"
                    name="timezone"
                    value={timezone}
                    onChange={(event) => setTimezone(event.target.value)}
                    className="mt-1"
                    disabled={inheritSchedule}
                    error={!!fieldErrors.timezone}
                  >
                    {(COMMON_TIMEZONES.includes(timezone) ? COMMON_TIMEZONES : [timezone, ...COMMON_TIMEZONES]).map(
                      (zone) => (
                        <option key={zone} value={zone}>
                          {zone}
                        </option>
                      ),
                    )}
                  </Select>
                  <FieldError message={fieldErrors.timezone} />
                </div>
                <div>
                  <Label htmlFor="url-drop">Drop Trigger</Label>
                  <Input
                    id="url-drop"
                    name="rank_drop_threshold"
                    type="number"
                    min={1}
                    max={50}
                    placeholder="Inherit project"
                    value={rankDropThreshold}
                    onChange={(event) => setRankDropThreshold(event.target.value)}
                    className="mt-1"
                    disabled={inheritSchedule}
                    error={!!fieldErrors.rank_drop_threshold}
                  />
                  <FieldError message={fieldErrors.rank_drop_threshold} />
                </div>
                <div>
                  <Label htmlFor="url-depth">Fetch Depth</Label>
                  <Input
                    id="url-depth"
                    name="dataforseo_depth"
                    type="number"
                    min={10}
                    max={100}
                    placeholder="Inherit project"
                    value={depth}
                    onChange={(event) => setDepth(event.target.value)}
                    className="mt-1"
                    disabled={inheritSchedule}
                    error={!!fieldErrors.dataforseo_depth}
                  />
                  <FieldError message={fieldErrors.dataforseo_depth} />
                </div>
              </div>

              <label className="flex items-start gap-2 rounded border border-slate-200 dark:border-yoyaba-border bg-slate-50 dark:bg-slate-800/50 px-3 py-2 text-sm">
                <input
                  type="checkbox"
                  checked={inheritSchedule}
                  onChange={(event) => setInheritSchedule(event.target.checked)}
                  className="mt-1"
                />
                <span>
                  <span className="font-medium text-slate-800 dark:text-slate-200">
                    Use the project&apos;s default schedule
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400">
                    Recommended, so changing the project schedule reschedules this URL too.
                    Uncheck to set the fields above independently.
                  </span>
                </span>
              </label>
            </form>
          </Modal>

          <Modal
            open={scheduling !== null}
            title={scheduling ? `Schedule for ${scheduling.url}` : 'Schedule'}
            onClose={() => setScheduling(null)}
          >
            {scheduling ? (
              <ScheduleForm
                targetUrl={scheduling}
                onSaved={() => {
                  setScheduling(null);
                  void fetchPage(page, pageSize);
                }}
              />
            ) : null}
          </Modal>

          <Modal
            open={editingUrl !== null}
            title="Edit target URL"
            onClose={() => setEditingUrl(null)}
            footer={
              <>
                <Button variant="secondary" onClick={() => setEditingUrl(null)}>
                  Cancel
                </Button>
                <Button form="edit-url-form" type="submit" disabled={saving || !url}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </Button>
              </>
            }
          >
            <form id="edit-url-form" onSubmit={handleUpdate} className="space-y-4" noValidate>
              <div>
                <Label htmlFor="edit-url-value" required>URL</Label>
                <Input
                  id="edit-url-value"
                  name="url"
                  type="url"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://example.com/pricing"
                  required
                  className="mt-1"
                  error={!!fieldErrors.url}
                />
                <FieldError message={fieldErrors.url} />
                <p className="mt-0.5 text-xs text-slate-500">
                  Note: The project cannot be changed here. To move a URL to another project, you must delete and recreate it.
                </p>
              </div>
              <div>
                <Label htmlFor="edit-url-drop">Custom Rank Drop Trigger (positions)</Label>
                <Input
                  id="edit-url-drop"
                  name="rank_drop_threshold"
                  type="number"
                  min={1}
                  max={50}
                  placeholder="Inherit project"
                  value={rankDropThreshold}
                  onChange={(event) => setRankDropThreshold(event.target.value)}
                  className="mt-1"
                  error={!!fieldErrors.rank_drop_threshold}
                />
                <FieldError message={fieldErrors.rank_drop_threshold} />
                <p className="mt-0.5 text-xs text-slate-500">
                  Overrides the project's default drop threshold. Leave empty to inherit.
                </p>
              </div>
              <div>
                <Label htmlFor="edit-url-depth">Custom Fetch Depth</Label>
                <Input
                  id="edit-url-depth"
                  name="dataforseo_depth"
                  type="number"
                  min={10}
                  max={100}
                  placeholder="Inherit project"
                  value={depth}
                  onChange={(event) => setDepth(event.target.value)}
                  className="mt-1"
                  error={!!fieldErrors.dataforseo_depth}
                />
                <FieldError message={fieldErrors.dataforseo_depth} />
                <p className="mt-0.5 text-xs text-slate-500">
                  Overrides the project's default depth. Leave empty to inherit.
                </p>
              </div>
            </form>
          </Modal>
        </>
      ) : null}
    </Card>
  );
}
