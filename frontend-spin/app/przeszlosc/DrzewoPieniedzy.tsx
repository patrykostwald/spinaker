"use client";
import { Sprostowanie } from './Sprostowanie';
import { useEffect, useRef, useState, type RefObject } from 'react';
import { Loading } from '@spin-clinic/ui/kit';
import { Przybornik, companyTools } from './Przybornik';
import { Bar, Foot, Icon, day, nb, plural, useStandalone, type Access } from './ui';

/**
 * Drzewo przepływu pieniędzy (właściciel 6.10, wersja 1): jeden podmiot z KRS u góry, pod nim trzy równe gałęzie
 * (zamówienia publiczne, dotacje UE, osoby z funkcjami w KRS) połączone liniami jak w drzewie tematu (px-tree, px-node, px-lines).
 * Każdy boks: tytuł i suma u góry, wiersze w środku, źródło z licencją przy dolnej krawędzi. Pod drzewem pełna lista
 * z zakładkami, w tym „niepowiązane” (zgodność nazwy bez identyfikatora - pokazane, ale nie liczone). Bez oceny, ta sama miara.
 */
type Sum = { currency: string; total: number };
type Source = { key: string; label: string; license: string; url: string; note?: string };
type Contract = { id: string; source: 'ted' | 'bzp'; role: string; title: string; party: string; amount: number | null; currency: string; date: string | null; kind: string; url: string; matched_by: string };
type Grant = { id: string; source: 'fts'; title: string; programme: string; amount: number | null; currency: string; date: string | null; year: number | null; url: string; matched_by: string };
type Person = { id: string; figure_id: number; name: string; slug: string; profile_url: string; role: string; function: string; status: string; since: string | null; until: string | null; method: string; url: string };
type Unlinked = { id: string; source: string; title: string; amount: number | null; currency: string; date: string | null; url: string; reason: string };
export type MoneyTree = {
  organisation: { id: number; name: string; krs_number: string; nip: string; regon: string; kind: string; legal_form: string; sector: string; url: string; source: Source };
  identifiers: Record<string, string>; identifiers_missing: boolean;
  contracts: { count: number; sums: Sum[]; suspect_count?: number; results: Contract[] };
  grants: { count: number; sums: Sum[]; results: Grant[] };
  people: { count: number; results: Person[] };
  unlinked: { count: number; results: Unlinked[] };
  sources: Source[]; note: string; unlinked_reason: string; generated_at: string; access?: Access;
};

const KIND: Record<string, string> = { company: 'Spółka z KRS', foundation: 'Fundacja z KRS', association: 'Stowarzyszenie z KRS', other: 'Podmiot z KRS' };
const SRC: Record<string, string> = { ted: 'TED', bzp: 'BZP', fts: 'FTS', kohesio: 'Kohesio', krs: 'KRS' };
const LIC: Record<string, string> = { ted: 'dane publiczne', bzp: 'dane publiczne', fts: 'CC BY 4.0', kohesio: 'CC0 1.0', krs: 'dane publiczne' };
const ROWS = 5;

/** Kwota z ogłoszenia: „1,5 mln zł”, „200 €”; bez kwoty: „bez kwoty”. */
export const money = (amount: number | null, currency: string) => {
  if (amount === null || amount === undefined) return 'bez kwoty';
  const unit = currency === 'PLN' || !currency ? 'zł' : currency === 'EUR' ? '€' : currency;
  const abs = Math.abs(amount);
  const short = abs >= 1e9 ? `${(amount / 1e9).toLocaleString('pl-PL', { maximumFractionDigits: 2 })} mld` : abs >= 1e6 ? `${(amount / 1e6).toLocaleString('pl-PL', { maximumFractionDigits: 1 })} mln`
    : abs >= 1e4 ? `${(amount / 1e3).toLocaleString('pl-PL', { maximumFractionDigits: 0 })} tys.` : amount.toLocaleString('pl-PL', { maximumFractionDigits: 0 });
  return `${short} ${unit}`;  // jednostka nigdy sama na końcu wiersza
};
export const sumLine = (sums: Sum[]) => sums.length ? sums.map(s => money(s.total, s.currency)).join(' + ') : '-';

/* Linie od węzła podmiotu (dół) do górnej krawędzi każdej gałęzi; przeliczane przy zmianie rozmiaru (jak useLinks w drzewie tematu). */
function useBranchLines(root: RefObject<HTMLElement | null>, ids: string[], on: boolean) {
  const [paths, setPaths] = useState<{ id: string; d: string }[]>([]);
  useEffect(() => {
    const el = root.current; if (!el || !on) { setPaths([]); return; }
    const draw = () => {
      const box = el.getBoundingClientRect(); if (!box.width) return;
      const a = el.querySelector<HTMLElement>('[data-g="root"]')?.getBoundingClientRect(); if (!a) return;
      const x1 = a.left + a.width / 2 - box.left, y1 = a.bottom - box.top;
      setPaths(ids.flatMap(id => {
        const b = el.querySelector<HTMLElement>(`[data-g="${id}"]`)?.getBoundingClientRect(); if (!b?.width) return [];
        const x2 = b.left + b.width / 2 - box.left, y2 = b.top - box.top, k = Math.max(16, (y2 - y1) * .55);
        return [{ id, d: `M${x1},${y1} C${x1},${y1 + k} ${x2},${y2 - k} ${x2},${y2}` }];
      }));
    };
    draw(); const ro = new ResizeObserver(draw); ro.observe(el); return () => ro.disconnect();
  }, [root, ids, on]);
  return paths;
}
function useNarrow(query = '(max-width: 760px)') {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => { const m = window.matchMedia(query); const sync = () => setNarrow(m.matches); sync(); m.addEventListener('change', sync); return () => m.removeEventListener('change', sync); }, [query]);
  return narrow;
}

export function DrzewoPieniedzy({ ident }: { ident: string }) {
  useStandalone();
  const [data, setData] = useState<MoneyTree | null>(null);
  const [state, setState] = useState<'loading' | 'idle' | 'missing' | 'off' | 'locked' | 'error'>('loading');
  useEffect(() => {
    fetch(`/api/przeszlosc/spolka/${encodeURIComponent(ident)}/`).then(async r => {
      if (r.status === 404) { const body = await r.json().catch(() => ({})); setState(String(body.detail ?? '').includes('wyłączona') ? 'off' : 'missing'); return; }
      if (r.status === 403) { setState('locked'); return; }
      if (!r.ok) throw new Error();
      const d: MoneyTree = await r.json(); setData(d); setState('idle');
      if (d.organisation.krs_number !== ident) window.history.replaceState(null, '', `/przeszlosc/spolka/${d.organisation.krs_number}`);
      document.title = `${d.organisation.name} - drzewo przepływu pieniędzy - przeszłość.today`;
    }).catch(() => setState('error'));
  }, [ident]);
  return <main className="px px-mt">
    <Bar />
    {state === 'loading' && <div className="px-wait"><Loading label="Ładowanie drzewa" /></div>}
    {state === 'missing' && <p className="px-msg">{nb('Nie ma takiego podmiotu w naszym rejestrze KRS.')} <a href="/przeszlosc?tryb=osoba">Szukaj osoby</a></p>}
    {state === 'off' && <p className="px-msg">Podgląd jest jeszcze wyłączony na serwerze.</p>}
    {state === 'locked' && <p className="px-msg">{nb('Drzewo przepływu pieniędzy jest w pilotażu przeszłość.today.')} <a href="/przeszlosc/pilot">Pilotaż</a></p>}
    {state === 'error' && <p className="px-msg" role="alert">Nie udało się pobrać drzewa. Spróbuj ponownie.</p>}
    {data && <TreeView data={data} />}
    <Foot />
  </main>;
}

type Tab = 'contracts' | 'grants' | 'people' | 'unlinked';
const BRANCH: { id: Tab; title: string; icon: string }[] = [
  { id: 'contracts', title: 'Zamówienia publiczne', icon: 'record' }, { id: 'grants', title: 'Dotacje UE', icon: 'institution' }, { id: 'people', title: 'Osoby z funkcjami w KRS', icon: 'people' }];

export function TreeView({ data, lines = true }: { data: MoneyTree; lines?: boolean }) {
  const [tab, setTab] = useState<Tab>('contracts');
  const narrow = useNarrow();
  const wrap = useRef<HTMLDivElement>(null);
  const paths = useBranchLines(wrap, BRANCH.map(b => b.id), lines && !narrow);
  const o = data.organisation;
  const sub = [o.legal_form, `KRS ${o.krs_number}`, o.nip ? `NIP ${o.nip}` : 'NIP: brak w naszych danych', o.regon ? `REGON ${o.regon}` : ''].filter(Boolean).join(' · ');
  const src = (keys: string[]) => data.sources.filter(s => keys.includes(s.key));
  // stopka boksu w jednej linii: skrót źródła i krótka licencja; pełne nazwy i licencje pod listą rekordów
  const foot = (keys: string[]) => {
    const rows = src(keys);
    return rows.length ? <>Źródło: {rows.map((s, i) => <span key={s.key}>{i ? ' · ' : ''}<a href={s.url} target="_blank" rel="noopener noreferrer" title={`${s.label} (${s.license})`}>{SRC[s.key] ?? s.label}</a></span>)} ({rows.map(s => LIC[s.key] ?? s.license).filter((v, i, a) => a.indexOf(v) === i).join(', ')})</> : 'Brak rekordów w bazie';
  };
  const stamp = data.generated_at.slice(0, 10);
  const counts: Record<Tab, number> = { contracts: data.contracts.count, grants: data.grants.count, people: data.people.count, unlinked: data.unlinked.count };
  return <>
    <header className="px-tv__head px-mt__head">
      <div>
        <p className="px-kicker">{KIND[o.kind] ?? KIND.other}</p>
        <h1>{o.name}</h1>
        <p className="px-mt__sub">{sub}</p>
        <p className="px-mt__links"><a href={o.url} target="_blank" rel="noopener noreferrer">Wyszukiwarka KRS (MS) ↗</a>
          <a href={`/przeszlosc/przeplyw/${encodeURIComponent(`spolka:${o.krs_number || o.nip}`)}`}>Drzewo przepływu →</a></p>
      </div>
      <div className="px-tv__tools"><Sprostowanie recordId={`spolka:${o.krs_number || o.nip}`} label={o.name} /></div>
    </header>

    <section className="px-proof px-mt__proof" aria-label="Liczby">
      <div><b>{data.contracts.count.toLocaleString('pl-PL')}</b><span>{nb(plural(data.contracts.count, 'zamówienie publiczne', 'zamówienia publiczne', 'zamówień publicznych'))}</span></div>
      <div><b>{data.contracts.sums.length ? money(data.contracts.sums[0].total, data.contracts.sums[0].currency) : '-'}</b>
        <span>{nb('suma z ogłoszeń o zamówieniach')}{data.contracts.sums.length > 1 ? ` + ${sumLine(data.contracts.sums.slice(1))}` : ''}{data.contracts.suspect_count ? nb(` · bez ${data.contracts.suspect_count} kwot do weryfikacji`) : ''}</span></div>
      <div><b>{data.grants.count.toLocaleString('pl-PL')}</b><span>{nb(plural(data.grants.count, 'dotacja UE', 'dotacje UE', 'dotacji UE'))}{data.grants.sums.length ? ` · ${sumLine(data.grants.sums)}` : ''}</span></div>
      <div><b>{data.people.count.toLocaleString('pl-PL')}</b><span>{nb(plural(data.people.count, 'osoba publiczna z funkcją w KRS', 'osoby publiczne z funkcjami w KRS', 'osób publicznych z funkcjami w KRS'))}</span></div>
    </section>

    <figure className="px-tree px-mt__tree" data-list={narrow || undefined} aria-label="Drzewo przepływu pieniędzy">
      <figcaption className="px-tree__head">
        <div><h2 className="px-h3">Drzewo przepływu pieniędzy</h2><p>{nb('Skąd pieniądze przychodzą (zamówienia, dotacje) i kto odpowiada za podmiot (funkcje w KRS). Powiązania tylko po NIP, KRS i REGON.')}</p></div>
        <ul className="px-legend"><li><Icon name="organisation" />podmiot z KRS</li><li><Icon name="record" />zamówienie</li><li><Icon name="institution" />dotacja UE</li><li><Icon name="people" />osoba publiczna</li></ul>
      </figcaption>
      <div className="px-mt__wrap" ref={wrap}>
        <svg className="px-lines" aria-hidden="true">{paths.map(p => <path key={p.id} d={p.d} />)}</svg>
        <div className="px-mt__root"><a className="px-node px-mt__node" data-g="root" href={o.url} target="_blank" rel="noopener noreferrer">
          <span className="px-node__ic"><Icon name="organisation" /></span>
          <span className="px-node__body"><b>{o.name}</b><small>{KIND[o.kind] ?? KIND.other} · KRS {o.krs_number}{o.nip ? ` · NIP ${o.nip}` : ''}</small></span></a></div>
        <div className="px-mt__branches">
          {BRANCH.map(b => {
            const n = counts[b.id];
            const rows = b.id === 'contracts' ? data.contracts.results.slice(0, ROWS).map(c => ({ id: c.id, href: c.url, text: c.title || c.party, meta: [money(c.amount, c.currency), day(c.date) || '', c.role, SRC[c.source]].filter(Boolean).join(' · '), blank: true }))
              : b.id === 'grants' ? data.grants.results.slice(0, ROWS).map(g => ({ id: g.id, href: g.url, text: g.title || g.programme, meta: [money(g.amount, g.currency), g.year ? String(g.year) : day(g.date) || '', g.programme, SRC[g.source]].filter(Boolean).join(' · '), blank: true }))
              : data.people.results.slice(0, ROWS).map(p => ({ id: p.id, href: p.profile_url, text: p.name, meta: [p.role, p.since ? `od ${day(p.since)}` : '', p.until ? `do ${day(p.until)}` : p.status === 'former' ? 'historyczna' : 'obecna'].filter(Boolean).join(' · '), blank: false }));
            const sum = b.id === 'contracts' ? sumLine(data.contracts.sums) : b.id === 'grants' ? sumLine(data.grants.sums) : `${n} ${plural(n, 'osoba', 'osoby', 'osób')}`;
            const empty = b.id === 'people' ? 'Brak potwierdzonych osób publicznych w organach.' : data.identifiers_missing ? 'Bez NIP w naszych danych nie łączymy ogłoszeń.' : 'Brak rekordów po identyfikatorach podmiotu.';
            return <section key={b.id} className="px-card px-mt__branch" data-g={b.id} aria-labelledby={`mt-${b.id}-h`}>
              <div className="px-mt__top"><h3 id={`mt-${b.id}-h`} className="px-h3"><Icon name={b.icon} />{b.title}</h3><b className="px-mt__sum">{sum}</b><small>{n} {plural(n, 'rekord', 'rekordy', 'rekordów')}{n > ROWS ? ` · ${ROWS} najnowszych poniżej` : ''}</small></div>
              {rows.length ? <ul className="px-mt__rows">{rows.map(r => <li key={r.id}>
                <a href={r.href} {...(r.blank ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>{r.text}</a><small>{r.meta}</small></li>)}</ul>
                : <p className="px-note px-mt__empty">{nb(empty)}</p>}
              <p className="px-card__foot px-mt__foot"><span>{foot(b.id === 'contracts' ? ['ted', 'bzp'] : b.id === 'grants' ? ['fts'] : ['krs'])}</span>
                {n > 0 && <a className="px-quiet" href="#mt-lista" onClick={() => setTab(b.id)}>Wszystkie {n} ↓</a>}</p>
            </section>;
          })}
        </div>
      </div>
      <p className="px-card__foot px-tree__foot"><span>{narrow ? 'Dotknij elementu, aby otworzyć źródło.' : 'Kliknij element, aby otworzyć źródło w nowej karcie.'}</span><span>{nb('Niepowiązane (ta sama nazwa, brak identyfikatora) są w liście poniżej, poza sumami.')}</span></p>
    </figure>

    <Przybornik id="mt-tools-h" tools={companyTools({ krs: o.krs_number, nip: o.nip, regon: o.regon })} />

    <section className="px-mt__list" id="mt-lista" aria-labelledby="mt-list-h">
      <div className="px-time__head"><h2 id="mt-list-h" className="px-h3">Wszystkie rekordy</h2><span>{counts[tab]} {plural(counts[tab], 'pozycja', 'pozycje', 'pozycji')}</span></div>
      <div className="px-seg px-mt__seg" role="group" aria-label="Gałąź">
        {([['contracts', 'Zamówienia'], ['grants', 'Dotacje UE'], ['people', 'Osoby'], ['unlinked', 'Niepowiązane']] as const).map(([k, l]) =>
          <button key={k} type="button" aria-pressed={tab === k} onClick={() => setTab(k)}>{l} <em>{counts[k]}</em></button>)}
      </div>
      <ul className="px-panel__rows px-mt__all">
        {tab === 'contracts' && data.contracts.results.map(c => <li key={c.id}><span><a href={c.url} target="_blank" rel="noopener noreferrer">{c.title || c.party}</a></span>
          <small>{[money(c.amount, c.currency), day(c.date) || '', `${c.role}: ${c.party}`, `${SRC[c.source]} · po ${c.matched_by}`].filter(Boolean).join(' · ')}</small></li>)}
        {tab === 'grants' && data.grants.results.map(g => <li key={g.id}><span><a href={g.url} target="_blank" rel="noopener noreferrer">{g.title || g.programme}</a></span>
          <small>{[money(g.amount, g.currency), g.year ? String(g.year) : day(g.date) || '', g.programme, `${SRC[g.source]} · po ${g.matched_by}`].filter(Boolean).join(' · ')}</small></li>)}
        {tab === 'people' && data.people.results.map(p => <li key={p.id}><span><a href={p.profile_url}>{p.name}</a> <small>· profil przeszłość.today</small></span>
          <small>{[p.role, p.function !== p.role ? p.function : '', p.since ? `od ${day(p.since)}` : '', p.until ? `do ${day(p.until)}` : p.status === 'former' ? 'historyczna' : 'obecna', p.method === 'krs_register' ? 'potwierdzone w KRS' : 'źródła publiczne'].filter(Boolean).join(' · ')} · <a href={p.url} target="_blank" rel="noopener noreferrer">odpis ↗</a></small></li>)}
        {tab === 'unlinked' && data.unlinked.results.map(u => <li key={u.id}><span><a href={u.url} target="_blank" rel="noopener noreferrer">{u.title}</a> <em className="px-mt__tag">niepowiązane</em></span>
          <small>{[money(u.amount, u.currency), day(u.date) || '', SRC[u.source] ?? u.source, u.reason].filter(Boolean).join(' · ')}</small></li>)}
        {counts[tab] === 0 && <li><span className="px-note">{tab === 'unlinked' ? nb('Brak rekordów dopasowanych tylko po nazwie.') : nb('Brak rekordów w tej gałęzi.')}</span></li>}
      </ul>
      <p className="px-note">Źródła i licencje: {data.sources.map((s, i) => <span key={s.key}>{i ? ' · ' : ''}<a href={s.url} target="_blank" rel="noopener noreferrer">{s.label}</a> ({s.license})</span>)}</p>
      <p className="px-note">{nb(data.note)} Stan na {day(stamp)}.</p>
    </section>
  </>;
}
