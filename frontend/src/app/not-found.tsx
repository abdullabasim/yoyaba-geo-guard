export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="text-center">
        <p className="text-sm font-semibold text-brand-600">404</p>
        <h1 className="mt-2 text-xl font-semibold text-slate-900 dark:text-slate-100">Page not found</h1>
        <p className="mt-1 text-sm text-slate-500">
          The page you requested does not exist.
        </p>
        <a
          href="/"
          className="mt-4 inline-block rounded-md bg-brand-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          Back to the dashboard
        </a>
      </div>
    </div>
  );
}
