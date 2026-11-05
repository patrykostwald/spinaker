"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CAMPS, CAMP_LABELS, CAMP_NOTE, getClinicPage, type Camp } from "../../lib/clinic";
import { HomeSpinScanner } from "./HomeSpinScanner";
import { CampSwitch } from "../CampSwitch";
import { MessageBox } from "../../components/clinic/ClinicExtras";
import { FORMS, plural } from "../../lib/plural";

/** Godziny generowania przekazu dnia (jak w harmonogramie serwera). */
const MESSAGE_SLOTS: Array<[number, number]> = [[9, 0], [12, 0], [15, 0], [18, 0], [21, 30]];

function nextMessageSlot(now: Date): string {
  const minutes = now.getHours() * 60 + now.getMinutes();
  const next = MESSAGE_SLOTS.find(([hour, minute]) => hour * 60 + minute > minutes) ?? MESSAGE_SLOTS[0];
  return `${next[0]}:${String(next[1]).padStart(2, "0")}`;
}

/** Zdanie o puli wpisów: poprawna odmiana także dla 1 wpisu (bez „wśród 1 przeanalizowanych”). */
function poolSentence(pool: number | null | undefined, campGenitive: string): string {
  if (typeof pool !== "number") return `Pokazujemy wpis z najwyższą siłą spinu spośród dostępnych przeanalizowanych wpisów ${campGenitive}`;
  if (pool === 1) return `Pokazujemy jedyny przeanalizowany wpis ${campGenitive}`;
  return `Pokazujemy wpis z najwyższą siłą spinu spośród ${pool} ${plural(pool, ["przeanalizowanego wpisu", "przeanalizowanych wpisów", "przeanalizowanych wpisów"])} ${campGenitive}`;
}

export function HomeSpinTeaser() {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, staleTime: 5 * 60_000 });
  const data = query.data;
  const [slot, setSlot] = useState<string | null>(null);
  const [selectedCamp, setSelectedCamp] = useState<Camp | null>(null);
  useEffect(() => { setSlot(nextMessageSlot(new Date())); }, []);
  if (!data) return <section id="dr-spin" className="sc-home-section"><h2>Dr. Spin</h2>{query.isError ? <p role="alert">Nie udało się pobrać danych. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p> : <p role="status">Wczytujemy diagnozy…</p>}</section>;

  const emptyMessage = `Najbliższy przekaz${slot ? ` o ${slot}` : ""} — gdy wpisy opublikują co najmniej trzy konta tego obozu.`;
  const spins = data.spin_by_camp?.spins;
  const order = data.spin_by_camp?.order ?? CAMPS;
  const shown: Camp = selectedCamp ?? order[0] ?? CAMPS[0];

  return (
    <section id="dr-spin" className="sc-home-section sc-scan-s" aria-labelledby="home-drspin-title">
      {query.isError ? <p role="status">Pokazujemy dane z {new Date(query.dataUpdatedAt).toLocaleString("pl-PL")}. Aktualizacja jest chwilowo niedostępna. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p> : null}
      <div className="sc-scan-s-top">
        <header className="sc-scan-s-head">
          <h2 id="home-drspin-title">Dr. Spin</h2>
          <p className="sc-scan-s-links"><Link href="/metodologia">Jak wybieramy i oceniamy?</Link><Link href="/klinika/diagnozy">Wszystkie diagnozy →</Link></p>
        </header>
        <CampSwitch className="sc-scan-s-tabs" mode="tabs" value={shown} onChange={setSelectedCamp} label="Strona polityczna" panelId={`scan-camp-panel-${shown}`} idPrefix="scan-tab" />
      </div>
      {/* J5: na szerokim ekranie oba obozy obok siebie (te same zasady dla obu stron); na telefonie jeden wybór przez CampSwitch. */}
      <div className="sc-scan-camps" data-shown={shown}>
        {CAMPS.map((camp) => {
          const campSpin = spins?.[camp];
          return (
            <div key={camp} id={`scan-camp-panel-${camp}`} className="sc-scan-camp" data-camp={camp} data-active={camp === shown || undefined} role="tabpanel" aria-labelledby={`scan-tab-${camp}`}>
              <h3 className="sc-scan-camp__title"><span className="sc-camp-mark" aria-hidden="true">{camp === "government" ? "●" : "■"}</span> {CAMP_LABELS[camp]}</h3>
              {campSpin ? <>
                <p className="sc-scan-s-rule">{campSpin.window === "latest" ? "Najnowsza dostępna diagnoza tej strony — w ostatnich trzech dobach nie było nowych diagnoz." :
                  `${poolSentence(campSpin.pool, camp === "government" ? "rządzących" : "opozycji")} (${campSpin.window_label || ({ today: "dzisiaj", "24h": "ostatnia doba", "72h": "ostatnie trzy doby" }[campSpin.window] ?? "okres niepodany")}).`}</p>
                <HomeSpinScanner key={`${camp}-${campSpin.id}`} spin={campSpin} />
              </> : <p>Nie ma jeszcze opublikowanych diagnoz dla tego wyboru.</p>}
            </div>
          );
        })}
      </div>
      <p className="sc-home-doctor__scale">
        <strong>Siła spinu 0–100</strong> — jak mocno wpis opiera się na technikach perswazji. To nie jest ocena prawdziwości ani osoby;
        prawdziwość twierdzeń sprawdzamy osobno, ze źródłami. Obie strony — te same zasady. {CAMP_NOTE}
      </p>
      {/* Przekazy dnia obu obozów: szerszy obraz dnia pod konkretnymi wpisami. */}
      <div className="sc-clinic-split sc-home-spin__messages" aria-label="Przekazy dnia">
        {CAMPS.map((key) => <MessageBox key={key} camp={key} message={data.messages[key]} emptyText={emptyMessage} />)}
      </div>
      {data.stats ? (
        <footer className="sc-home-doctor__work">
          Dr. Spin przeczytał <strong>{data.stats.read.total.toLocaleString("pl-PL")}</strong> {plural(data.stats.read.total, FORMS.entry)} polityków,
          wstępnie ocenił <strong>{data.stats.screened.total.toLocaleString("pl-PL")}</strong> i postawił <strong>{data.stats.diagnosed.total.toLocaleString("pl-PL")}</strong> {plural(data.stats.diagnosed.total, FORMS.diagnosis)}.
          <Link href="/klinika/diagnozy">Wszystkie diagnozy →</Link>
          <Link href="/klinika/wskazniki">Wskaźniki i wykresy →</Link>
        </footer>
      ) : null}
    </section>
  );
}
