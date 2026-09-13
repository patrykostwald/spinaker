'use client';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
type ArchiveStatus = { records: number; active_sources: number; worker_status: 'running' | 'unconfirmed'; checked_at: string; complete: false };
export function ArchiveProgress() {
  const status = useQuery({ queryKey: ['archive-progress'], queryFn: () => apiFetch<ArchiveStatus>('/api/archive/status/'), staleTime: 10_000, refetchInterval: 30_000, retry: false });
  const data = status.data;
  return <section aria-label="Rozbudowa archiwum" className="archive-progress flex flex-wrap items-center justify-between gap-3 border-b py-3 text-xs text-slate-400">
    <div><p className="font-medium text-slate-200">Budujemy archiwum polskich źródeł.</p><p className="mt-1">Uzupełniamy bieżące doniesienia i materiały z przeszłości. Pokazujemy także znane braki.</p></div>
    <div className="space-y-1 md:text-right"><p>{data ? <><span className="tabular-nums text-slate-200">{data.records.toLocaleString('pl-PL')}</span> materiałów · {data.active_sources} aktywnych źródeł</> : 'Odczyt stanu archiwum…'}</p><p>{status.isError ? 'Stan importerów chwilowo niedostępny' : data?.worker_status === 'running' ? 'Importery działają · archiwum jest rozbudowywane' : data ? 'Brak bieżącego potwierdzenia pracy importerów' : 'Sprawdzam pracę importerów…'}</p></div>
  </section>;
}
