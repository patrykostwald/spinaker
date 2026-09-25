"use client";

/**
 * Pionowa oś czasu profilu osoby publicznej (zakładka „Oś czasu”) — z `GET /api/public-figures/:id/dossier/`,
 * wyłącznie z rekordów, które mają publiczny dowód:
 * 1) funkcje w podmiotach publicznych (role/urzędy; źródła nie podają dziś dat objęcia i zakończenia — mówimy to wprost),
 * 2) relacje z podmiotami rejestrowymi (spółki, fundacje, stowarzyszenia — tylko potwierdzone przez redakcję),
 * 3) zdarzenia z datą: oficjalne głosowania i potwierdzone materiały, od najnowszych,
 * 4) powiązane osoby — wyłącznie przez wspólne, potwierdzone podmioty (wymaga danych po stronie serwera).
 * Żadnych wniosków ani dopasowań automatycznych: brak danych to brak danych.
 */

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import { ORGANISATION_KIND_LABELS, type PublicFigureOrganisation } from "../lib/publicFigures";
import { formatDatePl } from "../lib/utils";
import { voteLabel } from "./VotingDetails";

type DossierRole = {
  office: { id: number; title: string; official_roster_url: string } | null;
  role_title: string;
  organisation: string;
  status: string;
  evidence_url: string;
  source_checked_at?: string;
};
type DossierEvent = { kind: "material" | "official_vote"; date: string | null; label: string; url: string; evidence_url: string; vote?: string };
type Dossier = {
  roles: DossierRole[];
  organisations: PublicFigureOrganisation[];
  timeline: DossierEvent[];
  graph: { gaps: string[] };
};

function monthKey(iso: string | null): string {
  return iso ? iso.slice(0, 7) : "unknown";
}

function monthLabel(key: string): string {
  if (key === "unknown") return "Data nieustalona";
  return new Intl.DateTimeFormat("pl-PL", { month: "long", year: "numeric" }).format(new Date(`${key}-01T12:00:00Z`));
}

export function PublicFigureTimeline({ figureId, onShowMaterials, materialsTotal }: { figureId: number; onShowMaterials?: () => void; materialsTotal?: number | null }) {
  const dossier = useQuery({
    queryKey: ["public-figure-dossier", figureId],
    queryFn: () => apiFetch<Dossier>(`/api/public-figures/${figureId}/dossier/`),
    staleTime: 60_000,
  });

  if (dossier.isPending) return <p role="status" className="sc-public-figure__hint">Układam oś czasu…</p>;
  if (dossier.isError || !dossier.data) return <p role="alert" className="sc-public-figure__hint">Nie udało się pobrać osi czasu. Spróbuj ponownie za chwilę.</p>;

  const { roles, organisations, timeline, graph } = dossier.data;
  const months = new Map<string, DossierEvent[]>();
  for (const event of timeline) {
    const key = monthKey(event.date);
    months.set(key, [...(months.get(key) ?? []), event]);
  }

  return (
    <section id="os-czasu" className="sc-public-figure-section sc-pf-timeline" aria-labelledby="pf-timeline">
      <header>
        <h2 id="pf-timeline">Oś czasu</h2>
        <p>Funkcje publiczne, potwierdzone relacje z podmiotami i zdarzenia z datą — każdy wpis prowadzi do publicznego źródła. Nie łączymy danych automatycznie po nazwisku.</p>
      </header>

      <ol className="sc-pf-axis">
        <li className="sc-pf-axis__group">
          <h3 className="sc-pf-axis__label">Funkcje w podmiotach publicznych</h3>
          {roles.length ? (
            <ul className="sc-pf-axis__items">
              {roles.map((role, index) => (
                <li key={`${role.role_title}-${index}`} className="sc-pf-axis__item" data-status={role.status}>
                  <span className="sc-pf-axis__dot" aria-hidden="true" />
                  <p className="sc-pf-axis__when">{role.status === "current" ? "obecnie" : "wcześniej"} · daty objęcia i zakończenia: brak w źródle</p>
                  <p className="sc-pf-axis__title">{role.office?.title ?? role.role_title}</p>
                  {role.organisation ? <p className="sc-pf-axis__meta">{role.organisation}</p> : null}
                  <a className="sc-pf-axis__source" href={role.evidence_url} target="_blank" rel="noopener noreferrer">
                    Źródło publiczne ↗
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="sc-pf-axis__empty">Brak funkcji potwierdzonej w oficjalnym wykazie. Pokazujemy tylko role ze źródeł urzędowych.</p>
          )}
        </li>

        <li className="sc-pf-axis__group">
          <h3 className="sc-pf-axis__label">Spółki, fundacje, stowarzyszenia</h3>
          {organisations.length ? (
            <ul className="sc-pf-axis__items">
              {organisations.map((relation) => (
                <li key={`${relation.id}-${relation.public_role}`} className="sc-pf-axis__item" data-status={relation.relation_status}>
                  <span className="sc-pf-axis__dot" aria-hidden="true" />
                  <p className="sc-pf-axis__when">
                    {ORGANISATION_KIND_LABELS[relation.kind].singular} · {relation.relation_status === "current" ? "relacja obecna" : "relacja historyczna"}
                  </p>
                  <p className="sc-pf-axis__title">{relation.name}</p>
                  <p className="sc-pf-axis__meta">{relation.public_role}</p>
                  <a className="sc-pf-axis__source" href={relation.evidence_url} target="_blank" rel="noopener noreferrer">
                    Dowód publiczny ↗
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="sc-pf-axis__empty">Brak jeszcze relacji potwierdzonych w rejestrze (np. KRS). Nie oznacza to, że ich nie ma — dodajemy wyłącznie sprawdzone wpisy.</p>
          )}
        </li>

        <li className="sc-pf-axis__group">
          <h3 className="sc-pf-axis__label">Zdarzenia z datą</h3>
          {months.size ? (
            [...months.entries()].map(([key, events]) => (
              <section key={key} className="sc-pf-axis__month" aria-label={monthLabel(key)}>
                <p className="sc-pf-axis__month-label">{monthLabel(key)}</p>
                <ul className="sc-pf-axis__items">
                  {events.map((event, index) => (
                    <li key={`${event.url}-${index}`} className="sc-pf-axis__item" data-kind={event.kind}>
                      <span className="sc-pf-axis__dot" aria-hidden="true" />
                      <p className="sc-pf-axis__when">
                        {event.date ? formatDatePl(event.date) : "Data nieustalona"} · {event.kind === "official_vote" ? `głosowanie w Sejmie${event.vote ? ` · ${voteLabel(event.vote)}` : ""}` : "materiał potwierdzony przez redakcję"}
                      </p>
                      <a className="sc-pf-axis__title sc-pf-axis__link" href={event.url} target="_blank" rel="noopener noreferrer">
                        {event.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            ))
          ) : (
            <p className="sc-pf-axis__empty">Brak zdarzeń z datą (oficjalnych głosowań lub potwierdzonych materiałów).</p>
          )}
        </li>

        <li className="sc-pf-axis__group">
          <h3 className="sc-pf-axis__label">Doniesienia w Bazie</h3>
          <p className="sc-pf-axis__empty">
            {materialsTotal ? `${materialsTotal} materiałów zawiera to imię i nazwisko (dopasowanie po słowach — sprawdź, czy dotyczą tej osoby). ` : "Materiały zawierające to imię i nazwisko. "}
            {onShowMaterials ? (
              <button type="button" className="sc-home-linkbtn" onClick={onShowMaterials}>
                Pokaż wszystkie doniesienia
              </button>
            ) : null}
          </p>
        </li>

        <li className="sc-pf-axis__group">
          <h3 className="sc-pf-axis__label">Powiązane osoby</h3>
          <p className="sc-pf-axis__empty">
            Pokażemy osoby publiczne połączone z tą osobą przez wspólne, potwierdzone podmioty (np. wspólnicy w spółce z KRS). {organisations.length ? "" : "Najpierw potrzebne są potwierdzone relacje z podmiotami."}
          </p>
        </li>
      </ol>

      {graph.gaps.length ? (
        <ul className="sc-pf-axis__gaps" aria-label="Luki w danych">
          {graph.gaps.map((gap) => (
            <li key={gap}>{gap}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
