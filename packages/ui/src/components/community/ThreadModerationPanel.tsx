"use client";
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch, apiWrite } from '../../lib/api';
import { ClampedText } from './SocialPrimitives';

type Report = { id: number; thread_id: number | null; target_kind: string; reason: string; details: string; snapshot: string; status: string; ai: { state?: string; probability?: number; rule?: string }; appeal: string; decisions: { action: string; rule: string; explanation: string }[] };
type Queue = { results: Report[]; next_page: number | null; rules: Record<string, string> };

function Review({ report, rules, done }: { report: Report; rules: Queue['rules']; done: () => void }) {
  const [action, setAction] = useState(''), [rule, setRule] = useState(''), [explanation, setExplanation] = useState('');
  const [pending, setPending] = useState(false), [error, setError] = useState('');
  return <article className="sc-command-card sc-thread-social">
    <h3>Zgłoszenie {report.id} · {report.target_kind === 'comment' ? 'komentarz' : 'trop'}</h3>
    <p>{report.reason}: {report.details}</p><ClampedText>{report.snapshot}</ClampedText>
    <p>Wstępna ocena AI: {report.ai.state === 'assessed' ? `${Math.round((report.ai.probability ?? 0)*100)}%, ${report.ai.rule}` : 'brak oceny'}. Decyzję podejmuje człowiek.</p>
    {report.thread_id && <a href={`/tropy/${report.thread_id}`}>Otwórz trop</a>}
    {report.decisions.map((d, i) => <p key={i}>Poprzednia decyzja: {d.action}, {d.rule}. {d.explanation}</p>)}
    {report.appeal && <p><strong>Odwołanie: </strong>{report.appeal}</p>}
    <form onSubmit={async event => {
      event.preventDefault(); if (pending) return; setPending(true); setError('');
      try { await apiWrite('/api/community/moderation/', { report_id: report.id, action, rule, explanation }); done(); }
      catch (error) { setError(error instanceof Error ? error.message : 'Nie udało się zapisać decyzji.'); } finally { setPending(false); }
    }}>
      <label>Decyzja<select value={action} onChange={e => setAction(e.target.value)} required><option value="">Wybierz</option><option value="hide">Ukryj</option><option value="restore">Przywróć</option></select></label>
      <label>Punkt regulaminu<select value={rule} onChange={e => setRule(e.target.value)} required><option value="">Wybierz</option>{Object.entries(rules).map(([key,label]) => <option value={key} key={key}>{key}: {label}</option>)}</select></label>
      <label>Uzasadnienie dla autora i osoby zgłaszającej<textarea value={explanation} maxLength={2000} onChange={e => setExplanation(e.target.value)} required /></label>
      <button disabled={pending || !action || !rule || !explanation.trim()}>Zapisz decyzję i powiadom strony</button><p role="alert">{error}</p>
    </form>
  </article>;
}

export function ThreadModerationPanel() {
  const [open, setOpen] = useState(false), [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ['thread-moderation', page], queryFn: () => apiFetch<Queue>(`/api/community/moderation/?page=${page}`), enabled: open, retry: false });
  return <details className="sc-command-card sc-thread-moderation" onToggle={e => setOpen(e.currentTarget.open)}><summary>Moderacja tropów i komentarzy</summary>
    {query.isLoading && <div className="sc-social-skeleton" aria-label="Ładowanie zgłoszeń" />}
    {query.isError && <p role="alert">Nie można odczytać kolejki. Potrzebujesz uprawnienia do moderacji tropów. <button onClick={() => query.refetch()}>Ponów</button></p>}
    {query.data?.results.map(row => <Review key={row.id} report={row} rules={query.data.rules} done={() => { setPage(1); void query.refetch(); }} />)}
    {query.isSuccess && !query.data.results.length && <p>Nie ma zgłoszeń oczekujących na decyzję.</p>}
    {page > 1 && <button onClick={() => setPage(p => p-1)}>Poprzednie</button>}
    {query.data?.next_page && <button onClick={() => setPage(query.data!.next_page!)}>Kolejne</button>}
    <p><a href="/admin/news/threadmoderationdecision/">Rejestr decyzji i eksport do raportu przejrzystości</a></p>
  </details>;
}
