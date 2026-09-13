"use client";
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import { formatDateTimePl } from '../lib/utils';

type Status = {
  local_worker_active: boolean; archive_queue: {status: string; count: number}[]; articles: number; rss_sources: number; rss_with_errors: number; local_mode: boolean; x_enabled: boolean; newsapi_enabled: boolean;
  source_errors: {id: number; name: string; last_error: string; last_scraped: string | null}[];
  jobs: {name: string; last_success: string | null; last_error: string; imported: number}[];
};

export function ImportStatus() {
  const status = useQuery({ queryKey: ['editor-status'], queryFn: () => apiFetch<Status>('/api/editor/status/'), refetchOnWindowFocus: false });
  if (status.isPending) return <p role="status" className="text-sm text-slate-500">Sprawdzam stan źródeł…</p>;
  if (!status.data) return <p className="text-sm text-red-700">Nie udało się odczytać stanu importów.</p>;
  const data = status.data;
  return <details className="rounded-xl border bg-white p-5"><summary className="cursor-pointer font-semibold">Stan bazy: {data.articles.toLocaleString('pl-PL')} materiałów · {data.rss_with_errors} źródeł RSS z błędem</summary>
    <div className="mt-4 space-y-4 text-sm"><p>X: odnośniki dodawane do nitek, bez importu treści · NewsAPI: {data.newsapi_enabled ? 'integracja włączona' : 'nieaktywne — potrzebny klucz i aktywacja'}</p>
      {data.local_mode && <p className="rounded-lg bg-rose-50 p-3">{data.local_worker_active ? 'Lokalny proces pobierania działa. Poniżej wyniki i błędy poszczególnych importów.' : 'Lokalny proces pobierania nie zgłosił aktywności w ostatnich 90 sekundach.'}</p>}
      {data.jobs.map(job => <p key={job.name}><strong>{job.name}</strong> · ostatni sukces: {job.last_success ? formatDateTimePl(job.last_success) : 'jeszcze nie zapisano'}{job.last_error && <span className="block text-red-700">{job.last_error}</span>}</p>)}
      {data.source_errors.length > 0 && <div className="max-h-64 space-y-2 overflow-y-auto"><h3 className="font-semibold">Źródła wymagające sprawdzenia</h3>{data.source_errors.map(source => <p key={source.id}><strong>{source.name}</strong>: {source.last_error}</p>)}</div>}
      <button type="button" onClick={() => status.refetch()} className="font-semibold text-primary">Odśwież stan</button>
    </div>
  </details>;
}
