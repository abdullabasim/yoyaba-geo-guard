import { AlertsList } from '@/components/AlertsList';
import { alertsApi } from '@/lib/api';
import { getCookieHeader, requireUser } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export default async function AlertsPage({
  searchParams,
}: {
  searchParams: Promise<{ search?: string }>;
}) {
  const params = await searchParams;
  const initialSearch = params?.search || '';

  const [currentUser, cookieHeader] = await Promise.all([
    requireUser(),
    getCookieHeader(),
  ]);
  const initialPage = await alertsApi.list(
    { limit: 10, search: initialSearch || undefined },
    cookieHeader
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-yoyaba-yellow">AI Alerts</h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-300">
          Intent-shift diagnoses and recommended actions for detected ranking drops
        </p>
      </div>
      <AlertsList initialPage={initialPage} currentUser={currentUser} initialSearch={initialSearch} />
    </div>
  );
}
