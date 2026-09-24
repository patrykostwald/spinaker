"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { Article, Ballot, Paginated } from "../types";
import { Button, SearchField } from "../kit";

export function voteLabel(code: string) {
  return ({ YES: "Za", NO: "Przeciw", ABSTAIN: "Wstrzymał(a) się", ABSENT: "Nieobecność", NO_VOTE: "Brak głosu", VOTE_VALID: "Głos ważny", VOTE_INVALID: "Głos nieważny", PRESENT: "Obecność" } as Record<string, string>)[code] ?? code;
}

function BallotRow({ ballot }: { ballot: Ballot }) {
  return <li className="sc-voting-details__ballot"><div><span>{ballot.name} <small>{ballot.club}</small></span><strong>{voteLabel(ballot.vote)}</strong></div>{Object.keys(ballot.list_votes).length ? <p>Wybory na liście: {Object.entries(ballot.list_votes).map(([key, value]) => `${key}: ${voteLabel(value)}`).join("; ")}</p> : null}</li>;
}

export function VotingDetails({ article }: { article: Article }) {
  const voting = article.voting!;
  const [input, setInput] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const ballots = useQuery({ queryKey: ["ballots", article.id, q, page], queryFn: () => apiFetch<Paginated<Ballot>>(`${voting.ballots_url}?${new URLSearchParams({ q, page: String(page) })}`) });
  return <section className="sc-voting-details">
    <p className="sc-voting-details__meta">Sejm · kadencja {voting.term} · posiedzenie {voting.sitting} · głosowanie {voting.number}</p>
    <div><h3>Dokładny przedmiot głosowania</h3><p>{voting.motion}</p><p className="sc-voting-details__note">„Za” i „przeciw” odnoszą się do tego wniosku. Sam wynik nie wyjaśnia motywacji posła.</p></div>
    <div className="sc-voting-details__counts">{[["yes", "Za"], ["no", "Przeciw"], ["abstain", "Wstrzymanie"], ["notParticipating", "Nie głosowało"]].map(([key, label]) => voting.counts[key] !== undefined ? <span key={key}>{label}: <strong>{voting.counts[key]}</strong></span> : null)}</div>
    {voting.matching_ballots.length ? <div><h4>Osoby pasujące do wyszukiwania</h4><ul className="sc-voting-details__list">{voting.matching_ballots.map(ballot => <BallotRow key={ballot.mp_id} ballot={ballot} />)}</ul></div> : null}
    <form className="sc-voting-details__search" onSubmit={event => { event.preventDefault(); setPage(1); setQ(input.trim()); }}><SearchField label="Nazwisko posła" placeholder="Sprawdź nazwisko posła…" maxLength={200} value={input} onChange={setInput} /><Button type="submit" variant="primary">Sprawdź</Button></form>
    {ballots.isPending ? <p role="status">Pobieram głosy…</p> : null}{ballots.isError ? <p role="alert">Nie udało się pobrać głosów. <Button type="button" variant="quiet" size="sm" onClick={() => ballots.refetch()}>Ponów</Button></p> : null}
    {ballots.data ? <><p className="sc-voting-details__note">Znaleziono: {ballots.data.count}</p><ul className="sc-voting-details__list is-scrollable">{ballots.data.results.map(ballot => <BallotRow key={ballot.mp_id} ballot={ballot} />)}</ul><div className="sc-voting-details__pager"><Button type="button" variant="quiet" size="sm" disabled={!ballots.data.previous} onClick={() => setPage(current => current - 1)}>Poprzednie</Button><span>Strona {page}</span><Button type="button" variant="quiet" size="sm" disabled={!ballots.data.next} onClick={() => setPage(current => current + 1)}>Następne</Button></div></> : null}
    <a href={`${article.url}/pdf`} target="_blank" rel="noopener noreferrer" className="sc-voting-details__print">Otwórz urzędowy wydruk głosowania ↗</a>
  </section>;
}
