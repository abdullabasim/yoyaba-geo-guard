'use client';

import Link from 'next/link';

import { Badge, DeltaBadge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { formatDateTime, formatIssueType, formatRank, rankDelta } from '@/lib/format';
import type { AiAlert, IssueType } from '@/lib/types';

function issueTone(issueType: IssueType) {
  if (issueType === 'INTENT_SHIFT') return 'danger' as const;
  if (issueType === 'NEW_COMPETITOR') return 'warning' as const;
  if (issueType === 'NO_SIGNIFICANT_CHANGE') return 'neutral' as const;
  return 'brand' as const;
}

function renderParts(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, pIdx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={pIdx} className="font-bold text-slate-900 dark:text-slate-100">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={pIdx}
          className="font-mono text-[13px] bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-1.5 py-0.5 rounded font-semibold text-slate-800 dark:text-slate-200"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

function FormattedParagraphs({ text, className }: { text: string; className?: string }) {
  if (!text) return null;
  const lines = text.split('\n').filter((l) => l.trim().length > 0);
  return (
    <div className={`space-y-4 ${className || 'text-slate-700 dark:text-slate-300 text-sm'}`}>
      {lines.map((line, idx) => (
        <p key={idx} className="leading-relaxed break-words">
          {renderParts(line.trim())}
        </p>
      ))}
    </div>
  );
}

function FormattedList({ text, className }: { text: string; className?: string }) {
  if (!text) return null;
  const lines = text.split('\n').filter((l) => l.trim().length > 0);
  return (
    <div className={`space-y-3 ${className || 'text-slate-700 text-sm'}`}>
      {lines.map((line, idx) => {
        const content = line.replace(/^(\(\d+\)|\d+[\.\)])\s*/, '').trim();
        return (
          <div
            key={idx}
            className="flex items-start gap-3 p-4 rounded-xl bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-yoyaba-border shadow-xs"
          >
            <span className="shrink-0 font-bold text-sm bg-brand-600 dark:bg-yoyaba-yellow text-white dark:text-slate-900 w-6 h-6 flex items-center justify-center rounded-full font-mono shadow-xs">
              {idx + 1}
            </span>
            <div className="leading-relaxed min-w-0 flex-1 text-slate-800 dark:text-slate-200 break-words">
              {renderParts(content)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function AlertDetail({ alert }: { alert: AiAlert }) {
  const delta = rankDelta(alert.previous_rank, alert.current_rank);
  const hasCompetitors = alert.competitor_signals && alert.competitor_signals.length > 0;

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Back Button */}
      <div className="mb-2">
        <Link
          href="/alerts"
          className="text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors flex items-center gap-2"
        >
          &larr; Back to AI Alerts
        </Link>
      </div>

      {/* Header Info */}
      <div className="bg-white dark:bg-[#0B0F19]/60 backdrop-blur-sm rounded-2xl border border-slate-200 dark:border-yoyaba-border p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
          <div>
            <div className="flex flex-wrap items-center gap-3 mb-3">
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-yoyaba-yellow tracking-tight">
                &quot;{alert.keyword_text}&quot;
              </h1>
              <Badge tone={issueTone(alert.issue_type)}>
                {formatIssueType(alert.issue_type)}
              </Badge>
            </div>

            {alert.url ? (
              <a
                href={alert.url}
                target="_blank"
                rel="noreferrer"
                className="text-sm font-medium text-brand-600 hover:text-brand-800 hover:underline flex items-center gap-1.5 mb-4"
              >
                🔗 {alert.url} ↗
              </a>
            ) : null}

            <div className="flex flex-wrap items-center gap-4 text-sm text-slate-500 dark:text-slate-400">
              <span className="flex items-center gap-1.5 font-mono bg-slate-50 dark:bg-slate-800/80 px-2.5 py-1.5 rounded-md border border-slate-200/60 dark:border-yoyaba-border shadow-xs">
                ⏱️ {formatDateTime(alert.created_at)}
              </span>
              <span className="flex items-center gap-1.5 font-medium text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/80 px-2.5 py-1.5 rounded-md border border-slate-200/60 dark:border-yoyaba-border shadow-xs">
                👤 {alert.client_name}
              </span>
              <span className="flex items-center gap-1.5 text-xs font-mono bg-slate-50 dark:bg-slate-800/80 px-2.5 py-1.5 rounded-md border border-slate-200/60 dark:border-yoyaba-border shadow-xs">
                🤖 {alert.model_used || 'GPT'} · {alert.confidence !== null ? `${Math.round(alert.confidence * 100)}% Conf` : 'N/A'}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 bg-slate-50 dark:bg-slate-800/50 p-5 rounded-xl border border-slate-200 dark:border-yoyaba-border shadow-xs shrink-0">
            <div className="text-right">
              <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                Rank Shift
              </div>
              <div className="flex items-center justify-end gap-2 font-mono text-xl font-black text-slate-800 dark:text-white">
                {formatRank(alert.previous_rank)} &rarr; {formatRank(alert.current_rank)}
              </div>
            </div>
            <div className="pl-4 border-l-2 border-slate-200 dark:border-yoyaba-border">
              <DeltaBadge direction={delta.direction} label={delta.label} />
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: Diagnosis & Competitors */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="shadow-sm border-slate-200/80">
            <CardHeader
              title="AI Diagnosis"
              description="Detailed breakdown of the intent shift"
            />
            <CardBody className="p-6">
              <FormattedParagraphs text={alert.ai_diagnosis} className="text-slate-800 dark:text-slate-300 text-[15px] leading-relaxed" />
            </CardBody>
          </Card>

          {hasCompetitors ? (
            <Card className="shadow-sm border-slate-200/80">
              <CardHeader
                title="Competitor Signals"
                description="Observations from current top-ranking pages"
              />
              <CardBody className="p-6 bg-slate-50/30 dark:bg-transparent">
                <div className="space-y-3">
                  {alert.competitor_signals!.map((signal, index) => {
                    const domain = String(signal.domain || '');
                    const title = String(signal.title || domain || 'Competitor');
                    const url = String(signal.url || '');
                    const note = String(signal.note || signal.reason || '');
                    const isNew = Boolean(signal.is_new_entrant);

                    return (
                        <div
                        key={index}
                        className="flex flex-col sm:flex-row sm:items-baseline gap-2.5 p-4 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200/70 dark:border-yoyaba-border shadow-xs"
                      >
                        <div className="flex items-center gap-2 shrink-0">
                          {domain ? (
                            <span className="font-bold font-mono text-[11px] bg-slate-100 dark:bg-slate-700 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-600 px-2 py-1 rounded">
                              {domain}
                            </span>
                          ) : null}
                          {isNew ? (
                            <span className="font-bold text-[10px] bg-amber-100 dark:bg-amber-900/30 text-amber-900 dark:text-amber-400 border border-amber-300 dark:border-amber-700/50 px-1.5 py-1 rounded uppercase tracking-wider">
                              New Entrant
                            </span>
                          ) : null}
                        </div>

                        <div className="min-w-0 flex-1 leading-relaxed text-sm break-words">
                          {url ? (
                            <a
                              href={url}
                              target="_blank"
                              rel="noreferrer"
                              className="font-bold text-brand-700 dark:text-yoyaba-yellow hover:text-brand-900 dark:hover:text-[#E6C100] hover:underline"
                            >
                              {title}
                            </a>
                          ) : (
                            <span className="font-bold text-slate-900 dark:text-white">{title}</span>
                          )}
                          {note ? (
                            <span className="text-slate-600 dark:text-slate-400 ml-2 font-normal">— {note}</span>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardBody>
            </Card>
          ) : null}
        </div>

        {/* Right Column: Recommendations */}
        <div className="lg:col-span-1">
          <div className="sticky top-6">
            <Card className="h-full border-brand-200 dark:border-yoyaba-border shadow-md shadow-brand-100/50 dark:shadow-none bg-brand-50/10 dark:bg-slate-900/50">
              <div className="bg-brand-50/80 dark:bg-slate-800/80 border-b border-brand-100/80 dark:border-yoyaba-border px-6 py-5 rounded-t-xl">
                <h3 className="text-lg font-bold text-brand-900 dark:text-white">Recommended Actions</h3>
                <p className="text-xs font-medium text-brand-700 dark:text-slate-400 mt-1">Steps to recover rankings</p>
              </div>
              <div className="p-6 bg-slate-50/30 dark:bg-transparent">
                <FormattedList text={alert.actionable_advice} />
              </div>
            </Card>
          </div>
        </div>
        
      </div>
    </div>
  );
}
