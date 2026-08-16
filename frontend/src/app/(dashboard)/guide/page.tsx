import { UserGuide } from '@/components/UserGuide';
import { requireUser } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export default async function GuidePage() {
  const currentUser = await requireUser();

  return <UserGuide currentUser={currentUser} />;
}
