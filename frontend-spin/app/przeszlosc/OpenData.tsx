"use client";
import { day, nb, spinColor } from './ui';

/**
 * Raport źródeł 6.10: bloki z otwartych zbiorów w profilu osoby i w temacie. Te same boksy co reszta kolumny bocznej
 * (px-card: tytuł u góry, wiersze w środku, źródło z licencją na dole; Common Region, Similarity). Wskazówki kont X
 * z Wikidata nie są pokazywane (nie są potwierdzone).
 */
type Source = { key: string; label: string; license: string; url: string; note?: string };
export type SejmVideo = { id: number; day: string; place: 'sala' | 'komisja'; place_label: string; headline: string; intensity: number;
  verdict: string; video_url: string; timecode: string; exact: boolean; source_url: string; committee: string };
export type OpenData = {
  ep_votes?: { count: number; results: { date: string | null; title: string; reference: string; position: string; url: string }[] };
  ep_integrity?: { declarations: { title: string; url: string }[]; income: { total_eur: number; paid: number; activities: { activity: string; total_eur: number }[] } | null;
    meetings: { count: number; results: { date: string | null; lobbyists: string; title: string; role: string }[] } };
  identity?: { wikidata: string; wikipedia: string; parties: { name: string; start: string | null; end: string | null }[] };
  mp_expenses?: { mileage: { period: string; amount_pln: number | null; km: number | null; check: string; origin: string; origin_url: string }[];
    offices: { year: number; total_pln: number | null; pdf_url: string; check: string }[] };
  sources: Source[];
};
export type EuFunds = { results: { kind: string; beneficiary: string; title: string; amount_eur: number | null; year: number | null; url: string; krs: string; link: string }[];
  total_eur: number; sources: { label: string; license: string; url: string }[] };

const pln = (v: number | null) => v === null ? '-' : `${v.toLocaleString('pl-PL', { maximumFractionDigits: 0 })} zł`;
const eur = (v: number | null) => v === null ? '-' : `${v.toLocaleString('pl-PL', { maximumFractionDigits: 0 })} €`;
const year = (iso: string | null) => (iso ? iso.slice(0, 4) : '');

function SourceFoot({ sources, keys }: { sources: Source[]; keys: string[] }) {
  const rows = sources.filter(s => keys.includes(s.key));
  if (!rows.length) return null;
  return <p className="px-note px-od__src">{rows.map((s, i) => <span key={s.key}>{i ? ' · ' : 'Źródło: '}<a href={s.url} target="_blank" rel="noopener noreferrer">{s.label}</a> ({s.license}){s.note ? `. ${s.note}` : ''}</span>)}</p>;
}

export function SejmVideos({ items }: { items: SejmVideo[] }) {
  if (!items.length) return null;
  return <section className="px-card" aria-labelledby="pp-video-h">
    <h3 id="pp-video-h" className="px-h3">Wystąpienia w&nbsp;Sejmie z&nbsp;diagnozą</h3>
    <ul className="px-panel__rows">{items.map(v => <li key={v.id}>
      <span><a href={v.video_url} target="_blank" rel="noopener noreferrer"><i className="px-spin-dot" style={{ ['--spin' as string]: spinColor(v.intensity) }} />{v.headline || 'Diagnoza wystąpienia'}</a></span>
      <small>{[day(v.day), v.place === 'sala' ? 'sala posiedzeń' : v.committee || 'komisja', `spin ${v.intensity}/100`].join(' · ')} · <a href={v.video_url} target="_blank" rel="noopener noreferrer">nagranie {v.exact ? 'od' : 'ok.'} {v.timecode} ↗</a> · <a href={v.source_url} target="_blank" rel="noopener noreferrer">zapis ↗</a></small>
    </li>)}</ul>
    <p className="px-note">{nb('Tekst wystąpienia z zapisu Kancelarii Sejmu; w komisjach miejsce w nagraniu jest szacowane.')}</p>
  </section>;
}

export function ProfileOpenData({ data }: { data?: OpenData | null }) {
  if (!data) return null;
  const { ep_votes: votes, ep_integrity: iw, identity, mp_expenses: exp, sources } = data;
  return <>
    {votes && <section className="px-card" aria-labelledby="pp-ep-h">
      <h3 id="pp-ep-h" className="px-h3">Głosowania w&nbsp;PE</h3>
      <ul className="px-panel__rows">{votes.results.slice(0, 6).map((v, i) => <li key={i}>
        <span><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a></span>
        <small>{[day(v.date ?? ''), v.reference].filter(Boolean).join(' · ')}{v.position ? <> · <b>{v.position}</b></> : null}</small></li>)}</ul>
      <SourceFoot sources={sources} keys={['howtheyvote']} />
    </section>}
    {iw && <section className="px-card" aria-labelledby="pp-iw-h">
      <h3 id="pp-iw-h" className="px-h3">Dochody i&nbsp;spotkania w&nbsp;PE</h3>
      <ul className="px-panel__rows">
        <li><span>Dochody dodatkowe (deklaracja)</span><small>{iw.income ? `${eur(iw.income.total_eur)} · ${iw.income.paid} płatne` : 'brak w deklaracji'}</small></li>
        {(iw.income?.activities ?? []).slice(0, 3).map((a, i) => <li key={`a${i}`}><span>{a.activity}</span><small>{eur(a.total_eur)}</small></li>)}
        <li><span>Spotkania z&nbsp;lobbystami</span><small>{iw.meetings.count}</small></li>
        {iw.meetings.results.slice(0, 3).map((m, i) => <li key={`m${i}`}><span>{m.lobbyists}</span><small>{[day(m.date ?? ''), m.title].filter(Boolean).join(' · ')}</small></li>)}
        {iw.declarations.slice(0, 2).map(d => <li key={d.url}><span><a href={d.url} target="_blank" rel="noopener noreferrer">{d.title}</a></span><small>PDF PE</small></li>)}
      </ul>
      <SourceFoot sources={sources} keys={['integrity_watch']} />
    </section>}
    {identity && <section className="px-card" aria-labelledby="pp-id-h">
      <h3 id="pp-id-h" className="px-h3">Przynależność partyjna</h3>
      {identity.parties.length ? <ul className="px-panel__rows">{identity.parties.map((p, i) => <li key={i}><span>{p.name}</span>
        <small>{p.start || p.end ? `${year(p.start) || '?'} - ${year(p.end) || 'obecnie'}` : 'bez dat'}</small></li>)}</ul>
        : <p className="px-note">{nb('Brak historii partyjnej w Wikidata.')}</p>}
      <p className="px-note"><a href={identity.wikidata} target="_blank" rel="noopener noreferrer">Wikidata ↗</a>{identity.wikipedia ? <> · <a href={identity.wikipedia} target="_blank" rel="noopener noreferrer">Wikipedia ↗</a></> : null}</p>
      <SourceFoot sources={sources} keys={['wikidata']} />
    </section>}
    {exp && <section className="px-card" aria-labelledby="pp-exp-h">
      <h3 id="pp-exp-h" className="px-h3">Wydatki posła</h3>
      <ul className="px-panel__rows">
        {exp.mileage.map((m, i) => <li key={`k${i}`}><span>Kilometrówka {m.period}</span>
          <small>{pln(m.amount_pln)}{m.km ? ` · ${m.km.toLocaleString('pl-PL')} km` : ''} · {m.check}</small></li>)}
        {exp.offices.map(o => <li key={`b${o.year}`}><span>{o.pdf_url ? <a href={o.pdf_url} target="_blank" rel="noopener noreferrer">Biuro poselskie {o.year}</a> : `Biuro poselskie ${o.year}`}</span>
          <small>{pln(o.total_pln)} · {o.check}</small></li>)}
      </ul>
      {exp.mileage.some(m => m.origin) && <p className="px-note">{nb(`Kilometrówki: źródło pierwotne ${exp.mileage.find(m => m.origin)?.origin}, nie Kancelaria Sejmu.`)}</p>}
      <SourceFoot sources={sources} keys={['mileage']} />
    </section>}
  </>;
}

export function TopicFunds({ funds }: { funds?: EuFunds }) {
  if (!funds?.results.length) return null;
  return <section className="px-card" aria-labelledby="eu-h">
    <h3 id="eu-h" className="px-h3">Fundusze UE w&nbsp;temacie</h3>
    <ul className="px-panel__rows">{funds.results.slice(0, 8).map((f, i) => <li key={i}>
      <span><a href={f.url} target="_blank" rel="noopener noreferrer">{f.beneficiary}</a></span>
      <small>{[eur(f.amount_eur), f.year ? String(f.year) : '', f.kind, f.krs ? `KRS ${f.krs}` : ''].filter(Boolean).join(' · ')}</small></li>)}</ul>
    <p className="px-note">{nb('Tylko organizacje; osoby fizyczne pomijamy. Powiązanie z KRS po nazwie - do sprawdzenia.')}</p>
    <p className="px-note px-od__src">Źródło: {funds.sources.map((s, i) => <span key={s.url}>{i ? ' · ' : ''}<a href={s.url} target="_blank" rel="noopener noreferrer">{s.label}</a> ({s.license})</span>)}</p>
  </section>;
}
