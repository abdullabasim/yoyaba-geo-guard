/**
 * Server-side auth helpers for React Server Components.
 *
 * Server fetches carry no cookie jar, so the incoming request cookies must be
 * read and forwarded explicitly on every server-side API call.
 */
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

import { authApi, ApiError } from './api';
import type { User } from './types';

export const ACCESS_COOKIE = 'seo_access_token';

/** Serialize the incoming cookies into a header for server-side API calls. */
export async function getCookieHeader(): Promise<string> {
  const store = await cookies();
  return store
    .getAll()
    .map(({ name, value }) => `${name}=${value}`)
    .join('; ');
}

export async function getCurrentUser(): Promise<User | null> {
  const cookieHeader = await getCookieHeader();
  if (!cookieHeader.includes(ACCESS_COOKIE)) {
    return null;
  }
  try {
    return await authApi.me(cookieHeader);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
    // A backend outage should not masquerade as "logged out".
    throw error;
  }
}

/** Use at the top of a protected server component. */
export async function requireUser(): Promise<User> {
  const user = await getCurrentUser();
  if (!user) {
    redirect('/login');
  }
  return user;
}
