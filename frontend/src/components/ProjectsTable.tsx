'use client';

import { useState } from 'react';

import { ProjectScheduleForm } from '@/components/ProjectScheduleForm';
import { ActiveBadge, Badge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Alert, Button, FieldError, Input, Label, Select } from '@/components/ui/Form';
import { Modal } from '@/components/ui/Modal';
import { Pagination } from '@/components/ui/Pagination';
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table';
import { ToggleSwitch } from '@/components/ui/ToggleSwitch';
import { ApiError, projectsApi } from '@/lib/api';
import type { Client, Page, Project, ProjectSchedule, User } from '@/lib/types';

export function ProjectsTable({
  initialPage,
  clients,
  currentUser,
}: {
  initialPage: Page<Project>;
  clients: Client[];
  currentUser?: User;
}) {
  const [projects, setProjects] = useState<Project[]>(initialPage.items);
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
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [scheduling, setScheduling] = useState<{
    project: Project;
    schedule: ProjectSchedule;
  } | null>(null);
  const [clientId, setClientId] = useState<number | ''>(clients[0]?.id ?? '');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [rankDropThreshold, setRankDropThreshold] = useState(3);
  const [depth, setDepth] = useState(10);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const isReadOnly = currentUser?.role === 'read_only' || (!currentUser?.is_superuser && currentUser?.role !== 'read_write');

  async function fetchPage(targetPage: number, targetSize: number) {
    setLoading(true);
    try {
      const skip = (targetPage - 1) * targetSize;
      const res = await projectsApi.list(undefined, skip, targetSize);
      setProjects(res.items);
      setTotal(res.total);
      setPage(targetPage);
      setPageSize(targetSize);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to fetch projects');
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle(project: Project, isActive: boolean) {
    if (isReadOnly) return;
    await projectsApi.toggle(project.id, isActive);
    setProjects((current) =>
      current.map((item) => (item.id === project.id ? { ...item, is_active: isActive } : item)),
    );
  }

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    if (isReadOnly || clientId === '') return;
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      await projectsApi.create({
        client_id: Number(clientId),
        name,
        description: description || null,
        rank_drop_threshold: Number(rankDropThreshold),
        dataforseo_depth: Number(depth),
      });
      setName('');
      setDescription('');
      setRankDropThreshold(3);
      setDepth(10);
      setCreating(false);
      await fetchPage(1, pageSize);
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        setFieldErrors(caught.fieldErrors);
      }
      setError(caught instanceof Error ? caught.message : 'Failed to create project');
    } finally {
      setSaving(false);
    }
  }

  function openEdit(project: Project) {
    if (isReadOnly) return;
    setEditingProject(project);
    setName(project.name);
    setDescription(project.description ?? '');
    setRankDropThreshold(project.rank_drop_threshold);
    setDepth(project.dataforseo_depth);
    setError(null);
    setFieldErrors({});
  }

  async function handleUpdate(event: React.FormEvent) {
    event.preventDefault();
    if (isReadOnly || !editingProject) return;
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      await projectsApi.update(editingProject.id, {
        name,
        description: description || null,
        rank_drop_threshold: Number(rankDropThreshold),
        dataforseo_depth: Number(depth),
      });
      setEditingProject(null);
      setName('');
      setDescription('');
      setRankDropThreshold(3);
      setDepth(10);
      await fetchPage(page, pageSize);
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        setFieldErrors(caught.fieldErrors);
      }
      setError(caught instanceof Error ? caught.message : 'Failed to update project');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(project: Project) {
    if (isReadOnly) return;
    const confirmed = window.confirm(
      `Delete "${project.name}"? This also deletes its URLs, keywords, history and alerts.`,
    );
    if (!confirmed) return;
    try {
      await projectsApi.remove(project.id);
      await fetchPage(page, pageSize);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to delete project');
    }
  }

  async function openSchedule(project: Project) {
    if (isReadOnly) return;
    setError(null);
    try {
      const schedule = await projectsApi.getSchedule(project.id);
      setScheduling({ project, schedule });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to load schedule');
    }
  }

  const colSpan = isReadOnly ? 5 : 7;

  return (
    <Card>
      <CardHeader
        title="Projects"
        description="Groups of target URLs belonging to one client"
        action={
          !isReadOnly ? (
            <Button size="sm" onClick={() => setCreating(true)} disabled={clients.length === 0}>
              Add project
            </Button>
          ) : undefined
        }
      />
      <div className="border-b border-slate-200 dark:border-yoyaba-border bg-slate-50/80 dark:bg-slate-800/40 p-4">
        <div className="relative max-w-md">
          <Input
            type="text"
            placeholder="Search projects, clients..."
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
              <TH sortable sortActive={sortBy === 'name'} sortOrder={sortOrder} onSort={() => handleSort('name')}>Project</TH>
              <TH sortable sortActive={sortBy === 'client'} sortOrder={sortOrder} onSort={() => handleSort('client')}>Client</TH>
              <TH sortable sortActive={sortBy === 'target_url_count'} sortOrder={sortOrder} onSort={() => handleSort('target_url_count')} align="right">URLs</TH>
              <TH sortable sortActive={sortBy === 'check_interval'} sortOrder={sortOrder} onSort={() => handleSort('check_interval')}>Schedule</TH>
              <TH sortable sortActive={sortBy === 'is_active'} sortOrder={sortOrder} onSort={() => handleSort('is_active')}>State</TH>
              {!isReadOnly ? <TH align="right">Enabled</TH> : null}
              {!isReadOnly ? <TH /> : null}
            </TR>
          </THead>
          <TBody>
            {projects
              .filter((item) => {
                if (!search.trim()) return true;
                const q = search.toLowerCase();
                return (
                  item.name.toLowerCase().includes(q) ||
                  (item.client_name ?? '').toLowerCase().includes(q) ||
                  (item.description ?? '').toLowerCase().includes(q)
                );
              })
              .length === 0 ? (
              <EmptyRow colSpan={colSpan} message="No projects match your search." />
            ) : (
              projects
                .filter((item) => {
                  if (!search.trim()) return true;
                  const q = search.toLowerCase();
                  return (
                    item.name.toLowerCase().includes(q) ||
                    (item.client_name ?? '').toLowerCase().includes(q) ||
                    (item.description ?? '').toLowerCase().includes(q)
                  );
                })
                .map((project) => (
                <TR key={project.id}>
                  <TD className="font-medium text-slate-900 dark:text-slate-100">
                    {project.name}
                    {project.description ? (
                      <p className="text-xs font-normal text-slate-500">
                        {project.description}
                      </p>
                    ) : null}
                  </TD>
                  <TD className="text-xs">{project.client_name ?? '-'}</TD>
                  <TD align="right" className="tabular-nums text-xs">
                    {project.active_url_count} / {project.url_count}
                  </TD>
                  <TD className="whitespace-nowrap text-xs">
                    <div className="flex flex-wrap items-center gap-1">
                      <Badge tone="brand">{project.default_check_interval}</Badge>
                      <Badge tone="warning">Drop &ge; {project.rank_drop_threshold}</Badge>
                      <Badge tone="neutral">Depth: {project.dataforseo_depth}</Badge>
                      <span className="ml-1 tabular-nums">
                        {project.default_execution_time.slice(0, 5)} {project.default_timezone}
                      </span>
                    </div>
                    <span className="mt-0.5 block text-slate-400">
                      {project.inheriting_url_count} of {project.url_count} URL(s) follow it
                    </span>
                  </TD>
                  <TD>
                    <ActiveBadge isActive={project.is_active} />
                  </TD>
                  {!isReadOnly ? (
                    <TD align="right">
                      <div className="flex justify-end">
                        <ToggleSwitch
                          checked={project.is_active}
                          onChange={(next) => handleToggle(project, next)}
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
                          onClick={() => void openSchedule(project)}
                        >
                          Schedule
                        </Button>
                        <Button variant="secondary" size="sm" onClick={() => openEdit(project)}>
                          Edit
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(project)}>
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
            open={scheduling !== null}
            title={scheduling ? `Schedule for ${scheduling.project.name}` : 'Schedule'}
            onClose={() => setScheduling(null)}
          >
            {scheduling ? (
              <ProjectScheduleForm
                projectName={scheduling.project.name}
                schedule={scheduling.schedule}
                onSaved={() => {
                  setScheduling(null);
                  void fetchPage(page, pageSize);
                }}
              />
            ) : null}
          </Modal>

          <Modal
            open={creating}
            title="Add project"
            onClose={() => setCreating(false)}
            footer={
              <>
                <Button variant="secondary" onClick={() => setCreating(false)}>
                  Cancel
                </Button>
                <Button form="create-project-form" type="submit" disabled={saving || !name}>
                  {saving ? 'Saving...' : 'Create'}
                </Button>
              </>
            }
          >
            <form id="create-project-form" onSubmit={handleCreate} className="space-y-4" noValidate>
              <div>
                <Label htmlFor="project-client" required>Client</Label>
                <Select
                  id="project-client"
                  name="client_id"
                  value={clientId}
                  onChange={(event) => setClientId(Number(event.target.value))}
                  error={!!fieldErrors.client_id}
                  className="mt-1"
                >
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.name}
                    </option>
                  ))}
                </Select>
                <FieldError message={fieldErrors.client_id} />
              </div>
              <div>
                <Label htmlFor="project-name" required>Name</Label>
                <Input
                  id="project-name"
                  name="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Acme Website"
                  required
                  error={!!fieldErrors.name}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.name} />
              </div>
              <div>
                <Label htmlFor="project-description">Description (optional)</Label>
                <Input
                  id="project-description"
                  name="description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  error={!!fieldErrors.description}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.description} />
              </div>
              <div>
                <Label htmlFor="project-threshold" required>Default Rank Drop Trigger (positions)</Label>
                <Input
                  id="project-threshold"
                  name="rank_drop_threshold"
                  type="number"
                  min={1}
                  max={50}
                  value={rankDropThreshold}
                  onChange={(event) => setRankDropThreshold(Number(event.target.value))}
                  required
                  error={!!fieldErrors.rank_drop_threshold}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.rank_drop_threshold} />
                <p className="mt-0.5 text-xs text-slate-500">
                  Number of position drops required to trigger AI Analysis for URLs in this project (default: 3).
                </p>
              </div>
              <div>
                <Label htmlFor="project-depth" required>SERP Fetch Depth</Label>
                <Input
                  id="project-depth"
                  name="dataforseo_depth"
                  type="number"
                  min={10}
                  max={100}
                  value={depth}
                  onChange={(event) => setDepth(Number(event.target.value))}
                  required
                  error={!!fieldErrors.dataforseo_depth}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.dataforseo_depth} />
                <p className="mt-0.5 text-xs text-slate-500">
                  Number of results to fetch (10-100).
                </p>
              </div>
            </form>
          </Modal>

          <Modal
            open={editingProject !== null}
            title="Edit project"
            onClose={() => setEditingProject(null)}
            footer={
              <>
                <Button variant="secondary" onClick={() => setEditingProject(null)}>
                  Cancel
                </Button>
                <Button form="edit-project-form" type="submit" disabled={saving || !name}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </Button>
              </>
            }
          >
            <form id="edit-project-form" onSubmit={handleUpdate} className="space-y-4" noValidate>
              <div>
                <Label htmlFor="edit-project-name" required>Name</Label>
                <Input
                  id="edit-project-name"
                  name="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Acme Website"
                  required
                  error={!!fieldErrors.name}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.name} />
              </div>
              <div>
                <Label htmlFor="edit-project-description">Description (optional)</Label>
                <Input
                  id="edit-project-description"
                  name="description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  error={!!fieldErrors.description}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.description} />
              </div>
              <div>
                <Label htmlFor="edit-project-threshold" required>Default Rank Drop Trigger (positions)</Label>
                <Input
                  id="edit-project-threshold"
                  name="rank_drop_threshold"
                  type="number"
                  min={1}
                  max={50}
                  value={rankDropThreshold}
                  onChange={(event) => setRankDropThreshold(Number(event.target.value))}
                  required
                  error={!!fieldErrors.rank_drop_threshold}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.rank_drop_threshold} />
                <p className="mt-0.5 text-xs text-slate-500">
                  Number of position drops required to trigger AI Analysis for URLs in this project.
                </p>
              </div>
              <div>
                <Label htmlFor="edit-project-depth" required>SERP Fetch Depth</Label>
                <Input
                  id="edit-project-depth"
                  name="dataforseo_depth"
                  type="number"
                  min={10}
                  max={100}
                  value={depth}
                  onChange={(event) => setDepth(Number(event.target.value))}
                  required
                  error={!!fieldErrors.dataforseo_depth}
                  className="mt-1"
                />
                <FieldError message={fieldErrors.dataforseo_depth} />
                <p className="mt-0.5 text-xs text-slate-500">
                  Number of results to fetch (10-100).
                </p>
              </div>
            </form>
          </Modal>
        </>
      ) : null}
    </Card>
  );
}
