import clsx from 'clsx';
import type { ReactNode } from 'react';

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-yoyaba-border">
      <table className={clsx('w-full divide-y divide-slate-200 dark:divide-yoyaba-border text-sm', className)}>
        {children}
      </table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return <thead className="bg-slate-50 dark:bg-[#0B0F19]/80 backdrop-blur-md">{children}</thead>;
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-slate-100 dark:divide-yoyaba-border bg-white dark:bg-transparent">{children}</tbody>;
}

export function TR({
  children,
  className,
  onClick,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <tr onClick={onClick} className={clsx('hover:bg-slate-50 dark:hover:bg-[#0f2a36]/50 transition-colors', className, onClick && 'cursor-pointer')}>
      {children}
    </tr>
  );
}

export function TH({
  children,
  align = 'left',
  className,
  sortable,
  sortActive,
  sortOrder,
  onSort,
}: {
  children?: ReactNode;
  align?: 'left' | 'right' | 'center';
  className?: string;
  sortable?: boolean;
  sortActive?: boolean;
  sortOrder?: 'asc' | 'desc';
  onSort?: () => void;
}) {
  return (
    <th
      scope="col"
      onClick={sortable ? onSort : undefined}
      className={clsx(
        'px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400',
        align === 'right' && 'text-right',
        align === 'center' && 'text-center',
        align === 'left' && 'text-left',
        sortable && 'cursor-pointer select-none hover:bg-slate-100 dark:hover:bg-[#0f2a36]/50 hover:text-slate-900 dark:hover:text-slate-200 transition-colors',
        sortActive && 'text-brand-700 dark:text-yoyaba-yellow bg-brand-50/50 dark:bg-yoyaba-yellow/10 font-bold',
        className,
      )}
    >
      <div
        className={clsx(
          'inline-flex items-center gap-1.5',
          align === 'right' && 'justify-end',
          align === 'center' && 'justify-center',
        )}
      >
        <span>{children}</span>
        {sortable ? (
          <span className="text-[11px] leading-none font-mono">
            {sortActive ? (
              sortOrder === 'asc' ? (
                <span className="text-brand-600 font-bold">▲</span>
              ) : (
                <span className="text-brand-600 font-bold">▼</span>
              )
            ) : (
              <span className="text-slate-300 opacity-60">↕</span>
            )}
          </span>
        ) : null}
      </div>
    </th>
  );
}

export function TD({
  children,
  align = 'left',
  className,
  title,
}: {
  children?: ReactNode;
  align?: 'left' | 'right' | 'center';
  className?: string;
  title?: string;
}) {
  return (
    <td
      title={title}
      className={clsx(
        'px-4 py-3 text-slate-700 dark:text-slate-300',
        align === 'right' && 'text-right',
        align === 'center' && 'text-center',
        className,
      )}
    >
      {children}
    </td>
  );
}

export function EmptyRow({ colSpan, message }: { colSpan: number; message: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-10 text-center text-sm text-slate-400">
        {message}
      </td>
    </tr>
  );
}
