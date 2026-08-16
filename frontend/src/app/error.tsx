'use client';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-white">Something went wrong</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
          {error.message || 'An unexpected error occurred while loading this page.'}
        </p>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          If this persists, check that the backend API is reachable at the configured
          NEXT_PUBLIC_API_URL.
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-4 rounded-md bg-brand-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
