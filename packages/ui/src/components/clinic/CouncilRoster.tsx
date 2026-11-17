"use client";

/**
 * Skład Konsylium AI na żywo (GET /api/clinic/council/): model, firma, role, dostępność i przyjęcie Karty z oświadczeniem
 * modelu. Przyjęcie to odpowiedź konkretnej wersji modelu na pełną treść Karty - nie podpis ani poparcie firmy.
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
type LanguageProps = { lang?: "pl" | "en" };
const EN_ROLES: Record<string, string> = { "członek": "member", "przewodniczący": "Chair", "językoznawca": "Linguist", "recenzent": "Reviewer" };
const councilDate = (date: string, en: boolean) => en
  ? new Date(date).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Warsaw" })
  : formatDatePl(date);

export function CouncilRoster({ lang = "pl" }: LanguageProps) {
  const en = lang === "en";
  const query = useQuery({ queryKey: ["clinic-council"], queryFn: () => apiFetch<Council>("/api/clinic/council/"), staleTime: 10 * 60_000 });
  if (query.isPending) return <p className="sc-council__empty">{en ? "Loading Council membership…" : "Wczytujemy skład Konsylium…"}</p>;
  if (query.isError || !query.data) return <p className="sc-council__empty">{en ? "Council membership is temporarily unavailable." : "Skład Konsylium jest chwilowo niedostępny."}</p>;
  // Pokazujemy cały skonfigurowany skład (także modele na przerwie po dziennym limicie); oświadczenie tylko tam, gdzie model je złożył.
  const members = query.data.members.filter(m => m.status !== "niedostępny");
  const accepted = members.filter(m => m.charter?.accepts).length;
  return (
    <div className="sc-council">
      <p className="sc-council__summary">
        <strong>{members.length}</strong> {en ? "models" : "modeli"} · <strong>{new Set(members.map(m => m.company)).size}</strong> {en ? "companies" : "firm"}
        {accepted === members.length && members.length ? <> · {en ? "all have accepted Charter" : "wszystkie przyjęły Kartę"} {query.data.charter_version}</> : null}
      </p>
      <ul className="sc-council__list">
        {members.map(member => (
          <li key={`${member.provider}-${member.model}`} className="sc-council__member" data-status={member.status}>
            <div className="sc-council__head">
              <p className="sc-council__model">{shortModel(member.model)}</p>
              <p className="sc-council__company">{member.company}</p>
              <p className="sc-council__provider">{en ? "Service provider:" : "Dostawca usługi:"} {member.provider}</p>
            </div>
            <p className="sc-council__roles">{member.roles.map(role => en ? EN_ROLES[role] ?? `${role} (in Polish)` : role).join(" · ")}</p>
            {member.status === "limit dzienny" ? <p className="sc-council__provider">{en ? "Today's free request quota is exhausted - returns at midnight." : "Dziś wyczerpał darmowy limit zapytań - wraca o północy."}</p> : null}
            {member.status === "zawieszony" ? <p className="sc-council__provider">{en ? "Suspended by the Recruiter after several days without a response. Returns automatically when it works again." : "Zawieszony przez Rekrutera: od kilku dni nie odpowiada. Wróci sam, gdy znów zacznie działać."}</p> : null}
            {member.charter?.accepts ? (
              <blockquote className="sc-council__statement" data-accepts={member.charter.accepts}>
                {en ? <><small>Model statement (in Polish): </small><span lang="pl">„{member.charter.statement || "Przyjmuję zasady Karty."}”</span></> : <>„{member.charter.statement || "Przyjmuję zasady Karty."}”</>}
                <footer>{en ? "Accepted Charter" : "Przyjął Kartę"} {member.charter.version} · {councilDate(member.charter.date, en)}</footer>
              </blockquote>
            ) : null}
          </li>
        ))}
      </ul>
      <p className="sc-council__note">{en ? "Statements are responses by individual model versions to the full Charter. They do not imply endorsement by the companies providing those models." : "Oświadczenia są odpowiedziami poszczególnych wersji modeli na pełną treść Karty. Nie oznaczają poparcia firm, które te modele udostępniają."}</p>
    </div>
  );
}

const DECISIONS: Record<string, string> = {
  admitted: "przyjęty", rejected: "odrzucony", would_admit: "rekomendacja: przyjąć", would_reject: "rekomendacja: odrzucić", deferred: "odłożony (awaria dostawcy)",
  suspended: "zawieszony", returned: "powrót do składu",
};
const EN_DECISIONS: Record<string, string> = {
  admitted: "admitted", rejected: "rejected", would_admit: "recommendation: admit", would_reject: "recommendation: reject", deferred: "deferred (provider failure)",
  suspended: "suspended", returned: "returned to membership",
};

/** Jawny dziennik Rekrutera Konsylium: kandydaci, egzamin, głosy członków, zawieszenia i powroty. */
export function CouncilRecruitmentLog({ lang = "pl" }: LanguageProps) {
  const en = lang === "en";
  const query = useQuery({ queryKey: ["clinic-council"], queryFn: () => apiFetch<Council>("/api/clinic/council/"), staleTime: 10 * 60_000 });
  if (query.isPending || query.isError || !query.data) return null;
  const rows = query.data.recruitment ?? [];
  if (!rows.length) return <p className="sc-council__empty">{en ? "The Recruiter has not assessed any candidates yet. The first review takes place overnight." : "Rekruter nie ocenił jeszcze żadnego kandydata. Pierwszy przegląd odbywa się w nocy."}</p>;
  return <ol className="sc-recruit">{rows.map((row, index) => (
    <li key={index} className="sc-recruit__row" data-decision={row.decision}>
      <p className="sc-recruit__head"><strong>{shortModel(row.model)}</strong><span>{row.company}</span>
        <span className="sc-recruit__decision">{(en ? EN_DECISIONS : DECISIONS)[row.decision] ?? row.decision}{row.mode === "trial" && row.kind === "candidate" ? en ? " · trial mode" : " · tryb próbny" : ""}</span>
        <time dateTime={row.date}>{councilDate(row.date, en)}</time></p>
      {row.exam ? <p className="sc-recruit__exam">{en ? "Exam:" : "Egzamin:"} {row.exam.answered}/{row.exam.items} {en ? "responses · agreement with the Council" : "odpowiedzi · zgodność z Konsylium"} {Math.round(row.exam.agreement * 100)}% · {en ? "strength difference" : "różnica siły"} {row.exam.mae} {en ? "points" : "pkt"} · {row.exam.passed ? en ? "thresholds met" : "progi spełnione" : en ? "thresholds not met" : "progi niespełnione"}</p> : null}
      <p className="sc-recruit__reason">{en && "Reason (in Polish): "}<span lang={en ? "pl" : undefined}>{row.reason}</span></p>
      {row.votes.length ? <ul className="sc-recruit__votes">{row.votes.map((vote, voteIndex) => (
        <li key={voteIndex}><strong>{shortModel(vote.model)}</strong> {en ? "-" : "-"} {vote.admit === true ? en ? "in favour" : "za" : vote.admit === false ? en ? "against" : "przeciw" : en ? "no vote" : "brak głosu"}{vote.reason ? <>{en ? " (reason in Polish): " : ": "}<span lang={en ? "pl" : undefined}>{vote.reason}</span></> : ""}</li>
      ))}</ul> : null}
    </li>
  ))}</ol>;
}
