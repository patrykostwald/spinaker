"use client";

import { useQuery } from "@tanstack/react-query";
import { CAMPS, CAMP_LABELS, searchClinicSpins, type Camp, type ClinicPageData } from "../../lib/clinic";
import { SectionHeader } from "../../kit/SectionHeader";
import { SpinRow } from "./SpinParts";

function RankingColumn({ camp, from, to }: { camp: Camp; from: string; to: string }) {
  const query = useQuery({ queryKey: ["clinic-ranking", camp, from, to],
    queryFn: () => searchClinicSpins({ camp, sort: "strong", page_size: 3, date_from: from, date_to: to }),
    staleTime: 5 * 60_000 });
  return <section className="sc-clinic-column" aria-labelledby={`clinic-ranking-${camp}`}>
    <h3 id={`clinic-ranking-${camp}`} className="sc-camp-heading" data-camp={camp}>{CAMP_LABELS[camp]}
      {query.data?.count !== undefined ? <small> z {query.data.count} diagnoz</small> : null}</h3>
    {query.isPending ? <p role="status">Wczytywanie rankingu…</p> : null}
    {query.isError ? <p role="alert">Nie udało się pobrać rankingu. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p> : null}
    {query.data ? query.data.results.length ? <ol className="sc-clinic-ranking__list">
      {query.data.results.slice(0, 3).map(spin => <li key={spin.id}><SpinRow spin={spin} /></li>)}
    </ol> : <p>Brak diagnoz w tym okresie.</p> : null}
  </section>;
}

export function ClinicRanking({ data }: { data: ClinicPageData }) {
  if (!data.generated_at) return null;
  const to = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Warsaw", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(data.generated_at));
  const start = new Date(`${to}T12:00:00Z`);
  start.setUTCDate(start.getUTCDate() - data.scale.window_days + 1);
  const from = start.toISOString().slice(0, 10);
  return <section className="sc-clinic-group sc-clinic-ranking" aria-labelledby="clinic-ranking-title">
    <SectionHeader titleId="clinic-ranking-title" title="Najwyższa siła spinu"
      subtitle={`Po trzy najsilniejsze spiny każdej strony z ostatnich ${data.scale.window_days} dni, w tej samej skali. To wybrane wpisy, nie przegląd całej polityki.`} />
    <div className="sc-clinic-ranking__columns">{CAMPS.map(camp => <RankingColumn key={camp} camp={camp} from={from} to={to} />)}</div>
  </section>;
}
