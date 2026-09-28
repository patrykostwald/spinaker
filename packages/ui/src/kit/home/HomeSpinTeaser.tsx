"use client";

/**
 * Niski pas „Spin dnia” na stronie głównej — jedna karta z Kliniki i przejście do pełnej strony /klinika.
 * Bez zatwierdzonych diagnoz: jedno zdanie, czym jest Klinika (bez pustych atrap).
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CAMPS, getClinicPage, sharePercent } from "../../lib/clinic";
import { formatDatePl } from "../../lib/utils";
import { AiTag } from "../../components/clinic/SpinParts";
import { InterviewArchive, InterviewBox, MessageBox, SpinSwitch } from "../../components/clinic/ClinicExtras";
import { SpinOfDay } from "../../components/clinic/ClinicPage";

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
  const left = data ? sharePercent(data.scale.government) : null;
  const right = data ? sharePercent(data.scale.opposition) : null;
  const [slot, setSlot] = useState<string | null>(null);
  const [interviewOpen, setInterviewOpen] = useState(false);
  useEffect(() => setSlot(nextMessageSlot(new Date())), []);
  const emptyMessage = `Najbliższy przekaz${slot ? ` o ${slot}` : ""} — gdy posty opublikują co najmniej trzy konta tego obozu.`;
  return (
    <>
    {/* Wywiad dnia (najważniejszy wywiad z poprzedniego dnia) — nad spinem dnia, w tym samym stylu boxa. */}
    {data?.interview ? (
      <section className="sc-home-spin sc-home-interview" aria-labelledby="home-interview-title">
        {/* Tytuł sekcji po lewej (jak „Dr. Spin”), box wywiadu przesunięty w prawo. */}
        <header className="sc-home-interview__head">
          <p className="sc-t-caption sc-text-3 sc-home-kicker">Klinika spinu <AiTag /></p>
          <h2 id="home-interview-title" className="sc-t-title-l sc-home-section__title">Wywiad dnia</h2>
          <p className="sc-home-spin__meta">{data.interview.channel} · {formatDatePl(data.interview.day)}</p>
          <button type="button" className="sc-home-spin__open sc-home-interview__more" onClick={() => setInterviewOpen(true)} aria-haspopup="dialog">Pełna analiza ze źródłami →</button>
        </header>
        <InterviewBox interview={data.interview} open={interviewOpen} onOpenChange={setInterviewOpen} hideMore />
        {/* Wcześniejsze wywiady na pełną szerokość sekcji — od lewej krawędzi, jak tytuł „Wywiad dnia”. */}
        {data.interview_archive?.length ? <div className="sc-home-interview__archive"><InterviewArchive items={data.interview_archive.slice(0, 3)} /></div> : null}
      </section>
    ) : null}
    <section className="sc-home-spin" aria-labelledby="home-spin-title">
      {/* Sekcja „Dr. Spin”: nagłówek jak w innych sekcjach, pod nim ten sam element co w Klinice —
          przełącznik „Spin dnia | Najnowszy spin” i post obok pełnej odpowiedzi Dr. Spina. */}
      {data ? (
        <div className="sc-clinic-sotd sc-home-spin__sotd">
          {/* Jedna linia: „Dr. Spin” po lewej, zakładki na środku, link do Kliniki po prawej. */}
          <SpinSwitch spinOfDay={data.spin_of_day} latest={data.latest_spin} render={item => <SpinOfDay key={item.id} spin={item} />}
            left={<header>
              <p className="sc-t-caption sc-text-3 sc-home-kicker">Klinika spinu <AiTag /></p>
              <h2 id="home-spin-title" className="sc-sr-only">Dr. Spin</h2>
            </header>}
            right={<p className="sc-home-spin__meta">
              {data.scale.enough_data && left !== null && right !== null ? <>Waga {data.scale.window_days} dni: rządzący {left}% · opozycja {right}% · </> : null}
              <Link className="sc-home-spin__open" href="/klinika">Otwórz Klinikę spinu →</Link>
            </p>}
            empty={<p className="sc-t-body-s sc-text-2 sc-home-spin__empty">
              Strażnik przegląda każdy nowy post polityków z oficjalnych kont, a te warte sprawdzenia bada Dr. Spin — rządzący i opozycja według tych samych zasad.
            </p>} />
        </div>
      ) : null}
      {/* Przekazy dnia obu obozów pod spinem dnia: najpierw jeden konkretny post, potem szerszy obraz dnia. */}
      {data ? (
        <div className="sc-clinic-split sc-home-spin__messages" aria-label="Przekazy dnia">
          {CAMPS.map(camp => <MessageBox key={camp} camp={camp} message={data.messages[camp]} emptyText={emptyMessage} />)}
        </div>
      ) : null}
    </section>
    </>
  );
}
