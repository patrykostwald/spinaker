"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { apiWrite, glueShortWords as nbsp } from "@spin-clinic/ui";
import { Button } from "@spin-clinic/ui/kit";
import "./raporty.css";

/**
 * Raporty dla instytucji (plan finansowy 6.10, ruch 6): publiczna próbka raportu tygodniowego (tylko liczby zbiorcze,
 * bez cen) i formularz zapytania z podwójnym potwierdzeniem. Ta sama oferta dla wszystkich; bez pytań o poglądy.
 */
type Camp = { count: number; weighted_spin_percent: number | null; average_intensity: number | null; top_techniques: string[] };
type Sample = { available: boolean; start?: string; week_end?: string; total?: number; total_before?: number; club_min?: number;
  camps?: Record<"government" | "opposition", Camp>; clubs?: { club: string; count: number; weighted_spin_percent: number | null; trend_pp: number | null }[];
  summary?: string[] };

const ORG_TYPES: [string, string][] = [
  ["agencja", "Agencja PR lub public affairs"], ["firma", "Dział komunikacji firmy"], ["instytucja", "Instytucja publiczna lub ambasada"],
  ["nauka", "Uczelnia lub think tank"], ["redakcja", "Redakcja"], ["ngo", "Organizacja pozarządowa"], ["partia", "Partia lub sztab"], ["inne", "Inne"],
];
export const REPORTS_NEWSLETTER_CONSENT = "Zgadzam się na e-maile spin.clinic (iapply sp. z o.o.) z bezpłatną próbką raportu tygodniowego i informacjami o raportach. Mogę się wypisać jednym kliknięciem.";
const pl = (value: number | null | undefined) => value === null || value === undefined ? "-" : value.toLocaleString("pl-PL", { maximumFractionDigits: 1 });
const day = (value?: string) => value ? new Date(value + "T12:00:00").toLocaleDateString("pl-PL", { day: "numeric", month: "long" }) : "";

function SampleBox({ title, camp }: { title: string; camp: Camp }) {
  return <article className="sc-rep-box">
    <h3>{title}</h3>
    <dl className="sc-rep-box__nums">
      <div><dt>Ocenione wypowiedzi</dt><dd>{camp.count}</dd></div>
      <div><dt>Wskaźnik ważony spinu</dt><dd>{camp.weighted_spin_percent === null ? "-" : `${pl(camp.weighted_spin_percent)}%`}</dd></div>
      <div><dt>Średnia siła</dt><dd>{pl(camp.average_intensity)}/100</dd></div>
    </dl>
    <p className="sc-rep-box__foot">{camp.top_techniques.length ? nbsp("Najczęściej: " + camp.top_techniques.join(", ").toLowerCase()) : "Brak rozpoznanych technik"}</p>
  </article>;
}

export function ReportSample() {
  const [sample, setSample] = useState<Sample | null>(null);
  useEffect(() => {
    fetch("/api/raporty/probka/", { cache: "no-store" }).then(r => r.ok ? r.json() : { available: false })
      .then(setSample).catch(() => setSample({ available: false }));
  }, []);
  if (!sample) return <div className="sc-rep-sample" aria-busy="true"><p className="sc-rep-muted">Wczytuję próbkę…</p></div>;
  if (!sample.available || !sample.camps) return <div className="sc-rep-sample">
    <p className="sc-rep-muted">{nbsp("Próbka z ostatniego pełnego tygodnia pojawi się tutaj po pierwszym numerze raportu. Pełny raport (PDF i CSV) wysyłamy na zapytanie.")}</p>
  </div>;
  return <div className="sc-rep-sample">
    <p className="sc-rep-sample__head"><b>Próbka: {day(sample.start)} - {day(sample.week_end)}</b><span>{sample.total} ocenionych wypowiedzi</span></p>
    <div className="sc-rep-grid">
      <SampleBox title="Rządzący" camp={sample.camps.government} />
      <SampleBox title="Opozycja" camp={sample.camps.opposition} />
    </div>
    {sample.clubs && sample.clubs.length > 0 && <table className="sc-rep-clubs">
      <caption>{nbsp(`Kluby: ten sam próg dla każdego (co najmniej ${sample.club_min} diagnozy w tygodniu)`)}</caption>
      <thead><tr><th scope="col">Klub</th><th scope="col">Liczba</th><th scope="col">Wskaźnik</th><th scope="col">Zmiana</th></tr></thead>
      <tbody>{sample.clubs.map(c => <tr key={c.club}><th scope="row">{c.club}</th><td>{c.count}</td>
        <td>{c.weighted_spin_percent === null ? "za mało danych" : `${pl(c.weighted_spin_percent)}%`}</td>
        <td>{c.trend_pp === null ? "-" : `${c.trend_pp > 0 ? "+" : ""}${pl(c.trend_pp)} pkt`}</td></tr>)}</tbody>
    </table>}
    <p className="sc-rep-muted">{nbsp("Wskaźnik ważony spinu = (spin + 0,5 × częściowy spin) / liczba diagnoz. To nie jest odsetek wpisów ze spinem. Pełny raport zawiera też listę wypowiedzi z linkami do źródeł i metodę.")} <Link href="/metodologia">Metodologia</Link></p>
  </div>;
}

type State = { kind: "idle" | "sending" | "done" | "error"; message?: string };

export function ReportInquiry() {
  const [form, setForm] = useState({ name: "", organisation: "", org_type: "agencja", email: "", message: "" });
  const [privacy, setPrivacy] = useState(false);
  const [newsletter, setNewsletter] = useState(false);
  const [website, setWebsite] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });
  const [confirmed, setConfirmed] = useState<"" | "ok" | "error">("");
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("potwierdz");
    if (!token) return;
    window.history.replaceState(null, "", "/dla-redakcji#zapytanie");
    apiWrite("/api/leady/potwierdz/", { token }).then(() => setConfirmed("ok")).catch(() => setConfirmed("error"));
    document.getElementById("zapytanie")?.scrollIntoView();
  }, []);
  const set = (key: keyof typeof form) => (event: { target: { value: string } }) => setForm({ ...form, [key]: event.target.value });

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!privacy) { setState({ kind: "error", message: "Zaznacz zgodę na kontakt w sprawie zapytania." }); return; }
    setState({ kind: "sending" });
    try {
      const result = await apiWrite<{ detail: string }>("/api/raporty/zapytanie/", { ...form, privacy, newsletter, website });
      setState({ kind: "done", message: result.detail });
    } catch (error) {
      setState({ kind: "error", message: error instanceof Error ? error.message : "Nie udało się wysłać. Napisz na kontakt@spin.clinic." });
    }
  }

  return <div className="sc-rep-form" id="zapytanie">
    <h3>Raporty dla instytucji</h3>
    {confirmed && <p className={confirmed === "ok" ? "sc-rep-done" : "sc-rep-error"} role="status">
      {confirmed === "ok" ? nbsp("Dziękujemy, zapytanie potwierdzone. Odpowiemy w 1 dzień roboczy i wyślemy bezpłatną próbkę raportu.")
        : nbsp("Link wygasł albo jest niepoprawny. Wyślij formularz ponownie albo napisz na kontakt@spin.clinic.")}</p>}
    {state.kind === "done" ? <p className="sc-rep-done" role="status">✓ {state.message}</p> :
      <form onSubmit={submit} noValidate>
        <div className="sc-rep-fields">
          <label><span>Imię i nazwisko</span><input className="sc-input" required autoComplete="name" value={form.name} onChange={set("name")} /></label>
          <label><span>Organizacja</span><input className="sc-input" autoComplete="organization" value={form.organisation} onChange={set("organisation")} /></label>
          <label><span>Typ odbiorcy</span><select className="sc-input" value={form.org_type} onChange={set("org_type")}>
            {ORG_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label><span>E-mail</span><input className="sc-input" type="email" required autoComplete="email" inputMode="email" value={form.email} onChange={set("email")} /></label>
          <label className="sc-rep-fields__wide"><span>Czego potrzebujesz? (opcjonalnie)</span>
            <textarea className="sc-input" rows={3} maxLength={2000} value={form.message} onChange={set("message")} /></label>
        </div>
        <input className="sc-newsletter__trap" tabIndex={-1} autoComplete="off" aria-hidden="true" name="website" value={website} onChange={e => setWebsite(e.target.value)} />
        <label className="sc-rep-check"><input type="checkbox" checked={privacy} onChange={e => setPrivacy(e.target.checked)} />
          <span>{nbsp("Zgadzam się na kontakt w sprawie tego zapytania (iapply sp. z o.o., operator spin.clinic).")} <Link href="/polityka-prywatnosci">Prywatność</Link></span></label>
        <label className="sc-rep-check"><input type="checkbox" checked={newsletter} onChange={e => setNewsletter(e.target.checked)} />
          <span>{nbsp(REPORTS_NEWSLETTER_CONSENT)} <em>(opcjonalnie)</em></span></label>
        {state.kind === "error" && <p className="sc-rep-error" role="alert">{state.message}</p>}
        <div className="sc-rep-actions">
          <Button type="submit" variant="primary" loading={state.kind === "sending"}>{state.kind === "sending" ? "Wysyłam…" : "Wyślij zapytanie"}</Button>
          <span className="sc-rep-muted">{nbsp("Potwierdzisz je linkiem z e-maila. Odpowiadamy w 1 dzień roboczy.")}</span>
        </div>
      </form>}
  </div>;
}
