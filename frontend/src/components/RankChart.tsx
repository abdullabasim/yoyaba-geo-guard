'use client';

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { formatDate, formatDateTime } from '@/lib/format';
import type { RankSeries } from '@/lib/types';

/**
 * Rank-over-time chart.
 *
 * The y-axis is REVERSED: rank 1 is the best result and must appear at the top.
 * A conventional axis would render an improvement as a downward line.
 */

interface ChartPoint {
  timestamp: number;
  label: string;
  rank: number | null;
  fullDate: string;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ChartPoint }>;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-slate-900">{point.fullDate}</p>
      <p className="mt-0.5 text-slate-600">
        {point.rank === null ? 'Not in tracked results' : `Position #${point.rank}`}
      </p>
    </div>
  );
}

export function RankChart({ series }: { series: RankSeries }) {
  const data: ChartPoint[] = series.points.map((point) => ({
    timestamp: new Date(point.check_date).getTime(),
    label: formatDate(point.check_date),
    rank: point.rank,
    fullDate: formatDateTime(point.check_date),
  }));

  const ranked = data.filter((point) => point.rank !== null);
  const hasData = ranked.length > 0;

  // Pad the domain so the best and worst points are not flush against the edge.
  const best = Math.max(1, (series.best_rank ?? 1) - 1);
  const worst = (series.worst_rank ?? 10) + 1;

  return (
    <Card>
      <CardHeader
        title={`"${series.keyword_text}"`}
        description={`${series.url} · ${series.language_code}/${series.location_code}`}
      />
      <CardBody>
        <div className="mb-4 flex flex-wrap gap-6 text-sm">
          <div>
            <span className="text-slate-500">Latest</span>
            <p className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">
              {series.latest_rank === null ? 'not ranking' : `#${series.latest_rank}`}
            </p>
          </div>
          <div>
            <span className="text-slate-500">Best</span>
            <p className="font-semibold tabular-nums text-emerald-600">
              {series.best_rank === null ? '-' : `#${series.best_rank}`}
            </p>
          </div>
          <div>
            <span className="text-slate-500">Worst</span>
            <p className="font-semibold tabular-nums text-red-600">
              {series.worst_rank === null ? '-' : `#${series.worst_rank}`}
            </p>
          </div>
          <div>
            <span className="text-slate-500">Observations</span>
            <p className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">{series.points.length}</p>
          </div>
        </div>

        {hasData ? (
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 10, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 12, fill: '#64748b' }}
                  tickLine={false}
                  axisLine={{ stroke: '#cbd5e1' }}
                />
                <YAxis
                  // Rank 1 at the top: lower number is a better position.
                  reversed
                  domain={[best, worst]}
                  allowDecimals={false}
                  tick={{ fontSize: 12, fill: '#64748b' }}
                  tickLine={false}
                  axisLine={{ stroke: '#cbd5e1' }}
                  label={{
                    value: 'Position',
                    angle: -90,
                    position: 'insideLeft',
                    style: { fontSize: 12, fill: '#64748b' },
                  }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Line
                  type="monotone"
                  dataKey="rank"
                  stroke="#213feb"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#213feb' }}
                  activeDot={{ r: 5 }}
                  // Gaps mean "not ranking" and must not be interpolated over.
                  connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="py-16 text-center text-sm text-slate-400">
            No ranking observations recorded yet for this keyword.
          </p>
        )}
      </CardBody>
    </Card>
  );
}
