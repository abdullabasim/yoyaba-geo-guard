'use client';

import Image from 'next/image';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';

import { Alert, Button, FieldError, Input, Label } from '@/components/ui/Form';
import { ApiError, authApi } from '@/lib/api';

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setFieldErrors({});
    try {
      await authApi.login(email, password);
      const next = searchParams.get('next') || '/';
      router.push(next);
      router.refresh();
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors) {
        setFieldErrors(caught.fieldErrors);
      }
      setError(caught instanceof Error ? caught.message : 'Sign in failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="flex min-h-screen items-center justify-center px-4"
      style={{
        backgroundColor: '#0d0e12',
        backgroundImage: `
          radial-gradient(circle at 40% 10%, #0f2a36 0%, transparent 50%),
          linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)
        `,
        backgroundSize: '100% 100%, 60px 60px, 60px 60px',
      }}
    >
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="flex items-center justify-center gap-3 mb-4">
            <Image src="/yoyaba-logo.png" alt="YOYABA" width={48} height={48} className="rounded-lg" />
          </div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight" style={{ fontFamily: 'Mulish, sans-serif' }}>
            YOYABA
          </h1>
          <p className="mt-1 text-sm font-semibold text-[#FFD600] tracking-wide">GEO & IntentShift Guard</p>
          <p className="mt-2 text-sm text-slate-400">Sign in to your dashboard</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-xl bg-[#111827]/80 backdrop-blur-md p-8 shadow-2xl border border-[#2b3644]"
          noValidate
        >
          <div className="space-y-5">
            {error ? <Alert tone="error">{error}</Alert> : null}

            <div>
              <Label htmlFor="email" required>
                <span className="text-slate-300">Email address</span>
              </Label>
              <Input
                id="email"
                name="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                error={!!fieldErrors.email}
                className="mt-1.5 block w-full bg-[#0b0f19]/80 border-[#374151] text-slate-200 placeholder:text-slate-500 focus:border-[#FFD600] focus:ring-[#FFD600]"
              />
              <FieldError message={fieldErrors.email} />
            </div>

            <div>
              <Label htmlFor="password" required>
                <span className="text-slate-300">Password</span>
              </Label>
              <Input
                id="password"
                name="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                error={!!fieldErrors.password}
                className="mt-1.5 block w-full bg-[#0b0f19]/80 border-[#374151] text-slate-200 focus:border-[#FFD600] focus:ring-[#FFD600]"
              />
              <FieldError message={fieldErrors.password} />
            </div>
          </div>

          <Button type="submit" disabled={submitting} className="w-full mt-6">
            {submitting ? 'Signing in...' : 'Sign in →'}
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-500">
          © {new Date().getFullYear()} YOYABA. All rights reserved.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-sm text-slate-400">Loading…</div>}>
      <LoginForm />
    </Suspense>
  );
}
