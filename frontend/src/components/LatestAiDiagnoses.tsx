'use client';

import Link from 'next/link';

import { Badge, DeltaBadge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import {
  formatDateTime,
  formatIssueType,
  formatRank,
  rankDelta,
  truncate,
} from '@/lib/format';
import type { AiAlert, IssueType } from '@/lib/types';

function issueTone(issueType: IssueType) {
  if (issueType === 'INTENT_SHIFT') return 'danger' as const;
  if (issueType === 'NEW_COMPETITOR') return 'warning' as const;
  if (issueType === 'NO_SIGNIFICANT_CHANGE') return 'neutral' as const;
  return 'brand' as const;
}

export function LatestAiDiagnoses({ alerts }: { alerts: AiAlert[] }) {
  return (
    <Card>
      <CardHeader
        title="Latest AI diagnoses"
        description="Click any item to view its full diagnosis on the AI Alerts page"
        action={
          <Link href="/alerts" target="_blank" rel="noreferrer" className="text-xs font-medium text-brand-700 hover:underline">
            View all ↗
          </Link>
        }
      />
      <CardBody className="space-y-3">
        {alerts.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-400">
            No AI alerts yet.
          </p>
        ) : (
          alerts.map((alert) => {
            const delta = rankDelta(alert.previous_rank, alert.current_rank);
            const targetHref = `/alerts/${alert.id}`;

            return (
              <Link
                key={alert.id}
                href={targetHref}
                target="_blank"
                rel="noreferrer"
                className="group block rounded-md border border-slate-200 dark:border-yoyaba-border p-3.5 hover:border-brand-400 dark:hover:border-yoyaba-yellow hover:bg-brand-50/20 dark:hover:bg-[#0f2a36]/50 hover:shadow-xs transition-all"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm font-bold text-slate-900 dark:text-white truncate">
                      &quot;{alert.keyword_text}&quot;
                    </span>
                    <Badge tone={issueTone(alert.issue_type)}>
                      {formatIssueType(alert.issue_type)}
                    </Badge>
                  </div>
                  <span className="text-[11px] text-slate-500 dark:text-slate-400 font-mono shrink-0">
                    ⏱️ {formatDateTime(alert.created_at)}
                  </span>
                </div>

                {alert.url ? (
                  <div className="mt-1 text-xs font-medium text-brand-700 dark:text-yoyaba-yellow group-hover:underline truncate">
                    🔗 {alert.url}
                  </div>
                ) : null}

                <div className="mt-1.5 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <DeltaBadge direction={delta.direction} label={delta.label} />
                  <span>
                    {formatRank(alert.previous_rank)} &rarr; {formatRank(alert.current_rank)}
                  </span>
                  <span>·</span>
                  <span>{alert.client_name}</span>
                </div>

                <p className="mt-2 text-xs text-slate-600 dark:text-slate-300 line-clamp-2 leading-relaxed">
                  {truncate(alert.ai_diagnosis, 180)}
                </p>

                <div className="mt-2.5 flex items-center text-[11px] font-semibold text-brand-700 dark:text-yoyaba-yellow group-hover:text-brand-900 dark:group-hover:text-[#E6C100] group-hover:translate-x-0.5 transition-transform">
                  View full diagnosis & action plan on AI Alerts page &rarr;
                </div>
              </Link>
            );
          })
        )}
      </CardBody>
    </Card>
  );
}
