'use client';

import { useState } from 'react';

import { Alert, Button, FieldError, Input, Label, Select } from '@/components/ui/Form';
import { ApiError, urlsApi } from '@/lib/api';
import type { CheckInterval, ProjectSchedule, TargetUrl } from '@/lib/types';

/**
 * Per-URL scheduling form.
 *
 * A URL either follows its project's default or keeps its own schedule. The own
 * columns are always submitted so that turning inheritance off restores a real
 * schedule instead of a blank one.
 */

const INTERVALS: Array<{ value: CheckInterval; label: string; hint: string }> = [
  { value: 'daily', label: 'Daily', hint: 'checked every day' },
  { value: 'weekly', label: 'Weekly', hint: 'checked every 7 days' },
  { value: 'monthly', label: 'Monthly', hint: 'checked every 30 days' },
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
  // Backend returns HH:MM:SS; <input type="time"> wants HH:MM.
  return value.slice(0, 5);
}

export function ScheduleForm({
  targetUrl,
  projectSchedule,
  onSaved,
}: {
  targetUrl: TargetUrl;
  projectSchedule?: ProjectSchedule | null;
  onSaved?: (updated: TargetUrl) => void;
}) {
  const [inherit, setInherit] = useState(targetUrl.inherit_schedule);
  const [interval, setInterval] = useState<CheckInterval>(targetUrl.check_interval);
  const [executionTime, setExecutionTime] = useState(toTimeInput(targetUrl.execution_time));
  const [timezone, setTimezone] = useState(targetUrl.timezone);
  const [threshold, setThreshold] = useState<string>(
    targetUrl.rank_drop_threshold !== null && targetUrl.rank_drop_threshold !== undefined
      ? String(targetUrl.rank_drop_threshold)
      : '',
  );
  const [depth, setDepth] = useState<string>(
    targetUrl.dataforseo_depth !== null && targetUrl.dataforseo_depth !== undefined
      ? String(targetUrl.dataforseo_depth)
      : '',
  );
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
      // The URL's own columns are always sent, even when inheriting, so that
      // switching inheritance off later restores a real schedule rather than a
      // blank one.
      const updated = await urlsApi.updateSchedule(targetUrl.id, {
        check_interval: interval,
        execution_time: `${executionTime}:00`,
        timezone,
        rank_drop_threshold: threshold.trim() ? Number(threshold) : null,
        dataforseo_depth: depth.trim() ? Number(depth) : null,
        inherit_schedule: inherit,
      });
      setMessage({
        tone: 'success',
        text: inherit
          ? 'Saved. This URL now follows its project schedule.'
          : 'Saved. This URL uses its own schedule.',
      });
      onSaved?.(updated);
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        setFieldErrors(caught.fieldErrors);
      }
      setMessage({
        tone: 'error',
        text: caught instanceof Error ? caught.message : 'Failed to save schedule',
      });
    } finally {
      setSaving(false);
    }
  }

  const effectiveInterval = inherit
    ? projectSchedule?.default_check_interval ?? targetUrl.effective_check_interval ?? interval
    : interval;
  const effectiveTime = inherit
    ? toTimeInput(
        projectSchedule?.default_execution_time ??
          targetUrl.effective_execution_time ??
          targetUrl.execution_time,
      )
    : executionTime;
  const effectiveZone = inherit
    ? projectSchedule?.default_timezone ?? targetUrl.effective_timezone ?? timezone
    : timezone;

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <label className="flex items-start gap-2 rounded border border-slate-200 dark:border-yoyaba-border bg-slate-50 dark:bg-[#111827]/50 px-3 py-2 text-sm cursor-pointer hover:bg-slate-100 dark:hover:bg-[#111827] transition-colors">
        <input
          type="checkbox"
          checked={inherit}
          onChange={(event) => setInherit(event.target.checked)}
          className="mt-1 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-600 dark:border-slate-600 dark:bg-slate-900 dark:text-yoyaba-yellow dark:focus:ring-yoyaba-yellow dark:focus:ring-offset-slate-900 cursor-pointer"
        />
        <span>
          <span className="font-medium text-slate-800 dark:text-slate-200">
            Follow the project&apos;s default schedule
          </span>
          <span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400">
            Recommended. Changing the project schedule then reschedules this URL
            automatically. Uncheck to stagger this URL separately.
          </span>
        </span>
      </label>

      <fieldset disabled={inherit} className={inherit ? 'opacity-50' : undefined}>
        <div className="grid items-start gap-4 sm:grid-cols-3">
          <div>
            <Label htmlFor="sched-interval" required={!inherit}>
              Interval
            </Label>
            <Select
              id="sched-interval"
              name="check_interval"
              value={effectiveInterval}
              onChange={(event) => setInterval(event.target.value as CheckInterval)}
              disabled={inherit}
              error={!!fieldErrors.check_interval}
              className="mt-1"
            >
              {INTERVALS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
            <FieldError message={fieldErrors.check_interval} />
          </div>
          <div>
            <Label htmlFor="sched-time" required={!inherit}>
              Local Time
            </Label>
            <Input
              id="sched-time"
              name="execution_time"
              type="time"
              value={effectiveTime}
              onChange={(event) => setExecutionTime(event.target.value)}
              disabled={inherit}
              error={!!fieldErrors.execution_time}
              className="mt-1"
            />
            <FieldError message={fieldErrors.execution_time} />
          </div>
          <div>
            <Label htmlFor="sched-tz" required={!inherit}>
              Timezone
            </Label>
            <Select
              id="sched-tz"
              name="timezone"
              value={effectiveZone}
              onChange={(event) => setTimezone(event.target.value)}
              disabled={inherit}
              error={!!fieldErrors.timezone}
              className="mt-1"
            >
              {timezoneOptions.map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </Select>
            <FieldError message={fieldErrors.timezone} />
          </div>
        </div>

        <div className="grid items-start gap-4 sm:grid-cols-2 mt-4">
          <div>
            <Label htmlFor={`drop-${targetUrl.id}`} required={!inherit}>Custom Rank Drop Trigger (positions)</Label>
            <Input
              id={`drop-${targetUrl.id}`}
              name="rank_drop_threshold"
              type="number"
              min={1}
              max={50}
              placeholder="Inherit project"
              value={threshold}
              onChange={(event) => setThreshold(event.target.value)}
              disabled={inherit}
              error={!!fieldErrors.rank_drop_threshold}
              className="mt-1"
            />
            <FieldError message={fieldErrors.rank_drop_threshold} />
            <p className="mt-0.5 text-xs text-slate-500">
              Overrides the project's default drop threshold. Leave empty to inherit.
            </p>
          </div>
          <div>
            <Label htmlFor={`depth-${targetUrl.id}`} required={!inherit}>Custom Fetch Depth</Label>
            <Input
              id={`depth-${targetUrl.id}`}
              name="dataforseo_depth"
              type="number"
              min={10}
              max={100}
              placeholder="Inherit project"
              value={depth}
              onChange={(event) => setDepth(event.target.value)}
              disabled={inherit}
              error={!!fieldErrors.dataforseo_depth}
              className="mt-1"
            />
            <FieldError message={fieldErrors.dataforseo_depth} />
            <p className="mt-0.5 text-xs text-slate-500">
              Overrides the project's default depth. Leave empty to inherit.
            </p>
          </div>
        </div>
      </fieldset>

      <p className="text-xs text-slate-500">
        {inherit ? 'Following the project default: ' : 'Using its own schedule: '}
        checked <span className="font-medium">{effectiveInterval}</span> when local time in{' '}
        <span className="font-medium">{effectiveZone}</span> reaches{' '}
        <span className="font-medium">{effectiveTime}</span> and the interval has elapsed
        since the last check.
      </p>

      {message ? (
        <Alert tone={message.tone === 'success' ? 'success' : 'error'}>{message.text}</Alert>
      ) : null}

      <div className="flex justify-end">
        <Button type="submit" disabled={saving}>
          {saving ? 'Saving...' : 'Save schedule'}
        </Button>
      </div>
    </form>
  );
}
