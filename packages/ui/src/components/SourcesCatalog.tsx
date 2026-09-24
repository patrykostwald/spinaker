'use client';
import { useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { apiFetch, apiWrite, getMe } from '../lib/api';
import { ThreadEditor } from './ThreadEditor';
import { Button, SearchField } from '../kit';

type CatalogSource = {
  id: number; name: string; url: string; source_type: string; rss_url: string;
  is_active: boolean; scrape_enabled: boolean; scrape_frequency_minutes: number;
  catalog_notes: string; catalog_stage: 'candidate' | 'configured' | 'excluded'; article_count: number;
  last_scraped: string | null; last_attempted: string | null; last_error: string;
  oldest_publication: string | null; newest_publication: string | null;
  access_check?: {checked_at?: string; configuration_changed?: boolean; skipped_reason?: string;
    rss?: {status: string; url?: string; usable_entry_count?: number; error?: string};
    archive?: {status: string; sitemap_urls?: string[]; listing_urls?: string[]};
    official_api?: {status: string; url?: string}; recommendation?: string} | null;
  archive_status?: {pending: number; running: number; error: number; done: number; last_checked: string | null};
};
type Catalog = {sources: CatalogSource[]; source_types: {value: string; label: string}[]};
type Form = {catalog_stage: 'candidate' | 'configured' | 'excluded'; name: string; url: string; source_type: string; rss_url: string; catalog_notes: string; scrape_frequency_minutes: number};
const emptyForm: Form = {catalog_stage: 'candidate', name: '', url: '', source_type: 'portal', rss_url: '', catalog_notes: '', scrape_frequency_minutes: 60};
const input = 'sc-source-editor__input';
const button = 'sc-source-editor__button';
function sourceState(source: CatalogSource) {
  return source.catalog_stage === 'excluded' ? 'excluded' : source.catalog_stage === 'candidate' ? 'candidate' : source.is_active && source.scrape_enabled ? 'active' : 'disabled';
}
const states = {excluded: 'Wykluczone', candidate: 'Kandydat', active: 'Import włączony', disabled: 'Import wyłączony'};
const rssStates: Record<string,string> = {working: 'działa', empty: 'kanał bez materiałów', unavailable: 'niedostępny w próbie', not_found: 'nie znaleziono', unknown: 'nieustalone'};
const archiveMethods: Record<string,string> = {sitemap: 'mapy witryny', html_candidate: 'lista na stronie do podłączenia', unavailable: 'niedostępna metoda', unknown: 'metoda nieustalona'};
function dateLabel(value: string | null) {
  if (!value) return 'Jeszcze nie odnotowano';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Data nieustalona' : new Intl.DateTimeFormat('pl-PL', {dateStyle: 'short', timeStyle: 'short'}).format(date);
}
export function SourcesCatalog() {
  const cache = useQueryClient();
  const me = useQuery({queryKey: ['me'], queryFn: getMe, retry: false});
  const catalog = useQuery({queryKey: ['editor-sources'], queryFn: () => apiFetch<Catalog>('/api/editor/sources/'), enabled: Boolean(me.data?.is_editor)});
  const [query, setQuery] = useState('');
  const [state, setState] = useState('included');
  const [kind, setKind] = useState('all');
  const [editing, setEditing] = useState<CatalogSource | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<Form>(emptyForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const formElement = useRef<HTMLFormElement>(null);
  const rows = catalog.data?.sources ?? [];
  const filtered = useMemo(() => {
    const phrase = query.trim().toLocaleLowerCase('pl-PL');
    return rows.filter(row => (!phrase || [row.name, row.url, row.rss_url, row.catalog_notes].join(' ').toLocaleLowerCase('pl-PL').includes(phrase))
      && (state === 'all' || (state === 'included' ? sourceState(row) !== 'excluded' : sourceState(row) === state)) && (kind === 'all' || row.source_type === kind));
  }, [rows, query, state, kind]);
  function edit(source: CatalogSource | null) {
    setEditing(source); setForm(source ? {catalog_stage: source.catalog_stage, name: source.name, url: source.url, source_type: source.source_type, rss_url: source.rss_url, catalog_notes: source.catalog_notes, scrape_frequency_minutes: source.scrape_frequency_minutes} : {...emptyForm});
    setShowForm(true); setError(''); setNotice('');
    window.setTimeout(() => { formElement.current?.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'}); formElement.current?.querySelector('input')?.focus({preventScroll: true}); }, 0);
  }
  async function toggle(source: CatalogSource) {
    const enable = sourceState(source) !== 'active';
    setBusy(true); setError(''); setNotice('');
    try {
      await apiWrite(`/api/editor/sources/${source.id}/`, {is_active: enable, scrape_enabled: enable}, 'PATCH');
      await cache.invalidateQueries({queryKey: ['editor-sources']});
      setNotice(`${source.name}: ${enable ? 'włączono pobieranie' : 'wyłączono pobieranie'}. Zgromadzone materiały pozostają w bazie.`);
    } catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się zmienić stanu źródła.'); }
    finally { setBusy(false); }
  }
  async function excludeOrRestore(source: CatalogSource) {
    const restore = source.catalog_stage === 'excluded';
    setBusy(true); setError(''); setNotice('');
    try {
      await apiWrite(`/api/editor/sources/${source.id}/`, {catalog_stage: restore ? 'candidate' : 'excluded', is_active: false, scrape_enabled: false}, 'PATCH');
      await cache.invalidateQueries({queryKey: ['editor-sources']});
      setNotice(`${source.name}: ${restore ? 'przywrócono jako nieaktywnego kandydata' : 'wykluczono z bieżącej listy'}. Zgromadzone materiały pozostają w bazie.`);
    } catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się zmienić wpisu.'); }
    finally { setBusy(false); }
  }
  if (me.isPending) return <p role="status">Sprawdzam dostęp…</p>;
  if (me.isError) return <div role="alert"><p>Nie udało się sprawdzić dostępu.</p><button onClick={() => me.refetch()} className={button}>Spróbuj ponownie</button></div>;
  if (!me.data?.is_editor) return <ThreadEditor />;
  return <div className="sc-source-editor">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><Link href="/editor" className="sc-source-editor__back">← Warsztat redakcji</Link><h1 className="sc-t-title-l">Katalog źródeł</h1><p className="sc-t-body sc-text-2">Jedna lista mediów i instytucji. Zapis kandydata nie uruchamia importu. Wykluczenie usuwa wpis z bieżącej listy i zatrzymuje pobieranie, zachowując historię oraz materiały.</p></div><div className="flex flex-wrap gap-2"><button disabled={busy} onClick={() => edit(null)} className={button}>+ Dodaj źródło</button><a href="/api/editor/sources/export/" className={button} download>Eksport całego katalogu CSV</a></div></div>
    {error && <p role="alert" className="rounded-lg border border-rose-400/30 p-3 text-sm text-rose-300">{error}</p>}
    {notice && <p role="status" className="rounded-lg border p-3 text-sm">{notice}</p>}
    {showForm && <form ref={formElement} className="grid scroll-mt-4 gap-4 rounded-xl border p-4 md:grid-cols-2" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(''); setNotice('');
      try {
        const payload = form.catalog_stage !== 'configured' ? {...form, is_active: false, scrape_enabled: false} : form;
        await apiWrite(editing ? `/api/editor/sources/${editing.id}/` : '/api/editor/sources/', payload, editing ? 'PATCH' : 'POST');
        setNotice(editing ? `Zapisano zmiany źródła: ${form.name}.` : `Dodano kandydata: ${form.name}. Import pozostaje wyłączony.`);
        setShowForm(false); await cache.invalidateQueries({queryKey: ['editor-sources']});
      } catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się zapisać źródła.'); }
      finally { setBusy(false); }
    }}>
      <h2 className="text-lg font-medium md:col-span-2">{editing ? `Edytuj: ${editing.name}` : 'Nowe źródło'}</h2>
      <label className="text-sm">Nazwa<input required maxLength={255} value={form.name} onChange={event => setForm({...form, name: event.target.value})} className={input} disabled={busy} /></label>
      <label className="text-sm">Adres strony · wymagany dla skonfigurowanego źródła<input required={form.catalog_stage === 'configured'} type="url" maxLength={4096} value={form.url} onChange={event => setForm({...form, url: event.target.value})} placeholder="https://…" className={input} disabled={busy} /></label>
      <label className="text-sm">Rodzaj źródła<select value={form.source_type} onChange={event => setForm({...form, source_type: event.target.value})} className={input} disabled={busy}>{(catalog.data?.source_types ?? [{value: 'portal', label: 'Portal'}]).map(type => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
      <label className="text-sm">Adres RSS · opcjonalnie<input type="url" maxLength={4096} value={form.rss_url} onChange={event => setForm({...form, rss_url: event.target.value})} placeholder="https://…" className={input} disabled={busy} /></label>
      <label className="text-sm md:col-span-2">Notatki<textarea rows={3} maxLength={10000} value={form.catalog_notes} onChange={event => setForm({...form, catalog_notes: event.target.value})} className={input} disabled={busy} /></label>
      {editing && <label className="text-sm">Etap<select value={form.catalog_stage} onChange={event => setForm({...form, catalog_stage: event.target.value as Form['catalog_stage']})} className={input} disabled={busy}><option value="candidate">Kandydat</option><option value="configured">Skonfigurowane</option><option value="excluded">Wykluczone</option></select><span className="mt-1 block text-xs text-slate-400">Skonfigurowane nie oznacza sprawdzonego importu. Zmiana etapu nie włącza pobierania; powrót do kandydata lub wykluczenie wyłącza pobieranie.</span></label>}
      {editing && <label className="text-sm">Odstęp między pobraniami · minuty<input required type="number" min={1} max={10080} value={form.scrape_frequency_minutes} onChange={event => setForm({...form, scrape_frequency_minutes: Number(event.target.value)})} className={input} disabled={busy} /><span className="mt-1 block text-xs text-slate-400">Większa liczba oznacza rzadsze pobieranie.</span></label>}
      <div className="flex flex-wrap items-center gap-3 md:col-span-2"><button type="submit" disabled={busy} className={button}>{busy ? 'Zapisuję…' : 'Zapisz źródło'}</button><button type="button" disabled={busy} onClick={() => setShowForm(false)} className={button}>Anuluj</button>{(!editing || editing.catalog_stage === 'candidate') && <p className="sc-source-editor__back">Kandydat wymaga sprawdzenia i konfiguracji przed uruchomieniem pobierania.</p>}</div>
    </form>}
    {catalog.isPending ? <p role="status">Ładuję pełny katalog…</p> : catalog.isError ? <div role="alert"><p>Nie udało się pobrać katalogu.</p><button className={button} onClick={() => catalog.refetch()}>Spróbuj ponownie</button></div> : <>
      <div className="flex flex-wrap gap-x-6 gap-y-2 border-y py-3 text-sm"><span>Wszystkie: <strong>{rows.length}</strong></span><span>Włączone: <strong>{rows.filter(row => sourceState(row) === 'active').length}</strong></span><span>Kandydaci: <strong>{rows.filter(row => sourceState(row) === 'candidate').length}</strong></span><span>Wyłączone: <strong>{rows.filter(row => sourceState(row) === 'disabled').length}</strong></span><span>Wykluczone: <strong>{rows.filter(row => sourceState(row) === 'excluded').length}</strong></span></div>
      <div className="grid items-end gap-3 md:grid-cols-[minmax(0,1fr)_auto_auto]"><label className="text-sm">Szukaj w katalogu<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Nazwa, adres lub notatka…" className={input} /></label><label className="text-sm">Stan<select value={state} onChange={event => setState(event.target.value)} className={input}><option value="included">Bieżący katalog</option><option value="all">Wszystkie, także wykluczone</option><option value="excluded">Wykluczone</option><option value="active">Włączone</option><option value="candidate">Kandydaci</option><option value="disabled">Wyłączone</option></select></label><label className="text-sm">Rodzaj<select value={kind} onChange={event => setKind(event.target.value)} className={input}><option value="all">Wszystkie rodzaje</option>{catalog.data?.source_types.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label></div>
      <p role="status" className="sc-source-editor__back">Wyświetlono {filtered.length} z {rows.length} źródeł. Eksport obejmuje cały katalog, niezależnie od filtrów.</p>
      <div className="space-y-0">{filtered.map(source => <article key={source.id} className="border-t py-4"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-3"><h2 className="text-base font-medium">{source.name}</h2><span className="text-xs text-primary">{states[sourceState(source)]}</span><span className="sc-source-editor__back">{catalog.data?.source_types.find(type => type.value === source.source_type)?.label ?? source.source_type}</span></div>{source.url ? <a href={source.url} target="_blank" rel="noopener noreferrer" className="mt-1 block break-all text-xs text-slate-400 underline underline-offset-4">{source.url}</a> : <p className="mt-1 text-xs text-slate-400">Adres do uzupełnienia</p>}</div><div className="flex flex-wrap gap-2"><button className={button} disabled={busy} onClick={() => edit(source)}>Edytuj</button>{source.catalog_stage === 'configured' && <button className={button} disabled={busy} onClick={() => toggle(source)}>{sourceState(source) === 'active' ? 'Wyłącz import' : 'Włącz import'}</button>}<button className={button} disabled={busy} onClick={() => excludeOrRestore(source)}>{source.catalog_stage === 'excluded' ? 'Przywróć jako kandydata' : 'Wyklucz z katalogu'}</button></div></div>
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-400"><span>Materiały: {source.article_count}</span><span>Odstęp RSS: {source.scrape_frequency_minutes} min</span><span>Ostatni odbiór RSS: {dateLabel(source.last_scraped)}</span><span>Ostatnia próba RSS: {dateLabel(source.last_attempted)}</span></div>
        {source.archive_status && <p className="mt-2 text-xs text-slate-400">Archiwum: {source.archive_status.done} zakończonych zadań · {source.archive_status.pending} oczekujących · {source.archive_status.running} w toku · {source.archive_status.error} z błędem · ostatnia kontrola: {dateLabel(source.archive_status.last_checked)}</p>}
        <p className="mt-2 text-xs text-slate-400">Zapisane daty publikacji: {source.oldest_publication ? `${dateLabel(source.oldest_publication)} — ${dateLabel(source.newest_publication)}` : 'Jeszcze brak datowanych materiałów'}. Zakres nie oznacza kompletnego archiwum.</p>
        {source.access_check?.checked_at ? <div className="mt-3 border-l border-white/20 pl-3 text-xs text-slate-400">
          <p>Kontrola dostępu: {dateLabel(source.access_check.checked_at)}</p>
          {source.access_check.configuration_changed && <p className="mt-1 text-amber-200">Adresy zmieniono od ostatniej kontroli. Wynik wymaga odświeżenia.</p>}
          <p className="mt-1">RSS: {rssStates[source.access_check.rss?.status ?? 'unknown'] ?? 'nieustalone'} · Archiwum: {source.access_check.official_api?.status === 'working' ? 'oficjalne API' : archiveMethods[source.access_check.archive?.status ?? 'unknown'] ?? 'metoda nieustalona'}</p>
          {source.access_check.recommendation && <p className="mt-1">{source.access_check.recommendation}</p>}
          <details className="mt-2"><summary className="cursor-pointer">Sprawdzone adresy</summary>
            {[source.access_check.rss?.url, source.access_check.official_api?.url, ...(source.access_check.archive?.sitemap_urls ?? []), ...(source.access_check.archive?.listing_urls ?? [])].filter((url): url is string => Boolean(url && /^https?:\/\//.test(url))).map((url,index) => <a key={`${index}-${url}`} href={url} target="_blank" rel="noopener noreferrer" className="mt-1 block break-all underline">{url}</a>)}
          </details>
        </div> : <p className="mt-2 text-xs text-amber-200">RSS i metoda archiwum: oczekuje na kontrolę.</p>}
        {source.rss_url && <p className="mt-2 break-all text-xs text-slate-400">RSS: <a href={source.rss_url} target="_blank" rel="noopener noreferrer" className="underline">{source.rss_url}</a></p>}
        {source.catalog_notes && <details className="mt-2 text-sm text-slate-400"><summary className="cursor-pointer">Notatki i historia zgłoszenia</summary><p className="mt-2 text-xs">Zapisane uwagi mogą opisywać wcześniejszy stan weryfikacji. Obecne ustawienie importu widzisz przy nazwie źródła.</p><p className="mt-2 whitespace-pre-wrap">{source.catalog_notes}</p></details>}
        {source.last_error && <p className="mt-2 text-xs text-rose-300">Ostatni błąd pobierania: {source.last_error}</p>}
      </article>)}</div>
      {!filtered.length && <p className="py-8 text-center text-sm text-slate-400">Brak źródeł pasujących do filtrów.</p>}
    </>}
  </div>;
}
