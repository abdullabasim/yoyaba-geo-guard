'use client';

import { useState } from 'react';

import { ActiveBadge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Alert, Button, FieldError, Input, Label } from '@/components/ui/Form';
import { Modal } from '@/components/ui/Modal';
import { Pagination } from '@/components/ui/Pagination';
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table';
import { ToggleSwitch } from '@/components/ui/ToggleSwitch';
import { ApiError, clientsApi } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import type { Client, Page, User } from '@/lib/types';

export function ClientsTable({
  initialPage,
  currentUser,
}: {
  initialPage: Page<Client>;
  currentUser?: User;
}) {
  const [clients, setClients] = useState<Client[]>(initialPage.items);
  const [total, setTotal] = useState(initialPage.total);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPage.limit || 10);
  const [loading, setLoading] = useState(false);

  const [sortBy, setSortBy] = useState<string>('name');
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
  const [editingClient, setEditingClient] = useState<Client | null>(null);
  const [name, setName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const isReadOnly = currentUser?.role === 'read_only' || (!currentUser?.is_superuser && currentUser?.role !== 'read_write');

  async function fetchPage(targetPage: number, targetSize: number) {
    setLoading(true);
    try {
      const skip = (targetPage - 1) * targetSize;
      const res = await clientsApi.list(skip, targetSize);
      setClients(res.items);
      setTotal(res.total);
      setPage(targetPage);
      setPageSize(targetSize);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to fetch clients');
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle(client: Client, isActive: boolean) {
    if (isReadOnly) return;
    await clientsApi.toggle(client.id, isActive);
    setClients((current) =>
      current.map((item) => (item.id === client.id ? { ...item, is_active: isActive } : item)),
    );
  }

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    if (isReadOnly) return;
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      await clientsApi.create({ name, company_name: companyName || null });
      setName('');
      setCompanyName('');
      setCreating(false);
      await fetchPage(1, pageSize);
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        setFieldErrors(caught.fieldErrors);
      }
      setError(caught instanceof Error ? caught.message : 'Failed to create client');
    } finally {
      setSaving(false);
    }
  }

  function openEdit(client: Client) {
    if (isReadOnly) return;
    setEditingClient(client);
    setName(client.name);
    setCompanyName(client.company_name ?? '');
    setError(null);
    setFieldErrors({});
  }

  async function handleUpdate(event: React.FormEvent) {
    event.preventDefault();
    if (isReadOnly || !editingClient) return;
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      await clientsApi.update(editingClient.id, { name, company_name: companyName || null });
      setEditingClient(null);
      setName('');
      setCompanyName('');
      await fetchPage(page, pageSize);
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        setFieldErrors(caught.fieldErrors);
      }
      setError(caught instanceof Error ? caught.message : 'Failed to update client');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(client: Client) {
    if (isReadOnly) return;
    const confirmed = window.confirm(
      `Delete "${client.name}"? This also deletes its projects, URLs, keywords, ranking history and alerts.`,
    );
    if (!confirmed) return;
    try {
      await clientsApi.remove(client.id);
      await fetchPage(page, pageSize);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to delete client');
    }
  }

  const colSpan = isReadOnly ? 5 : 7;

  return (
    <Card>
      <CardHeader
        title="Clients"
        description="Top level of the hierarchy. Accounts and monitored companies."
        action={
          !isReadOnly ? (
            <Button size="sm" onClick={() => setCreating(true)}>
              Add client
            </Button>
          ) : undefined
        }
      />
      <div className="border-b border-slate-200 dark:border-yoyaba-border bg-slate-50/80 dark:bg-slate-800/40 p-4">
        <div className="relative max-w-md">
          <Input
            type="text"
            placeholder="Search clients, companies..."
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
              <TH sortable sortActive={sortBy === 'name'} sortOrder={sortOrder} onSort={() => handleSort('name')}>Name</TH>
              <TH sortable sortActive={sortBy === 'company_name'} sortOrder={sortOrder} onSort={() => handleSort('company_name')}>Company</TH>
              <TH sortable sortActive={sortBy === 'project_count'} sortOrder={sortOrder} onSort={() => handleSort('project_count')} align="right">Projects</TH>
              <TH sortable sortActive={sortBy === 'created_at'} sortOrder={sortOrder} onSort={() => handleSort('created_at')}>Created</TH>
              <TH sortable sortActive={sortBy === 'is_active'} sortOrder={sortOrder} onSort={() => handleSort('is_active')}>State</TH>
              {!isReadOnly ? <TH align="right">Enabled</TH> : null}
              {!isReadOnly ? <TH /> : null}
            </TR>
          </THead>
          <TBody>
            {clients
              .filter((item) => {
                if (!search.trim()) return true;
                const q = search.toLowerCase();
                return (
                  item.name.toLowerCase().includes(q) ||
                  (item.company_name ?? '').toLowerCase().includes(q)
                );
              })
              .length === 0 ? (
              <EmptyRow colSpan={colSpan} message="No clients match your search." />
            ) : (
              clients
                .filter((item) => {
                  if (!search.trim()) return true;
                  const q = search.toLowerCase();
                  return (
                    item.name.toLowerCase().includes(q) ||
                    (item.company_name ?? '').toLowerCase().includes(q)
                  );
                })
                .map((client) => (
                <TR key={client.id}>
                  <TD className="font-medium text-slate-900 dark:text-slate-100">{client.name}</TD>
                  <TD className="text-xs">{client.company_name ?? '-'}</TD>
                  <TD align="right" className="tabular-nums text-xs">
                    {client.active_project_count} / {client.project_count}
                  </TD>
                  <TD className="whitespace-nowrap text-xs">
                    {formatDateTime(client.created_at)}
                  </TD>
                  <TD>
                    <ActiveBadge isActive={client.is_active} />
                  </TD>
                  {!isReadOnly ? (
                    <TD align="right">
                      <div className="flex justify-end">
                        <ToggleSwitch
                          checked={client.is_active}
                          onChange={(next) => handleToggle(client, next)}
                          label={undefined}
                        />
                      </div>
                    </TD>
                  ) : null}
                  {!isReadOnly ? (
                    <TD align="right">
                      <div className="flex justify-end gap-1">
                        <Button variant="secondary" size="sm" onClick={() => openEdit(client)}>
                          Edit
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(client)}>
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
            title="Add client"
            onClose={() => setCreating(false)}
            footer={
              <>
                <Button variant="secondary" onClick={() => setCreating(false)}>
                  Cancel
                </Button>
                <Button form="create-client-form" type="submit" disabled={saving || !name}>
                  {saving ? 'Saving...' : 'Create'}
                </Button>
              </>
            }
          >
            <form id="create-client-form" onSubmit={handleCreate} className="space-y-4" noValidate>
              <div>
                <Label htmlFor="client-name" required>Name</Label>
                <Input
                  id="client-name"
                  name="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Acme Corp"
                  required
                  error={!!fieldErrors.name}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.name} />
              </div>
              <div>
                <Label htmlFor="client-company">Company Details (optional)</Label>
                <Input
                  id="client-company"
                  name="company_name"
                  value={companyName}
                  onChange={(event) => setCompanyName(event.target.value)}
                  placeholder="Acme Corporation Ltd."
                  error={!!fieldErrors.company_name}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.company_name} />
              </div>
            </form>
          </Modal>

          <Modal
            open={editingClient !== null}
            title="Edit client"
            onClose={() => setEditingClient(null)}
            footer={
              <>
                <Button variant="secondary" onClick={() => setEditingClient(null)}>
                  Cancel
                </Button>
                <Button form="edit-client-form" type="submit" disabled={saving || !name}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </Button>
              </>
            }
          >
            <form id="edit-client-form" onSubmit={handleUpdate} className="space-y-4" noValidate>
              <div>
                <Label htmlFor="edit-client-name" required>Name</Label>
                <Input
                  id="edit-client-name"
                  name="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                  error={!!fieldErrors.name}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.name} />
              </div>
              <div>
                <Label htmlFor="edit-client-company">Company Details (optional)</Label>
                <Input
                  id="edit-client-company"
                  name="company_name"
                  value={companyName}
                  onChange={(event) => setCompanyName(event.target.value)}
                  error={!!fieldErrors.company_name}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.company_name} />
              </div>
            </form>
          </Modal>
        </>
      ) : null}
    </Card>
  );
}
