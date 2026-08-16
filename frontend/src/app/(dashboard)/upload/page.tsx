import { CsvUploader } from '@/components/CsvUploader';
import { requireUser } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export default async function UploadPage() {
  const currentUser = await requireUser();

  return (
    <div className="tour-upload-page space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-yoyaba-yellow">Bulk Upload</h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-300">
          Import clients, projects, target URLs and keywords from a single CSV file
        </p>
      </div>
      <CsvUploader currentUser={currentUser} />
    </div>
  );
}
