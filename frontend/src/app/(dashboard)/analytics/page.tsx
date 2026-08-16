import { AnalyticsView } from '@/components/AnalyticsView';
import { keywordsApi, rankingsApi } from '@/lib/api';
import { getCookieHeader } from '@/lib/auth';
import type { RankSeries } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default async function AnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<{ keyword?: string }>;
}) {
  const cookieHeader = await getCookieHeader();
  const params = await searchParams;

  const keywords = await keywordsApi.list(undefined, 0, 200, cookieHeader);

  const requestedId = Number.parseInt(params.keyword ?? '', 10);
  const initialKeywordId = Number.isFinite(requestedId)
    ? requestedId
    : (keywords.items[0]?.id ?? null);

  let initialSeries: RankSeries | null = null;
  if (initialKeywordId !== null) {
    try {
      initialSeries = await rankingsApi.series(initialKeywordId, 90, cookieHeader);
    } catch {
      // A deleted keyword id in the query string must not break the page.
      initialSeries = null;
    }
  }

  return (
    <div className="tour-analytics-page space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-yoyaba-yellow">Analytics</h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-300">
          Ranking position over time. The vertical axis is reversed so position 1 is at the
          top.
        </p>
      </div>
      <AnalyticsView
        keywords={keywords.items}
        initialSeries={initialSeries}
        initialKeywordId={initialKeywordId}
      />
    </div>
  );
}
