"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Loading } from '@spin-clinic/ui/kit';
import { Bar, Foot, Icon, host, nb, plural, useStandalone } from '../ui';
import '../glosowania-lista.css';
import {
  EMPTY_FILTERS, MIN_QUERY, PER_PAGE, buildVotesQuery, clubSummary, filtersToSearch, hasFilters, mergeRows, outcomeLabel, parseFilters,
  queryTooShort, safeUrl, shortDay, sortRows, votesToCsv,
  type SortDir, type SortKey, type VoteFilters, type VoteListRow, type VotesListResponse,
} from '../glosowania-lista';

/**
 * Lista głosowań Sejmu (przeszłość.today, port v3, 13.10.2026): GET /api/przeszlosc/glosowania/ (gust/spin/port/API-v3.md, sekcja 3).
 * Tabela ze wspólnymi liniami kolumn, zero pasków (ani przewijania, ani słupków wyniku): wynik ogółem w liczbach, głos klubu
 * kształtem i słowem w jednym kolorze. Poniżej 900 px wiersze kartowe z etykietą kolumny. Notka o zakresie danych zawsze widoczna.
 * Sortowanie jest po stronie klienta (API zwraca tylko datę malejąco) i obejmuje wczytane wiersze - interfejs mówi o tym wprost.
 */
type State = 'loading' | 'idle' | 'off' | 'bad' | 'error';
const OUTCOMES = [['', 'Wszystkie'], ['przyjete', 'Przyjęte'], ['odrzucone', 'Odrzucone'], ['nieustalone', 'Nieustalone']] as const;
const SORTS: [SortKey, string][] = [['date', 'Data'], ['result', 'Wynik ogółem']];
const STATIC_COVER = 'To nie jest pełne archiwum głosowań Sejmu: pokazujemy tylko to, co zaimportowaliśmy do naszej bazy.';

function Source({ v }: { v: VoteListRow }) {
  const href = safeUrl(v.url);
  if (!href) return <span className="pt-nd">brak w naszych danych</span>;
  return <a className="pt-src" href={href} target="_blank" rel="noopener noreferrer"
    aria-label={`Wynik głosowania na stronie Sejmu, ${shortDay(v.date)}, źródło: ${host(v.url) || 'sejm.gov.pl'}`}>
    <span>{host(v.url) || 'sejm.gov.pl'}</span><i aria-hidden="true">↗</i></a>;
}

function Row({ v, club }: { v: VoteListRow; club: string }) {
  const r = v.result;
  const sum = clubSummary(v.club_votes);
  const unknown = v.outcome === 'nieustalone' || !['przyjete', 'odrzucone'].includes(v.outcome);
  return <tr className="gl-row">
    <td data-c="d" data-l="Data"><time dateTime={v.date ?? undefined}>{shortDay(v.date) || 'brak w naszych danych'}</time></td>
    <td data-c="t"><p className="gl-t" title={v.title}>{v.title}</p>
      {v.motion && v.motion !== v.title && <small className="gl-m" title={v.motion}>{v.motion}</small>}</td>
    <td data-c="r" data-l="Wynik ogółem">
      {r ? <>
        <span className="gl-out" data-o={v.outcome} title={unknown ? 'Brak w naszych danych: wymaganej większości dla tego głosowania (np. głosowania na listach).' : undefined}>
          {outcomeLabel(v.outcome)}{v.majority ? <small> · wymagane {v.majority.votes}</small> : null}</span>
        <span className="gl-n">za <b>{r.yes ?? '-'}</b> · przeciw <b>{r.no ?? '-'}</b></span>
        <span className="gl-n">wstrz. <b>{r.abstain ?? '-'}</b> · nieob. <b>{r.notParticipating ?? '-'}</b></span>
      </> : <span className="pt-nd">brak w naszych danych</span>}
    </td>
    {club && <td data-c="k" data-l={`Głos klubu ${club}`}>
      {sum ? <><span className="px-pp__vote gl-vote" data-v={sum.word}><i aria-hidden="true" />{sum.word}</span>
        <span className="gl-n">{sum.counts}</span></>
        : <span className="pt-nd">brak w naszych danych</span>}
    </td>}
    <td data-c="s"><Source v={v} /></td>
  </tr>;
}

export function GlosowaniaPage() {
  useStandalone();
  const [filters, setFilters] = useState<VoteFilters>(EMPTY_FILTERS);
  const [draft, setDraft] = useState('');
  const [ready, setReady] = useState(false);
  const [state, setState] = useState<State>('loading');
  const [detail, setDetail] = useState('');
  const [rows, setRows] = useState<VoteListRow[]>([]);
  const [meta, setMeta] = useState<Omit<VotesListResponse, 'results'> | null>(null);
  const [clubs, setClubs] = useState<string[]>([]);
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: 'date', dir: 'desc' });
  const [busy, setBusy] = useState(false);
  const [moreError, setMoreError] = useState(false);
  const seq = useRef(0);

  // filtry z adresu (udostępnialny link), raz po wejściu
  useEffect(() => {
    const f = parseFilters(window.location.search);
    setFilters(f); setDraft(f.q); setReady(true);
  }, []);

  const fetchPage = useCallback(async (f: VoteFilters, page: number, append: boolean) => {
    const id = ++seq.current;
    setBusy(true); setMoreError(false);
    try {
      const r = await fetch(`/api/przeszlosc/glosowania/?${buildVotesQuery(f, page, PER_PAGE)}`);
      if (id !== seq.current) return;
      if (r.status === 404) { setState('off'); return; }
      if (r.status === 400) { const b = await r.json().catch(() => ({})); setDetail(String(b.detail ?? '')); setState('bad'); return; }
      if (!r.ok) throw new Error(String(r.status));
      const d: VotesListResponse = await r.json();
      if (id !== seq.current) return;
      const { results, ...rest } = d;
      setRows(prev => append ? mergeRows(prev, results) : results);
      setMeta(rest); setClubs(c => d.clubs.length ? d.clubs : c); setState('idle');
    } catch {
      if (id !== seq.current) return;
      if (append) setMoreError(true); else setState('error');
    } finally { if (id === seq.current) setBusy(false); }
  }, []);

  useEffect(() => {
    if (!ready) return;
    window.history.replaceState(null, '', `${window.location.pathname}${filtersToSearch(filters)}`);
    void fetchPage(filters, 1, false);
  }, [filters, ready, fetchPage]);

  const sorted = useMemo(() => sortRows(rows, sort.key, sort.dir), [rows, sort]);
  const total = meta?.total ?? 0;
  const remaining = Math.max(0, total - rows.length);
  const page = meta?.page ?? 1;
  const short = queryTooShort(draft);
  const club = meta?.filter.klub ?? filters.klub;
  const cov = meta?.coverage;
  const terms = cov?.terms ?? [];
  const first = terms.map(t => t.first).filter(Boolean).sort()[0] ?? null;
  const last = terms.map(t => t.last).filter(Boolean).sort().reverse()[0] ?? null;
  const scope = cov ? `Zakres: ${terms.length === 1 ? `kadencja ${terms[0].term}, ` : terms.length > 1 ? `kadencje ${terms.map(t => t.term).join(', ')}, ` : ''}${cov.total_votings.toLocaleString('pl-PL')} ${plural(cov.total_votings, 'głosowanie', 'głosowania', 'głosowań')}${first && last ? `, od ${shortDay(first)} do ${shortDay(last)}` : ''}.` : '';

  const apply = (patch: Partial<VoteFilters>) => setFilters(f => {
    const next = { ...f, ...patch };
    if (next.od && next.do && next.od > next.do) { if (patch.od !== undefined) next.do = next.od; else next.od = next.do; }
    return next;
  });
  const submit = (e: React.FormEvent) => { e.preventDefault(); if (!short) apply({ q: draft.trim() }); };
  const reset = () => { setDraft(''); setFilters(EMPTY_FILTERS); };
  const toggleSort = (key: SortKey) => setSort(s => s.key === key ? { key, dir: s.dir === 'desc' ? 'asc' : 'desc' } : { key, dir: 'desc' });
  const csv = () => {
    const stamp = new Date().toLocaleDateString('sv-SE');
    const blob = new Blob([votesToCsv(sorted, { klub: club || undefined, stamp, total, description: cov?.description })], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `glosowania-sejmu-${stamp}.csv`; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return <div className="px pt-page">
    <Bar />
    <section className="px-sec gl" aria-labelledby="gl-h" aria-busy={busy || undefined}>
      <div className="gl-head">
        <div className="pt-head__l"><p className="px-kicker">Tabela danych</p><h1 id="gl-h">Głosowania Sejmu</h1></div>
        <a className="px-link gl-head__link" href="/przeszlosc/odstepstwa">Odstępstwa od klubu&nbsp;→</a>
      </div>
      <p className="gl-lead">{nb('Głosowania imienne z naszej bazy: wynik ogółem w liczbach, głos wybranego klubu i odnośnik do źródła w Sejmie.')}</p>
      <div className="gl-cover" id="gl-cover">
        <p>{nb(cov?.description || STATIC_COVER)}</p>
        {scope && <p className="gl-cover__scope">{scope}</p>}
      </div>

      <form className="gl-filters" role="search" aria-label="Filtry głosowań" onSubmit={submit}>
        <div className="gl-line">
          <label className="gl-lab" htmlFor="gl-q">Szukaj</label>
          <div className="gl-find">
            <div className="gl-field"><Icon name="search" />
              <input id="gl-q" type="search" enterKeyHint="search" autoComplete="off" value={draft} maxLength={120} aria-describedby="gl-q-hint"
                placeholder="Tytuł lub opis głosowania" onChange={e => setDraft(e.target.value)} /></div>
            <button type="submit" className="px-btn" disabled={short}>Szukaj</button>
          </div>
          <p id="gl-q-hint" className="gl-hint" role={short ? 'alert' : undefined} data-bad={short || undefined}>
            {short ? `Wpisz co najmniej ${MIN_QUERY} znaki.` : `Szukamy w tytule i opisie głosowania, od ${MIN_QUERY} znaków.`}</p>
        </div>
        <div className="gl-line">
          <span className="gl-lab" id="gl-club-l">Klub</span>
          <div className="px-chips" role="group" aria-labelledby="gl-club-l">
            <button type="button" aria-pressed={!filters.klub} onClick={() => apply({ klub: '' })}>Wszystkie</button>
            {clubs.map(c => <button key={c} type="button" aria-pressed={filters.klub === c} onClick={() => apply({ klub: c })}>{c}</button>)}
          </div>
        </div>
        <div className="gl-line">
          <span className="gl-lab" id="gl-out-l">Wynik</span>
          <div className="px-seg" role="group" aria-labelledby="gl-out-l">
            {OUTCOMES.map(([k, l]) => <button key={k || 'all'} type="button" aria-pressed={filters.wynik === k} onClick={() => apply({ wynik: k })}>{l}</button>)}
          </div>
        </div>
        <div className="gl-line">
          <span className="gl-lab" id="gl-date-l">Daty</span>
          <div className="gl-dates px-flow__dates" role="group" aria-labelledby="gl-date-l">
            <label>Od <input type="date" value={filters.od} max={filters.do || undefined} onChange={e => apply({ od: e.target.value })} /></label>
            <label>Do <input type="date" value={filters.do} min={filters.od || undefined} onChange={e => apply({ do: e.target.value })} /></label>
            {hasFilters(filters) && <button type="button" className="px-quiet" onClick={reset}>Wyczyść filtry</button>}
          </div>
        </div>
      </form>

      {state === 'loading' && <div className="px-wait gl-wait"><Loading label="Ładowanie głosowań" /></div>}
      {state === 'off' && <p className="px-msg gl-msg" role="status">Funkcja jeszcze wyłączona.</p>}
      {state === 'bad' && <p className="px-msg gl-msg" role="alert">{detail || 'Takie filtry nie są poprawne. Zmień daty albo zapytanie.'} <button type="button" className="px-quiet" onClick={reset}>Wyczyść filtry</button></p>}
      {state === 'error' && <p className="px-msg gl-msg" role="alert">Nie udało się pobrać głosowań. <button type="button" className="px-quiet" onClick={() => void fetchPage(filters, 1, false)}>Spróbuj ponownie</button></p>}

      {state === 'idle' && <>
        <div className="gl-sum">
          <p className="gl-count" role="status">
            {rows.length ? <>Wczytano <b>{rows.length}</b>&nbsp;z&nbsp;<b>{total.toLocaleString('pl-PL')}</b>&nbsp;{plural(total, 'głosowania', 'głosowań', 'głosowań')}{page > 0 && (meta?.pages ?? 1) > 1 ? ` (strona ${page} z ${meta?.pages})` : ''}</> : 'Brak głosowań'}
          </p>
          <div className="gl-tools">
            <div className="px-seg" role="group" aria-label="Sortowanie wczytanych wierszy">
              {SORTS.map(([k, l]) => <button key={k} type="button" aria-pressed={sort.key === k} onClick={() => toggleSort(k)}>{l}
                <i className="gl-dir" aria-hidden="true" data-on={sort.key === k || undefined}>{sort.key === k && sort.dir === 'asc' ? '↑' : '↓'}</i>
                <span className="px-sr">{sort.key === k ? (sort.dir === 'desc' ? ', od największych' : ', od najmniejszych') : ''}</span></button>)}
            </div>
            <button type="button" className="px-tool" onClick={csv} disabled={!rows.length} aria-label={`Pobierz CSV z widocznych wierszy (${sorted.length})`}>
              <Icon name="down" />CSV z widocznych wierszy</button>
          </div>
        </div>
        {(sort.key !== 'date' || sort.dir !== 'desc') && remaining > 0 &&
          <p className="gl-hint gl-sortnote">Sortowanie obejmuje wczytane głosowania ({rows.length} z {total.toLocaleString('pl-PL')}). Pokaż więcej, żeby uporządkować kolejne.</p>}

        {!rows.length && <p className="px-msg gl-msg">{nb(`Brak w naszych danych: głosowań spełniających te filtry (zakres: ${first && last ? `${shortDay(first)} - ${shortDay(last)}` : 'zaimportowane głosowania Sejmu'}, ostatnie głosowanie w bazie: ${shortDay(last) || 'brak daty'}).`)}{' '}
          {hasFilters(filters) && <button type="button" className="px-quiet" onClick={reset}>Wyczyść filtry</button>}</p>}

        {rows.length > 0 && <table className="gl-tbl" data-club={club || undefined}>
          <caption className="px-sr">Głosowania Sejmu: data, tytuł, wynik ogółem{club ? `, głos klubu ${club}` : ''}, źródło</caption>
          <thead><tr>
            <th scope="col" aria-sort={sort.key === 'date' ? (sort.dir === 'desc' ? 'descending' : 'ascending') : undefined}>Data</th>
            <th scope="col">Głosowanie</th>
            <th scope="col" aria-sort={sort.key === 'result' ? (sort.dir === 'desc' ? 'descending' : 'ascending') : undefined}>Wynik ogółem</th>
            {club && <th scope="col">Głos klubu {club}</th>}
            <th scope="col">Źródło</th>
          </tr></thead>
          <tbody>{sorted.map(v => <Row key={v.id} v={v} club={club} />)}</tbody>
        </table>}

        {rows.length > 0 && <>
          {club && <ul className="px-votes__legend gl-legend" aria-hidden="true">
            {['za', 'przeciw', 'wstrzymał się', 'nieobecny'].map(v => <li key={v} data-v={v}><i />{v}</li>)}
          </ul>}
          <p className="gl-hint">{nb(`Wynik ogółem: liczby głosów za, przeciw, wstrzymanych i nieobecnych. „Wynik nieustalony” znaczy: brak w naszych danych wymaganej większości (np. głosowania na listach). Nieobecność nie jest głosem.${club ? ' „Brak w naszych danych” przy klubie znaczy: klub nie ma zapisanych głosów w tym głosowaniu w zaimportowanej bazie.' : ''}`)}</p>
        </>}

        {(remaining > 0 || moreError) && <div className="gl-more">
          {moreError && <span role="alert">Nie udało się pobrać kolejnych głosowań.</span>}
          {remaining > 0 && <button type="button" className="px-more" disabled={busy} onClick={() => void fetchPage(filters, page + 1, true)}>
            {busy ? 'Wczytuję…' : `Pokaż więcej (${remaining.toLocaleString('pl-PL')})`}</button>}
        </div>}
      </>}
    </section>
    <Foot />
  </div>;
}
