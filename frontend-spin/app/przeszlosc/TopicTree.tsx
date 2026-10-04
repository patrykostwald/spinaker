"use client";
import { useEffect, useMemo, useState } from 'react';
import { Loading } from '@spin-clinic/ui/kit';

/**
 * przeszłość.today, tydzień 1 (właściciel 5.10): drzewo powiązań tematu z danych spin.clinic.
 * Kolumny według rodzaju, najechanie lub dotknięcie podświetla powiązane elementy; pod spodem oś czasu.
 */
type Node = { id: string; kind: string; label: string; date?: string | null; url?: string; sub?: string; role?: string; camp?: string; intensity?: number; links: number };
type Edge = { source: string; target: string; label: string };
type Start = { counts: Record<string, number>; latest: { title: string; date: string | null; kind: string; url: string }[]; topics_enabled: boolean; auto_topics?: { topic: string; edges: number }[] };
type Vote = { id: string; title: string; motion: string; date: string | null; kind: string; result: Record<string, number>; url: string;
  clubs: { club: string; size: number; votes: Record<string, number> }[]; members: [string, string, string][] };
type Graph = { topic: string; terms: string[]; nodes: Node[]; edges: Edge[]; counts: Record<string, number>; votes?: Vote[] };

const COLUMNS: [string, string][] = [['person', 'Osoby'], ['organisation', 'Spółki i fundacje (KRS)'], ['record', 'Sejm'],
  ['statement', 'Wpisy na X'], ['diagnosis', 'Diagnozy Dr. Spina'], ['media', 'Media']];
const SUB: Record<string, string> = { print: 'druk', ballot: 'głosowanie', voting: 'głosowanie', consultation: 'konsultacje', lobby_activity: 'lobbing', lobby_document: 'lobbing', financial_document: 'finanse', financial_row: 'finanse' };
const EXAMPLES = ['CPK', 'ceny energii', 'Turów', 'KPO'];

export function TopicTree() {
  const [query, setQuery] = useState('');
  const [data, setData] = useState<Graph | null>(null);
  const [state, setState] = useState<'idle' | 'loading' | 'error' | 'off'>('idle');
  const [focus, setFocus] = useState<string | null>(null);
  const [start, setStart] = useState<Start | null>(null);

  async function load(q: string, remember = true) {
    setState('loading'); setFocus(null);
    try {
      const response = await fetch(`/api/przeszlosc/temat/?q=${encodeURIComponent(q)}`);
      if (response.status === 404) { setState('off'); return; }
      if (!response.ok) throw new Error();
      setData(await response.json()); setState('idle');
      if (remember) window.history.replaceState(null, '', `?q=${encodeURIComponent(q)}`);
    } catch { setState('error'); }
  }
  // osobna strona (przeszlosc.today): bez pasków i menu spin.clinic, własny nagłówek i stopka
  useEffect(() => {
    document.documentElement.dataset.standalone = '1';
    return () => { delete document.documentElement.dataset.standalone; };
  }, []);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('q');
    // strona główna od razu pokazuje stan bazy, najnowsze dokumenty Sejmu i przykładowy temat (właściciel 5.10: „wygląda, jakby nic nie było”)
    fetch('/api/przeszlosc/start/').then(r => r.ok ? r.json() : null).then((data: Start | null) => {
      setStart(data);
      const first = data?.auto_topics?.[0]?.topic ?? EXAMPLES[0];
      if (!q && data?.topics_enabled) { setQuery(first); void load(first, false); }
    }).catch(() => undefined);
    if (q) { setQuery(q); void load(q); }
  }, []);

  const linked = useMemo(() => {
    if (!data || !focus) return null;
    const ids = new Set([focus]);
    for (const e of data.edges) { if (e.source === focus) ids.add(e.target); if (e.target === focus) ids.add(e.source); }
    return ids;
  }, [data, focus]);
  const timeline = useMemo(() => (data?.nodes ?? []).filter(n => n.date).sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '')).slice(0, 40), [data]);

  return <main className="sc-pt">
    <div className="sc-pt__brand"><a href="/przeszlosc" className="sc-pt__mark">przeszłość<i>.</i>today</a>
      <nav><a href="#jak">Jak to działa</a><a href="#ceny">Ceny</a><a href="https://spin.clinic" target="_blank" rel="noopener noreferrer">spin.clinic ↗</a></nav></div>
    <header className="sc-pt__head">
      <p className="sc-pt__k">Wersja beta · bezpłatnie</p>
      <h1>Kto, co i kiedy w jednym temacie</h1>
      <p>Wpisz temat. Pokażemy osoby publiczne, ich spółki i fundacje z KRS, dokumenty Sejmu, wpisy na X z diagnozami Dr. Spina i artykuły. Każde powiązanie ma źródło.</p>
      <form onSubmit={event => { event.preventDefault(); if (query.trim().length >= 3) void load(query.trim()); }} className="sc-pt__search">
        <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Np. CPK, lotnisko" aria-label="Temat" />
        <button type="submit">Pokaż</button>
      </form>
      <p className="sc-pt__ex">{start?.auto_topics?.length ? 'Tematy dnia:' : 'Przykłady:'} {(start?.auto_topics?.length ? start.auto_topics.map(t => t.topic) : EXAMPLES).map(e => <button key={e} type="button" onClick={() => { setQuery(e); void load(e); }}>{e}</button>)}</p>
    </header>

    {state === 'idle' && data && !new URLSearchParams(typeof window === 'undefined' ? '' : window.location.search).get('q') && <p className="sc-pt__k">Temat dnia: {data.topic}</p>}
    {state === 'loading' && <Loading label="Ładowanie tematu" />}
    {state === 'off' && <p className="sc-pt__msg">Podgląd jest jeszcze wyłączony na serwerze.</p>}
    {state === 'error' && <p className="sc-pt__msg" role="alert">Nie udało się pobrać tematu. Spróbuj ponownie.</p>}
    {state === 'idle' && data && <TopicView data={data} />}

    {start && <section className="sc-pt__stats" aria-label="Co jest w bazie">
      {([['people', 'osób publicznych'], ['organisations', 'spółek i fundacji z KRS'], ['records', 'dokumentów Sejmu'], ['posts', 'wpisów polityków'], ['diagnoses', 'diagnoz Dr. Spina'], ['articles', 'artykułów']] as const)
        .map(([key, label]) => <div key={key}><b>{(start.counts[key] ?? 0).toLocaleString('pl-PL')}</b><span>{label}</span></div>)}
    </section>}
    {start && start.latest.length > 0 && <section className="sc-pt__latest" aria-label="Najnowsze w Sejmie">
      <h2>Najnowsze w Sejmie</h2>
      <ol>{start.latest.map((row, i) => <li key={i}><time>{row.date ?? ''}</time><span>{row.kind}</span><a href={row.url} target="_blank" rel="noopener noreferrer">{row.title}</a></li>)}</ol>
    </section>}
    <section className="sc-pt__about" id="jak" aria-label="Jak to działa">
      <div><b>Tylko osoby i podmioty publiczne</b><p>Politycy, urzędnicy, spółki i fundacje z KRS. Żadnych osób prywatnych.</p></div>
      <div><b>Każde powiązanie ma źródło</b><p>Oficjalne dane Sejmu i KRS, wpisy na X, artykuły. Nic nie łączymy po samym nazwisku.</p></div>
      <div><b>Ta sama miara dla wszystkich</b><p>Rządzący i opozycja przechodzą przez identyczne zapytania i te same reguły.</p></div>
    </section>
    <section className="sc-pt__price" id="ceny" aria-label="Ceny">
      <h2>Ceny</h2>
      <p>W becie wszystko jest bezpłatne. Po becie przeglądanie tematów zostaje bezpłatne, a narzędzia dla redakcji są płatne (ceny netto, miesięcznie):</p>
      <ul><li><b>Pro</b> 199 zł · dziennikarz</li><li><b>Zespół</b> 599 zł · redakcja</li><li><b>Instytucje</b> od 2 500 zł</li></ul>
    </section>
    <footer className="sc-pt__foot">przeszłość.today prowadzi iapply sp. z o.o. · dane wspólne ze spin.clinic · <a href="https://spin.clinic/polityka-prywatnosci">Prywatność</a></footer>
  </main>;
}


const KIND_LABEL: Record<string, string> = { record: 'Sejm', statement: 'Wpis', diagnosis: 'Diagnoza Dr. Spina', media: 'Media' };
const CAMP_LABEL: Record<string, string> = { government: 'rządzący', opposition: 'opozycja', public: 'instytucja' };

/** Widok tematu (właściciel 5.10): oś czasu jako główna treść, obok kto występuje, pod spodem rozkład źródeł medialnych. */
function TopicView({ data }: { data: Graph }) {
  const [more, setMore] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const byId = useMemo(() => new Map(data.nodes.map(n => [n.id, n])), [data]);
  const author = useMemo(() => {
    const map = new Map<string, Node>();
    for (const e of data.edges) if (e.label === 'napisał(a)') { const who = byId.get(e.source); if (who) map.set(e.target, who); }
    return map;
  }, [data, byId]);
  const diagnosisOf = useMemo(() => {
    const map = new Map<string, Node>();
    for (const e of data.edges) if (e.label === 'diagnoza Dr. Spina') { const d = byId.get(e.target); if (d) map.set(e.source, d); }
    return map;
  }, [data, byId]);
  const roles = useMemo(() => {
    const map = new Map<string, { org: Node; role: string }[]>();
    for (const e of data.edges) { const org = byId.get(e.target); if (org?.kind === 'organisation') map.set(e.source, [...(map.get(e.source) ?? []), { org, role: e.label }]); }
    return map;
  }, [data, byId]);
  const events = data.nodes.filter(n => n.date && (n.kind === 'statement' || n.kind === 'record' || n.kind === 'media'))
    .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''));
  const shown = more ? events : events.slice(0, 18);
  const people = data.nodes.filter(n => n.kind === 'person').sort((a, b) => b.links - a.links);
  const media = new Map<string, number>();
  for (const n of data.nodes) if (n.kind === 'media' && n.sub) media.set(n.sub, (media.get(n.sub) ?? 0) + 1);
  const mediaRows = [...media.entries()].sort((a, b) => b[1] - a[1]);
  const mediaTotal = mediaRows.reduce((sum, [, n]) => sum + n, 0);
  if (!data.nodes.length) return <p className="sc-pt__msg">Nic nie znaleźliśmy. Spróbuj innego słowa.</p>;
  let lastDay = '';
  return <div className="sc-tv">
    <header className="sc-tv__head">
      <h2>{data.topic}</h2>
      <p>{[['statement', 'wpisów polityków'], ['diagnosis', 'diagnoz Dr. Spina'], ['vote', 'głosowań'], ['record', 'dokumentów Sejmu'], ['media', 'artykułów'], ['person', 'osób i instytucji']]
        .filter(([k]) => data.counts[k]).map(([k, label]) => `${data.counts[k]} ${label}`).join(' · ')}</p>
      <Export data={data} author={author} />
    </header>
    <div className="sc-tv__grid">
      {Boolean(data.votes?.length) && <Votes votes={data.votes!} />}
      <section className="sc-tv__time" aria-label="Oś czasu">
        <h3>Oś czasu</h3>
        <ol>{shown.map(n => {
          const day = n.date ?? '';
          const head = day !== lastDay ? <li className="sc-tv__day" key={`d${day}`}>{new Date(day).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })}</li> : null;
          lastDay = day;
          const who = author.get(n.id);
          const dg = diagnosisOf.get(n.id);
          return [head, <li key={n.id} className="sc-tv__item" data-kind={n.kind} data-camp={n.camp || undefined}>
            <span className="sc-tv__kind">{KIND_LABEL[n.kind]}{n.kind === 'record' && n.sub ? ` · ${SUB[n.sub] ?? n.sub}` : ''}{n.kind === 'media' && n.sub ? ` · ${n.sub}` : ''}</span>
            {who && <span className="sc-tv__who">{who.label}{n.camp && CAMP_LABEL[n.camp] ? <em> · {CAMP_LABEL[n.camp]}</em> : null}</span>}
            <p>{n.label}</p>
            <span className="sc-tv__links">
              {dg && <a href={dg.url} target="_blank" rel="noopener noreferrer" className="sc-tv__dg">Diagnoza Dr. Spina: spin {dg.intensity}/100 →</a>}
              {n.url && <a href={n.url} target="_blank" rel="noopener noreferrer">źródło →</a>}
            </span>
          </li>];
        })}</ol>
        {events.length > 18 && <button type="button" className="sc-tv__more" onClick={() => setMore(!more)}>{more ? 'Pokaż mniej' : `Pokaż wszystko (${events.length})`}</button>}
      </section>
      <aside className="sc-tv__side">
        <section aria-label="Kto występuje">
          <h3>Kto występuje</h3>
          <ul className="sc-tv__people">{people.slice(0, 16).map(p => {
            const r = roles.get(p.id) ?? [];
            return <li key={p.id} data-camp={p.camp || undefined}>
              <span className="sc-tv__pname">{p.url ? <a href={p.url} target="_blank" rel="noopener noreferrer">{p.label}</a> : p.label}<small>{p.links}</small></span>
              {p.role && <span className="sc-tv__prole">{p.role}</span>}
              {r.length > 0 && <button type="button" onClick={() => setOpen(open === p.id ? null : p.id)} aria-expanded={open === p.id}>Funkcje w KRS ({r.length})</button>}
              {open === p.id && <ul className="sc-tv__krs">{r.map(({ org, role }) => <li key={org.id}><a href={org.url} target="_blank" rel="noopener noreferrer">{org.label}</a> <span>{role}</span></li>)}</ul>}
            </li>;
          })}</ul>
          <p className="sc-tv__note">Funkcje w KRS to kontekst osoby, nie dowód związku z tematem.</p>
        </section>
        {mediaTotal > 0 && <section aria-label="Źródła medialne">
          <h3>Źródła medialne w temacie</h3>
          <ul className="sc-tv__media">{mediaRows.slice(0, 8).map(([name, n]) => <li key={name}><span>{name}</span><i><b style={{ width: `${(100 * n) / mediaTotal}%` }} /></i><em>{n}</em></li>)}</ul>
          <p className="sc-tv__note">Pokazujemy, co jest w naszej bazie. Jeśli jedna redakcja przeważa, to informacja o bazie, nie o temacie.</p>
        </section>}
      </aside>
    </div>
  </div>;
}


/* Głosowania w temacie (właściciel 5.10, funkcja 1 z mapy): wynik, kluby zbiorczo w tej samej skali, imiennie po rozwinięciu.
   Kolory znaczą głos (za, przeciw, wstrzymał się, nieobecny), nigdy stronę sceny politycznej. */
const VOTE_ORDER = ['za', 'przeciw', 'wstrzymał się', 'nieobecny'];
const SHORT: Record<string, string> = { za: 'za', przeciw: 'przeciw', 'wstrzymał się': 'wstrz.', nieobecny: 'nieob.' };
function Votes({ votes }: { votes: Vote[] }) {
  const [open, setOpen] = useState<string | null>(null);
  return <section className="sc-tv__votes" aria-label="Głosowania w Sejmie">
    <h3>Głosowania w Sejmie</h3>
    <ul className="sc-tv__vote-legend" aria-hidden="true">{VOTE_ORDER.map(v => <li key={v} data-v={v}><i />{v}</li>)}</ul>
    <ol>{votes.map(v => {
      const max = Math.max(...v.clubs.map(c => c.size), 1);
      return <li key={v.id} className="sc-tv__vote">
        <div className="sc-tv__vote-head">
          <span className="sc-tv__kind">{v.date ? new Date(v.date).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' }) : ''}</span>
          <p>{v.title}</p>
          {v.motion && v.motion !== v.title && <small>{v.motion}</small>}
          <span className="sc-tv__vote-result">{[['yes', 'za'], ['no', 'przeciw'], ['abstain', 'wstrzymało się']].filter(([k]) => v.result[k] != null).map(([k, l]) => <b key={k} data-v={l === 'wstrzymało się' ? 'wstrzymał się' : l}>{v.result[k]} {l}</b>)}</span>
        </div>
        <ul className="sc-tv__clubs">{v.clubs.map(c => <li key={c.club}>
          <span>{c.club}</span>
          <i style={{ width: `${(100 * c.size) / max}%` }}>{VOTE_ORDER.map(k => c.votes[k] ? <b key={k} data-v={k} style={{ flexGrow: c.votes[k] }} title={`${k}: ${c.votes[k]}`} /> : null)}</i>
          <em>{VOTE_ORDER.filter(k => c.votes[k]).map(k => `${c.votes[k]} ${SHORT[k]}`).join(', ')}</em>
        </li>)}</ul>
        <span className="sc-tv__links">
          <button type="button" onClick={() => setOpen(open === v.id ? null : v.id)} aria-expanded={open === v.id}>{open === v.id ? 'Zwiń' : 'Kto jak głosował'}</button>
          <a href={v.url} target="_blank" rel="noopener noreferrer">wynik w Sejmie →</a>
        </span>
        {open === v.id && <div className="sc-tv__members">{v.clubs.map(c => <div key={c.club}>
          <h4>{c.club}</h4>
          <ul>{v.members.filter(m => m[1] === c.club).sort((a, b) => VOTE_ORDER.indexOf(a[2]) - VOTE_ORDER.indexOf(b[2])).map(m => <li key={m[0]} data-v={m[2]}><i />{m[0]}</li>)}</ul>
        </div>)}</div>}
      </li>;
    })}</ol>
  </section>;
}


/* Eksport tematu (właściciel 5.10, funkcja 3 z mapy): każdy wiersz z przypisem źródła i datą pobrania; w becie bez opłat. */
const KIND_EXPORT: Record<string, string> = { record: 'dokument Sejmu', statement: 'wpis polityka', diagnosis: 'diagnoza Dr. Spina', media: 'artykuł', person: 'osoba', organisation: 'podmiot KRS' };
function Export({ data, author }: { data: Graph; author: Map<string, Node> }) {
  const save = (name: string, type: string, text: string) => {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const stamp = new Date().toLocaleDateString('sv-SE');
  const slug = data.topic.toLowerCase().replace(/[^a-z0-9ąćęłńóśźż]+/gi, '-').replace(/^-|-$/g, '') || 'temat';
  const rows = data.nodes.filter(n => n.kind !== 'person').map(n => ({
    data: n.date ?? '', rodzaj: KIND_EXPORT[n.kind] ?? n.kind, tresc: n.label, autor: author.get(n.id)?.label ?? '',
    strona: n.camp === 'government' ? 'rządzący' : n.camp === 'opposition' ? 'opozycja' : '', zrodlo: n.sub ?? '', link: n.url ?? '',
  })).sort((a, b) => b.data.localeCompare(a.data));
  const csv = () => {
    const head = ['data', 'rodzaj', 'treść', 'autor', 'strona', 'źródło', 'link'];
    const cell = (v: string) => `"${String(v).replace(/"/g, '""')}"`;
    const lines = [head.join(';'), ...rows.map(r => [r.data, r.rodzaj, r.tresc, r.autor, r.strona, r.zrodlo, r.link].map(cell).join(';'))];
    for (const v of data.votes ?? []) for (const m of v.members) lines.push([v.date ?? '', 'głos imienny', `${v.title}: ${m[2]}`, m[0], m[1], 'Sejm RP', v.url].map(cell).join(';'));
    lines.push('', cell(`Źródło: przeszłość.today, temat „${data.topic}”, pobrano ${stamp}. Każdy wiersz prowadzi do oryginału.`));
    save(`przeszlosc-${slug}-${stamp}.csv`, 'text/csv;charset=utf-8', '﻿' + lines.join('\r\n'));
  };
  const json = () => save(`przeszlosc-${slug}-${stamp}.json`, 'application/json', JSON.stringify({
    temat: data.topic, pobrano: stamp, zrodlo: 'przeszłość.today', wiersze: rows, glosowania: data.votes ?? [],
    osoby: data.nodes.filter(n => n.kind === 'person').map(n => ({ nazwa: n.label, funkcja: n.role ?? '', link: n.url ?? '' })),
    powiazania: data.edges }, null, 2));
  return <p className="sc-tv__export"><button type="button" onClick={csv}>Pobierz CSV</button><button type="button" onClick={json}>Pobierz JSON</button></p>;
}
