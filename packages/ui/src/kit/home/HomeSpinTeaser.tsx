"use client";

/**
 * Niski pas „Spin dnia” na stronie głównej — jedna karta z Kliniki i przejście do pełnej strony /klinika.
 * Bez zatwierdzonych diagnoz: jedno zdanie, czym jest Klinika (bez pustych atrap).
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CAMPS, getClinicPage, sharePercent } from "../../lib/clinic";
import { AiTag, SpinRow } from "../../components/clinic/SpinParts";
import { MessageBox } from "../../components/clinic/ClinicPage";

/** Godziny generowania przekazu dnia (jak w harmonogramie serwera). */
const MESSAGE_SLOTS: Array<[number, number]> = [[9, 0], [12, 0], [15, 0], [18, 0], [21, 30]];

function nextMessageSlot(now: Date): string {
  const minutes = now.getHours() * 60 + now.getMinutes();
  const next = MESSAGE_SLOTS.find(([hour, minute]) => hour * 60 + minute > minutes) ?? MESSAGE_SLOTS[0];
  return `${next[0]}:${String(next[1]).padStart(2, "0")}`;
}

export function HomeSpinTeaser() {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, staleTime: 5 * 60_000 });
  const data = query.data;
  const spin = data?.spin_of_day ?? null;
  const left = data ? sharePercent(data.scale.government) : null;
  const right = data ? sharePercent(data.scale.opposition) : null;
  const [slot, setSlot] = useState<string | null>(null);
  useEffect(() => setSlot(nextMessageSlot(new Date())), []);
  const emptyMessage = `Najbliższy przekaz${slot ? ` o ${slot}` : ""} — gdy posty opublikują co najmniej trzy konta tego obozu.`;
  return (
    <section className="sc-home-spin" aria-labelledby="home-spin-title">
      {/* Jeden niski rząd: po lewej „Klinika spinu · Spin dnia”, na środku wiersz spinu, po prawej link do Kliniki. */}
      <div className="sc-home-spin__row">
        <header className="sc-home-spin__head">
          <p className="sc-t-caption sc-text-3 sc-home-kicker">Klinika spinu <AiTag /></p>
          <h2 id="home-spin-title" className="sc-t-title-l sc-home-section__title">{spin ? "Spin dnia" : "Klinika spinu"}</h2>
          {data?.scale.enough_data && left !== null && right !== null
            ? <p className="sc-home-spin__meta">Waga {data.scale.window_days} dni: rządzący {left}% · opozycja {right}%</p> : null}
        </header>
        {spin ? <div className="sc-home-spin__card"><SpinRow spin={spin} /></div> : (
          <p className="sc-t-body-s sc-text-2 sc-home-spin__empty">
            Strażnik przegląda każdy nowy post polityków z oficjalnych kont, a te warte sprawdzenia bada Dr. Spin — rządzący i opozycja według tych samych zasad.
          </p>
        )}
        <Link className="sc-home-spin__open" href="/klinika">Otwórz Klinikę spinu →</Link>
      </div>
      {/* Przekazy dnia obu obozów pod spinem dnia: najpierw jeden konkretny post, potem szerszy obraz dnia. */}
      {data ? (
        <div className="sc-clinic-split sc-home-spin__messages" aria-label="Przekazy dnia">
          {CAMPS.map(camp => <MessageBox key={camp} camp={camp} message={data.messages[camp]} emptyText={emptyMessage} />)}
        </div>
      ) : null}
    </section>
  );
}
