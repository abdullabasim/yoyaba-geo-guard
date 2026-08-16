'use client';

import clsx from 'clsx';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader, StatCard } from '@/components/ui/Card';
import { Alert, Button, Input, Label } from '@/components/ui/Form';
import { controlsApi } from '@/lib/api';
import type { ContainerStatus, ServiceControl, SystemStatus, User } from '@/lib/types';

/**
 * Service control panel.
 *
 * Two distinct halves, kept visually separate because they differ in kind:
 *
 * 1. Kill switches — things you CAN stop. Persisted in the database and read by
 *    the worker on every task, so a pause takes effect within seconds without a
 *    restart or shell access.
 * 2. Process status — read-only. Containers are deliberately not controllable
 *    from the browser: doing so needs the Docker socket mounted into the
 *    backend, which is equivalent to giving the web app root on the host.
 */

function statusTone(status: string): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'running' || status === 'active' || status === 'scheduled') return 'success';
  if (status === 'idle' || status === 'unknown') return 'neutral';
  if (status === 'paused') return 'warning';
  return 'danger';
}

function ControlRow({
  control,
  onChanged,
  isReadOnly,
}: {
  control: ServiceControl;
  onChanged: (updated: ServiceControl) => void;
  isReadOnly: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showReason, setShowReason] = useState(false);
  const [reason, setReason] = useState('');

  const isMaster = control.service_key === 'SCHEDULER';

  async function apply(nextEnabled: boolean, withReason?: string) {
    if (isReadOnly) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await controlsApi.setEnabled(
        control.service_key,
        nextEnabled,
        withReason,
      );
      onChanged(updated);
      setShowReason(false);
      setReason('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Update failed');
    } finally {
      setBusy(false);
    }
  }

  function handleToggleClick() {
    if (isReadOnly) return;
    if (control.is_enabled) {
      setShowReason(true);
      return;
    }
    void apply(true);
  }

  return (
    <div
      className={clsx(
        'rounded-lg border p-4',
        control.is_enabled ? 'border-slate-200 dark:border-yoyaba-border bg-white dark:bg-[#0B0F19]/50' : 'border-amber-300 dark:border-amber-700/50 bg-amber-50 dark:bg-amber-900/10',
        isMaster && 'ring-1 ring-inset ring-brand-200',
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">{control.display_name}</h3>
            {isMaster ? <Badge tone="brand">Master switch</Badge> : null}
            <Badge tone={control.is_enabled ? 'success' : 'warning'}>
              {control.is_enabled ? 'Running' : 'Paused'}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-slate-600">{control.summary}</p>
          <p className="mt-1 text-xs text-slate-500">{control.impact}</p>

          {!control.is_enabled ? (
            <p className="mt-2 rounded bg-white/70 dark:bg-transparent px-2 py-1 text-xs text-amber-900 dark:text-amber-400">
              Paused
              {control.paused_by ? ` by ${control.paused_by}` : ''}
              {control.paused_at
                ? ` on ${new Date(control.paused_at).toLocaleString()}`
                : ''}
              {control.paused_reason ? ` — ${control.paused_reason}` : ''}
            </p>
          ) : null}
        </div>

        {!isReadOnly ? (
          <div className="shrink-0">
            <Button
              variant={control.is_enabled ? 'secondary' : 'primary'}
              size="sm"
              disabled={busy}
              onClick={handleToggleClick}
            >
              {busy ? 'Saving...' : control.is_enabled ? 'Pause' : 'Resume'}
            </Button>
          </div>
        ) : null}
      </div>

      {!isReadOnly && showReason ? (
        <form
          className="mt-3 flex flex-wrap items-end gap-2 border-t border-amber-200 pt-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (!reason.trim()) return;
            void apply(false, reason.trim());
          }}
        >
          <div className="min-w-[16rem] flex-1">
            <Label htmlFor={`reason-${control.service_key}`}>
              Why are you pausing this?
            </Label>
            <Input
              id={`reason-${control.service_key}`}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="e.g. provider balance exhausted, waiting for top-up"
              required
              className="mt-1"
            />
          </div>
          <Button type="submit" variant="danger" size="sm" disabled={busy || !reason.trim()}>
            Confirm pause
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setShowReason(false)}
          >
            Cancel
          </Button>
        </form>
      ) : null}

      {error ? (
        <div className="mt-2">
          <Alert tone="error">{error}</Alert>
        </div>
      ) : null}
    </div>
  );
}

function ProcessRow({ container }: { container: ContainerStatus }) {
  return (
    <tr className="border-b border-slate-100 dark:border-yoyaba-border text-sm">
      <td className="px-3 py-2.5 font-mono text-xs text-slate-900 dark:text-slate-200">{container.name}</td>
      <td className="px-3 py-2.5 text-xs text-slate-600 dark:text-slate-400">{container.role}</td>
      <td className="px-3 py-2.5">
        <Badge tone={statusTone(container.status)}>{container.status}</Badge>
      </td>
      <td className="px-3 py-2.5 text-xs text-slate-500">{container.detail}</td>
    </tr>
  );
}

export function ServiceControls({
  initial,
  currentUser,
}: {
  initial: SystemStatus;
  currentUser?: User;
}) {
  const [controls, setControls] = useState<ServiceControl[]>(initial.controls);
  const containers = initial.containers;

  const isReadOnly = currentUser?.role === 'read_only' || (!currentUser?.is_superuser && currentUser?.role !== 'read_write');

  function handleChanged(updated: ServiceControl) {
    setControls((current) =>
      current.map((row) => (row.id === updated.id ? updated : row)),
    );
  }

  const enabled = controls.filter((c) => c.is_enabled);
  const paused = controls.filter((c) => !c.is_enabled);
  const schedulerPaused = controls.some(
    (c) => c.service_key === 'SCHEDULER' && !c.is_enabled,
  );

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Subsystems active"
          value={`${enabled.length} of ${controls.length}`}
          tone={enabled.length === controls.length ? 'success' : 'warning'}
        />
        <StatCard
          label="Subsystems paused"
          value={paused.length}
          tone={paused.length > 0 ? 'warning' : 'default'}
        />
        <StatCard
          label="Automation"
          value={schedulerPaused ? 'Halted' : 'Active'}
          tone={schedulerPaused ? 'danger' : 'success'}
          hint={
            schedulerPaused
              ? 'The master switch is off; nothing is dispatched'
              : 'Scheduled checks are being dispatched'
          }
        />
      </div>

      {schedulerPaused ? (
        <Alert tone="warning">
          The master scheduler is paused, so no scheduled checks run regardless of the
          individual switches below.
        </Alert>
      ) : null}

      <Card>
        <CardHeader
          title="Service controls"
          description={
            isReadOnly
              ? "Status view of pipeline subsystems."
              : "Pause or resume individual parts of the pipeline. Changes take effect within seconds — no restart needed."
          }
        />
        <CardBody className="space-y-3">
          {controls.map((control) => (
            <ControlRow
              key={control.id}
              control={control}
              onChanged={handleChanged}
              isReadOnly={isReadOnly}
            />
          ))}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Process status"
          description="Read-only. Container liveness view."
        />
        <CardBody>
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-slate-200 dark:border-yoyaba-border text-left text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  <th className="px-3 py-2">Process</th>
                  <th className="px-3 py-2">Role</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Detail</th>
                </tr>
              </thead>
              <tbody>
                {containers.map((container) => (
                  <ProcessRow key={container.name} container={container} />
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
