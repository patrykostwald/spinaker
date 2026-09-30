"use client";

/**
 * Skład Konsylium AI na żywo (GET /api/clinic/council/): model, firma, role, dostępność i przyjęcie Karty z oświadczeniem
 * modelu. Przyjęcie to odpowiedź konkretnej wersji modelu na pełną treść Karty — nie podpis ani poparcie firmy.
 */

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../../lib/api";
import { formatDatePl } from "../../lib/utils";

type Member = {
  model: string; company: string; provider: string; roles: string[]; status: string;
  charter: { version: string; date: string; accepts: boolean; statement?: string } | null;
};
type Recruitment = {
  date: string; kind: string; model: string; company: string; provider: string; decision: string; mode: string; roles: string[]; reason: string;
  exam: { items: number; answered: number; agreement: number; mae: number; passed: boolean } | null;
  votes: { model: string; admit: boolean | null; reason: string }[];
};
type Council = { charter_version: string; members: Member[]; recruitment?: Recruitment[] };

const shortModel = (model: string) => model.split("/").pop()!.replace(/:.*$/, "");

export function CouncilRoster() {
  const query = useQuery({ queryKey: ["clinic-council"], queryFn: () => apiFetch<Council>("/api/clinic/council/"), staleTime: 10 * 60_000 });
  if (query.isPending) return <p className="sc-council__empty">Wczytujemy skład Konsylium…</p>;
  if (query.isError || !query.data) return <p className="sc-council__empty">Skład Konsylium jest chwilowo niedostępny.</p>;
  // Pokazujemy cały skonfigurowany skład (także modele na przerwie po dziennym limicie); oświadczenie tylko tam, gdzie model je złożył.
  const members = query.data.members.filter(m => m.status !== "niedostępny");
  const accepted = members.filter(m => m.charter?.accepts).length;
  return (
    <div className="sc-council">
      <p className="sc-council__summary">
        <strong>{members.length}</strong> modeli · <strong>{new Set(members.map(m => m.company)).size}</strong> firm
        {accepted === members.length && members.length ? <> · wszystkie przyjęły Kartę {query.data.charter_version}</> : null}
      </p>
      <ul className="sc-council__list">
        {members.map(member => (
          <li key={`${member.provider}-${member.model}`} className="sc-council__member" data-status={member.status}>
            <div className="sc-council__head">
              <p className="sc-council__model">{shortModel(member.model)}</p>
              <p className="sc-council__company">{member.company}</p>
              <p className="sc-council__provider">Dostawca usługi: {member.provider}</p>
            </div>
            <p className="sc-council__roles">{member.roles.join(" · ")}</p>
            {member.status === "limit dzienny" ? <p className="sc-council__provider">Dziś wyczerpał darmowy limit zapytań — wraca o północy.</p> : null}
            {member.status === "zawieszony" ? <p className="sc-council__provider">Zawieszony przez Rekrutera: od kilku dni nie odpowiada. Wróci sam, gdy znów zacznie działać.</p> : null}
            {member.charter?.accepts ? (
              <blockquote className="sc-council__statement" data-accepts={member.charter.accepts}>
                „{member.charter.statement || "Przyjmuję zasady Karty."}”
                <footer>Przyjął Kartę {member.charter.version} · {formatDatePl(member.charter.date)}</footer>
              </blockquote>
            ) : null}
          </li>
        ))}
      </ul>
      <p className="sc-council__note">Oświadczenia są odpowiedziami poszczególnych wersji modeli na pełną treść Karty. Nie oznaczają poparcia firm, które te modele udostępniają.</p>
    </div>
  );
}

const DECISIONS: Record<string, string> = {
  admitted: "przyjęty", rejected: "odrzucony", would_admit: "rekomendacja: przyjąć", would_reject: "rekomendacja: odrzucić",
  suspended: "zawieszony", returned: "powrót do składu",
};

/** Jawny dziennik Rekrutera Konsylium: kandydaci, egzamin, głosy członków, zawieszenia i powroty. */
export function CouncilRecruitmentLog() {
  const query = useQuery({ queryKey: ["clinic-council"], queryFn: () => apiFetch<Council>("/api/clinic/council/"), staleTime: 10 * 60_000 });
  if (query.isPending || query.isError || !query.data) return null;
  const rows = query.data.recruitment ?? [];
  if (!rows.length) return <p className="sc-council__empty">Rekruter nie ocenił jeszcze żadnego kandydata. Pierwszy przegląd odbywa się w nocy.</p>;
  return <ol className="sc-recruit">{rows.map((row, index) => (
    <li key={index} className="sc-recruit__row" data-decision={row.decision}>
      <p className="sc-recruit__head"><strong>{shortModel(row.model)}</strong><span>{row.company}</span>
        <span className="sc-recruit__decision">{DECISIONS[row.decision] ?? row.decision}{row.mode === "trial" && row.kind === "candidate" ? " · tryb próbny" : ""}</span>
        <time dateTime={row.date}>{formatDatePl(row.date)}</time></p>
      {row.exam ? <p className="sc-recruit__exam">Egzamin: {row.exam.answered}/{row.exam.items} odpowiedzi · zgodność z Konsylium {Math.round(row.exam.agreement * 100)}% · różnica siły {row.exam.mae} pkt · {row.exam.passed ? "progi spełnione" : "progi niespełnione"}</p> : null}
      <p className="sc-recruit__reason">{row.reason}</p>
      {row.votes.length ? <ul className="sc-recruit__votes">{row.votes.map((vote, voteIndex) => (
        <li key={voteIndex}><strong>{shortModel(vote.model)}</strong> — {vote.admit === true ? "za" : vote.admit === false ? "przeciw" : "brak głosu"}{vote.reason ? `: ${vote.reason}` : ""}</li>
      ))}</ul> : null}
    </li>
  ))}</ol>;
}
