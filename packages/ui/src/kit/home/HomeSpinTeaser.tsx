"use client";

/**
 * Niski pas „Spin dnia” na stronie głównej — jedna karta z Kliniki i przejście do pełnej strony /klinika.
 * Bez zatwierdzonych diagnoz: jedno zdanie, czym jest Klinika (bez pustych atrap).
 */

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CAMPS, getClinicPage, sharePercent } from "../../lib/clinic";
import { AiTag, SpinRow } from "../../components/clinic/SpinParts";
import { MessageBox } from "../../components/clinic/ClinicPage";

export function HomeSpinTeaser() {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, staleTime: 5 * 60_000 });
  const data = query.data;
  const spin = data?.spin_of_day ?? null;
  const left = data ? sharePercent(data.scale.government) : null;
  const right = data ? sharePercent(data.scale.opposition) : null;
  const hasMessages = Boolean(data && (data.messages.government || data.messages.opposition));
  return (
    <section className="sc-home-spin" aria-labelledby="home-spin-title">
      <header className="sc-home-spin__head">
        <div>
          <p className="sc-t-caption sc-text-3 sc-home-kicker">Klinika spinu <AiTag /></p>
          <h2 id="home-spin-title" className="sc-t-title-l sc-home-section__title">{hasMessages ? (spin ? "Przekazy i spin dnia" : "Przekazy dnia") : spin ? "Spin dnia" : "Klinika spinu"}</h2>
        </div>
        <p className="sc-home-spin__meta">
          {data?.scale.enough_data && left !== null && right !== null ? <>Waga z {data.scale.window_days} dni: rządzący {left}% · opozycja {right}% · </> : null}
          <Link href="/klinika">Otwórz Klinikę spinu →</Link>
        </p>
      </header>
      {data && hasMessages ? (
        // Przekazy dnia obu obozów (jak w Klinice) — skrócone; całość na /klinika.
        <div className="sc-clinic-split sc-home-spin__messages" aria-label="Przekazy dnia">
          {CAMPS.map(camp => <MessageBox key={camp} camp={camp} message={data.messages[camp]} />)}
        </div>
      ) : null}
      {spin ? <div className="sc-home-spin__card"><SpinRow spin={spin} /></div> : (
        <p className="sc-t-body-s sc-text-2 sc-home-spin__empty">
          Każdy nowy post polityków z oficjalnych kont przegląda strażnik, a te warte sprawdzenia bada Dr. Spin — techniki perswazji z cytatami
          i twierdzenia porównane ze źródłami. Rządzący i opozycja według tych samych zasad.
        </p>
      )}
    </section>
  );
}
