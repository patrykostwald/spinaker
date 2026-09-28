"use client";

/**
 * Sekcja „Dr. Spin” na stronie głównej (28.09.2026, druga wersja): tytuł po lewej, na środku przełącznik
 * Rządzący | Opozycja (jak dawny „Spin dnia | Najnowszy spin”), link do Kliniki po prawej; pod spodem spin dnia
 * wybranej strony i przekazy dnia obu stron. Pierwsza strona — ta z mocniejszym spinem dnia (ocenia się wpis,
 * nie stronę). Wywiady, liczniki i reszta — w Klinice. Styl jak pozostałe sekcje (bez wyróżniającej ramki).
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CAMPS, CAMP_LABELS, getClinicPage, type Camp } from "../../lib/clinic";
import { formatDatePl } from "../../lib/utils";
import { AiTag } from "../../components/clinic/SpinParts";
import { MessageBox } from "../../components/clinic/ClinicExtras";
import { SpinOfDay } from "../../components/clinic/ClinicPage";

/** Godziny generowania przekazu dnia (jak w harmonogramie serwera). */
const MESSAGE_SLOTS: Array<[number, number]> = [[9, 0], [12, 0], [15, 0], [18, 0], [21, 30]];

function nextMessageSlot(now: Date): string {
  const minutes = now.getHours() * 60 + now.getMinutes();
  const next = MESSAGE_SLOTS.find(([hour, minute]) => hour * 60 + minute > minutes) ?? MESSAGE_SLOTS[0];
  return `${next[0]}:${String(next[1]).padStart(2, "0")}`;
}

const WINDOW_NOTE: Record<string, string> = {
  "24h": "Najmocniejszy spin tej strony z ostatniej doby.",
  "72h": "Najmocniejszy spin tej strony z ostatnich trzech dni.",
  latest: "Ta strona nie ma świeżego spinu — pokazujemy jej najnowszy",
};

export function HomeSpinTeaser() {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, staleTime: 5 * 60_000 });
  const data = query.data;
  const [slot, setSlot] = useState<string | null>(null);
  const [camp, setCamp] = useState<Camp | null>(null);
  useEffect(() => setSlot(nextMessageSlot(new Date())), []);
  if (!data) return null;

  const emptyMessage = `Najbliższy przekaz${slot ? ` o ${slot}` : ""} — gdy posty opublikują co najmniej trzy konta tego obozu.`;
  const byCamp = data.spin_by_camp;
  const order = byCamp?.order ?? CAMPS;
  const active: Camp = camp ?? order[0];
  const spin = byCamp?.spins?.[active] ?? null;

  return (
    <section className="sc-home-section sc-home-doctor" aria-labelledby="home-drspin-title">
      <div className="sc-clinic-sotd sc-home-doctor__body">
        <div className="sc-spin-switch__bar">
          <header>
            <p className="sc-t-caption sc-text-3 sc-home-kicker">Klinika spinu <AiTag /></p>
            <h2 id="home-drspin-title" className="sc-t-title-l sc-home-section__title">Dr. Spin</h2>
          </header>
          <div className="sc-spin-switch__tabs" role="tablist" aria-label="Spin dnia której strony pokazać">
            {order.map((key, index) => (
              <span key={key} className="sc-home-doctor__tab">
                {index ? <span aria-hidden="true">|</span> : null}
                <button type="button" role="tab" aria-selected={key === active} onClick={() => setCamp(key)}>{CAMP_LABELS[key]}</button>
              </span>
            ))}
          </div>
          <div className="sc-spin-switch__right">
            <Link className="sc-home-spin__open" href="/klinika">Otwórz Klinikę spinu →</Link>
          </div>
        </div>
        {spin ? (
          <>
            {spin.window && spin.window !== "today" ? (
              <p className="sc-home-doctor__window">
                {WINDOW_NOTE[spin.window]}{spin.window === "latest" && spin.post.published_at ? ` (${formatDatePl(spin.post.published_at)}).` : ""}
              </p>
            ) : null}
            <SpinOfDay key={spin.id} spin={spin} />
          </>
        ) : (
          <p className="sc-t-body-s sc-text-2 sc-home-spin__empty">
            {CAMP_LABELS[active]}: jeszcze bez diagnozy. Strażnik przegląda każdy nowy post z oficjalnych kont, a te warte sprawdzenia bada Dr. Spin — rządzący i opozycja według tych samych zasad.
          </p>
        )}
      </div>
      {/* Przekazy dnia obu obozów pod spinem dnia: najpierw jeden konkretny post, potem szerszy obraz dnia. */}
      <div className="sc-clinic-split sc-home-spin__messages" aria-label="Przekazy dnia">
        {CAMPS.map((key) => <MessageBox key={key} camp={key} message={data.messages[key]} emptyText={emptyMessage} />)}
      </div>
    </section>
  );
}
