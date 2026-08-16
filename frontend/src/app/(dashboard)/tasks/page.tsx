import { TaskMonitor } from '@/components/TaskMonitor';
import { tasksApi } from '@/lib/api';
import { getCookieHeader } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export default async function TasksPage() {
  const cookieHeader = await getCookieHeader();
  const [initialPage, stats] = await Promise.all([
    tasksApi.list({ limit: 10 }, cookieHeader),
    tasksApi.stats(24, cookieHeader),
  ]);

  return (
    <div className="tour-tasks-page space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-yoyaba-yellow">System Task Monitor</h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-300">
          Live status of every background execution. Failed rows expand to the full traceback.
        </p>
      </div>
      <TaskMonitor initialPage={initialPage} initialStats={stats} />
    </div>
  );
}
