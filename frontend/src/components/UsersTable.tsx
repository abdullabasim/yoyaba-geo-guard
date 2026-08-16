'use client';

import { useState } from 'react';

import { ActiveBadge, Badge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Alert, Button, FieldError, Input, Label, Select } from '@/components/ui/Form';
import { Modal } from '@/components/ui/Modal';
import { Pagination } from '@/components/ui/Pagination';
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table';
import { ToggleSwitch } from '@/components/ui/ToggleSwitch';
import { ApiError, usersApi } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import type { Page, User, UserRole } from '@/lib/types';

export function UsersTable({
  initialPage,
  currentUser,
}: {
  initialPage: Page<User>;
  currentUser: User;
}) {
  const [users, setUsers] = useState<User[]>(initialPage.items);
  const [total, setTotal] = useState(initialPage.total);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPage.limit || 10);
  const [loading, setLoading] = useState(false);

  const [sortBy, setSortBy] = useState<string>('email');
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
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState<UserRole>('read_write');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const isCurrentUserReadOnly = currentUser.role === 'read_only' || (!currentUser.is_superuser && currentUser.role !== 'read_write');

  async function fetchPage(targetPage: number, targetSize: number) {
    setLoading(true);
    try {
      const skip = (targetPage - 1) * targetSize;
      const res = await usersApi.list(skip, targetSize);
      setUsers(res.items);
      setTotal(res.total);
      setPage(targetPage);
      setPageSize(targetSize);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to fetch users');
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle(user: User, isActive: boolean) {
    if (user.is_main_account) {
      setError('The main admin account cannot be deactivated.');
      return;
    }
    setError(null);
    try {
      await usersApi.toggle(user.id, isActive);
      setUsers((current) =>
        current.map((item) => (item.id === user.id ? { ...item, is_active: isActive } : item)),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to update user status');
    }
  }

  async function handleRoleChange(user: User, newRole: UserRole) {
    if (user.is_main_account && newRole === 'read_only') {
      setError('The main admin account role cannot be changed to read-only.');
      return;
    }
    setError(null);
    try {
      await usersApi.update(user.id, { role: newRole });
      setUsers((current) =>
        current.map((item) =>
          item.id === user.id ? { ...item, role: newRole, is_superuser: newRole === 'read_write' } : item,
        ),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to update user role');
    }
  }

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      await usersApi.create({
        email,
        password,
        full_name: fullName || null,
        role,
      });
      setEmail('');
      setPassword('');
      setFullName('');
      setRole('read_write');
      setCreating(false);
      await fetchPage(1, pageSize);
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        setFieldErrors(caught.fieldErrors);
      }
      setError(caught instanceof Error ? caught.message : 'Failed to create user');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(user: User) {
    if (user.is_main_account) {
      setError('The main admin account cannot be deleted.');
      return;
    }
    if (user.id === currentUser.id) {
      setError('You cannot delete your own logged-in account.');
      return;
    }
    const confirmed = window.confirm(`Delete user "${user.email}"?`);
    if (!confirmed) return;
    setError(null);
    try {
      await usersApi.remove(user.id);
      await fetchPage(page, pageSize);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to delete user');
    }
  }

  return (
    <Card>
      <CardHeader
        title="User Accounts"
        description="System access and permissions (Read Only vs Read & Write)"
        action={
          <Button
            size="sm"
            onClick={() => setCreating(true)}
            disabled={isCurrentUserReadOnly}
          >
            Add user
          </Button>
        }
      />
      <div className="border-b border-slate-200 dark:border-yoyaba-border bg-slate-50/80 dark:bg-slate-800/40 p-4">
        <div className="relative max-w-md">
          <Input
            type="text"
            placeholder="Search users by email, name, role..."
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

        {isCurrentUserReadOnly ? (
          <div className="px-5 py-4">
            <Alert tone="warning">
              You are logged in as a <strong>Read Only</strong> user. Managing user accounts requires Read & Write admin permissions.
            </Alert>
          </div>
        ) : null}

        <Table className={loading ? 'opacity-50 pointer-events-none' : ''}>
          <THead>
            <TR>
              <TH sortable sortActive={sortBy === 'email'} sortOrder={sortOrder} onSort={() => handleSort('email')}>Email / Name</TH>
              <TH sortable sortActive={sortBy === 'is_superuser'} sortOrder={sortOrder} onSort={() => handleSort('is_superuser')}>Type</TH>
              <TH sortable sortActive={sortBy === 'role'} sortOrder={sortOrder} onSort={() => handleSort('role')}>Permission Level</TH>
              <TH sortable sortActive={sortBy === 'created_at'} sortOrder={sortOrder} onSort={() => handleSort('created_at')}>Created</TH>
              <TH sortable sortActive={sortBy === 'is_active'} sortOrder={sortOrder} onSort={() => handleSort('is_active')}>Status</TH>
              <TH align="right">Active</TH>
              <TH />
            </TR>
          </THead>
          <TBody>
            {users
              .filter((item) => {
                if (!search.trim()) return true;
                const q = search.toLowerCase();
                return (
                  item.email.toLowerCase().includes(q) ||
                  (item.full_name ?? '').toLowerCase().includes(q) ||
                  item.role.toLowerCase().includes(q)
                );
              })
              .length === 0 ? (
              <EmptyRow colSpan={7} message="No user accounts match your search." />
            ) : (
              users
                .filter((item) => {
                  if (!search.trim()) return true;
                  const q = search.toLowerCase();
                  return (
                    item.email.toLowerCase().includes(q) ||
                    (item.full_name ?? '').toLowerCase().includes(q) ||
                    item.role.toLowerCase().includes(q)
                  );
                })
                .map((user) => {
                const isMain = user.is_main_account || user.id === 1;
                const isReadOnlyRole = user.role === 'read_only' || (!user.is_superuser && user.role !== 'read_write');
                return (
                  <TR key={user.id}>
                    <TD className="font-medium text-slate-900 dark:text-slate-100">
                      <div>
                        <span>{user.email}</span>
                        {user.full_name ? (
                          <p className="text-xs font-normal text-slate-500 dark:text-slate-400">{user.full_name}</p>
                        ) : null}
                      </div>
                    </TD>
                    <TD>
                      {isMain ? (
                        <Badge tone="brand">Main Admin</Badge>
                      ) : (
                        <span className="text-xs text-slate-500 dark:text-slate-400">Standard User</span>
                      )}
                    </TD>
                    <TD>
                      {isMain || isCurrentUserReadOnly ? (
                        <Badge tone={isReadOnlyRole ? 'neutral' : 'success'}>
                          {isReadOnlyRole ? 'Read Only' : 'Read & Write'}
                        </Badge>
                      ) : (
                        <Select
                          value={user.role ?? (user.is_superuser ? 'read_write' : 'read_only')}
                          onChange={(e) => void handleRoleChange(user, e.target.value as UserRole)}
                          className="w-32 py-1 text-xs"
                          aria-label="Account permission role"
                        >
                          <option value="read_write">Read & Write</option>
                          <option value="read_only">Read Only</option>
                        </Select>
                      )}
                    </TD>
                    <TD className="whitespace-nowrap text-xs">
                      {user.created_at ? formatDateTime(user.created_at) : '-'}
                    </TD>
                    <TD>
                      <ActiveBadge isActive={user.is_active} />
                    </TD>
                    <TD align="right">
                      <div className="flex justify-end">
                        <ToggleSwitch
                          checked={user.is_active}
                          onChange={(next) => void handleToggle(user, next)}
                          disabled={isMain || isCurrentUserReadOnly}
                          label={undefined}
                        />
                      </div>
                    </TD>
                    <TD align="right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void handleDelete(user)}
                        disabled={isMain || user.id === currentUser.id || isCurrentUserReadOnly}
                        title={
                          isMain
                            ? 'Main admin account cannot be deleted'
                            : user.id === currentUser.id
                            ? 'Cannot delete logged in account'
                            : 'Delete user'
                        }
                      >
                        Delete
                      </Button>
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
          onPageChange={(newPage) => void fetchPage(newPage, pageSize)}
          onPageSizeChange={(newSize) => void fetchPage(1, newSize)}
        />
      </CardBody>

      <Modal
        open={creating}
        title="Add system user"
        onClose={() => setCreating(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button form="create-user-form" type="submit" disabled={saving || !email || !password}>
              {saving ? 'Creating...' : 'Create user'}
            </Button>
          </>
        }
      >
        <form id="create-user-form" onSubmit={handleCreate} className="space-y-4" noValidate>
          <div>
            <Label htmlFor="user-email" required>Email address</Label>
            <Input
              id="user-email"
              name="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="jane@example.com"
              required
              error={!!fieldErrors.email}
              className="mt-1"
            />
            <FieldError message={fieldErrors.email} />
          </div>
          <div>
            <Label htmlFor="user-name">Full name (optional)</Label>
            <Input
              id="user-name"
              name="full_name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Jane Doe"
              error={!!fieldErrors.full_name}
              className="mt-1"
            />
            <FieldError message={fieldErrors.full_name} />
          </div>
          <div>
            <Label htmlFor="user-role" required>Account Role</Label>
            <Select
              id="user-role"
              name="role"
              value={role}
              onChange={(event) => setRole(event.target.value as UserRole)}
              error={!!fieldErrors.role}
              className="mt-1"
            >
              <option value="read_write">Read/Write (Standard)</option>
              <option value="read_only">Read Only (Client/Guest)</option>
            </Select>
            <FieldError message={fieldErrors.role} />
          </div>
          <div>
            <Label htmlFor="user-password" required>Initial password</Label>
            <Input
              id="user-password"
              name="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              error={!!fieldErrors.password}
              className="mt-1"
            />
            <FieldError message={fieldErrors.password} />
            <p className="mt-1 text-xs text-slate-500">
              Must be at least 8 characters. The user can change this later.
            </p>
          </div>
        </form>
      </Modal>
    </Card>
  );
}
