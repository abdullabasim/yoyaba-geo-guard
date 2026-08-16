import { ProjectsTable } from '@/components/ProjectsTable';
import { clientsApi, projectsApi } from '@/lib/api';
import { getCookieHeader, requireUser } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export default async function ProjectsPage() {
  const [currentUser, cookieHeader] = await Promise.all([
    requireUser(),
    getCookieHeader(),
  ]);
  const [initialPage, clients] = await Promise.all([
    projectsApi.list(undefined, 0, 10, cookieHeader),
    clientsApi.list(0, 200, cookieHeader),
  ]);

  return (
    <div className="tour-projects-page space-y-6">
      <div className="tour-projects-header">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-yoyaba-yellow">Projects</h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-300">
          Group target URLs under a client
        </p>
      </div>
      <ProjectsTable initialPage={initialPage} clients={clients.items} currentUser={currentUser} />
    </div>
  );
}
