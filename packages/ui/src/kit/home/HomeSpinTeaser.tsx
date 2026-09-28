"use client";

/**
 * Sekcja „Dr. Spin” na stronie głównej (28.09.2026, wersja 3 — po audycie UX): obie strony OBOK SIEBIE w skrócie
 * (autor, przycięty cytat, wynik z wyjaśnieniem skali, dwuzdaniowy wniosek, dwie techniki, „Przeczytaj pełną analizę”,
 * „Zgłoś błąd”), bez przewijanej ramki w środku. Pod spodem przekazy dnia obu stron. Pełna diagnoza — w Klinice.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CAMPS, CAMP_LABELS, getClinicPage, type Camp, type SpinDetailData } from "../../lib/clinic";
import { formatDatePl } from "../../lib/utils";
import { AiTag, SpinAuthorRow, VerdictTag } from "../../components/clinic/SpinParts";
import { MessageBox } from "../../components/clinic/ClinicExtras";

/** Godziny generowania przekazu dnia (jak w harmonogramie serwera). */
const MESSAGE_SLOTS: Array<[number, number]> = [[9, 0], [12, 0], [15, 0], [18, 0], [21, 30]];

function nextMessageSlot(now: Date): string {
  const minutes = now.getHours() * 60 + now.getMinutes();
  const next = MESSAGE_SLOTS.find(([hour, minute]) => hour * 60 + minute > minutes) ?? MESSAGE_SLOTS[0];
  return `${next[0]}:${String(next[1]).padStart(2, "0")}`;
}

const WINDOW_NOTE: Record<string, string> = {
  today: "Spin dnia",
  "24h": "Najmocniejszy z ostatniej doby",
  "72h": "Najmocniejszy z ostatnich 3 dni",
  latest: "Najnowszy spin tej strony",
};

function minutesAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000));
  if (minutes < 60) return `${minutes} min temu`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours} godz. temu` : formatDatePl(iso);
}

function SpinPreview({ camp, spin, active }: { camp: Camp; spin: (SpinDetailData & { window: string }) | null; active: boolean }) {
  if (!spin) {
    return (
      <div className="sc-spin-preview-col" data-camp={camp} data-active={active || undefined}>
        <p className="sc-spin-preview__camp">{CAMP_LABELS[camp]}</p>
        <article className="sc-spin-preview">
          <p className="sc-t-body-s sc-text-2">Jeszcze bez diagnozy tej strony. Strażnik przegląda każdy nowy wpis z oficjalnych kont, a te warte sprawdzenia bada Dr. Spin — według tych samych zasad dla obu stron.</p>
        </article>
      </div>
    );
  }
  const techniques = (spin.techniques ?? []).filter((item) => item.name).slice(0, 2);
  return (
    <div className="sc-spin-preview-col" data-camp={camp} data-active={active || undefined}>
    <p className="sc-spin-preview__camp">
      {CAMP_LABELS[camp]} · <span>{WINDOW_NOTE[spin.window] ?? "Spin dnia"}{spin.window === "latest" && spin.post.published_at ? `, ${formatDatePl(spin.post.published_at)}` : ""}</span>
    </p>
    <article className="sc-spin-preview" aria-labelledby={`spin-preview-${spin.id}`}>
      {/* Jedna linia: autor po lewej, siła i metka („Spin” / „Częściowy spin”) po prawej — bez paska (29.09). */}
      <div className="sc-spin-preview__top">
        <SpinAuthorRow author={spin.author} publishedAt={spin.post.published_at} />
        <p className="sc-spin-preview__verdict">
          <span className="sc-spin-preview__strength" data-level={spin.intensity >= 70 ? "high" : spin.intensity >= 30 ? "mid" : "low"}
            title="Siła spinu 0–100: jak mocno wpis opiera się na technikach perswazji">siła {spin.intensity}/100</span>
          <VerdictTag verdict={spin.verdict} label={spin.verdict_label} />
        </p>
      </div>
      <blockquote className="sc-spin-preview__quote">{spin.post.text}</blockquote>
      <h3 id={`spin-preview-${spin.id}`} className="sc-spin-preview__headline">{spin.headline}</h3>
      {spin.summary ? <p className="sc-spin-preview__summary">{spin.summary}</p> : null}
      {techniques.length ? (
        <ul className="sc-spin-preview__techniques">
          {techniques.map((item) => (
            <li key={item.name}><strong>{item.name}</strong>{item.quote ? <span> — „{item.quote}”</span> : null}</li>
          ))}
        </ul>
      ) : null}
      <p className="sc-spin-preview__audit" title="Numer diagnozy — pod nim w Klinice pełna analiza, źródła i wersja modelu">
        #SPIN-{spin.id}{spin.created_at ? ` · diagnoza ${formatDatePl(spin.created_at)}` : ""}
      </p>
      <p className="sc-spin-preview__actions">
        <Link href={`/klinika/${spin.id}`}>Przeczytaj pełną analizę →</Link>
        <a href={`mailto:kontakt@spin.clinic?subject=${encodeURIComponent(`Zgłoszenie błędu w diagnozie ${spin.id}`)}`}>Zgłoś błąd</a>
      </p>
    </article>
    </div>
  );
}

export function HomeSpinTeaser() {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, staleTime: 5 * 60_000 });
  const data = query.data;
  const [slot, setSlot] = useState<string | null>(null);
  const [mobileCamp, setMobileCamp] = useState<Camp | null>(null);
  const [now, setNow] = useState(false);
  useEffect(() => { setSlot(nextMessageSlot(new Date())); setNow(true); }, []);
  if (!data) return null;

  const emptyMessage = `Najbliższy przekaz${slot ? ` o ${slot}` : ""} — gdy posty opublikują co najmniej trzy konta tego obozu.`;
  const spins = data.spin_by_camp?.spins;
  const order = data.spin_by_camp?.order ?? CAMPS;
  const shown: Camp = mobileCamp ?? order[0];
  const lastDiagnosis = data.latest_spin?.created_at;

  return (
    <section id="dr-spin" className="sc-home-section sc-home-doctor" aria-labelledby="home-drspin-title">
      <header className="sc-home-doctor__head">
        <div>
          <p className="sc-t-caption sc-text-3 sc-home-kicker">Klinika spinu <AiTag /></p>
          <p className="sc-home-doctor__title">
            <span id="home-drspin-title" className="sc-t-title-l sc-home-section__title" role="heading" aria-level={2}>Dr. Spin</span>
            <Link className="sc-home-doctor__how" href="/o-nas#klinika">Jak wybieramy i liczymy?</Link>
          </p>
        </div>
        <p className="sc-home-doctor__links">
          {now && lastDiagnosis ? <span className="sc-home-doctor__sync">Ostatnia diagnoza: {minutesAgo(lastDiagnosis)}</span> : null}
          <Link className="sc-home-spin__open" href="/klinika">Otwórz Klinikę spinu →</Link>
        </p>
      </header>
      {/* Telefon: kafelki obu stron z wynikiem (symetria widoczna od razu), pod nimi jedna karta. Komputer: dwie karty. */}
      <div className="sc-home-doctor__tiles" role="tablist" aria-label="Spin dnia której strony pokazać">
        {order.map((camp) => (
          <button key={camp} type="button" role="tab" aria-selected={camp === shown} className="sc-home-doctor__tile" data-camp={camp}
            onClick={() => setMobileCamp(camp)}>
            <span>{CAMP_LABELS[camp]}</span>
            <strong>{spins?.[camp] ? `${spins[camp]!.intensity}/100` : "—"}</strong>
          </button>
        ))}
      </div>
      <div className="sc-home-doctor__pair">
        {CAMPS.map((camp) => <SpinPreview key={camp} camp={camp} spin={spins?.[camp] ?? null} active={camp === shown} />)}
      </div>
      {data.stats ? (
        <p className="sc-home-doctor__work">
          Dr. Spin przeczytał <strong>{data.stats.read.total.toLocaleString("pl-PL")}</strong> wpisów polityków,
          ocenił <strong>{data.stats.screened.total.toLocaleString("pl-PL")}</strong> i postawił <strong>{data.stats.diagnosed.total.toLocaleString("pl-PL")}</strong> diagnoz.
          <Link href="/klinika/diagnozy">Wszystkie diagnozy →</Link>
          <Link href="/klinika/wskazniki">Wskaźniki i wykresy →</Link>
        </p>
      ) : null}
      <p className="sc-home-doctor__scale">
        <strong>Siła spinu 0–100</strong> — jak mocno wpis opiera się na technikach perswazji. To nie jest ocena prawdziwości ani osoby;
        prawdziwość twierdzeń sprawdzamy osobno, ze źródłami. Obie strony — te same zasady.
      </p>
      {/* Przekazy dnia obu obozów: szerszy obraz dnia pod konkretnymi wpisami. */}
      <div className="sc-clinic-split sc-home-spin__messages" aria-label="Przekazy dnia">
        {CAMPS.map((key) => <MessageBox key={key} camp={key} message={data.messages[key]} emptyText={emptyMessage} />)}
      </div>
    </section>
  );
}
