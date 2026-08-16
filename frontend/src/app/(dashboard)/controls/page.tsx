import { ServiceControls } from '@/components/ServiceControls';
import { controlsApi } from '@/lib/api';
import { getCookieHeader, requireUser } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export default async function ControlsPage() {
  const [currentUser, cookieHeader] = await Promise.all([
    requireUser(),
    getCookieHeader(),
  ]);
  const status = await controlsApi.status(cookieHeader);

  return (
    <div className="tour-controls-page space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-yoyaba-yellow">Service Controls</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-300">
          Pause individual parts of the pipeline without a restart, and see which processes
          are alive.
        </p>
      </div>

      <ServiceControls initial={status} currentUser={currentUser} />
    </div>
  );
}
