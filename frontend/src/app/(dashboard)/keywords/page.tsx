import { KeywordsTable } from '@/components/KeywordsTable';
import { keywordsApi, urlsApi } from '@/lib/api';
import { getCookieHeader, requireUser } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export default async function KeywordsPage() {
  const [currentUser, cookieHeader] = await Promise.all([
    requireUser(),
    getCookieHeader(),
  ]);
  const [initialPage, urls] = await Promise.all([
    keywordsApi.list(undefined, 0, 10, cookieHeader),
    urlsApi.list(undefined, 0, 200, cookieHeader),
  ]);

  return (
    <div className="tour-keywords-page space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-yoyaba-yellow">Keywords</h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-300">
          Tracked search terms with their latest observed position
        </p>
      </div>
      <KeywordsTable initialPage={initialPage} urls={urls.items} currentUser={currentUser} />
    </div>
  );
}
