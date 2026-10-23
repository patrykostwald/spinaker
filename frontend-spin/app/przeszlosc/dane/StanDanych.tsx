"use client";
import { useEffect, useState } from 'react';
import { Bar, Foot, day, nb, plural, useStandalone } from '../ui';
import './dane.css';

/**
 * Stan danych (Śledczy G4, 23.10): „czy brak wyniku to brak w świecie, czy brak w bazie?”. GET /api/przeszlosc/stan-danych/
 * Wiersz = źródło (Common Region): stan jako mała etykieta po prawej od nazwy, liczba rekordów i data w stałych kolumnach
 * (wspólne linie). Najpierw zaległe i puste - dziennikarz widzi braki przed wynikami (Tesler: system mówi, czego nie wie).
 */
type Src = { key: string; title: string; enabled: boolean; status: 'ok' | 'stale' | 'empty' | 'off'; records: number; last_fetch: string | null; last_error: string; gaps: string; kind?: 'dataset' | 'collector' };
type Krs = { people_total: number; people_checked: number; people_with_entity: number; relations_confirmed: number; relations_pending: number;
  entities_total: number; entities_with_nip: number; entities_stale: number; queue: Record<string, number>; agent_enabled: boolean; rules: string };
type Data = { generated_at: string; stale_hours: number; sources: Src[]; counts: Record<string, number>; krs: Krs; note: string };

const LABEL: Record<Src['status'], string> = { ok: 'aktualne', stale: 'zaległe', empty: 'brak rekordów', off: 'wyłączone' };
const pct = (a: number, b: number) => b ? `${Math.round(100 * a / b)}%` : '-';
/** „3 z 1 osoby” / „z 5 osób”: po „z” zawsze dopełniacz (1 - liczba pojedyncza). */
const of = (a: number, b: number, one: string, many: string) => `${a} z ${b} ${b === 1 ? one : many}`;

function Row({ s }: { s: Src }) {
  return <li className="px-sd__row">
    <div className="px-sd__name"><strong>{s.title}</strong><span className={`px-sd__tag is-${s.status}`}>{LABEL[s.status]}</span></div>
    <span className="px-sd__count">{s.records.toLocaleString('pl-PL')}<small>{` ${plural(s.records, 'rekord', 'rekordy', 'rekordów')}`}</small></span>
    <time className="px-sd__time">{s.last_fetch ? day(s.last_fetch) : 'nie pobrano'}</time>
    <small className="px-sd__gaps">{nb(s.last_error ? `Ostatni błąd: ${s.last_error}` : s.gaps || 'Braki nieopisane.')}</small>
  </li>;
}

export function StanDanych() {
  useStandalone();
  const [data, setData] = useState<Data | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    fetch('/api/przeszlosc/stan-danych/').then(r => r.ok ? r.json() : Promise.reject(r.status)).then(setData).catch(() => setFailed(true));
  }, []);
  const k = data?.krs;
  const sets = (data?.sources ?? []).filter(s => s.kind === 'dataset');
  const collectors = (data?.sources ?? []).filter(s => s.kind !== 'dataset');
  return <div className="px px-sd">
    <Bar />
    <header className="px-sd__hero">
      <h1 className="px-sd__title">Stan danych</h1>
      <p className="px-sd__lead">{nb('Brak wyniku w przeszłość.today znaczy „brak w naszych danych”, nie „brak w świecie”. Tu widać, które źródła zbieramy, kiedy ostatnio i czego w nich nie ma.')}</p>
    </header>
    {failed && <p className="px-msg" role="alert">Nie udało się pobrać stanu danych. Spróbuj ponownie.</p>}
    {data && k && <>
      <section aria-labelledby="sd-krs-h" className="px-sd__krs">
        <h2 id="sd-krs-h" className="px-sd__h2">Pokrycie KRS</h2>
        <div className="px-sd__nums">
          <div className="px-sd__box"><span>Osoby sprawdzone w KRS</span><strong>{pct(k.people_checked, k.people_total)}</strong><small>{nb(of(k.people_checked, k.people_total, 'osoby', 'osób'))}</small></div>
          <div className="px-sd__box"><span>Osoby z podmiotem</span><strong>{k.people_with_entity}</strong><small>{nb(`${k.relations_confirmed} ${plural(k.relations_confirmed, 'funkcja', 'funkcje', 'funkcji')}, ${k.relations_pending} do przeglądu`)}</small></div>
          <div className="px-sd__box"><span>Podmioty z NIP</span><strong>{pct(k.entities_with_nip, k.entities_total)}</strong><small>{nb(of(k.entities_with_nip, k.entities_total, 'podmiotu', 'podmiotów'))}</small></div>
          <div className="px-sd__box"><span>Kolejka KRS</span><strong>{k.queue.pending ?? 0}</strong><small>{nb(`czeka; błędów: ${k.queue.error ?? 0}`)}</small></div>
        </div>
        <p className="px-note">{nb(k.rules)}</p>
      </section>
      <section aria-labelledby="sd-set-h" className="px-sd__set">
        <h2 id="sd-set-h" className="px-sd__h2">{`Zbiory na profilach (${sets.length})`}</h2>
        <ul className="px-sd__list">{sets.map(s => <Row key={s.key} s={s} />)}</ul>
      </section>
      <section aria-labelledby="sd-src-h">
        <h2 id="sd-src-h" className="px-sd__h2">{`Zbieracze rejestrów (${collectors.length})`}</h2>
        <ul className="px-sd__list">{collectors.map(s => <Row key={s.key} s={s} />)}</ul>
      </section>
      <p className="px-note px-sd__foot">{nb(`Zaległe: bez udanego pobrania od ponad ${data.stale_hours} godzin. Stan na ${day(data.generated_at.slice(0, 10))}.`)}</p>
    </>}
    <Foot />
  </div>;
}
