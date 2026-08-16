'use client';

import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Alert, Button, FieldError, Input, Label, Select } from '@/components/ui/Form';
import { ApiError, projectsApi } from '@/lib/api';
import type { CheckInterval, ProjectSchedule } from '@/lib/types';

/**
 * Project-level cron defaults.
 *
 * Every URL with "inherit schedule" on follows these values, so editing here
 * reschedules the whole project at once. URLs deliberately staggered across the
 * day keep their own times unless `apply_to_all_urls` is used — which is why
 * that option is off by default and warns before it fires.
 */

const INTERVALS: Array<{ value: CheckInterval; label: string; hint: string }> = [
  { value: 'daily', label: 'Daily', hint: 'every day' },
  { value: 'weekly', label: 'Weekly', hint: 'every 7 days' },
  { value: 'monthly', label: 'Monthly', hint: 'every 30 days' },
];

const COMMON_TIMEZONES = [
  'Europe/Berlin',
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Berlin',
  'Europe/Madrid',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Sydney',
];

function toTimeInput(value: string): string {
  return value.slice(0, 5);
}

export function ProjectScheduleForm({
  projectName,
  schedule,
  onSaved,
}: {
  projectName: string;
  schedule: ProjectSchedule;
  onSaved?: (updated: ProjectSchedule) => void;
}) {
  const [interval, setIntervalValue] = useState<CheckInterval>(
    schedule.default_check_interval,
  );
  const [executionTime, setExecutionTime] = useState(
    toTimeInput(schedule.default_execution_time),
  );
  const [timezone, setTimezone] = useState(schedule.default_timezone);
  const [threshold, setThreshold] = useState(schedule.rank_drop_threshold || 3);
  const [depth, setDepth] = useState(schedule.dataforseo_depth || 10);
  const [applyToAll, setApplyToAll] = useState(false);
  const [counts, setCounts] = useState({
    inheriting: schedule.inheriting_url_count,
    overriding: schedule.overriding_url_count,
  });
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(
    null,
  );

  const timezoneOptions = COMMON_TIMEZONES.includes(timezone)
    ? COMMON_TIMEZONES
    : [timezone, ...COMMON_TIMEZONES];

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setMessage(null);
    setFieldErrors({});
    try {
      const updated = await projectsApi.updateSchedule(schedule.project_id, {
        default_check_interval: interval,
        default_execution_time: `${executionTime}:00`,
        default_timezone: timezone,
        rank_drop_threshold: Number(threshold),
        dataforseo_depth: Number(depth),
        apply_to_all_urls: applyToAll,
      });
      setCounts({
        inheriting: updated.inheriting_url_count,
        overriding: updated.overriding_url_count,
      });
      setApplyToAll(false);
      setMessage({
        tone: 'success',
        text: `Saved. ${updated.inheriting_url_count} URL(s) now follow this schedule.`,
      });
      onSaved?.(updated);
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        setFieldErrors(caught.fieldErrors);
      }
      setMessage({
        tone: 'error',
        text: caught instanceof Error ? caught.message : 'Failed to save project schedule',
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Badge tone="brand">{counts.inheriting} inheriting</Badge>
        <Badge tone={counts.overriding > 0 ? 'warning' : 'neutral'}>
          {counts.overriding} with their own schedule
        </Badge>
      </div>

      <div className="grid items-start gap-4 sm:grid-cols-5">
        <div>
          <Label htmlFor={`p-interval-${schedule.project_id}`} required>Interval</Label>
          <Select
            id={`p-interval-${schedule.project_id}`}
            name="default_check_interval"
            value={interval}
            onChange={(event) => setIntervalValue(event.target.value as CheckInterval)}
            error={!!fieldErrors.default_check_interval}
            className="mt-1"
          >
            {INTERVALS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
          <FieldError message={fieldErrors.default_check_interval} />
        </div>

        <div>
          <Label htmlFor={`p-time-${schedule.project_id}`} required>Execution Time (Local)</Label>
          <Input
            id={`p-time-${schedule.project_id}`}
            name="default_execution_time"
            type="time"
            value={executionTime}
            onChange={(event) => setExecutionTime(event.target.value)}
            required
            error={!!fieldErrors.default_execution_time}
            className="mt-1"
          />
          <FieldError message={fieldErrors.default_execution_time} />
        </div>

        <div>
          <Label htmlFor={`p-tz-${schedule.project_id}`} required>Timezone</Label>
          <Select
            id={`p-tz-${schedule.project_id}`}
            name="default_timezone"
            value={timezone}
            onChange={(event) => setTimezone(event.target.value)}
            error={!!fieldErrors.default_timezone}
            className="mt-1"
          >
            {timezoneOptions.map((zone) => (
              <option key={zone} value={zone}>
                {zone}
              </option>
            ))}
          </Select>
          <FieldError message={fieldErrors.default_timezone} />
        </div>

        <div>
          <Label htmlFor={`p-threshold-${schedule.project_id}`} required>Rank Drop Trigger</Label>
          <Input
            id={`p-threshold-${schedule.project_id}`}
            name="rank_drop_threshold"
            type="number"
            min={1}
            max={50}
            value={threshold}
            onChange={(event) => setThreshold(Number(event.target.value))}
            required
            error={!!fieldErrors.rank_drop_threshold}
            className="mt-1"
          />
          <FieldError message={fieldErrors.rank_drop_threshold} />
          <span className="mt-0.5 block text-[10px] text-slate-500">Drop of N positions triggers AI</span>
        </div>

        <div>
          <Label htmlFor={`p-depth-${schedule.project_id}`} required>SERP Fetch Depth</Label>
          <Input
            id={`p-depth-${schedule.project_id}`}
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
          <span className="mt-0.5 block text-[10px] text-slate-500">Number of results (10-100)</span>
        </div>
      </div>

      <p className="text-xs text-slate-500">
        URLs in <span className="font-medium">{projectName}</span> that inherit this schedule
        are checked when local time in <span className="font-medium">{timezone}</span> reaches{' '}
        <span className="font-medium">{executionTime}</span> and the interval has elapsed.
      </p>

      {counts.overriding > 0 ? (
        <label className="flex items-start gap-2 rounded border border-amber-200 dark:border-amber-700/50 bg-amber-50 dark:bg-amber-900/20 px-3 py-2 text-xs text-amber-900 dark:text-amber-200 cursor-pointer hover:bg-amber-100 dark:hover:bg-amber-900/40 transition-colors">
          <input
            type="checkbox"
            checked={applyToAll}
            onChange={(event) => setApplyToAll(event.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-amber-300 text-amber-600 focus:ring-amber-600 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-500 dark:focus:ring-amber-500 dark:focus:ring-offset-amber-950 cursor-pointer"
          />
          <span>
            Also force the {counts.overriding} URL(s) with their own schedule to follow this
            default. This discards their individual times, which were probably set to stagger
            provider load.
          </span>
        </label>
      ) : null}

      {message ? (
        <Alert tone={message.tone === 'success' ? 'success' : 'error'}>{message.text}</Alert>
      ) : null}

      <div className="flex justify-end">
        <Button type="submit" disabled={saving}>
          {saving ? 'Saving...' : 'Save project schedule'}
        </Button>
      </div>
    </form>
  );
}
