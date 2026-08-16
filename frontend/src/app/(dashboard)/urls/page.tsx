import { UrlsTable } from '@/components/UrlsTable';
import { projectsApi, urlsApi } from '@/lib/api';
import { getCookieHeader, requireUser } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export default async function UrlsPage() {
  const [currentUser, cookieHeader] = await Promise.all([
    requireUser(),
    getCookieHeader(),
  ]);
  const [initialPage, projects] = await Promise.all([
    urlsApi.list(undefined, 0, 10, cookieHeader),
    projectsApi.list(undefined, 0, 200, cookieHeader),
  ]);

  return (
    <div className="tour-urls-page space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-yoyaba-yellow">Target URLs</h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-300">
          Monitored pages, their check interval and their execution time
        </p>
      </div>
      <UrlsTable initialPage={initialPage} projects={projects.items} currentUser={currentUser} />
    </div>
  );
}
