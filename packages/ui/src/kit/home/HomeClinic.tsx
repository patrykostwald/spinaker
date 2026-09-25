"use client";

/**
 * Zapowiedź Kliniki spinu na stronie głównej: spin dnia (ta sama karta co w /klinika) i skrót wagi.
 * Bez zatwierdzonych diagnoz — krótkie wyjaśnienie, czym jest Klinika, zamiast pustych atrap.
 */

import { useQuery } from "@tanstack/react-query";
import { Button } from "../Button";
import { getClinicPage, sharePercent } from "../../lib/clinic";
import { SpinCard } from "../../components/clinic/SpinParts";

export function HomeClinic() {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, staleTime: 5 * 60_000 });
  const data = query.data;
  const spin = data?.spin_of_day ?? null;
  const left = data ? sharePercent(data.scale.government) : null;
  const right = data ? sharePercent(data.scale.opposition) : null;

  return (
    <section className="sc-home-section sc-home-clinic" aria-labelledby="home-clinic-title">
      <div className="sc-home-band-surface">
        <header className="sc-home-section__head">
          <div>
            <p className="sc-t-caption sc-text-3 sc-home-kicker">Klinika spinu · diagnozy AI</p>
            <h2 id="home-clinic-title" className="sc-t-title-l sc-home-section__title">{spin ? "Spin dnia" : "Klinika spinu"}</h2>
          </div>
          <div className="sc-home-section__actions">
            <Button href="/klinika" variant="quiet" size="sm">Otwórz Klinikę</Button>
          </div>
        </header>
        {spin ? (
          <div className="sc-home-clinic__body">
            <SpinCard spin={spin} />
            {data?.scale.enough_data && left !== null && right !== null ? (
              <p className="sc-home-clinic__scale">
                Waga spinu z {data.scale.window_days} dni: <strong>rządzący {left}%</strong> · <strong>opozycja {right}%</strong> postów ze spinem.
              </p>
            ) : null}
          </div>
        ) : (
          <p className="sc-t-body sc-text-2 sc-home-clinic__empty">
            Każdy nowy post polityków z kont, które czytamy, dostaje automatyczną diagnozę: jakie techniki perswazji zawiera i co o jego
            twierdzeniach mówią źródła. Rządzący i opozycja obok siebie, według tych samych zasad.
          </p>
        )}
      </div>
    </section>
  );
}
