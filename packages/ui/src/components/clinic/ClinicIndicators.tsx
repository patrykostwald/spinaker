"use client";

/**
 * Wskaźniki Kliniki (/klinika/wskazniki, 29.09.2026): ile pracy wykonuje Klinika i co widać w diagnozach.
 * Zasady uczciwości: obie strony obok siebie na tych samych osiach, zawsze z liczebnością próby, udziały liczone
 * względem diagnoz danej strony (strony mają różną liczbę diagnoz), poniżej progu próby - „za mało danych” zamiast średniej.
 * Dane: GET /api/clinic/stats/ (news/clinic_stats.py), cache 10 min.
 */

import { createContext, useContext, useEffect, useId, useRef, useState } from "react";
import { ClinicNav } from "./ClinicNav";
import { Button } from "../../kit/Button";
import { SectionHeader } from "../../kit/SectionHeader";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../../lib/api";
import { CAMPS, CAMP_LABELS, spinVar, type Camp, type Party, type DataPeriod } from "../../lib/clinic";
import { clinicPeriodLabel } from "../../lib/clinicPeriod";
import { formatDatePl } from "../../lib/utils";
import { AiTag } from "./SpinParts";

type Sample = { count: number; enough_data: boolean };
type Pair = { total: number; today: number };
type CampBucket = {
  diagnosed: number; spin: number; partial: number; no_spin: number; unclear: number;
  average_intensity: number | null; enough_data: boolean;
  intensity_histogram: Array<Sample & { min: number; max: number }>;
};
type IndicatorStats = DataPeriod & {
  min_sample: number;
  window: { days: number; date_from: string; date_to: string };
  totals: Record<"read" | "screened" | "rejected" | "diagnosed" | "spins", Pair> & {
    by_camp?: Record<Camp, { read: number; diagnosed: number; spins: number }>;
  };
  funnel: Record<"read" | "screened" | "flagged_queued" | "diagnosed" | "spin", Sample>;
  daily: Array<{ date: string; by_camp: Record<Camp, { read: number; screened: number; diagnosed: number; spins: number }> }>;
  by_camp: Record<Camp, CampBucket>;
  by_party: Record<string, CampBucket & { party: Party | null; camp: Camp | "mixed"; camps: Partial<Record<Camp, number>> }>;
  techniques: Record<string, Record<Camp, Sample>>;
  accounts: Array<{ account_id: number; name: string; handle: string; party: Party | null; camp: Camp; diagnosed: number }>;
};

const getIndicatorStats = () => apiFetch<IndicatorStats>("/api/clinic/stats/");
const format = (value: number) => value.toLocaleString("pl-PL");
const percent = (part: number, whole: number) => (whole > 0 ? Math.round((part / whole) * 100) : 0);
const VERDICTS: Array<[keyof Pick<CampBucket, "spin" | "partial" | "no_spin" | "unclear">, string]> = [
  ["spin", "spin"], ["partial", "częściowy spin"], ["no_spin", "bez spinu"], ["unclear", "nie da się ocenić"],
];

const UpdatedAt = createContext(0);

function PeriodNote({ stats, allTime = false, from, to }: { stats: IndicatorStats; allTime?: boolean; from?: string; to?: string }) {
  const updatedAt = useContext(UpdatedAt);
  const range = allTime ? "" : `${formatDatePl(from || stats.window.date_from)} – ${formatDatePl(to || stats.window.date_to)}`;
  return <p className="sc-ind-note sc-ind-period">{range ? <>Zakres: {range} · </> : null}{clinicPeriodLabel(stats, updatedAt)}</p>;
}

function DataTable({ title, headers, rows }: { title: string; headers: string[]; rows: Array<Array<string | number>> }) {
  return <details className="sc-chart-data"><summary>Tabela danych - {title}</summary><p className="sc-ind-scroll-hint">Przewijaj tabelę w poziomie, aby zobaczyć wszystkie kolumny.</p><div className="sc-ind-table-wrap" role="region" aria-label={`${title} - tabela przewijana poziomo`} tabIndex={0}><table className="sc-ind-table"><caption>{title}</caption>
    <thead><tr>{headers.map(header => <th scope="col" key={header}>{header}</th>)}</tr></thead>
    <tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, column) => column === 0 ? <th scope="row" key={column}>{cell}</th> : <td key={column}>{cell}</td>)}</tr>)}</tbody>
  </table></div></details>;
}

/** Zaokrąglenie osi w górę do „ładnej” wartości (1, 2, 5 × 10^n). */
function niceMax(value: number): number {
  if (value <= 4) return 4;
  const power = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 5, 10].find((m) => m * power >= value) ?? 10;
  return step * power;
}

function Funnel({ stats }: { stats: IndicatorStats }) {
  const rows: Array<[string, number, number | null, string]> = [
    ["Przeczytane wpisy", stats.totals.read.total, stats.totals.read.today, "każdy nowy wpis z oficjalnych kont polityków"],
    ["Wstępnie ocenione wpisy", stats.totals.screened.total, stats.totals.screened.today, "czy we wpisie jest teza warta zbadania"],
    ["Diagnozy Dr. Spina", stats.totals.diagnosed.total, stats.totals.diagnosed.today, "opublikowane oceny konsylium modeli AI"],
    ["Spin lub częściowy spin", stats.totals.spins.total, stats.totals.spins.today, "diagnozy z jednym z tych dwóch werdyktów"],
  ];
  const max = Math.max(...rows.map((row) => row[1]), 1);
  return (
    <section className="sc-ind-card sc-ind-funnel" aria-labelledby="ind-funnel-title">
      <SectionHeader variant="panel" titleId="ind-funnel-title" title="Praca Kliniki od początku"
        subtitle="Dr. Spin bada tylko wpisy, w których jest teza do sprawdzenia. Stąd różnica między przeczytanymi a zdiagnozowanymi." />
      <PeriodNote stats={stats} allTime />
      <ol className="sc-ind-funnel__list">
        {rows.map(([label, total, today, hint]) => (
          <li key={label}>
            <div className="sc-ind-funnel__label"><strong>{label}</strong><span>{hint}</span></div>
            <div className="sc-ind-funnel__bar" aria-hidden="true"><i style={{ width: `${(total / max) * 100}%` }} /></div>
            <div className="sc-ind-funnel__value"><strong>{format(total)}</strong>{today ? <small>+{format(today)} dziś</small> : null}</div>
          </li>
        ))}
      </ol>
      <DataTable title="Praca Kliniki" headers={["Etap", "Od początku", "Dziś"]} rows={rows.map(([label, total, today]) => [label, total, today ?? "Brak danych"])} />
      {stats.funnel.flagged_queued.count ? (
        <p className="sc-ind-note">Teraz w kolejce do diagnozy: {format(stats.funnel.flagged_queued.count)}.</p>
      ) : null}
    </section>
  );
}

function Legend() {
  return (
    <p className="sc-ind-legend">
      {CAMPS.map((camp) => <span key={camp} data-camp={camp}><i aria-hidden="true" />{CAMP_LABELS[camp]}</span>)}
    </p>
  );
}

/** Słupki dzienne z podziałem na strony (skumulowane), jedna skala dla obu. */
function DailyChart({ stats, metric, title, note }: { stats: IndicatorStats; metric: "read" | "diagnosed"; title: string; note: string }) {
  const patternId = useId();
  const svgRef = useRef<SVGSVGElement>(null);
  const [width, setWidth] = useState(360);
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(1, entry.contentRect.width)));
    observer.observe(svg);
    return () => observer.disconnect();
  }, []);
  // Klinika działa krócej niż okno 30 dni - wykres zaczyna się od pierwszego dnia z danymi (co najmniej 7 dni).
  const first = stats.daily.findIndex((day) => CAMPS.some((camp) => day.by_camp[camp].read || day.by_camp[camp].diagnosed));
  const days = stats.daily.slice(Math.max(0, Math.min(first < 0 ? 0 : first, stats.daily.length - 7)));
  const totals = days.map((day) => CAMPS.reduce((sum, camp) => sum + day.by_camp[camp][metric], 0));
  const top = niceMax(Math.max(...totals, 1));
  const W = width, H = 200, L = 52, R = 16, T = 10, B = 26;
  const plotW = W - L - R, plotH = H - T - B;
  const slot = plotW / Math.max(1, days.length);
  const labelStep = Math.max(1, Math.ceil(days.length / Math.max(2, Math.floor(plotW / 58))));
  const y = (value: number) => T + plotH - (value / top) * plotH;
  const ticks = [0, top / 2, top];
  const sum = totals.reduce((a, b) => a + b, 0);
  return (
    <figure className="sc-ind-card sc-ind-chart">
      <figcaption className="sc-ind-card__head">
        <h3>{title}</h3>
        <p>{note} Razem w {days.length} dniach: {format(sum)}.</p>
      </figcaption>
      <Legend />
      <PeriodNote stats={stats} from={days[0]?.date} to={days.at(-1)?.date} />
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}: ${format(sum)} w ${days.length} dniach`}>
        <defs><pattern id={patternId} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="var(--sc-ind-opp)" /><line x1="0" y1="0" x2="0" y2="6" stroke="var(--sc-surface)" strokeWidth="2" /></pattern></defs>
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={L} x2={W - R} y1={y(tick)} y2={y(tick)} className="sc-ind-grid" />
            <text x={L - 6} y={y(tick) + 4} textAnchor="end" className="sc-ind-axis">{format(tick)}</text>
          </g>
        ))}
        {days.map((day, index) => {
          let base = 0;
          const x = L + index * slot + slot * 0.15;
          return (
            <g key={day.date}>
              <title>{`${day.date}: ${CAMPS.map((camp) => `${CAMP_LABELS[camp]} ${day.by_camp[camp][metric]}`).join(", ")}`}</title>
              {CAMPS.map((camp) => {
                const value = day.by_camp[camp][metric];
                const height = (value / top) * plotH;
                const rect = <rect key={camp} x={x} width={slot * 0.7} y={y(base + value)} height={height} className="sc-ind-bar" data-camp={camp} style={{ fill: camp === "opposition" ? `url(#${patternId})` : "var(--sc-ind-gov)" }} />;
                base += value;
                return value ? rect : null;
              })}
              {index === days.length - 1 || (index % labelStep === 0 && days.length - 1 - index >= labelStep / 2) ? (
                <text x={x + slot * 0.35} y={H - 8} textAnchor="middle" className="sc-ind-axis">{day.date.slice(8, 10)}.{day.date.slice(5, 7)}</text>
              ) : null}
            </g>
          );
        })}
      </svg>
      <DataTable title={title} headers={["Data", ...CAMPS.map(camp => CAMP_LABELS[camp])]} rows={days.map(day => [day.date, ...CAMPS.map(camp => day.by_camp[camp][metric])])} />
    </figure>
  );
}

function CampColumn({ camp, bucket, minSample, read, histMax }: { camp: Camp; bucket: CampBucket; minSample: number; read?: number; histMax: number }) {
  const n = bucket.diagnosed;
  return (
    <section className="sc-ind-camp" data-camp={camp} aria-labelledby={`ind-camp-${camp}`}>
      <h3 id={`ind-camp-${camp}`}><span aria-hidden="true">{camp === "government" ? "●" : "■"}</span> {CAMP_LABELS[camp]}</h3>
      <p className="sc-ind-camp__n">
        <strong>{format(n)}</strong> diagnoz{read !== undefined ? <> · {format(read)} przeczytanych wpisów w tym okresie</> : null}
      </p>
      <div className="sc-ind-stack" role="img" aria-label={VERDICTS.map(([key, label]) => `${label}: ${bucket[key]}`).join(", ")}>
        {VERDICTS.map(([key]) => bucket[key] ? <i key={key} data-verdict={key} style={{ flexGrow: bucket[key] }} /> : null)}
      </div>
      <ul className="sc-ind-verdicts">
        {VERDICTS.map(([key, label]) => (
          <li key={key} data-verdict={key}><i aria-hidden="true" />{label}<span>{bucket[key]} z {n} ({n ? `${percent(bucket[key], n)}%` : "brak danych"})</span></li>
        ))}
      </ul>
      <p className="sc-ind-avg">
        Średnia siła spinu:{" "}
        {bucket.enough_data && bucket.average_intensity !== null
          ? <strong><span className="sc-spin-num" style={spinVar(bucket.average_intensity)}>{Math.round(bucket.average_intensity)}</span>/100</strong>
          : <span className="sc-ind-few">za mało danych (n = {n}, próg {minSample})</span>}
      </p>
      <p className="sc-ind-note">Liczba diagnoz - wspólna skala: 0–{histMax}.</p>
      <div className="sc-ind-hist" aria-label="Rozkład siły spinu">
        {bucket.intensity_histogram.map((bin) => (
          <div key={bin.min} className="sc-ind-hist__bin">
            <span className="sc-ind-hist__plot"><span className="sc-ind-hist__bar" style={{ height: `${(bin.count / histMax) * 100}%` }} aria-hidden="true" /></span>
            <span className="sc-ind-hist__count">{bin.count}</span>
            <span className="sc-ind-hist__label">{bin.min}–{bin.max}</span>
          </div>
        ))}
      </div>
      <DataTable title={`Rozkład siły spinu - ${CAMP_LABELS[camp]}`} headers={["Siła spinu", "Diagnozy"]} rows={bucket.intensity_histogram.map(bin => [`${bin.min}–${bin.max}`, bin.count])} />
    </section>
  );
}

function Techniques({ stats }: { stats: IndicatorStats }) {
  const [all, setAll] = useState(false);
  const rows = Object.entries(stats.techniques)
    .map(([name, counts]) => ({ name, counts, total: CAMPS.reduce((sum, camp) => sum + counts[camp].count, 0) }))
    .filter((row) => row.total > 0)
    .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name, "pl"));
  return (
    <section className="sc-ind-card" aria-labelledby="ind-tech-title">
      <header className="sc-ind-card__head">
        <h2 id="ind-tech-title">Najczęstsze techniki</h2>
        <p>Odsetek diagnoz danej strony, w których Dr. Spin wskazał technikę (liczona raz na diagnozę). Odsetki, bo strony mają różną liczbę diagnoz.</p>
      </header>
      <PeriodNote stats={stats} />
      <Legend />
      {rows.length ? (
        <ul className="sc-ind-tech" id="ind-tech-list">
          {(all ? rows : rows.slice(0, 6)).map((row) => (
            <li key={row.name}>
              <span className="sc-ind-tech__name">{row.name}</span>
              {CAMPS.map((camp) => {
                const n = stats.by_camp[camp]?.diagnosed ?? 0;
                const share = percent(row.counts[camp].count, n);
                return (
                  <span key={camp} className="sc-ind-tech__row" data-camp={camp}>
                    <span className="sc-ind-tech__camp"><span aria-hidden="true">{camp === "government" ? "●" : "■"}</span> {CAMP_LABELS[camp]}</span>
                    <span className="sc-ind-tech__track" aria-hidden="true"><i style={{ width: `${share}%` }} /></span>
                    <span className="sc-ind-tech__value">{row.counts[camp].count} z {n} <small>({n ? `${share}%` : "brak danych"})</small></span>
                  </span>
                );
              })}
            </li>
          ))}
        </ul>
      ) : <p className="sc-ind-note">Brak diagnoz w tym okresie.</p>}
      {rows.length > 6 ? <Button type="button" variant="quiet" aria-expanded={all} aria-controls="ind-tech-list" onClick={() => setAll(value => !value)}>{all ? "Pokaż sześć najczęstszych" : `Pokaż wszystkie (${rows.length})`}</Button> : null}
      <DataTable title="Techniki" headers={["Technika", "Rządzący - liczba", "Rządzący - próba", "Opozycja - liczba", "Opozycja - próba"]} rows={rows.map(row => [row.name, ...CAMPS.flatMap(camp => [row.counts[camp].count, stats.by_camp[camp].diagnosed])])} />
    </section>
  );
}

function Parties({ stats }: { stats: IndicatorStats }) {
  const rows = Object.entries(stats.by_party).sort(([, a], [, b]) => b.diagnosed - a.diagnosed);
  if (!rows.length) return null;
  return (
    <section className="sc-ind-card" aria-labelledby="ind-party-title">
      <header className="sc-ind-card__head">
        <h2 id="ind-party-title">Według partii</h2>
        <p>Partia krajowa z rejestru osób publicznych. Europosłów liczymy przy ich partii, nie frakcji w Parlamencie Europejskim. „Nieustalona afiliacja” oznacza brak danych o partii w rejestrze, a nie osobną partię ani deklarację bezpartyjności.</p>
      </header>
      <PeriodNote stats={stats} />
      <p className="sc-ind-scroll-hint">Przewijaj tabelę w poziomie, aby zobaczyć wszystkie kolumny.</p>
      <div className="sc-ind-table-wrap" role="region" aria-label="Według partii - tabela przewijana poziomo" tabIndex={0}>
        <table className="sc-ind-table">
          <thead><tr><th scope="col">Partia</th><th scope="col">Strona</th><th scope="col">Diagnozy</th><th scope="col">Spin / częściowy</th><th scope="col">Średnia siła spinu</th></tr></thead>
          <tbody>
            {rows.map(([code, row]) => (
              <tr key={code}>
                <th scope="row">{row.party?.short ?? "Nieustalona afiliacja"}</th>
                <td>{row.camp === "mixed" ? "obie" : CAMP_LABELS[row.camp]}</td>
                <td>{row.diagnosed}</td>
                <td>{row.spin} / {row.partial}</td>
                <td>{row.enough_data && row.average_intensity !== null ? <><span className="sc-spin-num" style={spinVar(row.average_intensity)}>{Math.round(row.average_intensity)}</span>/100</> : <span className="sc-ind-few">za mało danych</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Accounts({ stats }: { stats: IndicatorStats }) {
  const rows = stats.accounts.slice(0, 10);
  if (!rows.length) return null;
  const max = Math.max(...rows.map((row) => row.diagnosed), 1);
  return (
    <section className="sc-ind-card" aria-labelledby="ind-acc-title">
      <header className="sc-ind-card__head">
        <h2 id="ind-acc-title">Najczęściej badane konta</h2>
        <p>Zakres wybranej próby: liczba przeanalizowanych wpisów z poszczególnych kont w podanym okresie. Zależy od doboru materiałów do badania i nie mierzy aktywności ani jakości wypowiedzi osoby.</p>
      </header>
      <PeriodNote stats={stats} />
      <Legend />
      <ol className="sc-ind-accounts">
        {rows.map((row) => (
          <li key={`${row.account_id}-${row.camp}`} data-camp={row.camp}>
            <Link href={`/klinika/diagnozy?account=${row.account_id}`}>{row.name}{row.party ? `, ${row.party.short}` : ""}<span className="sc-ind-account-camp"><span aria-hidden="true">{row.camp === "government" ? "●" : "■"}</span> {CAMP_LABELS[row.camp]}</span></Link>
            <span className="sc-ind-accounts__bar" aria-hidden="true"><i style={{ width: `${(row.diagnosed / max) * 100}%` }} /></span>
            <span className="sc-ind-accounts__n">{row.diagnosed}</span>
          </li>
        ))}
      </ol>
      <DataTable title="Badane konta" headers={["Autor", "Strona", "Diagnozy"]} rows={rows.map(row => [row.name, CAMP_LABELS[row.camp], row.diagnosed])} />
    </section>
  );
}

type PageTotals = Record<"read" | "screened" | "rejected" | "diagnosed" | "spins", Pair>;

/**
 * Panel „Praca Kliniki” na górze /klinika: duże liczniki (od początku i dziś), słupki diagnoz z ostatnich dni
 * i dwa wejścia - do bazy wszystkich diagnoz i do wskaźników. Gdy /api/clinic/stats/ niedostępne - liczniki z /api/clinic/.
 */
export function ClinicShowcase({ fallback, fallbackPeriod, fetchedAt = 0, compact = false }: { fallback?: PageTotals | null; fallbackPeriod?: DataPeriod; fetchedAt?: number; compact?: boolean }) {
  const query = useQuery({ queryKey: ["clinic-indicators"], queryFn: getIndicatorStats, staleTime: 10 * 60_000 });
  const stats = query.data;
  const totals: PageTotals | null | undefined = stats?.totals ?? fallback;
  if (!totals) return null;
  const accounts = stats ? new Set(stats.accounts.map((row) => row.account_id)).size : null;
  const first = stats ? stats.daily.findIndex((day) => CAMPS.some((camp) => day.by_camp[camp].diagnosed)) : -1;
  const days = stats && first >= 0 ? stats.daily.slice(Math.max(0, first, stats.daily.length - 14)) : [];
  const perDay = days.map((day) => CAMPS.reduce((sum, camp) => sum + day.by_camp[camp].diagnosed, 0));
  const top = Math.max(...perDay, 1);
  const tiles: Array<[string, number, number | null]> = [
    ["przeczytanych wpisów polityków", totals.read.total, totals.read.today],
    ["wstępnie ocenionych wpisów", totals.screened.total, totals.screened.today],
    ["diagnoz Dr. Spina", totals.diagnosed.total, totals.diagnosed.today],
  ];
  return (
    <UpdatedAt.Provider value={query.dataUpdatedAt}><section className="sc-ind-show" data-compact={compact || undefined} aria-labelledby="ind-show-title">
      <div className="sc-ind-show__main">
        <SectionHeader variant="panel" titleId="ind-show-title" title="Praca Kliniki od początku" />
        {stats ? <PeriodNote stats={stats} allTime /> : <p className="sc-ind-note">{clinicPeriodLabel(fallbackPeriod, fetchedAt)}</p>}
        <ul className="sc-ind-show__tiles">
          {tiles.map(([label, total, today]) => (
            <li key={label}>
              <strong>{format(total)}</strong>
              <span>{label}</span>
              {today ? <small>+{format(today)} dziś</small> : null}
            </li>
          ))}
          {accounts ? <li><strong>{format(accounts)}</strong><span>kont z opublikowaną diagnozą polityków</span></li> : null}
        </ul>
        <p className="sc-ind-show__actions">
          <Button variant="primary" href="/klinika/diagnozy">Wszystkie diagnozy ({format(totals.diagnosed.total)}) →</Button>
          <Link href="/klinika/wskazniki">Dane i wykresy →</Link>
        </p>
      </div>
      {!compact && perDay.length ? (
        <figure className="sc-ind-show__spark">
          <figcaption>Diagnozy dziennie</figcaption>
          <div className="sc-ind-show__chart-scroll" role="region" aria-label="Diagnozy dziennie - wykres przewijany poziomo" tabIndex={0}>
            <div className="sc-ind-show__bars" role="img" aria-label={`Diagnozy dziennie: ${days.map((day, index) => `${day.date}: ${perDay[index]}`).join(", ")}`}>
              {days.map((day, index) => (
                <div className="sc-ind-show__day" key={day.date} title={`${day.date}: ${perDay[index]}`} aria-hidden="true">
                  <span className="sc-ind-show__plot"><i style={{ height: `${(perDay[index] / top) * 100}%` }}><b>{perDay[index]}</b></i></span>
                  <time dateTime={day.date}>{day.date.slice(8, 10)}.{day.date.slice(5, 7)}</time>
                </div>
              ))}
            </div>
          </div>
          {stats ? <PeriodNote stats={stats} from={days[0].date} to={days.at(-1)?.date} /> : null}
          <DataTable title="Diagnozy dziennie" headers={["Data", "Diagnozy"]} rows={days.map((day, index) => [day.date, perDay[index]])} />
        </figure>
      ) : null}
    </section></UpdatedAt.Provider>
  );
}

export function ClinicIndicators() {
  const query = useQuery({ queryKey: ["clinic-indicators"], queryFn: getIndicatorStats, staleTime: 10 * 60_000 });
  const stats = query.data;
  const histMax = Math.max(1, ...(stats ? CAMPS.flatMap(camp => stats.by_camp[camp]?.intensity_histogram.map(bin => bin.count) ?? []) : []));
  return (
    <section className="sc-clinic sc-ind" aria-labelledby="ind-title">
      <ClinicNav />
      <SectionHeader variant="page" titleId="ind-title" title="Dane i wykresy"
        kicker={<><Link href="/klinika">Klinika spinu</Link> <AiTag /></>}
        subtitle="Co pokazują opublikowane diagnozy - obie strony obok siebie, techniki, partie i konta - a niżej, ile wpisów przetworzyliśmy. Porównania dotyczą analizowanych materiałów, nie całej polityki."
        action={<Button href="/klinika/diagnozy" variant="primary">Baza wszystkich diagnoz →</Button>}
        link={<Link href="/metodologia">Jak wybieramy i liczymy?</Link>} />

      {query.isError ? <p role="alert" className="sc-clinic-empty">Nie udało się pobrać wskaźników. <Button type="button" variant="quiet" onClick={() => query.refetch()}>Spróbuj ponownie</Button></p> : null}
      {query.isLoading ? <p className="sc-clinic-empty">Ładowanie wskaźników…</p> : null}

      {stats ? <UpdatedAt.Provider value={query.dataUpdatedAt}>
        <section className="sc-ind-card" aria-labelledby="ind-sides-title">
          <header className="sc-ind-card__head">
            <h2 id="ind-sides-title">Obie strony obok siebie</h2>
            <p>To wybrane materiały, nie reprezentatywna próba całej polityki. Ostatnie {stats.window.days} dni. Średnią siłę pokazujemy od {stats.min_sample} diagnoz strony, a przy mniejszej próbie tylko liczby.</p>
          </header>
          <PeriodNote stats={stats} />
          <Legend />
          <div className="sc-ind-camps">
            {CAMPS.map((camp) => stats.by_camp[camp]
              ? <CampColumn histMax={histMax} key={camp} camp={camp} bucket={stats.by_camp[camp]} minSample={stats.min_sample} read={stats.daily.reduce((sum, day) => sum + day.by_camp[camp].read, 0)} />
              : null)}
          </div>
        </section>
        <Techniques stats={stats} />
        <Parties stats={stats} />
        <Accounts stats={stats} />
        {/* Najpierw polityczne podsumowania (to czytelnik chce zobaczyć od razu), niżej - jak pracuje Klinika (uwaga testera UX). */}
        <Funnel stats={stats} />
        <div className="sc-ind-pair">
          <DailyChart stats={stats} metric="read" title="Przeczytane wpisy dziennie" note="Wszystkie nowe wpisy z kont obu stron." />
          <DailyChart stats={stats} metric="diagnosed" title="Diagnozy dziennie" note="Opublikowane diagnozy według dnia diagnozy." />
        </div>
        <aside className="sc-ind-method" aria-label="Jak czytać te dane">
          <h2>Jak czytać te dane</h2>
          <ul>
            <li>Diagnozy obejmują wpisy, które izba przyjęć uznała za warte zbadania. To nie jest próba całej polityki, więc liczba diagnoz jednej strony nie mówi, która strona spinuje więcej.</li>
            <li>Siła spinu (0–100) mówi, jak mocno wpis opiera się na technikach perswazji. Nie jest oceną prawdziwości ani osoby.</li>
            <li>Diagnozy stawia AI (konsylium kilku modeli). Każda ma numer, pełne uzasadnienie i przycisk „Zgłoś błąd”.</li>
            <li>Okres: {stats.window.date_from} – {stats.window.date_to}. Dane odświeżamy co 10 minut.</li>
          </ul>
        </aside>
      </UpdatedAt.Provider> : null}
    </section>
  );
}
