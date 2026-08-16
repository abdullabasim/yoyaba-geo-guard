'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/Form';
import type { User } from '@/lib/types';

export function WelcomeBanner({ user }: { user: User }) {
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    const key = `seo_welcome_dismissed_${user.id}`;
    if (!localStorage.getItem(key)) {
      setDismissed(false);
    }
  }, [user.id]);

  function handleDismiss() {
    const key = `seo_welcome_dismissed_${user.id}`;
    localStorage.setItem(key, 'true');
    setDismissed(true);
  }

  if (dismissed) return null;

  const isReadOnly = user.role === 'read_only' || (!user.is_superuser && user.role !== 'read_write');

  return (
    <div className="relative overflow-hidden rounded-xl border border-brand-200 bg-gradient-to-r from-brand-50 via-white to-blue-50 p-5 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="rounded bg-brand-600 px-2 py-0.5 text-xs font-bold text-white">
              Welcome!
            </span>
            <h2 className="text-base font-semibold text-slate-900">
              First time here? Take the Guided User Journey
            </h2>
          </div>
          <p className="text-xs text-slate-600">
            Learn step-by-step how to navigate each section of the platform. Your guide is customized specifically for your{' '}
            <strong className="text-brand-700">{isReadOnly ? 'Read Only' : 'Read & Write Admin'}</strong> permissions.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Link href="/guide">
            <Button size="sm">Start Guided Tour &rarr;</Button>
          </Link>
          <Button variant="ghost" size="sm" onClick={handleDismiss}>
            Dismiss
          </Button>
        </div>
      </div>
    </div>
  );
}
