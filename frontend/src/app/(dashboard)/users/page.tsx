import { UsersTable } from '@/components/UsersTable';
import { usersApi } from '@/lib/api';
import { getCookieHeader, requireUser } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export default async function UsersPage() {
  const [currentUser, cookieHeader] = await Promise.all([
    requireUser(),
    getCookieHeader(),
  ]);
  const initialPage = await usersApi.list(0, 10, cookieHeader);

  return (
    <div className="tour-users-page space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-yoyaba-yellow">User Management</h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-300">
          Manage system accounts, set permissions (Read Only vs Read & Write), and deactivate or delete users.
        </p>
      </div>
      <UsersTable initialPage={initialPage} currentUser={currentUser} />
    </div>
  );
}
