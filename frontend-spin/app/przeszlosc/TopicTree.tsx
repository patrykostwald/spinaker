"use client";
import { useEffect, useMemo, useRef, useState } from 'react';
import { Loading } from '@spin-clinic/ui/kit';

/**
 * przeszłość.today, tydzień 1 (właściciel 5.10): drzewo powiązań tematu z danych spin.clinic.
 * Kolumny według rodzaju, najechanie lub dotknięcie podświetla powiązane elementy; pod spodem oś czasu.
 */
type Node = { id: string; kind: string; label: string; text?: string; institution?: boolean; date?: string | null; url?: string; sub?: string; role?: string; camp?: string; intensity?: number; links: number };
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

    {state === 'loading' && !data && <Loading label="Ładowanie tematu" />}
    {state === 'off' && <p className="sc-pt__msg">Podgląd jest jeszcze wyłączony na serwerze.</p>}
    {state === 'error' && <p className="sc-pt__msg" role="alert">Nie udało się pobrać tematu. Spróbuj ponownie.</p>}
    {data && (state === 'idle' || state === 'loading') && <TopicView data={data} busy={state === 'loading'}
      daily={!new URLSearchParams(typeof window === 'undefined' ? '' : window.location.search).get('q')} />}

    {start && <section className="sc-pt__stats" aria-label="Co jest w bazie">
      {([['people', 'osób publicznych'], ['organisations', 'spółek i fundacji z KRS'], ['records', 'dokumentów Sejmu'], ['posts', 'wpisów polityków'], ['diagnoses', 'diagnoz Dr. Spina'], ['articles', 'artykułów']] as const)
        .map(([key, label]) => <div key={key}><b>{(start.counts[key] ?? 0).toLocaleString('pl-PL')}</b><span>{label}</span></div>)}
    </section>}
    {start && start.latest.length > 0 && <section className="sc-pt__latest" aria-label="Najnowsze w Sejmie">
      <h2>Najnowsze w Sejmie</h2>
      <ol>{start.latest.map((row, i) => <li key={i} data-nodate={!row.date || undefined}>{row.date && <time>{row.date}</time>}<span>{row.kind}</span><a href={row.url} target="_blank" rel="noopener noreferrer">{row.title}</a></li>)}</ol>
    </section>}
    <section className="sc-pt__about" id="jak" aria-label="Jak to działa">
      <div><b>Tylko osoby i podmioty publiczne</b><p>Politycy, urzędnicy, spółki i fundacje z KRS. Żadnych osób prywatnych.</p></div>
      <div><b>Każde powiązanie ma źródło</b><p>Oficjalne dane Sejmu i KRS, wpisy na X, artykuły. Nic nie łączymy po samym nazwisku.</p></div>
      <div><b>Ta sama miara dla wszystkich</b><p>Rządzący i opozycja przechodzą przez identyczne zapytania i te same reguły.</p></div>
    </section>
    <section className="sc-pt__price" id="ceny" aria-label="Dla redakcji i ceny">
      <h2>Dla redakcji</h2>
      <p>W becie wszystko jest bezpłatne. Przeglądanie tematów zostanie bezpłatne. Dla redakcji przygotowujemy narzędzia płatne (ceny netto, miesięcznie):</p>
      <div className="sc-pt__plans">
        <div><b>Bezpłatnie</b><em>0 zł</em><ul><li>tematy, oś czasu, drzewo powiązań</li><li>panel osoby i wpisu</li><li>RSS tematu</li></ul></div>
        <div data-hl><b>Pro</b><em>199 zł</em><ul><li>alerty e-mail o osobach i tematach</li><li>eksport z licencją do publikacji</li><li>historia i notatki śledztwa</li></ul></div>
        <div><b>Zespół</b><em>599 zł</em><ul><li>wszystko z Pro dla 5 osób</li><li>wspólne teczki tematów</li><li>pierwszeństwo nowych źródeł</li></ul></div>
        <div><b>Instytucje</b><em>od 2 500 zł</em><ul><li>dostęp do danych przez API</li><li>raporty na zamówienie</li><li>umowa i faktura</li></ul></div>
      </div>
      <p className="sc-pt__cta"><a href="mailto:kontakt@spin.clinic?subject=przeszłość.today%20dla%20redakcji">Umów 15 minut prezentacji →</a><span>Odpowiadamy w 1 dzień roboczy. Każdy klient na tych samych warunkach.</span></p>
    </section>
    <footer className="sc-pt__foot">przeszłość.today prowadzi iapply sp. z o.o. · dane wspólne ze spin.clinic · <a href="https://spin.clinic/polityka-prywatnosci">Prywatność</a></footer>
  </main>;
}


const KIND_LABEL: Record<string, string> = { record: 'Sejm', statement: 'Wpis', diagnosis: 'Diagnoza Dr. Spina', media: 'Media', vote: 'Głosowanie' };
const CAMP_LABEL: Record<string, string> = { government: 'rządzący', opposition: 'opozycja', public: 'instytucja' };

/** Widok tematu (właściciel 5.10): oś czasu jako główna treść, obok kto występuje, pod spodem rozkład źródeł medialnych. */
/** Nazwiska zapisane wielkimi literami (MÜLLER) jak zwykłe nazwiska; skróty do 3 liter zostają. */
// skróty kont instytucji pełną nazwą (panel designu 5.10: „ME” nic nie mówi czytelnikowi)
const INSTITUTIONS: Record<string, string> = { ME: 'Ministerstwo Energii', MF: 'Ministerstwo Finansów', MON: 'Ministerstwo Obrony Narodowej', MZ: 'Ministerstwo Zdrowia',
  MSZ: 'Ministerstwo Spraw Zagranicznych', MSWiA: 'Ministerstwo Spraw Wewnętrznych i Administracji', KPRM: 'Kancelaria Prezesa Rady Ministrów', MEN: 'Ministerstwo Edukacji Narodowej' };
const nice = (name: string) => INSTITUTIONS[name.trim()] ?? name.split(/(\s+|-)/).map(w => w.length > 3 && w === w.toUpperCase() && w !== w.toLowerCase()
  ? w[0] + w.slice(1).toLowerCase() : w).join('');
const CAMP_COLOR: Record<string, string> = { government: '#5B9BFF', opposition: '#FF6B6B' };

/** Pasek gęstości tematu (panel designu 5.10): kiedy temat „wybuchł”; słupek dnia w kolorach obozów, klik przewija do dnia. */
function Density({ events }: { events: Node[] }) {
  const days = new Map<string, Record<string, number>>();
  for (const n of events) { const d = n.date ?? ''; const row = days.get(d) ?? {}; const k = n.camp && CAMP_COLOR[n.camp] ? n.camp : 'other'; row[k] = (row[k] ?? 0) + 1; days.set(d, row); }
  const keys = [...days.keys()].sort();
  if (keys.length < 2) return null;
  const max = Math.max(...keys.map(k => Object.values(days.get(k)!).reduce((a, b) => a + b, 0)));
  const w = 100 / keys.length;
  return <figure className="sc-tv__density" aria-label="Kiedy o temacie było najgłośniej">
    <svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label={`Aktywność w temacie od ${keys[0]} do ${keys[keys.length - 1]}`}>
      {keys.map((k, i) => { let y = 40; const row = days.get(k)!;
        return <g key={k} className="sc-tv__dday" onClick={() => document.getElementById(`d-${k}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>
          <title>{`${k}: ${Object.values(row).reduce((a, b) => a + b, 0)}`}</title>
          <rect x={i * w} y={0} width={w} height={40} fill="transparent" />
          {(['government', 'opposition', 'other'] as const).filter(c => row[c]).map(c => { const h = (36 * row[c]) / max; y -= h;
            return <rect key={c} x={i * w + w * .15} y={y} width={w * .7} height={h} fill={CAMP_COLOR[c] ?? 'currentColor'} opacity={c === 'other' ? .35 : .85} />; })}
        </g>; })}
    </svg>
    <figcaption><span>{keys[0]}</span><span>niebieski: rządzący · czerwony: opozycja · szary: media i dokumenty</span><span>{keys[keys.length - 1]}</span></figcaption>
  </figure>;
}

function TopicView({ data, busy = false, daily = false }: { data: Graph; busy?: boolean; daily?: boolean }) {
  const [more, setMore] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [hot, setHot] = useState<string | null>(null);
  const [full, setFull] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState<string | null>(null);
  const [allPeople, setAllPeople] = useState(false);
  const byId = useMemo(() => new Map(data.nodes.map(n => [n.id, n])), [data]);
  // panel osoby albo wpisu (właściciel 6.10: „nie można wejść w nic, tylko odnosi do źródła”)
  const [panel, setPanel] = useState<{ kind: 'person' | 'entry'; id: string } | null>(null);
  useEffect(() => { const p = new URLSearchParams(window.location.search);
    const o = p.get('osoba'), w = p.get('wpis'); if (o) setPanel({ kind: 'person', id: o }); else if (w) setPanel({ kind: 'entry', id: w });
    else { const q = data.topic.trim().toLowerCase(); const hit = data.nodes.find(n => n.kind === 'person' && !n.institution && n.label.toLowerCase() === q);
      if (hit) setPanel({ kind: 'person', id: hit.id }); } }, [data.topic]); // eslint-disable-line react-hooks/exhaustive-deps
  const openPanel = (next: { kind: 'person' | 'entry'; id: string } | null) => {
    setPanel(next); const p = new URLSearchParams(window.location.search); p.delete('osoba'); p.delete('wpis');
    if (next) p.set(next.kind === 'person' ? 'osoba' : 'wpis', next.id);
    window.history.replaceState(null, '', `?${p.toString()}`); };
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
  const allEvents = data.nodes.filter(n => n.date && (n.kind === 'statement' || n.kind === 'record' || n.kind === 'media'))
    .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''));
  // filtry osi czasu (funkcja z mapy): obóz, rodzaj, tylko z diagnozą, okres
  const [kindFilter, setKindFilter] = useState('all');
  const [period, setPeriod] = useState('all');
  const since = period === 'all' ? '' : new Date(Date.now() - Number(period) * 864e5).toISOString().slice(0, 10);
  const events = allEvents.filter(n => (!since || (n.date ?? '') >= since) && (kindFilter === 'all' || (kindFilter === 'government' || kindFilter === 'opposition' ? n.camp === kindFilter
    : kindFilter === 'diag' ? diagnosisOf.has(n.id) : n.kind === kindFilter)));
  const shown = more ? events : events.slice(0, 10);
  // osoby najpierw, instytucje i konta partii po nich (audyt 6.10: instytucja to nie osoba)
  const people = data.nodes.filter(n => n.kind === 'person').sort((a, b) => Number(Boolean(a.institution)) - Number(Boolean(b.institution)) || b.links - a.links);
  const media = new Map<string, number>();
  for (const n of data.nodes) if (n.kind === 'media' && n.sub) media.set(n.sub, (media.get(n.sub) ?? 0) + 1);
  const mediaRows = [...media.entries()].sort((a, b) => b[1] - a[1]);
  const mediaTotal = mediaRows.reduce((sum, [, n]) => sum + n, 0);
  if (!data.nodes.length) return <p className="sc-pt__msg">Nic nie znaleźliśmy. Spróbuj innego słowa.</p>;
  let lastDay = '';
  return <div className="sc-tv" data-busy={busy || undefined} data-hot={hot ? '' : undefined}>
    <header className="sc-tv__head">
      <h2>{data.topic}</h2>
      <p>{daily ? 'Temat dnia · ' : ''}{([['statement', 'wpis polityka', 'wpisy polityków', 'wpisów polityków'], ['diagnosis', 'diagnoza Dr. Spina', 'diagnozy Dr. Spina', 'diagnoz Dr. Spina'],
        ['vote', 'głosowanie', 'głosowania', 'głosowań'], ['record', 'dokument Sejmu', 'dokumenty Sejmu', 'dokumentów Sejmu'], ['media', 'artykuł', 'artykuły', 'artykułów'],
        ['person', 'osoba lub instytucja', 'osoby i instytucje', 'osób i instytucji']] as const)
        .filter(([k]) => data.counts[k]).map(([k, one, few, many]) => { const n = data.counts[k]; const w = n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many; return `${n} ${w}`; }).join(' · ')}</p>
      <Export data={data} author={author} />
      <p className="sc-tv__follow"><a href={`/api/przeszlosc/rss/?q=${encodeURIComponent(data.topic)}`} target="_blank" rel="noopener noreferrer">Obserwuj temat (RSS)</a>
        <span>Nowe wpisy, dokumenty i artykuły trafią do Twojego czytnika lub poczty.</span></p>
    </header>
    <Brief data={data} events={allEvents} author={author} diagnosisOf={diagnosisOf} />
    <Density events={allEvents} />
    <TopicGraph data={data} byId={byId} onOpen={openPanel} />
    <div className="sc-tv__grid">
      <SejmPath data={data} />
      {Boolean(data.votes?.length) && <Votes votes={data.votes!} />}
      <section className="sc-tv__time" aria-label="Oś czasu">
        <h3>Oś czasu</h3>
        <div className="sc-tv__filters" role="group" aria-label="Filtry osi czasu">
          {([['all', 'Wszystko'], ['government', 'Rządzący'], ['opposition', 'Opozycja'], ['diag', 'Z diagnozą'], ['record', 'Sejm'], ['media', 'Media']] as const).map(([k, l]) =>
            <button key={k} type="button" aria-pressed={kindFilter === k} onClick={() => setKindFilter(k)}>{l}</button>)}
          <span className="sc-tv__fsep" aria-hidden="true" />
          {([['all', 'Cały okres'], ['30', '30 dni'], ['7', '7 dni']] as const).map(([k, l]) => <button key={k} type="button" aria-pressed={period === k} onClick={() => setPeriod(k)}>{l}</button>)}
        </div>
        {!events.length && <p className="sc-tv__note">Nic w tym filtrze. Zmień obóz, rodzaj albo okres.</p>}
        <ol>{shown.map(n => {
          const day = n.date ?? '';
          const head = day !== lastDay ? <li className="sc-tv__day" id={`d-${day}`} key={`d${day}`}>{new Date(day).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })}</li> : null;
          lastDay = day;
          const who = author.get(n.id);
          const dg = diagnosisOf.get(n.id);
          const kind = n.kind === 'statement' ? '' : `${KIND_LABEL[n.kind]}${n.kind === 'record' && n.sub ? ` · ${SUB[n.sub] ?? n.sub}` : ''}${n.kind === 'media' && n.sub ? ` · ${n.sub}` : ''}`;
          const cite = `„${n.text ?? n.label}” (${who ? nice(who.label) : (n.sub ?? KIND_LABEL[n.kind])}${who?.role ? `, ${who.role}` : ''}, ${n.date ?? ''}). Źródło: ${n.url ?? ''}. Zestawienie: przeszłość.today, ${typeof window === 'undefined' ? '' : window.location.origin}/przeszlosc?q=${encodeURIComponent(data.topic)}&wpis=${encodeURIComponent(n.id)}`;
          return [head, <li key={n.id} className="sc-tv__item" data-kind={n.kind} data-camp={n.camp || undefined}
            data-on={hot && who?.id === hot ? '' : undefined} data-copied={copied === n.id || undefined}>
            <span className="sc-tv__who"><span>{who ? <button type="button" className="sc-tv__pbtn" onClick={() => openPanel({ kind: 'person', id: who.id })}>{nice(who.label)}</button> : (n.kind === 'media' ? n.sub : KIND_LABEL[n.kind])}{n.camp && CAMP_LABEL[n.camp] ? <em> · {CAMP_LABEL[n.camp]}</em> : null}</span>{kind && <small>{kind}</small>}</span>
            <p data-full={full.has(n.id) || undefined}>{n.text ?? n.label}</p>
            {who && <span className="sc-tv__twig" aria-label="Powiązania wpisu"><i>{nice(who.label)}</i><i>wpis</i>{dg && <i data-dg>spin {dg.intensity}/100</i>}
              {(roles.get(who.id)?.length ?? 0) > 0 && <i>KRS: {roles.get(who.id)!.length}</i>}</span>}
            <span className="sc-tv__links">
              {dg && <button type="button" className="sc-tv__open" onClick={() => openPanel({ kind: 'entry', id: n.id })}>Diagnoza Dr. Spina: spin {dg.intensity}/100 →</button>}
              <button type="button" className="sc-tv__open" onClick={() => openPanel({ kind: 'entry', id: n.id })}>Więcej →</button>
              {n.url && <a href={n.url} target="_blank" rel="noopener noreferrer" aria-label={`źródło: ${who ? nice(who.label) : (n.sub ?? KIND_LABEL[n.kind])}, ${n.date ?? ''}`}>źródło →</a>}
              {n.url && <a href={`https://web.archive.org/web/*/${n.url}`} target="_blank" rel="noopener noreferrer" className="sc-tv__arch">archiwum</a>}
              <button type="button" className="sc-tv__cite" onClick={() => { void navigator.clipboard?.writeText(cite).catch(() => undefined); setCopied(n.id); setTimeout(() => setCopied(c => (c === n.id ? null : c)), 1400); }}
                aria-label="Kopiuj przypis">{copied === n.id ? 'skopiowano ✓' : 'cytuj'}</button>
            </span>
          </li>];
        })}</ol>
        {events.length > 10 && <button type="button" className="sc-tv__more" onClick={() => setMore(!more)}>{more ? 'Pokaż mniej' : `Pokaż wszystko (${events.length})`}</button>}
      </section>
      <aside className="sc-tv__side">
        <section aria-label="Kto występuje">
          <h3>Kto występuje</h3>
          <ul className="sc-tv__people" data-all={allPeople || undefined}>{people.slice(0, 16).map(p => {
            const r = roles.get(p.id) ?? [];
            return <li key={p.id} data-camp={p.camp || undefined} data-inst={p.institution || undefined} onMouseEnter={() => setHot(p.id)} onMouseLeave={() => setHot(null)}
              onFocus={() => setHot(p.id)} onBlur={() => setHot(null)}>
              <span className="sc-tv__pname"><button type="button" className="sc-tv__pbtn" onClick={() => openPanel({ kind: 'person', id: p.id })}>{nice(p.label)}</button><small title="wystąpień w temacie">{p.links}×</small></span>
              {p.role && <span className="sc-tv__prole">{p.role}</span>}
              {r.length > 0 && <button type="button" onClick={() => setOpen(open === p.id ? null : p.id)} aria-expanded={open === p.id}>Funkcje w KRS ({r.length})</button>}
              {open === p.id && <ul className="sc-tv__krs">{r.map(({ org, role }) => <li key={org.id}><a href={org.url} target="_blank" rel="noopener noreferrer">{org.label}</a> <span>{role}</span></li>)}</ul>}
            </li>;
          })}</ul>
          {people.length > 6 && <button type="button" className="sc-tv__more sc-tv__more--people" onClick={() => setAllPeople(!allPeople)}>{allPeople ? 'Pokaż mniej' : `Pokaż wszystkie osoby (${Math.min(people.length, 16)})`}</button>}
          <p className="sc-tv__note">Funkcje w KRS to kontekst osoby, nie dowód związku z tematem.</p>
        </section>
        {mediaTotal > 0 && <section aria-label="Źródła medialne">
          <h3>Źródła medialne w temacie</h3>
          <ul className="sc-tv__media">{mediaRows.slice(0, 8).map(([name, n]) => <li key={name}><span title={name}>{name}</span><i><b style={{ width: `${(100 * n) / mediaTotal}%` }} /></i><em>{n}</em></li>)}</ul>
          <p className="sc-tv__note">Pokazujemy, co jest w naszej bazie. Jeśli jedna redakcja przeważa, to informacja o bazie, nie o temacie.</p>
        </section>}
      </aside>
    </div>
    {panel && <Panel data={data} panel={panel} byId={byId} author={author} diagnosisOf={diagnosisOf} roles={roles} onOpen={openPanel} />}
  </div>;
}

/* Panel osoby i wpisu (właściciel 6.10): wejście „w głąb” bez wychodzenia do źródła. Dane osoby z rejestru spin.clinic
   (funkcje, KRS, historia stanowisk, głosowania, wpisy na X), diagnoza w środku wpisu. Esc zamyka, adres do udostępnienia. */
type Figure = { id: number; name: string; role_title: string; organisation: string; party?: string | null; evidence_url?: string; official_profile_url?: string;
  organisations?: { id: number; name: string; krs_number?: string; official_register_url?: string }[];
  employment_timeline?: { position: string; organisation: string; status: string; since?: string | null }[];
  votes?: { available: boolean; results: { date: string; topic: string; vote: string }[] };
  x_posts?: { available: boolean; results: { id: number; url: string; text: string; published_at: string }[] } };
type Diagnosis = { intensity: number; verdict_label: string; headline: string; summary: string; techniques?: { name: string; quote: string; explanation: string }[];
  claims?: { claim: string; assessment: string; explanation: string }[] };
const ASSESS: Record<string, string> = { true: 'prawdziwe', false: 'fałszywe', misleading: 'wprowadza w błąd', unverified: 'niezweryfikowane', partly_true: 'częściowo prawdziwe' };
const VOTE_PL: Record<string, string> = { YES: 'za', NO: 'przeciw', ABSTAIN: 'wstrzymał się', ABSENT: 'nieobecny', NO_VOTE: 'nieobecny' };
const day = (d?: string | null) => d ? new Date(d).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' }) : '';
function Panel({ data, panel, byId, author, diagnosisOf, roles, onOpen }: { data: Graph; panel: { kind: 'person' | 'entry'; id: string }; byId: Map<string, Node>;
  author: Map<string, Node>; diagnosisOf: Map<string, Node>; roles: Map<string, { org: Node; role: string }[]>; onOpen: (p: { kind: 'person' | 'entry'; id: string } | null) => void }) {
  const node = byId.get(panel.id);
  const [fig, setFig] = useState<Figure | null>(null);
  const [dg, setDg] = useState<Diagnosis | null>(null);
  const close = useRef<HTMLButtonElement>(null);
  const figureId = panel.kind === 'person' && panel.id.startsWith('figure:') ? panel.id.slice(7) : null;
  const diag = panel.kind === 'entry' ? diagnosisOf.get(panel.id) : undefined;
  useEffect(() => { setFig(null); if (figureId) fetch(`/api/public-figures/${figureId}/`).then(r => r.ok ? r.json() : null).then(setFig).catch(() => undefined); }, [figureId]);
  useEffect(() => { setDg(null); const id = diag?.id.split(':')[1]; if (id) fetch(`/api/clinic/spins/${id}/`).then(r => r.ok ? r.json() : null).then(setDg).catch(() => undefined); }, [diag?.id]);
  useEffect(() => { close.current?.focus(); const key = (e: KeyboardEvent) => { if (e.key === 'Escape') onOpen(null); };
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key); }, [panel.id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!node) return null;
  const entriesOf = (personId: string) => data.nodes.filter(n => author.get(n.id)?.id === personId).sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''));
  const who = panel.kind === 'entry' ? author.get(node.id) : node;
  const camp = (who ?? node).camp;
  return <div className="sc-ptp" role="dialog" aria-modal="true" aria-label={panel.kind === 'person' ? `Osoba: ${nice(node.label)}` : 'Wpis'}>
    <button type="button" className="sc-ptp__scrim" aria-label="Zamknij" tabIndex={-1} onClick={() => onOpen(null)} />
    <aside className="sc-ptp__box" data-camp={camp || undefined}>
      <header className="sc-ptp__head"><span className="sc-ptp__k">{panel.kind === 'person' ? 'Osoba w temacie' : node.kind === 'statement' ? 'Wpis' : KIND_LABEL[node.kind]} · {data.topic}</span>
        <button ref={close} type="button" className="sc-ptp__x" onClick={() => onOpen(null)} aria-label="Zamknij">×</button></header>
      {panel.kind === 'person' ? <>
        <h2>{nice(fig?.name ?? node.label)}</h2>
        <p className="sc-ptp__sub">{[fig?.role_title ?? node.role, fig?.organisation, fig?.party, camp && CAMP_LABEL[camp]].filter(Boolean).join(' · ')}</p>
        <section><h3>Powiązania w temacie</h3><TopicGraph data={data} byId={byId} focus={node.id} onOpen={onOpen} compact /></section>
        <section><h3>W tym temacie ({entriesOf(node.id).length})</h3>
          <ol className="sc-ptp__list">{entriesOf(node.id).map(n => <li key={n.id}><button type="button" onClick={() => onOpen({ kind: 'entry', id: n.id })}>
            <time>{day(n.date)}</time><span>{n.label}</span>{diagnosisOf.get(n.id) && <em>spin {diagnosisOf.get(n.id)!.intensity}/100</em>}</button></li>)}</ol></section>
        {Boolean((fig?.organisations?.length ?? 0) || roles.get(node.id)?.length) && <section><h3>Funkcje w KRS</h3>
          <ul className="sc-ptp__rows">{(fig?.organisations ?? roles.get(node.id)?.map(r => ({ id: r.org.id, name: r.org.label, official_register_url: r.org.url, krs_number: r.org.sub })) ?? []).map(o =>
            <li key={String(o.id)}><a href={o.official_register_url} target="_blank" rel="noopener noreferrer">{o.name}</a><small>{o.krs_number && !String(o.krs_number).startsWith('KRS') ? `KRS ${o.krs_number}` : o.krs_number}</small></li>)}</ul>
          <p className="sc-ptp__note">Funkcje w KRS to kontekst osoby, nie dowód związku z tematem.</p></section>}
        {Boolean(fig?.employment_timeline?.length) && <section><h3>Stanowiska</h3>
          <ul className="sc-ptp__rows">{fig!.employment_timeline!.slice(0, 6).map((r, i) => <li key={i}><span>{r.position}</span><small>{[r.organisation, r.status === 'current' ? 'obecnie' : 'wcześniej'].filter(Boolean).join(' · ')}</small></li>)}</ul></section>}
        {fig?.votes?.available && fig.votes.results.length > 0 && <section><h3>Ostatnie głosowania</h3>
          <ul className="sc-ptp__rows">{fig.votes.results.slice(0, 8).map((v, i) => <li key={i}><span>{v.topic}</span><small>{day(v.date)} · <b data-v={VOTE_PL[v.vote] ?? v.vote}>{VOTE_PL[v.vote] ?? v.vote}</b></small></li>)}</ul></section>}
        {fig?.x_posts?.available && fig.x_posts.results.length > 0 && <section><h3>Ostatnie wpisy na X</h3>
          <ul className="sc-ptp__rows">{fig.x_posts.results.slice(0, 5).map(p => <li key={p.id}><span>{p.text}</span><small>{day(p.published_at)} · <a href={p.url} target="_blank" rel="noopener noreferrer">na X →</a></small></li>)}</ul></section>}
        <footer className="sc-ptp__foot">{(fig?.official_profile_url || node.url) && <a href={fig?.official_profile_url || node.url} target="_blank" rel="noopener noreferrer">Oficjalny profil →</a>}
          {fig?.evidence_url && <a href={fig.evidence_url} target="_blank" rel="noopener noreferrer">Źródło funkcji →</a>}
          {figureId && <a href={`https://spin.clinic/osoby-publiczne/${figureId}`} target="_blank" rel="noopener noreferrer">Pełna karta w spin.clinic →</a>}</footer>
      </> : <>
        <p className="sc-ptp__by">{who ? <button type="button" className="sc-tv__pbtn" onClick={() => onOpen({ kind: 'person', id: who.id })}>{nice(who.label)}</button> : node.sub}
          {camp && CAMP_LABEL[camp] ? <em> · {CAMP_LABEL[camp]}</em> : null}<time> · {day(node.date)}</time></p>
        <blockquote className="sc-ptp__text">{node.text ?? node.label}</blockquote>
        {diag && <section className="sc-ptp__dg"><h3>Diagnoza Dr. Spina</h3>
          {!dg ? <p className="sc-ptp__note">Wczytuję diagnozę…</p> : <>
            <p className="sc-ptp__score"><b data-hi={dg.intensity >= 70 || undefined}>{dg.intensity}</b><small>/100 · {dg.verdict_label}</small></p>
            <p className="sc-ptp__dgh">{dg.headline}</p><p>{dg.summary}</p>
            {Boolean(dg.techniques?.length) && <><h4>Chwyty</h4><ul className="sc-ptp__rows">{dg.techniques!.map((t, i) => <li key={i}><span>{t.name}</span><small>„{t.quote}”</small></li>)}</ul></>}
            {Boolean(dg.claims?.length) && <><h4>Sprawdzone zdania</h4><ul className="sc-ptp__rows">{dg.claims!.map((c, i) => <li key={i}><span>{c.claim}</span><small>{ASSESS[c.assessment] ?? c.assessment}</small></li>)}</ul></>}
          </>}</section>}
        {who && entriesOf(who.id).length > 1 && <section><h3>Inne wpisy tej osoby w temacie</h3>
          <ol className="sc-ptp__list">{entriesOf(who.id).filter(n => n.id !== node.id).slice(0, 6).map(n => <li key={n.id}><button type="button" onClick={() => onOpen({ kind: 'entry', id: n.id })}>
            <time>{day(n.date)}</time><span>{n.label}</span></button></li>)}</ol></section>}
        <footer className="sc-ptp__foot">{diag && <a href={diag.url} target="_blank" rel="noopener noreferrer">Pełna diagnoza w spin.clinic →</a>}
          {node.url && <a href={node.url} target="_blank" rel="noopener noreferrer">Źródło →</a>}
          {node.url && <a href={`https://web.archive.org/web/*/${node.url}`} target="_blank" rel="noopener noreferrer">Kopie w archiwum →</a>}
          {node.url && <a href={`https://web.archive.org/save/${node.url}`} target="_blank" rel="noopener noreferrer">Zapisz kopię teraz →</a>}</footer>
      </>}
    </aside>
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
    data: n.date ?? '', rodzaj: KIND_EXPORT[n.kind] ?? n.kind, tresc: n.text ?? n.label, autor: author.get(n.id)?.label ?? '',
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

/* Drzewo powiązań (właściciel 6.10: „nie widać drzew powiązań na żadnym elemencie”): trzy kolumny - osoby, ich wpisy,
   dokumenty i artykuły, a z prawej diagnozy i funkcje w KRS; linie pokazują, co z czego wynika. Najechanie podświetla
   całą gałąź, kliknięcie otwiera osobę albo wpis. W panelu osoby to samo drzewo zawężone do niej. */
const TG_MID = new Set(['statement', 'record', 'media', 'vote']);
function TopicGraph({ data, byId, focus, onOpen, compact = false }: { data: Graph; byId: Map<string, Node>; focus?: string; compact?: boolean;
  onOpen: (p: { kind: 'person' | 'entry'; id: string } | null) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [paths, setPaths] = useState<{ id: string; d: string; s: string; t: string; ctx?: boolean }[]>([]);
  const [hot, setHot] = useState<string | null>(null);
  const model = useMemo(() => {
    const persons = focus ? [byId.get(focus)].filter(Boolean) as Node[] : data.nodes.filter(n => n.kind === 'person').sort((a, b) => b.links - a.links).slice(0, 8);
    const pid = new Set(persons.map(p => p.id));
    const midIds = new Set<string>();
    for (const e of data.edges) if (pid.has(e.source) && TG_MID.has(byId.get(e.target)?.kind ?? '')) midIds.add(e.target);
    const mid = [...midIds].map(id => byId.get(id)!).sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '')).slice(0, compact ? 6 : 9);
    const midSet = new Set(mid.map(n => n.id));
    const rightIds = new Set<string>();
    for (const e of data.edges) {
      const t = byId.get(e.target)?.kind;
      if ((midSet.has(e.source) && t === 'diagnosis') || (pid.has(e.source) && t === 'organisation')) rightIds.add(e.target);
    }
    const right = [...rightIds].map(id => byId.get(id)!).sort((a, b) => (a.kind === b.kind ? b.links - a.links : a.kind === 'diagnosis' ? -1 : 1)).slice(0, compact ? 6 : 9);
    const rightSet = new Set(right.map(n => n.id));
    const edges = data.edges.filter(e => (pid.has(e.source) && (midSet.has(e.target) || rightSet.has(e.target))) || (midSet.has(e.source) && rightSet.has(e.target)));
    return { persons, mid, right, edges };
  }, [data, byId, focus, compact]);
  const lit = useMemo(() => {
    if (!hot) return null;
    const on = new Set([hot]);
    for (let i = 0; i < 2; i++) for (const e of model.edges) { if (on.has(e.source)) on.add(e.target); if (on.has(e.target)) on.add(e.source); }
    return on;
  }, [hot, model]);
  useEffect(() => {
    const root = wrap.current; if (!root) return;
    const draw = () => {
      const box = root.getBoundingClientRect();
      const at = (id: string) => root.querySelector<HTMLElement>(`[data-g="${CSS.escape(id)}"]`)?.getBoundingClientRect();
      setPaths(model.edges.flatMap((e, i) => { const a = at(e.source), b = at(e.target); if (!a || !b) return [];
        const x1 = a.right - box.left, y1 = a.top + a.height / 2 - box.top, x2 = b.left - box.left, y2 = b.top + b.height / 2 - box.top, k = (x2 - x1) * .5;
        return [{ id: `${i}`, s: e.source, t: e.target, ctx: byId.get(e.target)?.kind === 'organisation', d: `M${x1},${y1} C${x1 + k},${y1} ${x2 - k},${y2} ${x2},${y2}` }]; }));
    };
    draw(); const ro = new ResizeObserver(draw); ro.observe(root); return () => ro.disconnect();
  }, [model, byId]);
  if (!model.persons.length || !model.mid.length) return null;
  const open = (n: Node) => {
    if (n.kind === 'person') onOpen({ kind: 'person', id: n.id });
    else if (n.kind === 'vote') { if (n.url) window.open(n.url, '_blank', 'noopener'); }
    else if (TG_MID.has(n.kind)) onOpen({ kind: 'entry', id: n.id });
    else if (n.kind === 'diagnosis') { const src = data.edges.find(e => e.target === n.id)?.source; if (src) onOpen({ kind: 'entry', id: src }); }
    else if (n.url) window.open(n.url, '_blank', 'noopener');
  };
  const item = (n: Node) => <li key={n.id}><button type="button" data-g={n.id} data-kind={n.kind} data-camp={n.camp || undefined}
    data-dim={lit && !lit.has(n.id) ? '' : undefined} onMouseEnter={() => setHot(n.id)} onMouseLeave={() => setHot(null)} onFocus={() => setHot(n.id)} onBlur={() => setHot(null)} onClick={() => open(n)}>
    {n.kind === 'person' ? <b>{nice(n.label)}</b> : n.kind === 'diagnosis' ? <><b>Spin {n.intensity}/100</b><span>{n.label}</span></>
      : n.kind === 'organisation' ? <><b>{n.label}</b><span>{n.sub}</span></> : <><small>{day(n.date)}{n.kind !== 'statement' ? ` · ${KIND_LABEL[n.kind]}` : ''}</small><span>{n.label}</span></>}
  </button></li>;
  return <figure className={`sc-tg${compact ? ' sc-tg--compact' : ''}`} aria-label="Drzewo powiązań">
    {!compact && <figcaption className="sc-tg__head"><h3>Drzewo powiązań</h3><span>osoby → wpisy, dokumenty i artykuły → diagnozy i funkcje w KRS</span></figcaption>}
    <div className="sc-tg__scroll"><div className="sc-tg__wrap" ref={wrap}>
      <svg className="sc-tg__lines" aria-hidden="true">{paths.map(p => <path key={p.id} d={p.d} data-ctx={p.ctx || undefined} data-on={lit && lit.has(p.s) && lit.has(p.t) ? '' : undefined} data-dim={lit && !(lit.has(p.s) && lit.has(p.t)) ? '' : undefined} />)}</svg>
      <ol className="sc-tg__col">{model.persons.map(item)}</ol>
      <ol className="sc-tg__col">{model.mid.map(item)}</ol>
      <ol className="sc-tg__col">{model.right.map(item)}</ol>
    </div></div>
  </figure>;
}

/* Ścieżka w Sejmie (funkcja z mapy): druki, konsultacje i głosowania w temacie po kolei, od najstarszego. */
function SejmPath({ data }: { data: Graph }) {
  const steps = [
    ...data.nodes.filter(n => n.kind === 'record' && n.date).map(n => ({ id: n.id, date: n.date!, kind: n.sub ? (SUB[n.sub] ?? n.sub) : 'dokument', title: n.label, url: n.url })),
    ...(data.votes ?? []).filter(v => v.date).map(v => ({ id: v.id, date: v.date!, kind: 'głosowanie', title: `${v.title}${v.result.yes != null ? ` (za ${v.result.yes}, przeciw ${v.result.no ?? 0})` : ''}`, url: v.url })),
  ].sort((a, b) => a.date.localeCompare(b.date));
  if (steps.length < 2) return null;
  return <section className="sc-tv__path" aria-label="Ścieżka w Sejmie"><h3>Ścieżka w Sejmie</h3>
    <ol>{steps.slice(-10).map(s => <li key={s.id} data-kind={s.kind}><time>{day(s.date)}</time><b>{s.kind}</b>
      {s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a> : <span>{s.title}</span>}</li>)}</ol></section>;
}


/* Temat w 30 sekund (audyt 6.10): streszczenie liczone z danych, bez AI - kiedy wybuchł, kto mówi najwięcej (obie strony),
   ile Sejmu i jaka średnia siła spinu. Każda liczba wynika z listy poniżej. */
function Brief({ data, events, author, diagnosisOf }: { data: Graph; events: Node[]; author: Map<string, Node>; diagnosisOf: Map<string, Node> }) {
  if (events.length < 3) return null;
  const byDay = new Map<string, number>(); for (const n of events) if (n.date) byDay.set(n.date, (byDay.get(n.date) ?? 0) + 1);
  const peak = [...byDay.entries()].sort((a, b) => b[1] - a[1])[0];
  const speakers = new Map<string, { n: number; who: Node }>();
  for (const n of events) { const w = author.get(n.id); if (w && !w.institution) speakers.set(w.id, { n: (speakers.get(w.id)?.n ?? 0) + 1, who: w }); }
  const top = (camp: string) => [...speakers.values()].filter(x => x.who.camp === camp).sort((a, b) => b.n - a.n)[0];
  const gov = top('government'), opp = top('opposition');
  const spins = [...diagnosisOf.values()].map(d => d.intensity ?? 0); const avg = spins.length ? Math.round(spins.reduce((a, b) => a + b, 0) / spins.length) : null;
  const first = [...events].sort((a, b) => (a.date ?? '').localeCompare(b.date ?? ''))[0];
  const parts = [
    `Najgłośniej było ${day(peak[0])} (${peak[1]} ${peak[1] === 1 ? 'pozycja' : peak[1] % 10 >= 2 && peak[1] % 10 <= 4 && (peak[1] % 100 < 10 || peak[1] % 100 >= 20) ? 'pozycje' : 'pozycji'}), pierwszy ślad ${day(first.date)}.`,
    gov || opp ? `Najczęściej mówią: ${[gov && `${nice(gov.who.label)} (rządzący, ${gov.n})`, opp && `${nice(opp.who.label)} (opozycja, ${opp.n})`].filter(Boolean).join(' i ')}.` : '',
    data.counts.record || data.counts.vote ? `W Sejmie: ${data.counts.record ?? 0} dokumentów i ${data.counts.vote ?? 0} głosowań.` : 'Sejm: brak dokumentów w tym temacie w naszej bazie.',
    avg !== null ? `Średnia siła spinu w ${spins.length} diagnozach Dr. Spina: ${avg}/100.` : '',
  ].filter(Boolean);
  return <p className="sc-tv__brief"><b>W 30 sekund:</b> {parts.join(' ')}</p>;
}
