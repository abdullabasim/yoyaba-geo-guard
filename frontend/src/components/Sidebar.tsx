'use client';

import Image from 'next/image';
import clsx from 'clsx';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';

import { authApi } from '@/lib/api';
import type { User } from '@/lib/types';

const NAV_ITEMS = [
  { href: '/', label: 'Overview' },
  { href: '/clients', label: 'Clients' },
  { href: '/projects', label: 'Projects' },
  { href: '/urls', label: 'Target URLs' },
  { href: '/keywords', label: 'Keywords' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/alerts', label: 'AI Alerts' },
  { href: '/tasks', label: 'Task Monitor' },
  { href: '/controls', label: 'Service Controls' },
  { href: '/upload', label: 'Bulk Upload', adminOnly: true },
  { href: '/users', label: 'Users', adminOnly: true },
  { href: '/guide', label: 'User Guide' },
];

export function Sidebar({ user }: { user: User }) {
  const pathname = usePathname();
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);
  const [isDark, setIsDark] = useState(true);

  // Initialize dark mode based on local storage
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedTheme === 'dark' || (!savedTheme && prefersDark) || !savedTheme) {
      document.documentElement.classList.add('dark');
      setIsDark(true);
    } else {
      document.documentElement.classList.remove('dark');
      setIsDark(false);
    }
  }, []);

  const toggleTheme = () => {
    const isDarkNow = document.documentElement.classList.toggle('dark');
    setIsDark(isDarkNow);
    localStorage.setItem('theme', isDarkNow ? 'dark' : 'light');
  };

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await authApi.logout();
    } finally {
      router.push('/login');
      router.refresh();
    }
  }

  const isReadOnly = user.role === 'read_only' || (!user.is_superuser && user.role !== 'read_write');
  const visibleNavItems = NAV_ITEMS.filter((item) => !isReadOnly || !item.adminOnly);

  return (
    <aside className="tour-sidebar w-64 flex-shrink-0 border-r border-slate-200 dark:border-yoyaba-border bg-white dark:bg-[#0a0c12]/80 dark:backdrop-blur-md flex flex-col h-full overflow-y-auto">
      <div className="p-5">
        {/* Logo Section */}
        <div className="flex items-center gap-3 mb-8 py-2">
          <img
            src="https://www.google.com/s2/favicons?domain=yoyaba.com&sz=256"
            alt="YOYABA Logo"
            width={36}
            height={36}
            className="rounded-md"
          />
          <div>
            <div className="text-slate-900 dark:text-white font-bold text-base tracking-wide leading-none">YOYABA</div>
            <div className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold tracking-widest uppercase mt-0.5">IntentShift Guard</div>
          </div>
        </div>

        
        {/* User Info */}
        <div className="flex flex-col gap-2 mb-8 p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-yoyaba-border">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-700 dark:text-slate-300 truncate" title={user.email}>{user.email}</span>
          </div>
          <div className="flex items-center justify-between">
            <span
              className={clsx(
                'rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
                isReadOnly ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400' : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
              )}
            >
              {isReadOnly ? 'Read Only' : 'Admin'}
            </span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="flex flex-col gap-1">
          {visibleNavItems.map((item) => {
            const active = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  'px-3 py-2.5 rounded-md text-sm font-medium transition-all duration-200',
                  active
                    ? 'bg-yoyaba-indigo/10 dark:bg-yoyaba-yellow/10 text-yoyaba-indigo dark:text-yoyaba-yellow'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-slate-200',
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="mt-auto p-6 border-t border-slate-200 dark:border-yoyaba-border">
        <div className="flex flex-col gap-3">
          <button
            type="button"
            onClick={toggleTheme}
            className="flex items-center justify-between w-full px-3 py-2 text-xs font-medium rounded-md text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <span>{isDark ? 'Light Mode' : 'Dark Mode'}</span>
            <div className={clsx(
              "w-8 h-4 rounded-full p-0.5 transition-colors duration-200 ease-in-out",
              isDark ? "bg-yoyaba-yellow" : "bg-slate-300"
            )}>
              <div className={clsx(
                "w-3 h-3 rounded-full bg-white transform transition-transform duration-200 ease-in-out",
                isDark ? "translate-x-4" : "translate-x-0"
              )} />
            </div>
          </button>
          <button
            type="button"
            onClick={handleLogout}
            disabled={loggingOut}
            className="w-full rounded-md px-3 py-2 text-xs font-medium text-slate-600 dark:text-slate-400 ring-1 ring-inset ring-slate-300 dark:ring-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50 disabled:opacity-60 transition-all"
          >
            {loggingOut ? 'Signing out...' : 'Sign out'}
          </button>
        </div>
      </div>
    </aside>
  );
}
