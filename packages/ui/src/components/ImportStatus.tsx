"use client";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import { formatDateTimePl } from "../lib/utils";
import { Button } from "../kit/Button";

type Status = { local_worker_active: boolean; archive_queue: { status: string; count: number }[]; articles: number; rss_sources: number; rss_with_errors: number; local_mode: boolean; x_enabled: boolean; newsapi_enabled: boolean; source_errors: { id: number; name: string; last_error: string; last_scraped: string | null }[]; jobs: { name: string; last_success: string | null; last_error: string; imported: number }[]; };

export function ImportStatus() {
  const status = useQuery({ queryKey: ["editor-status"], queryFn: () => apiFetch<Status>("/api/editor/status/"), refetchOnWindowFocus: false });
  if (status.isPending) return <p role="status" className="sc-t-body sc-text-2">Sprawdzam stan źródeł…</p>;
  if (!status.data) return <p role="alert" className="sc-t-body sc-editor-status__error">Nie udało się odczytać stanu importów.</p>;
  const data = status.data;
  return <details className="sc-editor-status"><summary>Stan bazy: {data.articles.toLocaleString("pl-PL")} materiałów · {data.rss_with_errors} źródeł RSS z błędem</summary><div className="sc-editor-status__body"><p className="sc-t-body sc-text-2">X: odnośniki dodawane do nitek, bez importu treści · NewsAPI: {data.newsapi_enabled ? "integracja włączona" : "nieaktywne — potrzebny klucz i aktywacja"}</p>{data.local_mode ? <p className="sc-editor-status__notice">{data.local_worker_active ? "Lokalny proces pobierania działa. Poniżej wyniki i błędy poszczególnych importów." : "Lokalny proces pobierania nie zgłosił aktywności w ostatnich 90 sekundach."}</p> : null}<dl>{data.jobs.map(job => <div key={job.name}><dt>{job.name}</dt><dd>ostatni sukces: {job.last_success ? formatDateTimePl(job.last_success) : "jeszcze nie zapisano"} · import: {job.imported}{job.last_error ? <span className="sc-editor-status__error">{job.last_error}</span> : null}</dd></div>)}</dl>{data.source_errors.length ? <section><h3 className="sc-t-title-s">Źródła wymagające sprawdzenia</h3><ul>{data.source_errors.map(source => <li key={source.id}><strong>{source.name}</strong>: {source.last_error}</li>)}</ul></section> : null}<Button type="button" variant="secondary" size="sm" onClick={() => status.refetch()}>Odśwież stan</Button></div></details>;
}
