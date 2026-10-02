"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CAMPS, CAMP_LABELS, getClinicPage, type Camp } from "../../lib/clinic";
import { HomeSpinScanner } from "./HomeSpinScanner";
import { MessageBox } from "../../components/clinic/ClinicExtras";
import { AiTag } from "../../components/clinic/SpinParts";

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
  const [slot, setSlot] = useState<string | null>(null);
  const [selectedCamp, setSelectedCamp] = useState<Camp | null>(null);
  useEffect(() => { setSlot(nextMessageSlot(new Date())); }, []);
  if (!data) return <section id="dr-spin" className="sc-home-section"><h2>Dr. Spin</h2>{query.isError ? <p role="alert">Nie udało się pobrać danych. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p> : <p role="status">Wczytujemy diagnozy…</p>}</section>;

  const emptyMessage = `Najbliższy przekaz${slot ? ` o ${slot}` : ""} - gdy wpisy opublikują co najmniej trzy konta tego obozu.`;
  const spins = data.spin_by_camp?.spins;
  const order = data.spin_by_camp?.order ?? CAMPS;
  const shown: Camp = selectedCamp ?? order[0] ?? CAMPS[0];
  const spin = spins?.[shown];

  return (
    <section id="dr-spin" className="sc-home-section sc-scan-s" aria-labelledby="home-drspin-title">
      {query.isError ? <p role="status">Pokazujemy dane z {new Date(query.dataUpdatedAt).toLocaleString("pl-PL")}. Aktualizacja jest chwilowo niedostępna. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p> : null}
      <div className="sc-scan-s-top">
        <header className="sc-scan-s-head">
          <h2 id="home-drspin-title">Dr. Spin<sup className="sc-tm-ai"><AiTag /></sup></h2>
          <p className="sc-scan-s-links"><Link href="/metodologia">Jak wybieramy i oceniamy?</Link><Link href="/klinika/diagnozy">Wszystkie diagnozy →</Link></p>
        </header>
        <div className="sc-scan-s-tabs" role="tablist" aria-label="Strona polityczna">
          {CAMPS.map((camp, index) => <button key={camp} type="button" role="tab" id={`scan-tab-${camp}`} aria-selected={shown === camp} aria-controls="scan-camp-panel" tabIndex={shown === camp ? 0 : -1}
            onClick={() => setSelectedCamp(camp)} onKeyDown={event => {
              if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
              event.preventDefault();
              const next = event.key === "Home" ? CAMPS[0] : event.key === "End" ? CAMPS[1] : CAMPS[1 - index];
              setSelectedCamp(next);
              document.getElementById(`scan-tab-${next}`)?.focus();
            }}>{CAMP_LABELS[camp]}</button>)}
        </div>
      </div>
      <div id="scan-camp-panel" role="tabpanel" aria-labelledby={`scan-tab-${shown}`}>
        {spin ? <>
          <p className="sc-scan-s-rule">{spin.window === "latest" ? "Najnowsza dostępna diagnoza tej strony - w ostatnich trzech dobach nie było nowych diagnoz." :
            `Pokazujemy wpis z najwyższą siłą spinu wśród ${spin.pool ?? "dostępnych"} przeanalizowanych wpisów ${shown === "government" ? "rządzących" : "opozycji"} (${spin.window_label || ({ today: "dzisiaj", "24h": "ostatnia doba", "72h": "ostatnie trzy doby" }[spin.window] ?? "okres niepodany")}).`}</p>
          <HomeSpinScanner key={`${shown}-${spin.id}`} spin={spin} />
        </> : <p>Nie ma jeszcze opublikowanych diagnoz dla tego wyboru.</p>}
      </div>
      <p className="sc-home-doctor__scale">
        <strong>Siła spinu 0–100</strong> - jak mocno wpis opiera się na technikach perswazji. To nie jest ocena prawdziwości ani osoby;
        prawdziwość twierdzeń sprawdzamy osobno, ze źródłami. Obie strony - te same zasady.
      </p>
      {/* Przekazy dnia obu obozów: szerszy obraz dnia pod konkretnymi wpisami. */}
      <div className="sc-clinic-split sc-home-spin__messages" aria-label="Przekazy dnia">
        {CAMPS.map((key) => <MessageBox key={key} camp={key} message={data.messages[key]} emptyText={emptyMessage} />)}
      </div>
      {data.stats ? (
        <footer className="sc-home-doctor__work">
          Dr. Spin przeczytał <strong>{data.stats.read.total.toLocaleString("pl-PL")}</strong> wpisów polityków,
          wstępnie ocenił <strong>{data.stats.screened.total.toLocaleString("pl-PL")}</strong> i postawił <strong>{data.stats.diagnosed.total.toLocaleString("pl-PL")}</strong> diagnoz.
          <Link href="/klinika/diagnozy">Wszystkie diagnozy →</Link>
          <Link href="/klinika/wskazniki">Wskaźniki i wykresy →</Link>
        </footer>
      ) : null}
    </section>
  );
}
