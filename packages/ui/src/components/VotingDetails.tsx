"use client";
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import type { Article, Ballot, Paginated } from '../types';

export function voteLabel(code: string) {
  return ({ YES: 'Za', NO: 'Przeciw', ABSTAIN: 'Wstrzymał(a) się', ABSENT: 'Nieobecność', NO_VOTE: 'Brak głosu',
    VOTE_VALID: 'Głos ważny', VOTE_INVALID: 'Głos nieważny', PRESENT: 'Obecność' } as Record<string, string>)[code] ?? code;
}

function BallotRow({ ballot }: { ballot: Ballot }) {
  return <li className="rounded-lg bg-white p-3"><div className="flex flex-wrap justify-between gap-2"><span>{ballot.name} <span className="text-sm text-slate-500">{ballot.club}</span></span><strong>{voteLabel(ballot.vote)}</strong></div>
    {Object.keys(ballot.list_votes).length > 0 && <p className="mt-2 text-sm">Wybory na liście: {Object.entries(ballot.list_votes).map(([key, value]) => `${key}: ${voteLabel(value)}`).join('; ')}</p>}</li>;
}

export function VotingDetails({ article }: { article: Article }) {
  const voting = article.voting!;
  const [input, setInput] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const ballots = useQuery({ queryKey: ['ballots', article.id, q, page], queryFn: () => apiFetch<Paginated<Ballot>>(`${voting.ballots_url}?${new URLSearchParams({ q, page: String(page) })}`) });
  return <section className="space-y-4 rounded-xl border border-primary/20 bg-slate-50 p-4">
    <p className="text-sm font-medium text-primary">Sejm · kadencja {voting.term} · posiedzenie {voting.sitting} · głosowanie {voting.number}</p>
    <div><h3 className="font-bold">Dokładny przedmiot głosowania</h3><p className="mt-2">{voting.motion}</p><p className="mt-2 text-sm text-slate-600">„Za” i „przeciw” odnoszą się do tego wniosku. Sam wynik nie wyjaśnia motywacji posła.</p></div>
    <div className="flex flex-wrap gap-4 text-sm">{[['yes', 'Za'], ['no', 'Przeciw'], ['abstain', 'Wstrzymanie'], ['notParticipating', 'Nie głosowało']].map(([key, label]) => voting.counts[key] !== undefined && <span key={key}>{label}: <strong>{voting.counts[key]}</strong></span>)}</div>
    {voting.matching_ballots.length > 0 && <div><h4 className="mb-2 font-semibold">Osoby pasujące do wyszukiwania</h4><ul className="space-y-2">{voting.matching_ballots.map(b => <BallotRow key={b.mp_id} ballot={b} />)}</ul></div>}
    <form className="flex gap-2" onSubmit={e => { e.preventDefault(); setPage(1); setQ(input.trim()); }}><input aria-label="Nazwisko posła" placeholder="Sprawdź nazwisko posła…" maxLength={200} value={input} onChange={e => setInput(e.target.value)} className="min-w-0 flex-1 rounded-lg border p-2" /><button className="rounded-lg bg-primary px-3 text-white">Sprawdź</button></form>
    {ballots.isPending && <p role="status">Pobieram głosy…</p>}{ballots.isError && <p role="alert">Nie udało się pobrać głosów. <button className="underline" onClick={() => ballots.refetch()}>Ponów</button></p>}
    {ballots.data && <><p className="text-sm text-slate-500">Znaleziono: {ballots.data.count}</p><ul className="max-h-80 space-y-2 overflow-y-auto">{ballots.data.results.map(b => <BallotRow key={b.mp_id} ballot={b} />)}</ul><div className="flex justify-between text-sm"><button disabled={!ballots.data.previous} onClick={() => setPage(p => p - 1)} className="disabled:opacity-30">← Poprzednie</button><span>Strona {page}</span><button disabled={!ballots.data.next} onClick={() => setPage(p => p + 1)} className="disabled:opacity-30">Następne →</button></div></>}
    <a href={`${article.url}/pdf`} target="_blank" rel="noopener noreferrer" className="block text-sm font-semibold text-primary">Otwórz urzędowy wydruk głosowania ↗</a>
  </section>;
}
