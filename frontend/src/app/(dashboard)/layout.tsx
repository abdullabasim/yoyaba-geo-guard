import { Sidebar } from '@/components/Sidebar';
import { AppTour } from '@/components/AppTour';
import { requireUser } from '@/lib/auth';

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await requireUser();

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-transparent transition-colors duration-200">
      <AppTour />
      <Sidebar user={user} />
      <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
        <div className="mx-auto max-w-[1600px] w-full">
          {children}
        </div>
      </main>
    </div>
  );
}
