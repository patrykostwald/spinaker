"use client";
import { useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from 'react';
import { Loading } from '@spin-clinic/ui/kit';

/**
 * przeszłość.today (właściciel 5.10, nowy wygląd 6.10): strona produktu i narzędzie w jednym.
 * Góra: hasło, wyszukiwarka i mała grafika „co dostajesz”; pod nią liczby z bazy. Wynik tematu: streszczenie, wykres,
 * drzewo powiązań jako środek strony, oś czasu i „Kto występuje”. Na dole: jak to działa, zasady, Sejm, dla redakcji.
 * Bez kolorów obozów (właściciel 6.10): obóz tylko słowem. Jeden akcent, siła spinu w skali zielony < niebieski < czerwony.
 */
type Node = { id: string; kind: string; label: string; text?: string; institution?: boolean; date?: string | null; url?: string; sub?: string; role?: string; camp?: string; intensity?: number; links: number };
type Edge = { source: string; target: string; label: string };
type Start = { counts: Record<string, number>; latest: { title: string; date: string | null; kind: string; url: string }[]; topics_enabled: boolean; auto_topics?: { topic: string; edges: number }[] };
type Vote = { id: string; title: string; motion: string; date: string | null; kind: string; result: Record<string, number>; url: string;
  clubs: { club: string; size: number; votes: Record<string, number> }[]; members: [string, string, string][] };
type Graph = { topic: string; terms: string[]; nodes: Node[]; edges: Edge[]; counts: Record<string, number>; votes?: Vote[] };
type Open = (p: { kind: 'person' | 'entry'; id: string } | null) => void;

const SUB: Record<string, string> = { print: 'druk', ballot: 'głosowanie', voting: 'głosowanie', consultation: 'konsultacje', lobby_activity: 'lobbing', lobby_document: 'lobbing', financial_document: 'finanse', financial_row: 'finanse' };
const EXAMPLES = ['CPK', 'ceny energii', 'Turów', 'KPO'];
const KIND_LABEL: Record<string, string> = { record: 'Sejm', statement: 'Wpis', diagnosis: 'Diagnoza Dr. Spina', media: 'Media', vote: 'Głosowanie', organisation: 'Spółka z KRS', person: 'Osoba' };
const CAMP_LABEL: Record<string, string> = { government: 'rządzący', opposition: 'opozycja', public: 'instytucja' };

/** Polska typografia (zasada właściciela): jednoliterowe słowa nie zostają na końcu wiersza. */
const nb = (text: string) => text.replace(/(^|[\s(])([aiouwzAIOUWZ])\s+/g, '$1$2 ');
const plural = (n: number, one: string, few: string, many: string) => n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many;
const day = (d?: string | null) => d ? new Date(d).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' }) : '';
const short = (d?: string | null) => d ? new Date(d).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' }) : '';
const spinColor = (v = 0) => v >= 70 ? 'var(--sc-spin-hi)' : v >= 40 ? 'var(--sc-spin-mid)' : 'var(--sc-spin-lo)';
const reduced = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// skróty kont instytucji pełną nazwą (panel designu 5.10: „ME” nic nie mówi czytelnikowi); NAZWISKA wielkimi literami jak zwykłe
const INSTITUTIONS: Record<string, string> = { ME: 'Ministerstwo Energii', MF: 'Ministerstwo Finansów', MON: 'Ministerstwo Obrony Narodowej', MZ: 'Ministerstwo Zdrowia',
  MSZ: 'Ministerstwo Spraw Zagranicznych', MSWiA: 'Ministerstwo Spraw Wewnętrznych i Administracji', KPRM: 'Kancelaria Prezesa Rady Ministrów', MEN: 'Ministerstwo Edukacji Narodowej' };
const nice = (name: string) => INSTITUTIONS[name.trim()] ?? name.split(/(\s+|-)/).map(w => w.length > 3 && w === w.toUpperCase() && w !== w.toLowerCase()
  ? w[0] + w.slice(1).toLowerCase() : w).join('');

/* Ikony rodzajów (jedna linia 1,7 px, ten sam styl wszędzie) */
const ICON: Record<string, string> = {
  person: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM5 20a7 7 0 0 1 14 0',
  institution: 'M3 10l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18',
  statement: 'M4 5h16v11H9l-5 4V5Z',
  record: 'M7 3h7l4 4v14H7V3Zm7 0v4h4M10 12h5M10 16h5',
  media: 'M4 5h13v14H6a2 2 0 0 1-2-2V5Zm13 4h3v8a2 2 0 0 1-2 2M8 9h5M8 13h5',
  diagnosis: 'M3 12h4l2-5 4 10 2-5h6',
  organisation: 'M4 21V8l8-5 8 5v13M9 21v-5h6v5M9 11h.01M15 11h.01',
  vote: 'M5 12l4 4 10-10',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm5-2 5 5',
  rss: 'M5 11a8 8 0 0 1 8 8M5 5a14 14 0 0 1 14 14M6 19h.01',
  down: 'M12 4v12m-5-5 5 5 5-5M5 20h14',
};
function Icon({ name, size = 16 }: { name: string; size?: number }) {
  return <svg className="px-ic" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth={1.7}
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={ICON[name] ?? ICON.statement} /></svg>;
}
const iconOf = (n: Node) => n.kind === 'person' && n.institution ? 'institution' : n.kind;

/* Linie drzewa liczone z położenia elementów (data-g). Element po prawej: łagodna krzywa; element niżej i z wcięciem: „kolanko”
   jak w drzewie katalogów (telefon i panel). Przeliczane przy każdej zmianie rozmiaru. */
type Link = { id: string; d: string; s: string; t: string; ctx?: boolean; step: number };
function useLinks(root: RefObject<HTMLElement | null>, edges: { source: string; target: string; ctx?: boolean; step?: number }[], elbow = 22) {
  const [paths, setPaths] = useState<Link[]>([]);
  useEffect(() => {
    const el = root.current; if (!el) return;
    const draw = () => {
      const box = el.getBoundingClientRect(); if (!box.width) return;
      const at = (id: string) => el.querySelector<HTMLElement>(`[data-g="${CSS.escape(id)}"]`)?.getBoundingClientRect();
      setPaths(edges.flatMap((e, i) => {
        const a = at(e.source), b = at(e.target); if (!a?.width || !b?.width) return [];
        const x1 = a.right - box.left, y1 = a.top + a.height / 2 - box.top, x2 = b.left - box.left, y2 = b.top + b.height / 2 - box.top;
        let d: string;
        if (b.left >= a.right - 2) { const k = (x2 - x1) * .55; d = `M${x1},${y1} C${x1 + k},${y1} ${x2 - k},${y2} ${x2},${y2}`; }
        else { const x = a.left - box.left + elbow, top = a.bottom - box.top, r = Math.min(10, Math.max(0, y2 - top)); d = `M${x},${top} V${y2 - r} Q${x},${y2} ${x + r},${y2} H${x2}`; }
        return [{ id: `${e.source}>${e.target}>${i}`, s: e.source, t: e.target, ctx: e.ctx, step: e.step ?? 0, d }];
      }));
    };
    draw(); const ro = new ResizeObserver(draw); ro.observe(el); return () => ro.disconnect();
  }, [root, edges, elbow]);
  return paths;
}
function useNarrow(query = '(max-width: 760px)') {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => { const m = window.matchMedia(query); const on = () => setNarrow(m.matches); on(); m.addEventListener('change', on); return () => m.removeEventListener('change', on); }, [query]);
  return narrow;
}

export function TopicTree() {
  const [query, setQuery] = useState('');
  const [data, setData] = useState<Graph | null>(null);
  const [state, setState] = useState<'idle' | 'loading' | 'error' | 'off'>('idle');
  const [start, setStart] = useState<Start | null>(null);
  const [daily, setDaily] = useState(false);

  async function load(q: string, remember = true) {
    setState('loading');
    try {
      const response = await fetch(`/api/przeszlosc/temat/?q=${encodeURIComponent(q)}`);
      if (response.status === 404) { setState('off'); return; }
      if (!response.ok) throw new Error();
      setData(await response.json()); setState('idle'); setDaily(!remember);
      if (remember) {
        window.history.replaceState(null, '', `?q=${encodeURIComponent(q)}`);
        requestAnimationFrame(() => document.getElementById('wynik')?.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'start' }));
      }
    } catch { setState('error'); }
  }
  // osobna strona (przeszlosc.today): bez pasków i menu spin.clinic, własny nagłówek i stopka
  useEffect(() => {
    document.documentElement.dataset.standalone = '1';
    return () => { delete document.documentElement.dataset.standalone; };
  }, []);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('q');
    // strona główna od razu pokazuje stan bazy i temat dnia (właściciel 5.10: „wygląda, jakby nic nie było”)
    fetch('/api/przeszlosc/start/').then(r => r.ok ? r.json() : null).then((s: Start | null) => {
      setStart(s);
      const first = s?.auto_topics?.[0]?.topic ?? EXAMPLES[0];
      if (!q && s?.topics_enabled) { setQuery(first); void load(first, false); }
    }).catch(() => undefined);
    if (q) {
      setQuery(q);
      // wejście z linku: bez przewijania, ale z adresem jak był (osoba, wpis)
      setState('loading');
      fetch(`/api/przeszlosc/temat/?q=${encodeURIComponent(q)}`).then(async r => {
        if (r.status === 404) { setState('off'); return; } if (!r.ok) throw new Error();
        setData(await r.json()); setState('idle');
      }).catch(() => setState('error'));
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const topics = start?.auto_topics?.length ? start.auto_topics.map(t => t.topic) : EXAMPLES;
  const pick = (t: string) => { setQuery(t); void load(t); };

  return <main className="px">
    <nav className="px-bar" aria-label="Menu">
      <a href="/przeszlosc" className="px-mark">przeszłość<i>.</i>today</a>
      <span className="px-bar__links"><a href="#jak">Jak to działa</a><a href="#redakcje">Dla redakcji</a>
        <a href="https://spin.clinic" target="_blank" rel="noopener noreferrer">spin.clinic ↗</a></span>
    </nav>

    <header className="px-hero">
      <div className="px-hero__copy">
        <p className="px-kicker"><span className="px-dot" aria-hidden="true" />Beta · bezpłatnie · dane publiczne</p>
        <h1>Kto, co i&nbsp;kiedy w&nbsp;jednym temacie</h1>
        <p className="px-lead">{nb('Wpisz temat, a w kilka sekund zobaczysz, kto o nim mówi, co dokładnie powiedział, jak głosował Sejm i z jakimi spółkami są związani ci ludzie. Każda informacja prowadzi do oryginału.')}</p>
        <form className="px-search" role="search" onSubmit={event => { event.preventDefault(); if (query.trim().length >= 3) void load(query.trim()); }}>
          <Icon name="search" size={20} />
          <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Np. CPK, VAT, ceny energii" aria-label="Temat do sprawdzenia" enterKeyHint="search" />
          <button type="submit">Pokaż</button>
        </form>
        <div className="px-chips"><span>{start?.auto_topics?.length ? 'Tematy dnia' : 'Przykłady'}</span>
          {topics.slice(0, 6).map(t => <button key={t} type="button" aria-pressed={data?.topic === t} onClick={() => pick(t)}>{t}</button>)}</div>
      </div>
      <HeroDemo />
    </header>

    <section className="px-proof" aria-label="Co jest w bazie">
      {([['people', 'osób publicznych'], ['organisations', 'spółek i fundacji z KRS'], ['records', 'dokumentów Sejmu'], ['posts', 'wpisów polityków'], ['diagnoses', 'diagnoz Dr. Spina'], ['articles', 'artykułów z mediów']] as const)
        .map(([key, label]) => <div key={key}><b>{start ? (start.counts[key] ?? 0).toLocaleString('pl-PL') : ' '}</b><span>{nb(label)}</span></div>)}
    </section>

    <section className="px-result" id="wynik" aria-label="Wynik tematu" data-empty={!data || undefined}>
      {state === 'loading' && !data && <div className="px-wait"><Loading label="Ładowanie tematu" /></div>}
      {state === 'off' && <p className="px-msg">Podgląd jest jeszcze wyłączony na serwerze.</p>}
      {state === 'error' && <p className="px-msg" role="alert">Nie udało się pobrać tematu. Spróbuj ponownie.</p>}
      {data && (state === 'idle' || state === 'loading') && <TopicView key={data.topic} data={data} busy={state === 'loading'} daily={daily} />}
    </section>

    <section className="px-sec" id="jak" aria-labelledby="jak-h">
      <h2 id="jak-h" className="px-h2">Jak to działa</h2>
      <ol className="px-steps">
        {([['Wpisz temat', 'Albo kliknij jeden z tematów dnia. Wystarczy słowo, na przykład VAT, CPK, Turów.'],
          ['Zobacz kto, co i kiedy', 'Drzewo powiązań, oś czasu, głosowania w Sejmie i wykres, kiedy temat wybuchł.'],
          ['Kliknij osobę lub wpis', 'Diagnoza spinu, funkcje w KRS, źródło, kopia w archiwum i gotowy przypis do cytowania.']] as const)
          .map(([title, text], i) => <li key={title}><b aria-hidden="true">{i + 1}</b><h3>{title}</h3><p>{nb(text)}</p></li>)}
      </ol>
    </section>

    <section className="px-sec" aria-labelledby="zasady-h">
      <h2 id="zasady-h" className="px-h2">Zasady</h2>
      <ul className="px-rules">
        {([['person', 'Tylko osoby i podmioty publiczne', 'Politycy, urzędy, spółki i fundacje z KRS. Żadnych osób prywatnych.'],
          ['record', 'Każde powiązanie ma źródło', 'Oficjalne dane Sejmu i KRS, wpisy na X, artykuły. Nic nie łączymy po samym nazwisku.'],
          ['vote', 'Ta sama miara dla wszystkich', 'Rządzący i opozycja przechodzą przez identyczne zapytania i te same reguły.']] as const)
          .map(([icon, title, text]) => <li key={title}><span className="px-rules__ic"><Icon name={icon} size={20} /></span><h3>{title}</h3><p>{nb(text)}</p></li>)}
      </ul>
    </section>

    {start && start.latest.length > 0 && <section className="px-sec" aria-labelledby="sejm-h">
      <h2 id="sejm-h" className="px-h2">Najnowsze w&nbsp;Sejmie</h2>
      <ol className="px-latest">{start.latest.map((row, i) => <li key={i}>
        <time>{row.date ? short(row.date) : 'bez daty'}</time><span>{row.kind}</span>
        <a href={row.url} target="_blank" rel="noopener noreferrer">{row.title}</a></li>)}</ol>
    </section>}

    {/* ceny wyłączone na razie (właściciel 6.10); zostaje kontakt dla redakcji */}
    <section className="px-cta" id="redakcje" aria-labelledby="red-h">
      <div>
        <h2 id="red-h">Dla redakcji</h2>
        <p>{nb('W becie wszystko jest bezpłatne. Przygotowujemy narzędzia dla zespołów:')}</p>
        <ul><li>alerty o&nbsp;osobach i&nbsp;tematach</li><li>eksport do publikacji z&nbsp;przypisami</li><li>wspólne teczki tematów</li></ul>
      </div>
      <a className="px-btn" href="mailto:kontakt@spin.clinic?subject=przeszłość.today%20dla%20redakcji">Umów 15 minut prezentacji</a>
    </section>
    <footer className="px-foot"><span>przeszłość.today prowadzi iapply sp. z&nbsp;o.o. · dane wspólne ze spin.clinic</span>
      <a href="https://spin.clinic/polityka-prywatnosci">Prywatność</a></footer>
  </main>;
}

/* Mała grafika w nagłówku: rysuje się raz i pokazuje, co dostaje czytelnik (bez liczb, same rodzaje). */
const DEMO: { id: string; kind: string; title: string; text: string; depth: number }[] = [
  { id: 'd-p', kind: 'person', title: 'Osoba publiczna', text: 'poseł, minister, urząd', depth: 0 },
  { id: 'd-s', kind: 'statement', title: 'Co powiedziała', text: 'wpis na X, druk Sejmu, artykuł', depth: 1 },
  { id: 'd-d', kind: 'diagnosis', title: 'Diagnoza Dr. Spina', text: 'ocena manipulacji od 0 do 100', depth: 2 },
  { id: 'd-o', kind: 'organisation', title: 'Spółka lub fundacja (KRS)', text: 'gdzie zasiada: zarząd, rada', depth: 1 },
];
const DEMO_EDGES = [{ source: 'd-p', target: 'd-s', step: 1 }, { source: 'd-s', target: 'd-d', step: 2 }, { source: 'd-p', target: 'd-o', ctx: true, step: 3 }];
function HeroDemo() {
  const wrap = useRef<HTMLDivElement>(null);
  const paths = useLinks(wrap, DEMO_EDGES, 26);
  return <figure className="px-demo" aria-label="Przykład wyniku: osoba, jej wypowiedź, diagnoza spinu i funkcja w spółce z KRS">
    <figcaption className="px-demo__head"><span>Tak wygląda wynik</span><small>każda linia ma źródło</small></figcaption>
    <div className="px-demo__wrap" ref={wrap}>
      <svg className="px-lines" aria-hidden="true">{paths.map(p => <path key={p.id} d={p.d} pathLength={p.ctx ? undefined : 1} data-ctx={p.ctx || undefined} style={{ ['--i' as string]: p.step }} />)}</svg>
      {DEMO.map((n, i) => <div key={n.id} className="px-node px-demo__n" data-g={n.id} data-kind={n.kind} style={{ ['--i' as string]: i, ['--depth' as string]: n.depth }}>
        <span className="px-node__ic"><Icon name={n.kind} /></span>
        <span className="px-node__body"><b>{n.title}</b><small>{n.text}</small></span>
        {n.kind === 'diagnosis' && <i className="px-scale" aria-hidden="true" />}
      </div>)}
    </div>
  </figure>;
}

function TopicView({ data, busy = false, daily = false }: { data: Graph; busy?: boolean; daily?: boolean }) {
  const [more, setMore] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [hot, setHot] = useState<string | null>(null);
  const [full, setFull] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState<string | null>(null);
  const toggleFull = (id: string) => setFull(s => { const x = new Set(s); if (x.has(id)) x.delete(id); else x.add(id); return x; });
  const [allPeople, setAllPeople] = useState(false);
  const byId = useMemo(() => new Map(data.nodes.map(n => [n.id, n])), [data]);
  // panel osoby albo wpisu (właściciel 6.10: „nie można wejść w nic, tylko odnosi do źródła”)
  const [panel, setPanel] = useState<{ kind: 'person' | 'entry'; id: string } | null>(null);
  useEffect(() => { const p = new URLSearchParams(window.location.search);
    const o = p.get('osoba'), w = p.get('wpis'); if (o) setPanel({ kind: 'person', id: o }); else if (w) setPanel({ kind: 'entry', id: w });
    else { const q = data.topic.trim().toLowerCase(); const hit = data.nodes.find(n => n.kind === 'person' && !n.institution && n.label.toLowerCase() === q);
      if (hit) setPanel({ kind: 'person', id: hit.id }); } }, [data.topic]); // eslint-disable-line react-hooks/exhaustive-deps
  const openPanel: Open = next => {
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
  const allEvents = useMemo(() => data.nodes.filter(n => n.date && (n.kind === 'statement' || n.kind === 'record' || n.kind === 'media'))
    .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '')), [data]);
  // filtry osi czasu: obóz (słowem), rodzaj, tylko z diagnozą, okres
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
  const mediaMax = Math.max(1, ...mediaRows.map(([, n]) => n));
  if (!data.nodes.length) return <p className="px-msg">Nic nie znaleźliśmy. Spróbuj innego słowa.</p>;
  const counts = ([['statement', 'wpis polityka', 'wpisy polityków', 'wpisów polityków'], ['diagnosis', 'diagnoza Dr. Spina', 'diagnozy Dr. Spina', 'diagnoz Dr. Spina'],
    ['vote', 'głosowanie', 'głosowania', 'głosowań'], ['record', 'dokument Sejmu', 'dokumenty Sejmu', 'dokumentów Sejmu'], ['media', 'artykuł', 'artykuły', 'artykułów'],
    ['person', 'osoba lub instytucja', 'osoby i instytucje', 'osób i instytucji']] as const).filter(([k]) => data.counts[k]);
  let lastDay = '';
  return <div className="px-tv" data-busy={busy || undefined} data-hot={hot ? '' : undefined}>
    <header className="px-tv__head">
      <div>
        <p className="px-kicker">{daily ? 'Temat dnia' : 'Temat'}</p>
        <h2>{data.topic}</h2>
        <p className="px-tv__counts">{counts.map(([k, one, few, many]) => <span key={k}><b>{data.counts[k]}</b> {plural(data.counts[k], one, few, many)}</span>)}</p>
      </div>
      <div className="px-tv__tools">
        <a className="px-tool" href={`/api/przeszlosc/rss/?q=${encodeURIComponent(data.topic)}`} target="_blank" rel="noopener noreferrer"
          title="Kanał RSS: nowe wpisy, dokumenty i artykuły trafią do Twojego czytnika lub poczty"><Icon name="rss" />Obserwuj temat</a>
        <Export data={data} author={author} />
      </div>
    </header>

    <div className="px-sum">
      <Brief data={data} events={allEvents} author={author} diagnosisOf={diagnosisOf} onOpen={openPanel} />
      <Density events={allEvents} />
    </div>

    <TopicGraph data={data} byId={byId} onOpen={openPanel} />

    <div className="px-grid">
      <div className="px-main">
        <SejmPath data={data} />
        {Boolean(data.votes?.length) && <Votes votes={data.votes!} />}
        <section className="px-time" aria-labelledby="os-h">
          <div className="px-time__head"><h3 id="os-h" className="px-h3">Oś czasu</h3><span>{events.length} {plural(events.length, 'pozycja', 'pozycje', 'pozycji')}</span></div>
          <div className="px-filters">
            <div className="px-seg" role="group" aria-label="Rodzaj">
              {([['all', 'Wszystko'], ['government', 'Rządzący'], ['opposition', 'Opozycja'], ['diag', 'Z diagnozą'], ['record', 'Sejm'], ['media', 'Media']] as const).map(([k, l]) =>
                <button key={k} type="button" aria-pressed={kindFilter === k} onClick={() => { setKindFilter(k); setMore(false); }}>{l}</button>)}
            </div>
            <div className="px-seg" role="group" aria-label="Okres">
              {([['all', 'Cały okres'], ['30', '30 dni'], ['7', '7 dni']] as const).map(([k, l]) => <button key={k} type="button" aria-pressed={period === k} onClick={() => { setPeriod(k); setMore(false); }}>{l}</button>)}
            </div>
          </div>
          {!events.length && <p className="px-note">Nic w tym filtrze. Zmień rodzaj albo okres.</p>}
          <ol className="px-events">{shown.map(n => {
            const d = n.date ?? '';
            const head = d !== lastDay ? <li className="px-day" id={`d-${d}`} key={`d${d}`}>{day(d)}</li> : null;
            lastDay = d;
            const who = author.get(n.id);
            const dg = diagnosisOf.get(n.id);
            const source = n.kind === 'record' ? `Sejm${n.sub ? ` · ${SUB[n.sub] ?? n.sub}` : ''}` : n.kind === 'media' ? (n.sub ?? 'Media') : KIND_LABEL[n.kind];
            const cite = `„${n.text ?? n.label}” (${who ? nice(who.label) : (n.sub ?? KIND_LABEL[n.kind])}${who?.role ? `, ${who.role}` : ''}, ${n.date ?? ''}). Źródło: ${n.url ?? ''}. Zestawienie: przeszłość.today, ${window.location.origin}/przeszlosc?q=${encodeURIComponent(data.topic)}&wpis=${encodeURIComponent(n.id)}`;
            return [head, <li key={n.id} className="px-ev" data-kind={n.kind} data-on={hot && who?.id === hot ? '' : undefined} data-copied={copied === n.id || undefined}>
              <div className="px-ev__meta">
                <span className="px-ev__ic"><Icon name={who ? iconOf(who) : n.kind} /></span>
                {who ? <button type="button" className="px-name" onClick={() => openPanel({ kind: 'person', id: who.id })}>{nice(who.label)}</button> : <b>{source}</b>}
                {n.camp && CAMP_LABEL[n.camp] && <span className="px-ev__camp">{CAMP_LABEL[n.camp]}</span>}
                <time dateTime={d}>{short(d)}</time>
              </div>
              <p className="px-ev__text" data-full={full.has(n.id) || undefined} role="button" tabIndex={0} aria-expanded={full.has(n.id)} title="Kliknij, aby rozwinąć lub zwinąć"
                onClick={() => toggleFull(n.id)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleFull(n.id); } }}>{n.text ?? n.label}</p>
              <div className="px-ev__act">
                {dg ? <button type="button" className="px-link" onClick={() => openPanel({ kind: 'entry', id: n.id })}>
                  <i className="px-spin-dot" style={{ ['--spin' as string]: spinColor(dg.intensity) }} />Diagnoza Dr. Spina · spin {dg.intensity}/100 →</button>
                  : null}
                <span className="px-ev__quiet">
                  {<button type="button" className="px-quiet" onClick={() => openPanel({ kind: 'entry', id: n.id })}>szczegóły</button>}
                  {n.url && <a className="px-quiet" href={n.url} target="_blank" rel="noopener noreferrer" aria-label={`źródło: ${who ? nice(who.label) : source}, ${d}`}>źródło ↗</a>}
                  {n.url && <a className="px-quiet" href={`https://web.archive.org/web/*/${n.url}`} target="_blank" rel="noopener noreferrer">archiwum</a>}
                  <button type="button" className="px-quiet" aria-label="Kopiuj przypis do cytowania"
                    onClick={() => { void navigator.clipboard?.writeText(cite).catch(() => undefined); setCopied(n.id); setTimeout(() => setCopied(c => (c === n.id ? null : c)), 1400); }}>
                    {copied === n.id ? 'skopiowano ✓' : 'cytuj'}</button>
                </span>
              </div>
            </li>];
          })}</ol>
          {events.length > 10 && <button type="button" className="px-more" onClick={() => setMore(!more)}>{more ? 'Pokaż mniej' : `Pokaż wszystko (${events.length})`}</button>}
        </section>
      </div>
      <aside className="px-side">
        <section className="px-card" aria-labelledby="kto-h">
          <h3 id="kto-h" className="px-h3">Kto występuje</h3>
          <ul className="px-people" data-all={allPeople || undefined}>{people.slice(0, 16).map(p => {
            const r = roles.get(p.id) ?? [];
            return <li key={p.id} data-inst={p.institution || undefined} onPointerEnter={e => { if (e.pointerType === 'mouse') setHot(p.id); }} onPointerLeave={() => setHot(null)}>
              <span className="px-people__ic"><Icon name={iconOf(p)} /></span>
              <span className="px-people__body">
                <button type="button" className="px-name" onClick={() => openPanel({ kind: 'person', id: p.id })} onFocus={() => setHot(p.id)} onBlur={() => setHot(null)}>{nice(p.label)}</button>
                <small>{p.role || (p.institution ? 'instytucja' : CAMP_LABEL[p.camp ?? ''] ?? '')}</small>
                {r.length > 0 && <button type="button" className="px-krs-btn" onClick={() => setOpen(open === p.id ? null : p.id)} aria-expanded={open === p.id}>Funkcje w KRS ({r.length})</button>}
                {open === p.id && <ul className="px-krs">{r.map(({ org, role }) => <li key={org.id}><a href={org.url} target="_blank" rel="noopener noreferrer">{org.label}</a><span>{role}</span></li>)}</ul>}
              </span>
              <em title="wystąpień w temacie">{p.links}×</em>
            </li>;
          })}</ul>
          {people.length > 6 && <button type="button" className="px-more px-more--people" onClick={() => setAllPeople(!allPeople)}>{allPeople ? 'Pokaż mniej' : `Pokaż wszystkie (${Math.min(people.length, 16)})`}</button>}
          <p className="px-note">Funkcje w&nbsp;KRS to kontekst osoby, nie dowód związku z&nbsp;tematem.</p>
        </section>
        {mediaRows.length > 0 && <section className="px-card" aria-labelledby="media-h">
          <h3 id="media-h" className="px-h3">Źródła medialne</h3>
          <ul className="px-media">{mediaRows.slice(0, 8).map(([name, n]) => <li key={name}><span title={name}>{name}</span><i><b style={{ width: `${(100 * n) / mediaMax}%` }} /></i><em>{n}</em></li>)}</ul>
          <p className="px-note">{nb('Pokazujemy, co jest w naszej bazie. Przewaga jednej redakcji to informacja o bazie, nie o temacie.')}</p>
        </section>}
      </aside>
    </div>
    {panel && <Panel data={data} panel={panel} byId={byId} author={author} diagnosisOf={diagnosisOf} roles={roles} onOpen={openPanel} />}
  </div>;
}

/* Temat w 30 sekund (audyt 6.10): streszczenie liczone z danych, bez AI. Każda liczba wynika z listy poniżej. */
function Brief({ data, events, author, diagnosisOf, onOpen }: { data: Graph; events: Node[]; author: Map<string, Node>; diagnosisOf: Map<string, Node>; onOpen: Open }) {
  if (events.length < 3) return null;
  const byDay = new Map<string, number>(); for (const n of events) if (n.date) byDay.set(n.date, (byDay.get(n.date) ?? 0) + 1);
  const peak = [...byDay.entries()].sort((a, b) => b[1] - a[1])[0];
  const speakers = new Map<string, { n: number; who: Node }>();
  for (const n of events) { const w = author.get(n.id); if (w && !w.institution) speakers.set(w.id, { n: (speakers.get(w.id)?.n ?? 0) + 1, who: w }); }
  const top = (camp: string) => [...speakers.values()].filter(x => x.who.camp === camp).sort((a, b) => b.n - a.n)[0];
  const tops = [top('government'), top('opposition')].filter(Boolean) as { n: number; who: Node }[];
  const spins = [...diagnosisOf.values()].map(d => d.intensity ?? 0); const avg = spins.length ? Math.round(spins.reduce((a, b) => a + b, 0) / spins.length) : null;
  const first = [...events].sort((a, b) => (a.date ?? '').localeCompare(b.date ?? ''))[0];
  const rows: [string, ReactNode][] = [
    ['Najgłośniej', <>{day(peak[0])} <small>· {peak[1]} {plural(peak[1], 'pozycja', 'pozycje', 'pozycji')}</small></>],
    ['Pierwsza wzmianka', day(first.date)],
  ];
  if (tops.length) rows.push(['Najwięcej wpisów', <>{tops.map((t, i) => <span key={t.who.id}>{i > 0 && ', '}<button type="button" className="px-name" onClick={() => onOpen({ kind: 'person', id: t.who.id })}>{nice(t.who.label)}</button>
    <small> ({CAMP_LABEL[t.who.camp ?? '']}, {t.n})</small></span>)}</>]);
  rows.push(['W Sejmie', data.counts.record || data.counts.vote ? `${data.counts.record ?? 0} ${plural(data.counts.record ?? 0, 'dokument', 'dokumenty', 'dokumentów')}, ${data.counts.vote ?? 0} ${plural(data.counts.vote ?? 0, 'głosowanie', 'głosowania', 'głosowań')}` : nb('brak dokumentów w naszej bazie')]);
  if (avg !== null) rows.push(['Średni spin', <><i className="px-spin-dot" style={{ ['--spin' as string]: spinColor(avg) }} />{avg}/100 <small>· {spins.length} {plural(spins.length, 'diagnoza', 'diagnozy', 'diagnoz')} Dr. Spina</small></>]);
  return <section className="px-card px-brief" aria-labelledby="brief-h">
    <h3 id="brief-h" className="px-h3">W 30 sekund</h3>
    <dl>{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
    <p className="px-card__foot">Policzone z&nbsp;listy poniżej, bez AI.</p>
  </section>;
}

/* Kiedy było najgłośniej: dni (albo tygodnie przy długim okresie) na prawdziwej osi czasu; szczyt jedynym wyróżnieniem. Klik przewija do dnia. */
function Density({ events }: { events: Node[] }) {
  const dates = events.map(n => n.date ?? '').filter(Boolean).sort();
  if (new Set(dates).size < 2) return null;
  const t0 = Date.parse(dates[0]), t1 = Date.parse(dates[dates.length - 1]);
  const span = Math.round((t1 - t0) / 864e5) + 1;
  const step = span > 120 ? 7 : 1;
  const buckets = Array.from({ length: Math.ceil(span / step) }, (_, i) => ({ from: new Date(t0 + i * step * 864e5).toISOString().slice(0, 10), n: 0, last: '' }));
  for (const d of dates) { const b = buckets[Math.floor(Math.round((Date.parse(d) - t0) / 864e5) / step)]; if (b) { b.n += 1; if (d > b.last) b.last = d; } }
  const max = Math.max(...buckets.map(b => b.n));
  const peak = buckets.findIndex(b => b.n === max);
  const w = 100 / buckets.length;
  return <section className="px-card px-chart" aria-labelledby="chart-h">
    <h3 id="chart-h" className="px-h3">Kiedy było najgłośniej <small>{step === 7 ? 'tygodnie' : 'dni'}</small></h3>
    <div className="px-chart__plot">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label={`Aktywność w temacie od ${day(dates[0])} do ${day(dates[dates.length - 1])}, szczyt ${day(buckets[peak].last)}`}>
        <line x1="0" x2="100" y1="99.5" y2="99.5" vectorEffect="non-scaling-stroke" />
        {buckets.map((b, i) => <g key={b.from} data-peak={i === peak || undefined} onClick={() => b.last && document.getElementById(`d-${b.last}`)?.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'center' })}>
          <title>{`${day(b.from)}: ${b.n}`}</title>
          <rect className="px-chart__hit" x={i * w} y={0} width={w} height={100} />
          {b.n > 0 && <rect x={i * w + w * .14} y={100 - Math.max(3, (94 * b.n) / max)} width={Math.max(w * .72, .4)} height={Math.max(3, (94 * b.n) / max)} />}
        </g>)}
      </svg>
      <button type="button" className="px-chart__peak" onClick={() => document.getElementById(`d-${buckets[peak].last}`)?.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'center' })} data-end={(peak + .5) * w > 55 || undefined} style={(peak + .5) * w > 55 ? { right: `${100 - (peak + .5) * w}%` } : { left: `${(peak + .5) * w}%` }}>szczyt: {short(buckets[peak].last)} · {max}</button>
    </div>
    <p className="px-card__foot px-chart__axis"><span>{day(dates[0])}</span><span>{day(dates[dates.length - 1])}</span></p>
  </section>;
}

/* Drzewo powiązań (właściciel 6.10): środek wyniku. Komputer: trzy kolumny z krzywymi; telefon i panel: drzewo w pionie z „kolankami”.
   Najechanie albo fokus podświetla całą ścieżkę (w górę i w dół), kliknięcie otwiera osobę albo wpis. */
const TG_MID = new Set(['statement', 'record', 'media', 'vote']);
function TopicGraph({ data, byId, focus, onOpen, compact = false }: { data: Graph; byId: Map<string, Node>; focus?: string; compact?: boolean; onOpen: Open }) {
  const narrow = useNarrow();
  const list = compact || narrow;
  const wrap = useRef<HTMLDivElement>(null);
  const [hot, setHot] = useState<string | null>(null);
  const model = useMemo(() => {
    const persons = focus ? [byId.get(focus)].filter(Boolean) as Node[] : data.nodes.filter(n => n.kind === 'person').sort((a, b) => b.links - a.links).slice(0, 8);
    const pid = new Set(persons.map(p => p.id));
    const midIds = new Set<string>();
    for (const e of data.edges) if (pid.has(e.source) && TG_MID.has(byId.get(e.target)?.kind ?? '')) midIds.add(e.target);
    const mid = [...midIds].map(id => byId.get(id)!).sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '')).slice(0, compact ? 6 : 8);
    const midSet = new Set(mid.map(n => n.id));
    const rightIds = new Set<string>();
    for (const e of data.edges) {
      const t = byId.get(e.target)?.kind;
      if ((midSet.has(e.source) && t === 'diagnosis') || (pid.has(e.source) && t === 'organisation')) rightIds.add(e.target);
    }
    const right = [...rightIds].map(id => byId.get(id)!).sort((a, b) => (a.kind === b.kind ? b.links - a.links : a.kind === 'diagnosis' ? -1 : 1)).slice(0, compact ? 6 : 8);
    const rightSet = new Set(right.map(n => n.id));
    const edges = data.edges.filter(e => (pid.has(e.source) && (midSet.has(e.target) || rightSet.has(e.target))) || (midSet.has(e.source) && rightSet.has(e.target)))
      .map(e => ({ source: e.source, target: e.target, ctx: byId.get(e.target)?.kind === 'organisation', step: midSet.has(e.source) ? 2 : 1 }));
    // drzewo w pionie: osoba, pod nią jej wpisy (a pod wpisem diagnoza), potem funkcje w KRS; każdy element raz
    const seen = new Set<string>();
    const rows: { n: Node; depth: number }[] = [];
    const listEdges: typeof edges = [];
    for (const p of persons) {
      const kids = edges.filter(e => e.source === p.id && !seen.has(e.target));
      if (!kids.length && !focus) continue;
      rows.push({ n: p, depth: 0 });
      for (const e of kids.sort((a, b) => Number(a.ctx) - Number(b.ctx))) {
        if (seen.has(e.target)) continue; seen.add(e.target);
        rows.push({ n: byId.get(e.target)!, depth: 1 }); listEdges.push(e);
        for (const e2 of edges.filter(x => x.source === e.target && !seen.has(x.target))) { seen.add(e2.target); rows.push({ n: byId.get(e2.target)!, depth: 2 }); listEdges.push(e2); }
      }
    }
    return { persons, mid, right, edges, rows, listEdges };
  }, [data, byId, focus, compact]);
  const paths = useLinks(wrap, list ? model.listEdges : model.edges, 26);
  const lit = useMemo(() => {
    if (!hot) return null;
    const on = new Set([hot]);
    const walk = (dir: 'down' | 'up') => { const q = [hot]; while (q.length) { const id = q.shift()!;
      for (const e of model.edges) { const [from, to] = dir === 'down' ? [e.source, e.target] : [e.target, e.source]; if (from === id && !on.has(to)) { on.add(to); q.push(to); } } } };
    walk('down'); walk('up');
    return on;
  }, [hot, model]);
  if (!model.persons.length || (!model.mid.length && !model.right.length)) return null;
  const open = (n: Node) => {
    if (n.kind === 'person') onOpen({ kind: 'person', id: n.id });
    else if (n.kind === 'vote') { if (n.url) window.open(n.url, '_blank', 'noopener'); }
    else if (TG_MID.has(n.kind)) onOpen({ kind: 'entry', id: n.id });
    else if (n.kind === 'diagnosis') { const src = data.edges.find(e => e.target === n.id)?.source; if (src) onOpen({ kind: 'entry', id: src }); }
    else if (n.url) window.open(n.url, '_blank', 'noopener');
  };
  const item = (n: Node, i: number, depth?: number) => <li key={n.id} style={{ ['--i' as string]: i, ['--depth' as string]: depth ?? 0 }}>
    <button type="button" className="px-node" data-g={n.id} data-kind={n.kind} data-on={lit?.has(n.id) || undefined} data-dim={lit && !lit.has(n.id) ? '' : undefined}
      onPointerEnter={e => { if (e.pointerType === 'mouse') setHot(n.id); }} onPointerLeave={() => setHot(null)} onFocus={e => { if (e.currentTarget.matches(':focus-visible')) setHot(n.id); }} onBlur={() => setHot(null)} onClick={() => open(n)}>
      <span className="px-sr">{KIND_LABEL[n.kind] ?? ''}: </span>{(n.kind === 'vote' || n.kind === 'organisation') && <span className="px-sr"> (otwiera nową kartę)</span>}
      <span className="px-node__ic"><Icon name={iconOf(n)} /></span>
      {n.kind === 'person' ? <span className="px-node__body"><b>{nice(n.label)}</b><small>{n.role || (n.institution ? 'instytucja' : CAMP_LABEL[n.camp ?? ''] ?? '')}</small></span>
        : n.kind === 'diagnosis' ? <span className="px-node__body"><small><em className="px-spin" style={{ ['--spin' as string]: spinColor(n.intensity) }}>spin {n.intensity}/100</em></small><span>{n.label}</span></span>
        : n.kind === 'organisation' ? <span className="px-node__body"><b>{n.label}</b><small>{n.sub}</small></span>
        : <span className="px-node__body"><small>{KIND_LABEL[n.kind]} · {short(n.date)}</small><span>{n.label}</span></span>}
    </button></li>;
  const kinds = [...new Set([...model.persons.map(iconOf), ...model.mid.map(n => n.kind), ...model.right.map(n => n.kind)])];
  const LEGEND: Record<string, string> = { person: 'osoba', institution: 'instytucja', statement: 'wpis', record: 'dokument Sejmu', media: 'artykuł', vote: 'głosowanie', diagnosis: 'diagnoza Dr. Spina', organisation: 'spółka lub fundacja z KRS' };
  const lines = <svg className="px-lines" aria-hidden="true">{paths.map(p => <path key={p.id} d={p.d} pathLength={p.ctx ? undefined : 1} data-ctx={p.ctx || undefined} style={{ ['--i' as string]: p.step }}
    data-on={lit && lit.has(p.s) && lit.has(p.t) ? '' : undefined} data-dim={lit && !(lit.has(p.s) && lit.has(p.t)) ? '' : undefined} />)}</svg>;
  return <figure className={`px-tree${compact ? ' px-tree--compact' : ''}`} data-list={list || undefined} data-hot={lit ? '' : undefined} aria-label="Drzewo powiązań">
    {!compact && <figcaption className="px-tree__head">
      <div><h3 className="px-h3">Drzewo powiązań</h3><p>Kto zabrał głos, co powiedział i&nbsp;jak ocenił to Dr. Spin (automatyczna ocena manipulacji 0-100).</p></div>
      <ul className="px-legend">{kinds.map(k => <li key={k}><Icon name={k} />{LEGEND[k] ?? k}</li>)}<li><i className="px-legend__dash" />funkcja w&nbsp;KRS</li></ul>
    </figcaption>}
    {list ? <div className="px-tree__wrap px-tree__wrap--list" ref={wrap}>{lines}<ol className="px-tree__list">{model.rows.map((r, i) => item(r.n, i, r.depth))}</ol></div>
      : <div className="px-tree__wrap" ref={wrap}>{lines}
        <div className="px-tree__col"><span className="px-tree__lab">Kto</span><ol>{model.persons.map((n, i) => item(n, i))}</ol></div>
        <div className="px-tree__col"><span className="px-tree__lab">Co powiedział lub opublikował</span><ol>{model.mid.map((n, i) => item(n, i))}</ol></div>
        <div className="px-tree__col"><span className="px-tree__lab">Diagnozy i&nbsp;funkcje w&nbsp;KRS</span><ol>{model.right.map((n, i) => item(n, i))}</ol></div>
      </div>}
    {!compact && <p className="px-card__foot px-tree__foot"><span>{list ? 'Dotknij elementu, aby go otworzyć.' : 'Najedź na element, aby zobaczyć całą ścieżkę. Kliknij, aby otworzyć.'}</span>
      <span>Linia przerywana: funkcja w&nbsp;KRS to kontekst osoby, nie dowód związku z&nbsp;tematem.</span></p>}
  </figure>;
}

/* Panel osoby i wpisu (właściciel 6.10): wejście „w głąb” bez wychodzenia do źródła. Esc zamyka, adres do udostępnienia. */
type Figure = { id: number; name: string; role_title: string; organisation: string; party?: string | null; evidence_url?: string; official_profile_url?: string;
  organisations?: { id: number; name: string; krs_number?: string; official_register_url?: string }[];
  employment_timeline?: { position: string; organisation: string; status: string; since?: string | null }[];
  votes?: { available: boolean; results: { date: string; topic: string; vote: string }[] };
  x_posts?: { available: boolean; results: { id: number; url: string; text: string; published_at: string }[] } };
type Diagnosis = { intensity: number; verdict_label: string; headline: string; summary: string; techniques?: { name: string; quote: string; explanation: string }[];
  claims?: { claim: string; assessment: string; explanation: string }[] };
const ASSESS: Record<string, string> = { true: 'prawdziwe', false: 'fałszywe', misleading: 'wprowadza w błąd', unverified: 'niezweryfikowane', partly_true: 'częściowo prawdziwe' };
const VOTE_PL: Record<string, string> = { YES: 'za', NO: 'przeciw', ABSTAIN: 'wstrzymał się', ABSENT: 'nieobecny', NO_VOTE: 'nieobecny' };
function Panel({ data, panel, byId, author, diagnosisOf, roles, onOpen }: { data: Graph; panel: { kind: 'person' | 'entry'; id: string }; byId: Map<string, Node>;
  author: Map<string, Node>; diagnosisOf: Map<string, Node>; roles: Map<string, { org: Node; role: string }[]>; onOpen: Open }) {
  const node = byId.get(panel.id);
  const [fig, setFig] = useState<Figure | null>(null);
  const [dg, setDg] = useState<Diagnosis | null>(null);
  const close = useRef<HTMLButtonElement>(null);
  const figureId = panel.kind === 'person' && panel.id.startsWith('figure:') ? panel.id.slice(7) : null;
  const diag = panel.kind === 'entry' ? diagnosisOf.get(panel.id) : undefined;
  useEffect(() => { setFig(null); if (figureId) fetch(`/api/public-figures/${figureId}/`).then(r => r.ok ? r.json() : null).then(setFig).catch(() => undefined); }, [figureId]);
  useEffect(() => { setDg(null); const id = diag?.id.split(':')[1]; if (id) fetch(`/api/clinic/spins/${id}/`).then(r => r.ok ? r.json() : null).then(setDg).catch(() => undefined); }, [diag?.id]);
  const box = useRef<HTMLElement>(null);
  useEffect(() => { const back = document.activeElement as HTMLElement | null; const html = document.documentElement; const was = html.style.overflow; html.style.overflow = 'hidden';
    return () => { html.style.overflow = was; if (back?.isConnected) back.focus({ preventScroll: true }); }; }, []);
  useEffect(() => { close.current?.focus(); const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpen(null);
      if (e.key === 'Tab' && box.current) { const f = [...box.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex="0"]')].filter(x => x.offsetParent);
        if (!f.length) return; const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); } } };
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key); }, [panel.id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!node) return null;
  const entriesOf = (personId: string) => data.nodes.filter(n => author.get(n.id)?.id === personId).sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''));
  const who = panel.kind === 'entry' ? author.get(node.id) : node;
  const camp = (who ?? node).camp;
  return <div className="px-panel" role="dialog" aria-modal="true" aria-label={panel.kind === 'person' ? `Osoba: ${nice(node.label)}` : 'Wpis'}>
    <button type="button" className="px-panel__scrim" aria-label="Zamknij" tabIndex={-1} onClick={() => onOpen(null)} />
    <aside className="px-panel__box" ref={box}>
      <header className="px-panel__head"><span className="px-kicker">{panel.kind === 'person' ? 'Osoba w temacie' : node.kind === 'statement' ? 'Wpis' : KIND_LABEL[node.kind]} · {data.topic}</span>
        <button ref={close} type="button" className="px-panel__x" onClick={() => onOpen(null)} aria-label="Zamknij">×</button></header>
      {panel.kind === 'person' ? <>
        <div className="px-panel__who"><span className="px-panel__av"><Icon name={iconOf(node)} size={22} /></span>
          <div><h2>{nice(fig?.name ?? node.label)}</h2>
            <p className="px-panel__sub">{[fig?.role_title ?? node.role, fig?.organisation, fig?.party, camp && CAMP_LABEL[camp]].filter(Boolean).join(' · ')}</p></div></div>
        <section><h3>Powiązania w temacie</h3><TopicGraph data={data} byId={byId} focus={node.id} onOpen={onOpen} compact /></section>
        <section><h3>W tym temacie ({entriesOf(node.id).length})</h3>
          <ol className="px-panel__list">{entriesOf(node.id).map(n => <li key={n.id}><button type="button" onClick={() => onOpen({ kind: 'entry', id: n.id })}>
            <time>{day(n.date)}</time><span>{n.label}</span>{diagnosisOf.get(n.id) && <em className="px-spin" style={{ ['--spin' as string]: spinColor(diagnosisOf.get(n.id)!.intensity) }}>spin {diagnosisOf.get(n.id)!.intensity}/100</em>}</button></li>)}</ol></section>
        {Boolean((fig?.organisations?.length ?? 0) || roles.get(node.id)?.length) && <section><h3>Funkcje w KRS</h3>
          <ul className="px-panel__rows">{(fig?.organisations ?? roles.get(node.id)?.map(r => ({ id: r.org.id, name: r.org.label, official_register_url: r.org.url, krs_number: r.org.sub })) ?? []).map(o =>
            <li key={String(o.id)}><a href={o.official_register_url} target="_blank" rel="noopener noreferrer">{o.name}</a><small>{o.krs_number && !String(o.krs_number).startsWith('KRS') ? `KRS ${o.krs_number}` : o.krs_number}</small></li>)}</ul>
          <p className="px-note">Funkcje w&nbsp;KRS to kontekst osoby, nie dowód związku z&nbsp;tematem.</p></section>}
        {Boolean(fig?.employment_timeline?.length) && <section><h3>Stanowiska</h3>
          <ul className="px-panel__rows">{fig!.employment_timeline!.slice(0, 6).map((r, i) => <li key={i}><span>{r.position}</span><small>{[r.organisation, r.status === 'current' ? 'obecnie' : 'wcześniej'].filter(Boolean).join(' · ')}</small></li>)}</ul></section>}
        {fig?.votes?.available && fig.votes.results.length > 0 && <section><h3>Ostatnie głosowania</h3>
          <ul className="px-panel__rows">{fig.votes.results.slice(0, 8).map((v, i) => <li key={i}><span>{v.topic}</span><small>{day(v.date)} · <b data-v={VOTE_PL[v.vote] ?? v.vote}>{VOTE_PL[v.vote] ?? v.vote}</b></small></li>)}</ul></section>}
        {fig?.x_posts?.available && fig.x_posts.results.length > 0 && <section><h3>Ostatnie wpisy na X</h3>
          <ul className="px-panel__rows">{fig.x_posts.results.slice(0, 5).map(p => <li key={p.id}><span>{p.text}</span><small>{day(p.published_at)} · <a href={p.url} target="_blank" rel="noopener noreferrer">na X ↗</a></small></li>)}</ul></section>}
        <footer className="px-panel__foot">{(fig?.official_profile_url || node.url) && <a href={fig?.official_profile_url || node.url} target="_blank" rel="noopener noreferrer">Oficjalny profil ↗</a>}
          {fig?.evidence_url && <a href={fig.evidence_url} target="_blank" rel="noopener noreferrer">Źródło funkcji ↗</a>}
          {figureId && <a href={`https://spin.clinic/osoby-publiczne/${figureId}`} target="_blank" rel="noopener noreferrer">Pełna karta w spin.clinic ↗</a>}</footer>
      </> : <>
        <p className="px-panel__by">{who ? <button type="button" className="px-name" onClick={() => onOpen({ kind: 'person', id: who.id })}>{nice(who.label)}</button> : <b>{node.sub}</b>}
          {camp && CAMP_LABEL[camp] ? <span> · {CAMP_LABEL[camp]}</span> : null}<time> · {day(node.date)}</time></p>
        <blockquote className="px-panel__text">{node.text ?? node.label}</blockquote>
        {diag && <section className="px-panel__dg"><h3>Diagnoza Dr. Spina</h3>
          {!dg ? <p className="px-note">Wczytuję diagnozę…</p> : <>
            <p className="px-panel__score" style={{ ['--spin' as string]: spinColor(dg.intensity) }}><b>{dg.intensity}</b><small>/100 · {dg.verdict_label}</small></p>
            <p className="px-panel__dgh">{dg.headline}</p><p>{dg.summary}</p>
            {Boolean(dg.techniques?.length) && <><h4>Chwyty retoryczne</h4><ul className="px-panel__rows">{dg.techniques!.map((t, i) => <li key={i}><span>{t.name}</span><small>„{t.quote}”</small></li>)}</ul></>}
            {Boolean(dg.claims?.length) && <><h4>Twierdzenia i ocena</h4><ul className="px-panel__rows">{dg.claims!.map((c, i) => <li key={i}><span>{c.claim}</span><small>{ASSESS[c.assessment] ?? c.assessment}</small></li>)}</ul></>}
          </>}</section>}
        {who && entriesOf(who.id).length > 1 && <section><h3>Inne wpisy tej osoby w temacie</h3>
          <ol className="px-panel__list">{entriesOf(who.id).filter(n => n.id !== node.id).slice(0, 6).map(n => <li key={n.id}><button type="button" onClick={() => onOpen({ kind: 'entry', id: n.id })}>
            <time>{day(n.date)}</time><span>{n.label}</span></button></li>)}</ol></section>}
        <footer className="px-panel__foot">{diag && <a href={diag.url} target="_blank" rel="noopener noreferrer">Pełna diagnoza w spin.clinic ↗</a>}
          {node.url && <a href={node.url} target="_blank" rel="noopener noreferrer">Źródło ↗</a>}
          {node.url && <a href={`https://web.archive.org/web/*/${node.url}`} target="_blank" rel="noopener noreferrer">Kopie w archiwum ↗</a>}
          {node.url && <a href={`https://web.archive.org/save/${node.url}`} target="_blank" rel="noopener noreferrer">Zapisz kopię teraz ↗</a>}</footer>
      </>}
    </aside>
  </div>;
}

/* Głosowania w temacie: kolory znaczą głos (za, przeciw, wstrzymał się, nieobecny), nigdy stronę sceny politycznej. */
const VOTE_ORDER = ['za', 'przeciw', 'wstrzymał się', 'nieobecny'];
const SHORT_V: Record<string, string> = { za: 'za', przeciw: 'przeciw', 'wstrzymał się': 'wstrz.', nieobecny: 'nieob.' };
function Votes({ votes }: { votes: Vote[] }) {
  const [open, setOpen] = useState<string | null>(null);
  return <section className="px-votes" aria-labelledby="votes-h">
    <h3 id="votes-h" className="px-h3">Głosowania w&nbsp;Sejmie</h3>
    <ul className="px-votes__legend" aria-hidden="true">{VOTE_ORDER.map(v => <li key={v} data-v={v}><i />{v}</li>)}</ul>
    <ol>{votes.map(v => {
      const max = Math.max(...v.clubs.map(c => c.size), 1);
      return <li key={v.id} className="px-card px-vote">
        <div className="px-vote__head">
          <span className="px-kicker">{day(v.date)}</span>
          <p>{v.title}</p>
          {v.motion && v.motion !== v.title && <small>{v.motion}</small>}
          <span className="px-vote__result">{[['yes', 'za'], ['no', 'przeciw'], ['abstain', 'wstrzymało się']].filter(([k]) => v.result[k] != null).map(([k, l]) => <b key={k} data-v={l === 'wstrzymało się' ? 'wstrzymał się' : l}>{v.result[k]} {l}</b>)}</span>
        </div>
        <ul className="px-vote__clubs">{v.clubs.map(c => <li key={c.club}>
          <span>{c.club}</span>
          <i style={{ width: `${(100 * c.size) / max}%` }}>{VOTE_ORDER.map(k => c.votes[k] ? <b key={k} data-v={k} style={{ flexGrow: c.votes[k] }} title={`${k}: ${c.votes[k]}`} /> : null)}</i>
          <em>{VOTE_ORDER.filter(k => c.votes[k]).map(k => `${c.votes[k]} ${SHORT_V[k]}`).join(', ')}</em>
        </li>)}</ul>
        <span className="px-vote__act">
          <button type="button" className="px-quiet" onClick={() => setOpen(open === v.id ? null : v.id)} aria-expanded={open === v.id}>{open === v.id ? 'Zwiń' : 'Kto jak głosował'}</button>
          <a className="px-quiet" href={v.url} target="_blank" rel="noopener noreferrer">wynik w Sejmie ↗</a>
        </span>
        {open === v.id && <div className="px-vote__members">{v.clubs.map(c => <div key={c.club}>
          <h4>{c.club}</h4>
          <ul>{v.members.filter(m => m[1] === c.club).sort((a, b) => VOTE_ORDER.indexOf(a[2]) - VOTE_ORDER.indexOf(b[2])).map(m => <li key={m[0]} data-v={m[2]}><i />{m[0]}<span className="px-sr">: {m[2]}</span></li>)}</ul>
        </div>)}</div>}
      </li>;
    })}</ol>
  </section>;
}

/* Eksport tematu (właściciel 5.10): każdy wiersz z przypisem źródła i datą pobrania; w becie bez opłat. */
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
  return <><button type="button" className="px-tool" onClick={csv}><Icon name="down" />CSV</button><button type="button" className="px-tool" onClick={json}><Icon name="down" />JSON</button></>;
}

/* Ścieżka w Sejmie: druki, konsultacje i głosowania w temacie po kolei, od najstarszego. */
function SejmPath({ data }: { data: Graph }) {
  const steps = [
    ...data.nodes.filter(n => n.kind === 'record' && n.date).map(n => ({ id: n.id, date: n.date!, kind: n.sub ? (SUB[n.sub] ?? n.sub) : 'dokument', title: n.label, url: n.url })),
    ...(data.votes ?? []).filter(v => v.date).map(v => ({ id: v.id, date: v.date!, kind: 'głosowanie', title: `${v.title}${v.result.yes != null ? ` (za ${v.result.yes}, przeciw ${v.result.no ?? 0})` : ''}`, url: v.url })),
  ].sort((a, b) => a.date.localeCompare(b.date));
  if (steps.length < 2) return null;
  return <section className="px-card px-path" aria-labelledby="path-h"><h3 id="path-h" className="px-h3">Ścieżka w&nbsp;Sejmie</h3>
    <ol>{steps.slice(-10).map(s => <li key={s.id}><time>{short(s.date)}</time><b>{s.kind}</b>
      {s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a> : <span>{s.title}</span>}</li>)}</ol></section>;
}
