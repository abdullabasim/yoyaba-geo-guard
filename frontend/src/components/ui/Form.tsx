import clsx from 'clsx';
import type { ButtonHTMLAttributes, InputHTMLAttributes, SelectHTMLAttributes } from 'react';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md';
};

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  ...props
}: ButtonProps) {
  const variants = {
    primary: 'bg-yoyaba-yellow text-black hover:bg-[#E6C100] disabled:opacity-50 shadow-sm font-bold',
    secondary:
      'bg-white dark:bg-transparent text-slate-700 dark:text-slate-300 ring-1 ring-inset ring-slate-300 dark:ring-yoyaba-border hover:bg-slate-50 dark:hover:bg-slate-800/50 disabled:opacity-50',
    danger: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300 dark:disabled:opacity-50',
    ghost: 'bg-transparent text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/50',
  }[variant];

  const sizes = { sm: 'px-2.5 py-1 text-xs', md: 'px-3.5 py-2 text-sm' }[size];

  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors',
        'focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1',
        'disabled:cursor-not-allowed',
        variants,
        sizes,
        className,
      )}
      {...props}
    />
  );
}

export function Label({
  children,
  htmlFor,
  required,
}: {
  children: React.ReactNode;
  htmlFor?: string;
  required?: boolean;
}) {
  return (
    <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-700 dark:text-slate-300">
      {children}
      {required ? <span className="ml-1 text-rose-500 font-bold">*</span> : null}
    </label>
  );
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
}

export function Input({ className, error, ...props }: InputProps) {
  return (
    <input
      className={clsx(
        'block w-full rounded-md border-0 px-3 py-2 text-sm text-slate-900 bg-white dark:text-slate-100 shadow-sm dark:bg-[#0B0F19]/50',
        error
          ? 'ring-2 ring-inset ring-red-500 dark:ring-red-500 focus:ring-red-500 dark:focus:ring-red-500'
          : 'ring-1 dark:ring-2 ring-inset ring-slate-300 dark:ring-yoyaba-yellow focus:ring-2 focus:ring-inset focus:ring-brand-500 dark:focus:ring-yoyaba-yellow',
        'placeholder:text-slate-400 dark:placeholder:text-slate-300',
        'disabled:bg-slate-50 dark:disabled:bg-slate-900/50 disabled:text-slate-400 dark:disabled:text-slate-600',
        className,
      )}
      {...props}
    />
  );
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  error?: boolean;
}

export function Select({ className, error, children, ...props }: SelectProps) {
  return (
    <select
      className={clsx(
        'block w-full rounded-md border-0 px-3 py-2 text-sm text-slate-900 bg-white dark:text-slate-100 shadow-sm dark:bg-[#0B0F19]/50',
        error
          ? 'ring-2 ring-inset ring-red-500 dark:ring-red-500 focus:ring-red-500 dark:focus:ring-red-500'
          : 'ring-1 ring-inset ring-slate-300 dark:ring-yoyaba-border focus:ring-2 focus:ring-inset focus:ring-brand-500 dark:focus:ring-yoyaba-yellow',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function FieldError({ message }: { message?: string | null }) {
  if (!message) return null;
  return <p className="mt-1 text-xs font-medium text-red-600 dark:text-red-400">{message}</p>;
}

export function Alert({
  tone = 'error',
  children,
}: {
  tone?: 'error' | 'success' | 'info' | 'warning';
  children: React.ReactNode;
}) {
  const styles = {
    error: 'bg-red-50 text-red-800 ring-red-200',
    success: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
    info: 'bg-brand-50 text-brand-800 ring-brand-200',
    warning: 'bg-amber-50 text-amber-800 ring-amber-200',
  }[tone];

  return (
    <div className={clsx('rounded-md px-3 py-2 text-sm ring-1 ring-inset', styles)}>
      {children}
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={clsx(
        'inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent',
        className,
      )}
      role="status"
      aria-label="Loading"
    />
  );
}
