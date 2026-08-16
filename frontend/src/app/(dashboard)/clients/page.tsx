import { ClientsTable } from '@/components/ClientsTable';
import { clientsApi } from '@/lib/api';
import { getCookieHeader, requireUser } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export default async function ClientsPage() {
  const [currentUser, cookieHeader] = await Promise.all([
    requireUser(),
    getCookieHeader(),
  ]);
  const initialPage = await clientsApi.list(0, 10, cookieHeader);

  return (
    <div className="tour-clients-page space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-yoyaba-yellow">Clients</h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-300">
          Manage accounts and pause monitoring at the top of the hierarchy
        </p>
      </div>
      <ClientsTable initialPage={initialPage} currentUser={currentUser} />
    </div>
  );
}
