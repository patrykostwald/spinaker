"use client";
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch, apiWrite } from '../../lib/api';
import { useFeature } from '../../lib/features';
import { Loading } from "../../kit/Loading";

type Decision = { action: string; rule: string; explanation: string; created_at: string; is_appeal: boolean };
export function ThreadAppealPage({ params }: { params: { id: string } }) {
  const enabled = useFeature('ACCOUNTS_ENABLED');
  const threads = useFeature('THREADS_ENABLED');
  const path = `/api/community/reports/${params.id}/`;
  const query = useQuery({ queryKey: ['thread-appeal', params.id], queryFn: () => apiFetch<{ status: string; appealed: boolean; decisions: Decision[] }>(path), enabled: enabled && threads, retry: false });
  const [body, setBody] = useState(''), [status, setStatus] = useState(''), [pending, setPending] = useState(false);
  if (!enabled || !threads) return <p>Odwołania będą dostępne po włączeniu kont i spinek. Kontakt: <a href="/zasady-korzystania#tropy">punkt kontaktowy</a>.</p>;
  return <article className="sc-community sc-thread-social"><h1>Decyzja i odwołanie</h1>
    {query.isLoading && <Loading label="Ładowanie decyzji" />}
    {query.isError && <p>Decyzję może odczytać autor lub osoba zgłaszająca. <a href="/konto">Zaloguj się</a>.</p>}
    {query.data?.decisions.map((d, i) => <section key={i}><h2>{d.is_appeal ? 'Rozpatrzenie odwołania' : 'Decyzja zespołu'}</h2><p>{d.action === 'hide' ? 'Ukrycie treści' : 'Przywrócenie widoczności'} · {d.rule}</p><p>{d.explanation}</p></section>)}
    {query.data?.status === 'resolved' && !query.data.appealed && <form onSubmit={async e => {
      e.preventDefault(); if (pending) return; setPending(true);
      try { await apiWrite(path, { body }); await query.refetch(); setStatus('Odwołanie czeka na rozpatrzenie przez człowieka.'); }
      catch (error) { setStatus(error instanceof Error ? error.message : 'Nie udało się wysłać.'); } finally { setPending(false); }
    }}><label>Uzasadnienie odwołania<textarea maxLength={2000} value={body} onChange={e => setBody(e.target.value)} required /></label><small>{body.length}/2000</small><button disabled={pending || !body.trim()}>Wyślij jednorazowe odwołanie</button></form>}
    {query.data?.appealed && <p>Odwołanie zostało już złożone. Rozpatruje je inny członek zespołu.</p>}<p role="status">{status}</p>
  </article>;
}
