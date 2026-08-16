'use client';

import { useRef, useState } from 'react';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Alert, Button } from '@/components/ui/Form';
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table';
import { bulkApi } from '@/lib/api';
import { ALL_COLUMNS, buildTemplateCsv, parseCsv, REQUIRED_COLUMNS } from '@/lib/csv';
import type { BulkRow, BulkUploadResponse, User } from '@/lib/types';

/**
 * Bulk CSV upload.
 *
 * The file is parsed and validated in the browser first, so the user sees a
 * preview and per-row errors before any data is sent. Only validated rows are
 * posted to the bulk-insert endpoint.
 */

const PREVIEW_ROWS = 10;

export function CsvUploader({ currentUser }: { currentUser?: User }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [rows, setRows] = useState<BulkRow[]>([]);
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<BulkUploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isReadOnly = currentUser?.role === 'read_only' || (!currentUser?.is_superuser && currentUser?.role !== 'read_write');

  function reset() {
    setRows([]);
    setParseErrors([]);
    setResult(null);
    setError(null);
    setFileName(null);
    if (inputRef.current) inputRef.current.value = '';
  }

  async function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    if (isReadOnly) return;
    const file = event.target.files?.[0];
    if (!file) return;

    setResult(null);
    setError(null);
    setFileName(file.name);

    try {
      const text = await file.text();
      const parsed = parseCsv(text);
      setRows(parsed.rows);
      setParseErrors(parsed.errors);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not read the file');
      setRows([]);
    }
  }

  async function handleUpload() {
    if (isReadOnly || rows.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      const res = await bulkApi.insertRows(rows);
      setResult(res);
      if (res.rows_processed > 0 && res.errors.length === 0) {
        setRows([]);
        setFileName(null);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Bulk import failed');
    } finally {
      setUploading(false);
    }
  }

  function downloadTemplate() {
    const csvContent = buildTemplateCsv();
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'seo_intent_bulk_template.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Bulk upload"
          description="Create clients, projects, target URLs and keywords from one CSV"
          action={
            <Button variant="secondary" size="sm" onClick={downloadTemplate}>
              Download template
            </Button>
          }
        />
        <CardBody className="space-y-4">
          <div className="rounded-md bg-slate-50 dark:bg-slate-800/40 p-4 text-sm text-slate-600 dark:text-slate-400">
            <p className="font-medium text-slate-800 dark:text-slate-200">Expected columns</p>
            <p className="mt-1 font-mono text-xs">{ALL_COLUMNS.join(', ')}</p>
            <p className="mt-2 text-xs">
              Required: <span className="font-mono">{REQUIRED_COLUMNS.join(', ')}</span>. All
              other columns are optional and fall back to the defaults (location 2840,
              language <span className="font-mono">en</span>, daily at 03:00 UTC). Existing
              clients, projects and URLs are reused rather than duplicated.
            </p>
          </div>

          {!isReadOnly ? (
            <div className="flex flex-wrap items-center gap-3">
              <input
                ref={inputRef}
                type="file"
                accept=".csv,text/csv"
                onChange={handleFile}
                className="block text-sm text-slate-600 dark:text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-brand-600 dark:file:bg-yoyaba-yellow file:px-3 file:py-2 file:text-sm file:font-medium file:text-white dark:file:text-slate-900 hover:file:bg-brand-700 dark:hover:file:bg-[#E6C100]"
              />
              {fileName ? (
                <Button variant="ghost" size="sm" onClick={reset}>
                  Clear
                </Button>
              ) : null}
            </div>
          ) : (
            <Alert tone="info">
              Bulk upload requires Read & Write permissions. As a Read Only user, you can download the template above to view the format.
            </Alert>
          )}

          {error ? <Alert tone="error">{error}</Alert> : null}

          {result ? (
            <Alert tone={result.errors.length > 0 ? 'warning' : 'success'}>
              Processed {result.rows_processed} row(s) (Created: {result.clients_created} clients, {result.projects_created} projects, {result.urls_created} URLs, {result.keywords_created} keywords).
              {result.rows_skipped > 0 ? ` Skipped ${result.rows_skipped} row(s).` : ''}
              {result.errors.length > 0 ? (
                <ul className="mt-2 list-disc pl-5 text-xs">
                  {result.errors.map((msg, idx) => (
                    <li key={idx}>{msg}</li>
                  ))}
                </ul>
              ) : null}
            </Alert>
          ) : null}

          {!isReadOnly && parseErrors.length > 0 ? (
            <Alert tone="error">
              <p className="font-medium">File validation errors:</p>
              <ul className="mt-1 list-disc pl-5 text-xs">
                {parseErrors.map((msg, idx) => (
                  <li key={idx}>{msg}</li>
                ))}
              </ul>
            </Alert>
          ) : null}
        </CardBody>
      </Card>

      {!isReadOnly && rows.length > 0 ? (
        <Card>
          <CardHeader
            title={`Preview (${rows.length} valid row${rows.length === 1 ? '' : 's'})`}
            description={`Showing first ${Math.min(rows.length, PREVIEW_ROWS)} rows`}
            action={
              <Button onClick={handleUpload} disabled={uploading || parseErrors.length > 0}>
                {uploading ? 'Importing...' : `Import ${rows.length} rows`}
              </Button>
            }
          />
          <CardBody className="px-0 py-0">
            <Table>
              <THead>
                <TR>
                  <TH>Client</TH>
                  <TH>Project</TH>
                  <TH>URL</TH>
                  <TH>Keyword</TH>
                  <TH>Market</TH>
                  <TH>Schedule</TH>
                </TR>
              </THead>
              <TBody>
                {rows.slice(0, PREVIEW_ROWS).map((row, idx) => (
                  <TR key={idx}>
                    <TD className="font-medium text-slate-900 dark:text-slate-100">{row.client_name}</TD>
                    <TD>{row.project_name}</TD>
                    <TD className="max-w-xs truncate text-xs" title={row.url}>
                      {row.url}
                    </TD>
                    <TD className="text-xs">{row.keyword}</TD>
                    <TD className="text-xs">
                      {(row.language_code || 'en').toUpperCase()} / {row.location_code || 2840}
                    </TD>
                    <TD className="text-xs">
                      {row.check_interval || 'daily'} @ {row.execution_time || '03:00'}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}
