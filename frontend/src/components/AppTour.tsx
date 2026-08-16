// @ts-nocheck
'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';

interface TourStep {
  target: string;
  content: string;
  route: string;
  title: string;
  placement?: 'right' | 'left' | 'bottom' | 'top' | 'center';
}

const STEPS: TourStep[] = [
  {
    route: '/',
    target: 'body',
    title: 'Welcome to IntentShift Guard 👋',
    content: 'This is your SEO monitoring command centre. We will walk you through each section of the app so you know exactly where everything lives.',
    placement: 'center',
  },
  {
    route: '/',
    target: '.tour-sidebar',
    title: 'Sidebar Navigation',
    content: 'Every section of the app lives here. Clients → Projects → Target URLs → Keywords form your monitoring hierarchy. Below those you have Analytics, AI Alerts, Task Monitor, and the User Guide.',
    placement: 'right',
  },
  {
    route: '/',
    target: '.tour-stats',
    title: 'Health Stats Cards',
    content: 'These four cards update in real time. They show your active client/URL counts, total keywords being tracked, and the number of background tasks that failed in the last 24 hours.',
    placement: 'bottom',
  },
  {
    route: '/clients',
    target: '.tour-clients-page',
    title: 'Clients',
    content: 'Create a client for each brand or business you are monitoring. Start here when onboarding a new account.',
    placement: 'bottom',
  },
  {
    route: '/projects',
    target: '.tour-projects-page',
    title: 'Projects',
    content: 'Projects allow you to group your Target URLs together under a single Client (e.g. "Main Website", "Blog", or "E-commerce store").',
    placement: 'bottom',
  },
  {
    route: '/urls',
    target: '.tour-urls-page',
    title: 'Target URLs',
    content: "This is where you specify the exact landing pages you want to track for ranking drops. Each URL belongs to a project and can have multiple keywords.",
    placement: 'bottom',
  },
  {
    route: '/keywords',
    target: '.tour-keywords-page',
    title: 'Keywords',
    content: "Here you can see the specific search terms being tracked for your Target URLs, along with their current Google rank and search volume.",
    placement: 'bottom',
  },
  {
    route: '/analytics',
    target: '.tour-analytics-page',
    title: 'Analytics',
    content: 'Pick any URL and view its full ranking timeline. You can overlay competitor data and zoom into any date range to understand exactly when and why a position changed.',
    placement: 'bottom',
  },
  {
    route: '/alerts',
    target: '.tour-alerts-filters',
    title: 'AI Alerts: Search & Filter',
    content: 'Welcome to the core of IntentShift Guard. Use this bar to search across all your AI diagnoses or filter by specific issue types (like Intent Shift, New Competitor, etc.).',
    placement: 'bottom',
  },
  {
    route: '/alerts',
    target: '.tour-alert-card',
    title: 'AI Alerts: Diagnosis Card',
    content: 'When a page drops in ranking, the AI generates a card like this. It shows the keyword, rank drop (e.g., 2 → 5), and a summary of why the drop happened. Click "View Full Report" to see the deep dive.',
    placement: 'bottom',
  },
  {
    route: '/tasks',
    target: '.tour-tasks-page',
    title: 'Task Monitor',
    content: 'Every scheduled rank-check and AI analysis runs as a background job. This page shows their status (pending, running, success, failed) so you can quickly spot any system errors.',
    placement: 'bottom',
  },
  {
    route: '/controls',
    target: '.tour-controls-page',
    title: 'Service Controls',
    content: 'System administrators can pause the background schedulers or reset active tasks here if the system gets stuck.',
    placement: 'bottom',
  },
  {
    route: '/upload',
    target: '.tour-upload-page',
    title: 'Bulk Upload',
    content: 'Need to import a lot of URLs and keywords at once? Use this page to upload a CSV file and populate your accounts instantly.',
    placement: 'bottom',
  },
  {
    route: '/users',
    target: '.tour-users-page',
    title: 'User Management',
    content: 'Invite your team members here. You can assign them Read-Only, Read-Write, or Superuser permissions.',
    placement: 'bottom',
  },
  {
    route: '/',
    target: 'body',
    title: "You're all set! 🎉",
    content: 'That covers the whole platform. Head to Clients to add your first account, or go to Target URLs to start tracking pages right away. Good luck!',
    placement: 'center',
  },
];

function getTooltipPosition(
  targetSelector: string,
  placement: TourStep['placement'],
  boxWidth = 340,
  boxHeight = 260,
): React.CSSProperties {
  const margin = 16;

  if (placement === 'center' || targetSelector === 'body') {
    return { position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', zIndex: 99999 };
  }

  const el = typeof document !== 'undefined' ? document.querySelector(targetSelector) : null;
  if (!el) {
    return { position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', zIndex: 99999 };
  }

  const rect = el.getBoundingClientRect();
  const vpW = window.innerWidth;
  const vpH = window.innerHeight;

  let top: number;
  let left: number;

  switch (placement) {
    case 'right':
      top = rect.top + rect.height / 2 - boxHeight / 2;
      left = rect.right + margin;
      if (left + boxWidth > vpW - margin) left = rect.left - boxWidth - margin;
      break;
    case 'left':
      top = rect.top + rect.height / 2 - boxHeight / 2;
      left = rect.left - boxWidth - margin;
      if (left < margin) left = rect.right + margin;
      break;
    case 'top':
      top = rect.top - boxHeight - margin;
      left = rect.left + rect.width / 2 - boxWidth / 2;
      if (top < margin) top = rect.bottom + margin;
      break;
    case 'bottom':
    default:
      top = rect.bottom + margin;
      left = rect.left + rect.width / 2 - boxWidth / 2;
      if (top + boxHeight > vpH - margin) top = rect.top - boxHeight - margin;
      break;
  }

  top = Math.max(margin, Math.min(top, vpH - boxHeight - margin));
  left = Math.max(margin, Math.min(left, vpW - boxWidth - margin));

  return { position: 'fixed', top, left, zIndex: 99999 };
}

function TooltipBox({
  step,
  index,
  total,
  onNext,
  onPrev,
  onClose,
}: {
  step: TourStep;
  index: number;
  total: number;
  onNext: () => void;
  onPrev: () => void;
  onClose: () => void;
}) {
  const isDark =
    typeof document !== 'undefined'
      ? document.documentElement.classList.contains('dark')
      : true;

  const containerStyle = getTooltipPosition(step.target, step.placement ?? 'bottom');

  return (
    <div style={containerStyle}>
      <div
        style={{
          background: isDark ? '#1e293b' : '#ffffff',
          border: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`,
          borderRadius: '12px',
          boxShadow: '0 25px 50px rgba(0,0,0,0.45)',
          width: '340px',
          padding: '20px',
          color: isDark ? '#f8fafc' : '#0f172a',
          fontFamily: 'inherit',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <span style={{ fontWeight: 700, fontSize: '15px', color: '#FFD600' }}>{step.title}</span>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: isDark ? '#94a3b8' : '#64748b', fontSize: '20px', lineHeight: 1, padding: '0 4px' }}
            aria-label="Close tour"
          >
            ×
          </button>
        </div>

        {/* Progress bar */}
        <div style={{ display: 'flex', gap: '4px', marginBottom: '14px' }}>
          {STEPS.map((_, i) => (
            <div
              key={i}
              style={{
                height: '4px',
                flex: 1,
                borderRadius: '2px',
                background: i <= index ? '#FFD600' : (isDark ? '#334155' : '#e2e8f0'),
                transition: 'background 0.3s',
              }}
            />
          ))}
        </div>

        {/* Content */}
        <p style={{ margin: '0 0 16px', fontSize: '14px', lineHeight: '1.6', color: isDark ? '#cbd5e1' : '#475569' }}>
          {step.content}
        </p>

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', color: isDark ? '#64748b' : '#94a3b8' }}>
            {index + 1} / {total}
          </span>
          <div style={{ display: 'flex', gap: '8px' }}>
            {index > 0 && (
              <button
                onClick={onPrev}
                style={{
                  background: 'none',
                  border: `1px solid ${isDark ? '#334155' : '#cbd5e1'}`,
                  color: isDark ? '#cbd5e1' : '#334155',
                  borderRadius: '6px',
                  padding: '6px 14px',
                  fontSize: '13px',
                  cursor: 'pointer',
                  fontWeight: 600,
                }}
              >
                Back
              </button>
            )}
            <button
              onClick={index === total - 1 ? onClose : onNext}
              style={{
                background: '#FFD600',
                color: '#000000',
                border: 'none',
                borderRadius: '6px',
                padding: '6px 16px',
                fontSize: '13px',
                cursor: 'pointer',
                fontWeight: 700,
              }}
            >
              {index === total - 1 ? 'Finish ✓' : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AppTour() {
  const [active, setActive] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const router = useRouter();
  const navigatingRef = useRef(false);

  // Auto-start on first visit
  useEffect(() => {
    const seen = localStorage.getItem('hasSeenTour');
    if (!seen) {
      localStorage.setItem('hasSeenTour', 'true');
      setTimeout(() => setActive(true), 800);
    }

    const handleStart = () => {
      setStepIndex(0);
      setActive(false);
      if (window.location.pathname !== '/') {
        router.push('/');
        setTimeout(() => setActive(true), 700);
      } else {
        setTimeout(() => setActive(true), 100);
      }
    };

    window.addEventListener('start-tour', handleStart);
    return () => window.removeEventListener('start-tour', handleStart);
  }, [router]);

  const goToStep = useCallback(
    (index: number) => {
      if (index < 0 || index >= STEPS.length) {
        setActive(false);
        setStepIndex(0);
        return;
      }
      const nextStep = STEPS[index];
      const currentPath = window.location.pathname;

      if (nextStep.route !== currentPath) {
        navigatingRef.current = true;
        router.push(nextStep.route);
        setTimeout(() => {
          navigatingRef.current = false;
          setStepIndex(index);
        }, 700);
      } else {
        setStepIndex(index);
      }
    },
    [router]
  );

  const handleNext = useCallback(() => goToStep(stepIndex + 1), [goToStep, stepIndex]);
  const handlePrev = useCallback(() => goToStep(stepIndex - 1), [goToStep, stepIndex]);
  const handleClose = useCallback(() => {
    setActive(false);
    setStepIndex(0);
  }, []);

  if (!active) return null;

  const step = STEPS[stepIndex];

  return (
    <>
      {/* Dark overlay */}
      <div
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 99998 }}
        onClick={handleClose}
      />
      <TooltipBox
        step={step}
        index={stepIndex}
        total={STEPS.length}
        onNext={handleNext}
        onPrev={handlePrev}
        onClose={handleClose}
      />
    </>
  );
}
