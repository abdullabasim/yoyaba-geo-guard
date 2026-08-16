'use client';

import clsx from 'clsx';
import { useState } from 'react';

interface ToggleSwitchProps {
  checked: boolean;
  onChange: (next: boolean) => Promise<void> | void;
  label?: string;
  disabled?: boolean;
}

/**
 * Optimistic is_active toggle.
 *
 * The switch flips immediately, then reverts if the API call fails, so a failed
 * pause is never silently displayed as successful.
 */
export function ToggleSwitch({ checked, onChange, label, disabled }: ToggleSwitchProps) {
  const [optimistic, setOptimistic] = useState(checked);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const value = busy ? optimistic : checked;

  async function handleClick() {
    if (busy || disabled) return;
    const next = !value;
    setOptimistic(next);
    setBusy(true);
    setError(null);
    try {
      await onChange(next);
    } catch (caught) {
      setOptimistic(!next);
      setError(caught instanceof Error ? caught.message : 'Update failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        role="switch"
        aria-checked={value}
        aria-label={label ?? 'Toggle active state'}
        disabled={disabled || busy}
        onClick={handleClick}
        className={clsx(
          'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2',
          value ? 'bg-emerald-500' : 'bg-slate-300',
          (disabled || busy) && 'cursor-not-allowed opacity-60',
        )}
      >
        <span
          className={clsx(
            'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition',
            value ? 'translate-x-5' : 'translate-x-0',
          )}
        />
      </button>
      {label ? <span className="text-sm text-slate-600">{label}</span> : null}
      {error ? <span className="text-xs text-red-600">{error}</span> : null}
    </div>
  );
}
