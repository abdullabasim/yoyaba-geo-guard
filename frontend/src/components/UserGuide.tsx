'use client';

import Link from 'next/link';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Form';
import type { User } from '@/lib/types';

interface Step {
  id: string;
  title: string;
  badge: string;
  route: string;
  summary: string;
  details: string[];
}

export function UserGuide({ currentUser }: { currentUser: User }) {
  const isReadOnly = currentUser.role === 'read_only' || (!currentUser.is_superuser && currentUser.role !== 'read_write');
  const [activeStepId, setActiveStepId] = useState<string>('overview');

  const readOnlySteps: Step[] = [
    {
      id: 'overview',
      title: '1. Overview Dashboard',
      badge: 'Monitoring',
      route: '/',
      summary: 'Get an instant high-level summary of your organic search health.',
      details: [
        'View top-level stat cards: Total Clients, Active Projects, Monitored URLs, and Tracked Keywords.',
        'Inspect recent AI Alerts summary: see how many ranking drops occurred in the past 24-72 hours.',
        'Check system liveness status indicators at a glance.',
      ],
    },
    {
      id: 'clients-projects',
      title: '2. Clients & Projects',
      badge: 'Account Views',
      route: '/clients',
      summary: 'Inspect client accounts and project structures.',
      details: [
        'Browse all monitored clients and their associated company names.',
        'View project listings under each client, including the default check interval (daily/weekly/monthly).',
        'Check active URL counts for each project without needing write access.',
      ],
    },
    {
      id: 'urls-keywords',
      title: '3. Target URLs & Keywords',
      badge: 'Rank Data',
      route: '/urls',
      summary: 'Explore tracked landing pages and search terms.',
      details: [
        'Inspect monitored target URLs along with their active check intervals and execution times.',
        'Review tracked keywords, their target market (Language / Location code), and last check timestamp.',
        'View the current observed Google position and rank movement delta for each term.',
      ],
    },
    {
      id: 'analytics',
      title: '4. Analytics & Rank History',
      badge: 'Charts',
      route: '/analytics',
      summary: 'Analyze position trends and historical SERP movements over time.',
      details: [
        'Select any tracked keyword to render interactive position trend charts.',
        'Compare current rank against historical checks over days or months.',
        'Inspect top-10 SERP competitor snapshots recorded during each check.',
      ],
    },
    {
      id: 'alerts',
      title: '5. AI Intent-Shift Alerts',
      badge: 'Diagnoses',
      route: '/alerts',
      summary: 'Review LLM-generated diagnoses for organic ranking drops.',
      details: [
        'Filter alerts by issue category (Intent Shift, SERP Feature Change, New Competitor, Content Freshness, Algorithm Update).',
        'Read detailed AI diagnoses explaining why a keyword dropped in rank.',
        'Review actionable recommendations and competitor signals (e.g. new ranking entrants).',
      ],
    },
    {
      id: 'tasks',
      title: '6. Task Monitor',
      badge: 'System Audit',
      route: '/tasks',
      summary: 'Monitor background Celery task execution logs in real time.',
      details: [
        'View live execution logs for background SERP checks and AI analysis tasks.',
        'Filter logs by status (Pending, Success, Failed, Skipped).',
        'Click on any failed execution to expand and inspect the full error traceback.',
      ],
    },
    {
      id: 'controls',
      title: '7. Service Controls Status',
      badge: 'System Health',
      route: '/controls',
      summary: 'Check the status of system subsystems and process health.',
      details: [
        'Check whether pipeline subsystems (Scheduler, SERP Fetching, AI Analysis, Slack Alerts) are active or paused.',
        'View read-only container process liveness (Database, Redis, Worker, Beat).',
      ],
    },
  ];

  const adminSteps: Step[] = [
    {
      id: 'users',
      title: '1. User Management & Permissions',
      badge: 'Admin Setup',
      route: '/users',
      summary: 'Invite team members and assign access roles.',
      details: [
        'Add new user accounts with Email, Password, and Full Name.',
        'Assign account permission levels: Read Only (monitoring access) vs Read & Write (Full Admin).',
        'Toggle user active/inactive status or delete standard user accounts when needed.',
      ],
    },
    {
      id: 'setup-hierarchy',
      title: '2. Setting Up Hierarchy (Clients -> Projects -> URLs -> Keywords)',
      badge: 'Structure',
      route: '/clients',
      summary: 'Build your monitoring structure step by step.',
      details: [
        'Create Clients at the top level of the hierarchy.',
        'Create Projects under a client and configure default check schedules (Interval, Time, Timezone).',
        'Add Target URLs under a project and choose whether to inherit the project schedule or set custom times.',
        'Add Keywords under a URL specifying DataForSEO location & language codes.',
      ],
    },
    {
      id: 'bulk-upload',
      title: '3. Bulk CSV Ingestion',
      badge: 'Imports',
      route: '/upload',
      summary: 'Import hundreds of monitoring targets at once via CSV.',
      details: [
        'Download the standard CSV template (client_name, project_name, url, keyword, etc.).',
        'Upload your file for instant browser-side validation and row previews.',
        'Import rows in bulk — existing clients, projects, and URLs are reused automatically.',
      ],
    },
    {
      id: 'scheduling-runs',
      title: '4. Schedules & Manual Triggers',
      badge: 'Execution',
      route: '/urls',
      summary: 'Manage automated check schedules or trigger immediate checks.',
      details: [
        'Configure project-level defaults or override individual URL execution times.',
        'Use the "Run now" action on Target URLs to trigger immediate SERP checks bypassing the schedule.',
      ],
    },
    {
      id: 'analytics-alerts',
      title: '5. Diagnoses, Analytics & Alerts',
      badge: 'AI Insights',
      route: '/alerts',
      summary: 'Analyze ranking drops and trigger Slack re-deliveries.',
      details: [
        'Inspect AI intent-shift diagnoses and actionable content recommendations.',
        'Manually re-send alerts to configured Slack webhooks if needed.',
      ],
    },
    {
      id: 'kill-switches',
      title: '6. Kill Switches & Service Controls',
      badge: 'Operations',
      route: '/controls',
      summary: 'Safely pause or resume individual pipeline stages.',
      details: [
        'Pause or resume specific subsystems (e.g. SERP Fetching or AI Analysis) without restarting containers.',
        'Provide mandatory audit reasons when pausing a service to maintain operational history.',
      ],
    },
  ];

  const steps = isReadOnly ? readOnlySteps : adminSteps;
  const currentStep = steps.find((s) => s.id === activeStepId) || steps[0];

  return (
    <div className="space-y-6">
      <div className="rounded-lg bg-brand-600 dark:bg-slate-800/50 dark:border dark:border-yoyaba-border p-6 text-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded bg-brand-700 px-2 py-0.5 text-xs font-semibold uppercase">
                {isReadOnly ? 'Read Only Guide' : 'Full Admin Guide'}
              </span>
              <h1 className="text-xl font-bold">User Journey & System Guide</h1>
            </div>
            <p className="mt-1 text-sm text-brand-100">
              Welcome, <span className="font-semibold">{currentUser.email}</span>! This step-by-step guided journey explains how to use every section of the platform tailored to your <strong className="underline">{currentUser.role === 'read_only' ? 'Read Only' : 'Admin (Read & Write)'}</strong> permissions.
            </p>
          </div>
          <div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => window.dispatchEvent(new Event('start-tour'))}
              className="bg-white/10 text-white hover:bg-white/20 border-white/20"
            >
              Start Interactive Tour
            </Button>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Journey Steps ({steps.length})
          </p>
          <div className="space-y-1">
            {steps.map((step) => {
              const isActive = step.id === currentStep.id;
              return (
                <button
                  key={step.id}
                  type="button"
                  onClick={() => setActiveStepId(step.id)}
                  className={`flex w-full items-center justify-between rounded-lg px-3.5 py-3 text-left text-sm transition-colors ${
                    isActive
                      ? 'bg-brand-50 dark:bg-[#0B0F19]/80 font-semibold text-brand-900 dark:text-yoyaba-yellow ring-1 ring-brand-300 dark:ring-yoyaba-border'
                      : 'bg-white dark:bg-slate-800/40 font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/60'
                  }`}
                >
                  <span className="truncate">{step.title}</span>
                  <Badge tone={isActive ? 'brand' : 'neutral'}>{step.badge}</Badge>
                </button>
              );
            })}
          </div>
        </div>

        <div className="lg:col-span-2">
          <Card>
            <CardHeader
              title={currentStep.title}
              description={currentStep.summary}
              action={
                <Link href={currentStep.route}>
                  <Button size="sm">Go to {currentStep.badge} Page &rarr;</Button>
                </Link>
              }
            />
            <CardBody className="space-y-4">
              <div className="rounded-md bg-slate-50 dark:bg-slate-800/40 p-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Key Steps & Features
                </h3>
                <ul className="mt-2 space-y-2">
                  {currentStep.details.map((detail, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
                      <span className="mt-1 text-brand-600 font-bold">&check;</span>
                      <span>{detail}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="flex items-center justify-between border-t border-slate-100 pt-4">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={steps.indexOf(currentStep) === 0}
                  onClick={() => {
                    const idx = steps.indexOf(currentStep);
                    if (idx > 0) setActiveStepId(steps[idx - 1].id);
                  }}
                >
                  &larr; Previous Step
                </Button>
                <span className="text-xs text-slate-500">
                  Step {steps.indexOf(currentStep) + 1} of {steps.length}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={steps.indexOf(currentStep) === steps.length - 1}
                  onClick={() => {
                    const idx = steps.indexOf(currentStep);
                    if (idx < steps.length - 1) setActiveStepId(steps[idx + 1].id);
                  }}
                >
                  Next Step &rarr;
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
