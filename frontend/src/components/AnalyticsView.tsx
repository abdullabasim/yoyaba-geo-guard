'use client';

import { useState } from 'react';

import { RankChart } from '@/components/RankChart';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Alert, Button, Label, Select, Spinner } from '@/components/ui/Form';
import { rankingsApi } from '@/lib/api';
import type { Keyword, RankSeries } from '@/lib/types';

const RANGE_OPTIONS = [
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
  { value: 180, label: 'Last 6 months' },
  { value: 365, label: 'Last year' },
];

export function AnalyticsView({
  keywords,
  initialSeries,
  initialKeywordId,
}: {
  keywords: Keyword[];
  initialSeries: RankSeries | null;
  initialKeywordId: number | null;
}) {
  const [keywordId, setKeywordId] = useState<number | ''>(initialKeywordId ?? '');
  const [days, setDays] = useState(90);
  const [series, setSeries] = useState<RankSeries | null>(initialSeries);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(nextKeywordId: number | '', nextDays: number) {
    if (nextKeywordId === '') {
      setSeries(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setSeries(await rankingsApi.series(Number(nextKeywordId), nextDays));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to load ranking history');
      setSeries(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Ranking analytics" description="Position over time per keyword" />
        <CardBody>
          <div className="flex flex-wrap items-end gap-4">
            <div className="min-w-64 flex-1">
              <Label htmlFor="analytics-keyword">Keyword</Label>
              <Select
                id="analytics-keyword"
                value={keywordId}
                onChange={(event) => {
                  const next = event.target.value === '' ? '' : Number(event.target.value);
                  setKeywordId(next);
                  void load(next, days);
                }}
                className="mt-1"
              >
                <option value="">Select a keyword...</option>
                {keywords.map((keyword) => (
                  <option key={keyword.id} value={keyword.id}>
                    {keyword.keyword_text} — {keyword.url ?? 'no url'}
                  </option>
                ))}
              </Select>
            </div>

            <div className="w-48">
              <Label htmlFor="analytics-range">Range</Label>
              <Select
                id="analytics-range"
                value={days}
                onChange={(event) => {
                  const next = Number(event.target.value);
                  setDays(next);
                  void load(keywordId, next);
                }}
                className="mt-1"
              >
                {RANGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>

            <Button
              variant="secondary"
              onClick={() => void load(keywordId, days)}
              disabled={keywordId === '' || loading}
            >
              {loading ? <Spinner /> : 'Reload'}
            </Button>
          </div>

          {error ? (
            <div className="mt-4">
              <Alert tone="error">{error}</Alert>
            </div>
          ) : null}
        </CardBody>
      </Card>

      {series ? (
        <RankChart series={series} />
      ) : (
        <Card>
          <CardBody>
            <p className="py-16 text-center text-sm text-slate-400">
              {keywords.length === 0
                ? 'No keywords are being tracked yet.'
                : 'Select a keyword to view its ranking history.'}
            </p>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
