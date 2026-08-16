import Link from 'next/link';

import { StatusBadge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader, StatCard } from '@/components/ui/Card';
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table';
import { LatestAiDiagnoses } from '@/components/LatestAiDiagnoses';
import { WelcomeBanner } from '@/components/WelcomeBanner';
import { alertsApi, clientsApi, tasksApi, urlsApi } from '@/lib/api';
import { getCookieHeader, requireUser } from '@/lib/auth';
import { formatDateTime, formatIssueType, formatRank, truncate } from '@/lib/format';

export const dynamic = 'force-dynamic';

export default async function OverviewPage() {
  const [currentUser, cookieHeader] = await Promise.all([
    requireUser(),
    getCookieHeader(),
  ]);

  const [clients, urls, taskStats, alertStats, recentTasks, recentAlerts] = await Promise.all([
    clientsApi.list(0, 200, cookieHeader),
    urlsApi.list(undefined, 0, 200, cookieHeader),
    tasksApi.stats(24, cookieHeader),
    alertsApi.stats(30, cookieHeader),
    tasksApi.list({ limit: 8 }, cookieHeader),
    alertsApi.list({ limit: 5 }, cookieHeader),
  ]);

  const activeClients = clients.items.filter((client) => client.is_active).length;
  const activeUrls = urls.items.filter((url) => url.is_active).length;
  const trackedKeywords = urls.items.reduce((total, url) => total + url.keyword_count, 0);

  return (
    <div className="space-y-6">
      <WelcomeBanner user={currentUser} />

      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-yoyaba-yellow">Overview</h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-300">
          System health and recent activity across all accounts
        </p>
      </div>

      <div className="tour-stats grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Clients"
          value={`${activeClients} / ${clients.total}`}
          hint="active / total"
        />
        <StatCard
          label="Target URLs"
          value={`${activeUrls} / ${urls.total}`}
          hint="active / total"
        />
        <StatCard label="Keywords tracked" value={trackedKeywords} hint="across all URLs" />
        <StatCard
          label="Failed tasks"
          value={taskStats.failed}
          tone={taskStats.failed > 0 ? 'danger' : 'success'}
          hint="last 24 h"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Checks succeeded" value={taskStats.success} tone="success" hint="last 24 h" />
        <StatCard label="Checks pending" value={taskStats.pending} tone="warning" hint="last 24 h" />
        <StatCard label="AI alerts" value={alertStats.total} hint="last 30 days" />
        <StatCard
          label="Slack undelivered"
          value={alertStats.unsent}
          tone={alertStats.unsent > 0 ? 'warning' : 'success'}
          hint="last 30 days"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Recent background tasks"
            action={
              <Link href="/tasks" className="text-xs font-medium text-brand-700 hover:underline">
                View all
              </Link>
            }
          />
          <CardBody className="px-0 py-0">
            <Table>
              <THead>
                <TR>
                  <TH>Status</TH>
                  <TH>Task</TH>
                  <TH>Keyword</TH>
                  <TH>Started</TH>
                </TR>
              </THead>
              <TBody>
                {recentTasks.items.length === 0 ? (
                  <EmptyRow colSpan={4} message="No task executions yet." />
                ) : (
                  recentTasks.items.map((log) => (
                    <TR key={log.id}>
                      <TD>
                        <StatusBadge status={log.status} />
                      </TD>
                      <TD className="font-mono text-xs">
                        {log.task_name.replace('app.worker.tasks.', '')}
                      </TD>
                      <TD className="text-xs">{log.keyword_text ?? '-'}</TD>
                      <TD className="whitespace-nowrap text-xs">
                        {formatDateTime(log.started_at)}
                      </TD>
                    </TR>
                  ))
                )}
              </TBody>
            </Table>
          </CardBody>
        </Card>

        <div className="tour-alerts">
          <LatestAiDiagnoses alerts={recentAlerts.items} />
        </div>
      </div>
    </div>
  );
}
