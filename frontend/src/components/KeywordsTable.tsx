'use client';

import Link from 'next/link';
import { useState } from 'react';

import { ActiveBadge, DeltaBadge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Alert, Button, FieldError, Input, Label, Select } from '@/components/ui/Form';
import { Modal } from '@/components/ui/Modal';
import { Pagination } from '@/components/ui/Pagination';
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table';
import { ToggleSwitch } from '@/components/ui/ToggleSwitch';
import { ApiError, keywordsApi } from '@/lib/api';
import { formatRank, formatRelative, rankDelta } from '@/lib/format';
import type { Keyword, Page, TargetUrl, User } from '@/lib/types';

export function KeywordsTable({
  initialPage,
  urls,
  currentUser,
}: {
  initialPage: Page<Keyword>;
  urls: TargetUrl[];
  currentUser?: User;
}) {
  const [keywords, setKeywords] = useState<Keyword[]>(initialPage.items);
  const [total, setTotal] = useState(initialPage.total);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPage.limit || 10);
  const [loading, setLoading] = useState(false);

  const [sortBy, setSortBy] = useState<string>('keyword_text');
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
  const [editingKeyword, setEditingKeyword] = useState<Keyword | null>(null);
  const [targetUrlId, setTargetUrlId] = useState<number | ''>(urls[0]?.id ?? '');
  const [keywordText, setKeywordText] = useState('');
  const [locationCode, setLocationCode] = useState(2840);
  const [languageCode, setLanguageCode] = useState('en');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const isReadOnly = currentUser?.role === 'read_only' || (!currentUser?.is_superuser && currentUser?.role !== 'read_write');

  async function fetchPage(targetPage: number, targetSize: number) {
    setLoading(true);
    try {
      const skip = (targetPage - 1) * targetSize;
      const res = await keywordsApi.list(undefined, skip, targetSize);
      setKeywords(res.items);
      setTotal(res.total);
      setPage(targetPage);
      setPageSize(targetSize);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to fetch keywords');
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle(keyword: Keyword, isActive: boolean) {
    if (isReadOnly) return;
    await keywordsApi.toggle(keyword.id, isActive);
    setKeywords((current) =>
      current.map((item) => (item.id === keyword.id ? { ...item, is_active: isActive } : item)),
    );
  }

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    if (isReadOnly || targetUrlId === '') return;
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      await keywordsApi.create({
        target_url_id: Number(targetUrlId),
        keyword_text: keywordText,
        location_code: locationCode,
        language_code: languageCode,
      });
      setKeywordText('');
      setCreating(false);
      await fetchPage(1, pageSize);
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        setFieldErrors(caught.fieldErrors);
      }
      setError(caught instanceof Error ? caught.message : 'Failed to add keyword');
    } finally {
      setSaving(false);
    }
  }

  function openEdit(keyword: Keyword) {
    if (isReadOnly) return;
    setEditingKeyword(keyword);
    setKeywordText(keyword.keyword_text);
    setLocationCode(keyword.location_code);
    setError(null);
    setFieldErrors({});
  }

  async function handleUpdate(event: React.FormEvent) {
    event.preventDefault();
    if (isReadOnly || !editingKeyword) return;
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      await keywordsApi.update(editingKeyword.id, {
        keyword_text: keywordText,
        location_code: locationCode,
      });
      setEditingKeyword(null);
      setKeywordText('');
      setLocationCode(2840);
      await fetchPage(page, pageSize);
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        setFieldErrors(caught.fieldErrors);
      }
      setError(caught instanceof Error ? caught.message : 'Failed to update keyword');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(keyword: Keyword) {
    if (isReadOnly) return;
    const confirmed = window.confirm(
      `Delete "${keyword.keyword_text}"? Its ranking history and alerts are deleted too.`,
    );
    if (!confirmed) return;
    try {
      await keywordsApi.remove(keyword.id);
      await fetchPage(page, pageSize);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to delete keyword');
    }
  }

  const colSpan = isReadOnly ? 7 : 9;

  return (
    <Card>
      <CardHeader
        title="Keywords"
        description="Tracked search terms and observed position positions."
        action={
          !isReadOnly ? (
            <Button size="sm" onClick={() => setCreating(true)} disabled={urls.length === 0}>
              Add keyword
            </Button>
          ) : undefined
        }
      />
      <div className="border-b border-slate-200 dark:border-yoyaba-border bg-slate-50/80 dark:bg-slate-800/40 p-4">
        <div className="relative max-w-md">
          <Input
            type="text"
            placeholder="Search keywords, markets..."
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
              <TH sortable sortActive={sortBy === 'keyword_text'} sortOrder={sortOrder} onSort={() => handleSort('keyword_text')}>Keyword</TH>
              <TH sortable sortActive={sortBy === 'target_url'} sortOrder={sortOrder} onSort={() => handleSort('target_url')}>Monitored URL</TH>
              <TH sortable sortActive={sortBy === 'location_code'} sortOrder={sortOrder} onSort={() => handleSort('location_code')}>Market</TH>
              <TH sortable sortActive={sortBy === 'latest_rank'} sortOrder={sortOrder} onSort={() => handleSort('latest_rank')} align="right">Rank</TH>
              <TH align="right">Change</TH>
              <TH sortable sortActive={sortBy === 'last_checked_at'} sortOrder={sortOrder} onSort={() => handleSort('last_checked_at')}>Checked</TH>
              <TH sortable sortActive={sortBy === 'is_active'} sortOrder={sortOrder} onSort={() => handleSort('is_active')}>State</TH>
              {!isReadOnly ? <TH align="right">Enabled</TH> : null}
              <TH align="right">Actions</TH>
            </TR>
          </THead>
          <TBody>
            {keywords
              .filter((item) => {
                if (!search.trim()) return true;
                const q = search.toLowerCase();
                return (
                  item.keyword_text.toLowerCase().includes(q) ||
                  item.language_code.toLowerCase().includes(q) ||
                  String(item.location_code).includes(q)
                );
              })
              .length === 0 ? (
              <EmptyRow colSpan={colSpan} message="No keywords match your search." />
            ) : (
              keywords
                .filter((item) => {
                  if (!search.trim()) return true;
                  const q = search.toLowerCase();
                  return (
                    item.keyword_text.toLowerCase().includes(q) ||
                    item.language_code.toLowerCase().includes(q) ||
                    String(item.location_code).includes(q)
                  );
                })
                .map((keyword) => {
                const delta = rankDelta(keyword.current_rank, keyword.previous_rank);
                return (
                  <TR key={keyword.id}>
                    <TD className="font-medium text-slate-900 dark:text-slate-100">
                      <Link
                        href={`/analytics?keyword_id=${keyword.id}`}
                        className="hover:text-brand-600 dark:hover:text-yoyaba-yellow hover:underline"
                      >
                        {keyword.keyword_text}
                      </Link>
                    </TD>
                    <TD className="max-w-xs truncate text-xs text-slate-600 dark:text-slate-400" title={keyword.url ?? ''}>
                      {keyword.url ?? '-'}
                    </TD>
                    <TD className="text-xs">
                      {keyword.language_code.toUpperCase()} / {keyword.location_code}
                    </TD>
                    <TD align="right" className="tabular-nums text-xs font-semibold">
                      {formatRank(keyword.current_rank)}
                    </TD>
                    <TD align="right">
                      <DeltaBadge direction={delta.direction} label={delta.label} />
                    </TD>
                    <TD className="whitespace-nowrap text-xs">
                      {formatRelative(keyword.last_check_date)}
                    </TD>
                    <TD>
                      <ActiveBadge isActive={keyword.is_active} />
                    </TD>
                    {!isReadOnly ? (
                      <TD align="right">
                        <div className="flex justify-end">
                          <ToggleSwitch
                            checked={keyword.is_active}
                            onChange={(next) => handleToggle(keyword, next)}
                          />
                        </div>
                      </TD>
                    ) : null}
                    <TD align="right">
                      <div className="flex justify-end gap-1">
                        <Link href={`/analytics?keyword_id=${keyword.id}`}>
                          <Button variant="secondary" size="sm">
                            Chart
                          </Button>
                        </Link>
                        {!isReadOnly ? (
                          <>
                            <Button variant="secondary" size="sm" onClick={() => openEdit(keyword)}>
                              Edit
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => handleDelete(keyword)}>
                              Delete
                            </Button>
                          </>
                        ) : null}
                      </div>
                    </TD>
                  </TR>
                );
              })
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
          title="Add keyword"
          onClose={() => setCreating(false)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button form="create-keyword-form" type="submit" disabled={saving || !keywordText}>
                {saving ? 'Saving...' : 'Create'}
              </Button>
            </>
          }
        >
          <form id="create-keyword-form" onSubmit={handleCreate} className="space-y-4" noValidate>
            <div>
              <Label htmlFor="kw-url" required>Target URL</Label>
              <Select
                id="kw-url"
                name="target_url_id"
                value={targetUrlId}
                onChange={(event) => setTargetUrlId(Number(event.target.value))}
                error={!!fieldErrors.target_url_id}
                className="mt-1"
              >
                {urls.map((target) => (
                  <option key={target.id} value={target.id}>
                    {target.url}
                  </option>
                ))}
              </Select>
              <FieldError message={fieldErrors.target_url_id} />
            </div>
            <div>
              <Label htmlFor="kw-text" required>Keyword</Label>
              <Input
                id="kw-text"
                name="keyword_text"
                type="text"
                value={keywordText}
                onChange={(event) => setKeywordText(event.target.value)}
                placeholder="e.g. affordable housing loans"
                required
                error={!!fieldErrors.keyword_text}
                className="mt-1"
              />
              <FieldError message={fieldErrors.keyword_text} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="kw-location" required>Location (DataForSEO)</Label>
                <Input
                  id="kw-location"
                  name="location_code"
                  type="number"
                  value={locationCode}
                  onChange={(event) => setLocationCode(Number(event.target.value))}
                  required
                  error={!!fieldErrors.location_code}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.location_code} />
              </div>
              <div>
                <Label htmlFor="kw-lang" required>Language (DataForSEO)</Label>
                <Input
                  id="kw-lang"
                  name="language_code"
                  type="text"
                  value={languageCode}
                  onChange={(event) => setLanguageCode(event.target.value)}
                  placeholder="en"
                  required
                  error={!!fieldErrors.language_code}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.language_code} />
              </div>
            </div>
          </form>
        </Modal>

        <Modal
          open={editingKeyword !== null}
          title="Edit keyword"
          onClose={() => setEditingKeyword(null)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setEditingKeyword(null)}>
                Cancel
              </Button>
              <Button form="edit-keyword-form" type="submit" disabled={saving || !keywordText}>
                {saving ? 'Saving...' : 'Save Changes'}
              </Button>
            </>
          }
        >
          <form id="edit-keyword-form" onSubmit={handleUpdate} className="space-y-4" noValidate>
            <div>
              <Label htmlFor="edit-kw-text" required>Keyword</Label>
              <Input
                id="edit-kw-text"
                name="keyword_text"
                type="text"
                value={keywordText}
                onChange={(event) => setKeywordText(event.target.value)}
                placeholder="e.g. affordable housing loans"
                required
                error={!!fieldErrors.keyword_text}
                className="mt-1"
              />
              <FieldError message={fieldErrors.keyword_text} />
            </div>
            <div>
              <Label htmlFor="edit-kw-location" required>Location Code</Label>
              <Input
                id="edit-kw-location"
                name="location_code"
                type="number"
                value={locationCode}
                onChange={(event) => setLocationCode(Number(event.target.value))}
                required
                error={!!fieldErrors.location_code}
                className="mt-1"
              />
              <FieldError message={fieldErrors.location_code} />
            </div>
          </form>
        </Modal>
        </>
      ) : null}
    </Card>
  );
}
