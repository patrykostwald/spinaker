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
type Council = { charter_version: string; members: Member[] };

const shortModel = (model: string) => model.split("/").pop()!.replace(/:.*$/, "");

export function CouncilRoster() {
  const query = useQuery({ queryKey: ["clinic-council"], queryFn: () => apiFetch<Council>("/api/clinic/council/"), staleTime: 10 * 60_000 });
  if (query.isPending) return <p className="sc-council__empty">Wczytujemy skład Konsylium…</p>;
  if (query.isError || !query.data) return <p className="sc-council__empty">Skład Konsylium jest chwilowo niedostępny.</p>;
  const members = query.data.members;
  const accepted = members.filter(m => m.charter?.accepts).length;
  return (
    <div className="sc-council">
      <p className="sc-council__summary">
        <strong>{members.length}</strong> modeli · <strong>{new Set(members.map(m => m.company)).size}</strong> firm ·
        Kartę w wersji {query.data.charter_version} przyjęło <strong>{accepted}</strong> z {members.length}
      </p>
      <ul className="sc-council__list">
        {members.map(member => (
          <li key={`${member.provider}-${member.model}`} className="sc-council__member" data-status={member.status}>
            <div className="sc-council__head">
              <p className="sc-council__model">{shortModel(member.model)}</p>
              <p className="sc-council__company">{member.company}</p>
            </div>
            <p className="sc-council__roles">{member.roles.join(" · ")}</p>
            {member.charter ? (
              <blockquote className="sc-council__statement" data-accepts={member.charter.accepts}>
                „{member.charter.statement || (member.charter.accepts ? "Przyjmuję zasady Karty." : "Nie przyjmuję zasad Karty.")}”
                <footer>{member.charter.accepts ? "Przyjął Kartę" : "Nie przyjął Karty"} · {formatDatePl(member.charter.date)}</footer>
              </blockquote>
            ) : <p className="sc-council__pending">Oczekuje na przyjęcie Karty</p>}
            {member.status !== "dostępny" ? <p className="sc-council__status">Chwilowo niedostępny</p> : null}
          </li>
        ))}
      </ul>
      <p className="sc-council__note">Oświadczenia są odpowiedziami poszczególnych wersji modeli na pełną treść Karty. Nie oznaczają poparcia firm, które te modele udostępniają.</p>
    </div>
  );
}
