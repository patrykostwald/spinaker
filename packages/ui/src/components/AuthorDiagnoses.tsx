"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { searchClinicSpins } from "../lib/clinic";
import { verifiedXAccount, type PublicFigureDetail } from "../lib/publicFigures";
import { SpinRow } from "./clinic/SpinParts";

/** Chronology from the verified account's database ID; never a name search. */
export function AuthorDiagnoses({ figure }: { figure: PublicFigureDetail }) {
  const account = verifiedXAccount(figure);
  const accountId = account?.account_id;
  const available = Number.isSafeInteger(accountId) && accountId! > 0;
  const query = useQuery({
    queryKey: ["author-diagnoses", accountId],
    queryFn: () => searchClinicSpins({ account: String(accountId), sort: "new" }),
    enabled: available,
  });
  const href = `/klinika/diagnozy?account=${accountId}`;
  return <section className="sc-public-figure-section sc-author-diagnoses" aria-labelledby="author-diagnoses-title">
    <header><h2 id="author-diagnoses-title">Diagnozy wpisów</h2>
      <p>Chronologia analiz wpisów z potwierdzonego konta, od najnowszego materiału. Każdy wynik dotyczy konkretnego wpisu.</p>
    </header>
    {!available ? <p>Brak powiązania z potwierdzonym kontem umożliwiającego pokazanie diagnoz.</p> : <>
      <p><a href={account!.url} target="_blank" rel="noopener noreferrer">@{account!.handle} ↗</a> · <Link href={href}>Wszystkie diagnozy tego konta w bazie →</Link></p>
      {query.isPending ? <p role="status">Wczytywanie diagnoz…</p> : null}
      {query.isError ? <p role="alert">Nie udało się pobrać diagnoz. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p> : null}
      {query.isSuccess && !query.data.results.length ? <p>Nie ma jeszcze opublikowanych diagnoz wpisów z tego konta.</p> : null}
      <ol className="sc-author-diagnoses__list">{query.data?.results.slice(0, 6).map(spin => <li key={spin.id}>
        <SpinRow spin={spin} withSummary withTechniques />
        <a className="sc-author-diagnoses__source" href={spin.post.url} target="_blank" rel="noopener noreferrer">Wpis źródłowy ↗</a>
      </li>)}</ol>
    </>}
  </section>;
}
