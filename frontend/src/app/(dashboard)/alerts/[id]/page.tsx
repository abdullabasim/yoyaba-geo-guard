import { notFound } from 'next/navigation';

import { AlertDetail } from '@/components/AlertDetail';
import { alertsApi } from '@/lib/api';
import { getCookieHeader, requireUser } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export default async function AlertDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireUser();
  const cookieHeader = await getCookieHeader();
  
  const { id } = await params;
  const alertId = parseInt(id, 10);
  if (isNaN(alertId)) {
    notFound();
  }

  try {
    const alert = await alertsApi.get(alertId, cookieHeader);
    return <AlertDetail alert={alert} />;
  } catch (error) {
    notFound();
  }
}
