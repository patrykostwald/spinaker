"use client";
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams, useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiWrite, getMe, searchTimeline } from '../lib/api';
import { categoryLabel, formatDateTimePl } from '../lib/utils';
import type { Article, Paginated, ThreadDetail } from '../types';
import { measurePost } from '../lib/xText';
import { openingPost } from '../lib/xStory';
import { ShareThreadOnX } from './ShareThreadOnX';
import { ImportStatus } from './ImportStatus';
import { DraftAssistant } from './DraftAssistant';
import { Button, SearchField } from '../kit';
const input = 'sc-editor-input';
const button = 'sc-editor-button';
const kinds = ['voting', 'legislation', 'parliamentary_print', 'document', 'factcheck', 'context', 'article', 'interview', 'reportage', 'statement', 'tweet', 'mention', 'sponsored', 'advertisement', 'video', 'podcast', 'opinion', 'other'];
type Picked = { article: Article; editorial_note: string };
/** Autoryzowana nitka dziennikarza: box otwierający + do 14 boxów kontekstu. */
const JOURNALIST_MAX = 15;

export function ThreadEditor() {
  const router = useRouter();
  const params = useSearchParams();
  const slug = params.get('slug');
  const sourceUrl = params.get('source_url') ?? '';
  const cache = useQueryClient();
  const me = useQuery({ queryKey: ['me'], queryFn: getMe, retry: false });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [published, setPublished] = useState(false);
  const [featured, setFeatured] = useState(false);
  const [editorialSlot, setEditorialSlot] = useState<'' | 'government' | 'opposition'>('');
  const [sponsored, setSponsored] = useState(false);
  const [sponsorName, setSponsorName] = useState('');
  const [picked, setPicked] = useState<Picked[]>([]);
  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  const [manual, setManual] = useState(Boolean(sourceUrl));
  const [saved, setSaved] = useState('');
  const [listPage, setListPage] = useState(1);
  const manualForm = useRef<HTMLFormElement>(null);
  const [previewNotice, setPreviewNotice] = useState('');
  const list = useQuery({ queryKey: ['editor-threads', listPage], queryFn: () => apiFetch<Paginated<ThreadDetail>>(`/api/editor/threads/?page=${listPage}`), enabled: Boolean(me.data?.can_edit_threads ?? me.data?.is_editor) });
  const existing = useQuery({ queryKey: ['editor-thread', slug], queryFn: () => apiFetch<ThreadDetail>(`/api/editor/threads/${encodeURIComponent(slug!)}/`), enabled: Boolean(slug && (me.data?.can_edit_threads ?? me.data?.is_editor)) });
  const results = useQuery({ queryKey: ['editor-search', q], queryFn: () => searchTimeline(q), enabled: Boolean(q && (me.data?.can_edit_threads ?? me.data?.is_editor)) });
  useEffect(() => {
    if (!existing.data) return;
    setTitle(existing.data.title); setDescription(existing.data.description); setPublished(existing.data.published); setFeatured(existing.data.is_featured);
    setEditorialSlot(existing.data.editorial_slot ?? '');
    setSponsored(existing.data.is_sponsored ?? false); setSponsorName(existing.data.sponsor_name ?? '');
    setPicked(existing.data.items.map(item => ({ article: item.article, editorial_note: item.editorial_note })));
  }, [existing.data]);
  const canPublish = Boolean(me.data?.can_publish ?? me.data?.is_editor);
  const journalist = !canPublish;
  const add = (article: Article) => setPicked(items => items.some(i => i.article.url === article.url) || (journalist && items.length >= JOURNALIST_MAX)
    ? items : [...items, { article: article.reference_only ? { ...article, id: -(Date.now()) } : article, editorial_note: '' }]);
  const chronological = (items: Picked[]) => [...items].sort((a, b) => (a.article.published_date ?? '9999').localeCompare(b.article.published_date ?? '9999'));
  // Dziennikarz sam ustala kolejność (pierwszy = box otwierający); zespół — chronologia jak dotąd.
  const ordered = journalist ? picked : editorialSlot && picked.length ? [picked[0], ...chronological(picked.slice(1))] : chronological(picked);
  const move = (index: number, delta: number) => setPicked(items => {
    const next = [...items]; const target = index + delta;
    if (target < 0 || target >= next.length) return items;
    [next[index], next[target]] = [next[target], next[index]]; return next;
  });
  const opening = openingPost(title, description, slug ?? '', Math.max(2, picked.length + 1));
  const full = journalist && picked.length >= JOURNALIST_MAX;
  const canEdit = Boolean(me.data?.can_edit_threads ?? me.data?.is_editor);
  if (me.isPending) return <p role="status">Sprawdzam dostęp…</p>;
  if (me.isError) return <div role="alert"><p>Nie udało się połączyć z serwisem.</p><button onClick={() => me.refetch()} className={button}>Spróbuj ponownie</button></div>;
  if (!canEdit) return <section className="sc-editor-login">
    <h1 className="sc-t-title-l">Warsztat</h1><p className="sc-editor-copy">W wersji beta nitki publikuje zespół spin.clinic. Czytanie i przeszukiwanie całej bazy jest dostępne bez konta.</p>
    <form className="sc-editor-stack" onSubmit={async e => {
      e.preventDefault(); const data = new FormData(e.currentTarget); setBusy(true); setError('');
      try { await apiWrite('/api/auth/login/', { username: data.get('username'), password: data.get('password') }); await Promise.all([cache.invalidateQueries({ queryKey: ['me'] }), cache.invalidateQueries({ queryKey: ['account'] })]); }
      catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się zalogować.'); } finally { setBusy(false); }
    }}><label className="sc-editor-field">Login<input required name="username" autoComplete="username" className={input} /></label><label className="sc-editor-field">Hasło<input required name="password" type="password" autoComplete="current-password" className={input} /></label><button disabled={busy} className={button}>{busy ? 'Loguję…' : 'Zaloguj się'}</button></form>{error && <p role="alert" className="sc-editor-error">{error}</p>}
  </section>;
  return <div className="sc-editor">
    {canPublish && <Link href="/editor/sources" className="sc-editor-link">Katalog źródeł · dodawanie, edycja i eksport ↗</Link>}
    {canPublish && <Link href="/editor/political" className="sc-editor-link">Panel przeglądu X · propozycje z zapisanych wpisów ↗</Link>}
    {canPublish && <ImportStatus />}
    <header className="sc-editor__head"><p className="sc-t-caption">WARSZTAT</p><h1 className="sc-t-title-l">{slug ? 'Edytuj nitkę' : journalist ? 'Autoryzowana nitka kontekstowa' : 'Połącz źródła w historię'}</h1><p className="sc-t-body sc-text-2">{journalist ? 'Box otwierający — materiał, który chcesz wypromować — i do 14 boxów kontekstu. Tytuł z opisem to pierwszy wpis wątku na X.' : 'Wybierz materiały, dodaj kontekst i opublikuj chronologiczną nitkę.'}</p></header>
    {slug && existing.isPending && <p role="status">Ładuję nitkę…</p>}
    {slug && existing.isError && <p role="alert" className="sc-editor-error">Nie udało się wczytać nitki. Wróć do listy i spróbuj ponownie.</p>}
    {!canPublish && <p className="sc-editor-notice">Warsztat dziennikarza. Tworzysz własne szkice; publikację zatwierdza zespół spin.clinic. Zmiana opublikowanej nitki wycofa ją do ponownego zatwierdzenia.</p>}
    {canPublish && <DraftAssistant key={slug ?? 'new'} articles={picked.map(item => item.article)} onAdd={add} />}
    <section className="sc-editor-form">
      <label className="sc-editor-field">Tytuł nitki<input required maxLength={255} value={title} onChange={e => setTitle(e.target.value)} className={input} placeholder="Jak rozwijał się ten temat?" /></label>
      <label className="sc-editor-field">{journalist ? `Opis nitki · pierwszy wpis na X ${opening.length}/280` : 'Wprowadzenie'}<textarea maxLength={journalist ? 250 : 5000} value={description} onChange={e => setDescription(e.target.value)} className={input} rows={3} placeholder={journalist ? 'Krótko: o czym jest historia i dlaczego warto ją przejrzeć.' : 'Wyjaśnij, co łączy wybrane źródła.'} />{journalist && !opening.fits && <span className="sc-editor-error">Skróć tytuł albo opis — pierwszy wpis na X ma najwyżej 280 znaków.</span>}</label>
      {canPublish && <label className="sc-editor-field">Sekcja na stronie<select value={editorialSlot} onChange={e => setEditorialSlot(e.target.value as typeof editorialSlot)} className={input}><option value="">Zwykła nitka</option><option value="government">Przekaz dnia obozu rządzącego</option><option value="opposition">Przekaz dnia opozycji</option></select></label>}
      {canPublish && <div className="sc-editor-stack"><label className="sc-editor-check"><input type="checkbox" checked={sponsored} onChange={e => setSponsored(e.target.checked)} />Nitka sponsorowana</label>{sponsored && <label className="sc-editor-field">Nazwa sponsora<input value={sponsorName} onChange={e => setSponsorName(e.target.value)} maxLength={200} required className={input} /><span className="sc-editor-hint">Oznaczenie będzie widoczne w nitce, boxach i eksporcie. Nie zmienia danych źródłowych.</span></label>}</div>}
    </section>
    <section className="sc-editor-stack"><div className="sc-editor-section-head"><h2 className="sc-t-title-m">1. Wybierz materiały z bazy</h2><button className="sc-editor-action" onClick={() => setManual(v => !v)}>{manual ? 'Zamknij formularz źródła' : '+ Dodaj materiał źródłowy'}</button></div>
      {manual && <form ref={manualForm} className="sc-editor-form sc-editor-form--wide" onSubmit={async e => {
        e.preventDefault(); const form = e.currentTarget; const values = Object.fromEntries(new FormData(form)); setBusy(true); setError('');
        try {
          const article = await apiWrite<Article>('/api/editor/articles/', { ...values, published_date: values.published_date ? new Date(String(values.published_date)).toISOString() : null });
          add(article); form.reset(); setManual(false); await cache.invalidateQueries({ queryKey: ['editor-search'] });
        } catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się zapisać materiału.'); } finally { setBusy(false); }
      }}>
        <p className="sc-editor-form-copy">Przepisz dane ze źródła. Opis powinien być wiernym fragmentem lub wyraźnie oznaczonym streszczeniem. Nieznaną datę i autora pozostaw puste.</p>
        <div className="sc-editor-form-actions"><button type="button" disabled={busy} className="sc-editor-action" onClick={async () => {
          const form = manualForm.current!;
          const url = String(new FormData(form).get('url') || '').trim();
          if (!url) { setPreviewNotice('Najpierw wklej adres materiału w polu poniżej.'); return; }
          setBusy(true); setError(''); setPreviewNotice('Pobieram metadane źródła…');
          try {
            const result = await apiWrite<{ reference?: Article; existing?: Article; metadata?: Record<string, unknown> }>('/api/editor/preview-url/', { url });
            if (result.reference) { add(result.reference); setManual(false); setSaved('Dodano odnośnik X do nitki. Nie pobieramy treści wpisu ani nie indeksujemy go w wyszukiwarce.'); }
            else if (result.existing) { add(result.existing); setManual(false); setSaved('Ten materiał jest już w bazie — dodano go do nitki.'); }
            else if (result.metadata) {
              for (const key of ['title', 'source_name', 'description', 'author', 'category', 'published_date', 'image_url']) {
                const field = form.elements.namedItem(key) as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null;
                let value = String(result.metadata[key] || '');
                if (key === 'published_date' && value) { const d = new Date(value); value = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); }
                if (field) field.value = value;
              }
              setPreviewNotice((result.metadata.warnings as string[]).join(' '));
            }
          } catch (err) { setPreviewNotice('Możesz uzupełnić dane ręcznie.'); setError(err instanceof Error ? err.message : 'Nie udało się pobrać źródła.'); }
          finally { setBusy(false); }
        }}>{busy ? 'Proszę czekać…' : 'Pobierz dane z wklejonego adresu'}</button>{previewNotice && <p role="status" className="sc-editor-hint">{previewNotice}</p>}</div>
        <label className="sc-editor-field">Oryginalny tytuł<input name="title" required maxLength={500} className={input} /></label>
        <label className="sc-editor-field">Adres materiału<input name="url" type="url" required maxLength={1024} defaultValue={sourceUrl} className={input} /></label>
        <label className="sc-editor-field">Nazwa źródła<input name="source_name" required maxLength={255} className={input} /></label>
        <label className="sc-editor-field">Kategoria<select name="category" defaultValue="other" className={input}>{kinds.map(k => <option key={k} value={k}>{categoryLabel(k)}</option>)}</select></label>
        <label className="sc-editor-field">Data i godzina publikacji (Twoja strefa czasu)<input name="published_date" type="datetime-local" className={input} /></label>
        <label className="sc-editor-field">Autor<input name="author" maxLength={200} className={input} /></label>
        <label className="sc-editor-field">Zdjęcie (adres https, opcjonalnie)<input name="image_url" type="url" maxLength={1024} className={input} placeholder="https://…/zdjecie.jpg" /></label>
        <label className="sc-editor-field">Opis / fragment<textarea name="description" maxLength={4000} rows={3} className={input} /></label>
        <label className="sc-editor-field">Uwagi o źródle<textarea name="evidence_note" maxLength={4000} rows={3} className={input} /></label>
        <button disabled={busy || full} className={button}>{journalist ? 'Utwórz box i dodaj do nitki' : 'Zapisz materiał i dodaj do nitki'}</button>
        {journalist && <p className="sc-editor-hint">Nowy box trafi do Bazy spin.clinic ze źródłem, datą i linkiem do oryginału.</p>}
      </form>}
      <form className="sc-editor-search" onSubmit={e => { e.preventDefault(); setQ(search.trim()); }}><label className="sr-only" htmlFor="source-search">Szukaj źródeł</label><input id="source-search" value={search} required maxLength={200} onChange={e => setSearch(e.target.value)} placeholder="Szukaj tematu w bazie…" className="sc-editor-input" /><button className={button}>Szukaj</button></form>
      {results.isFetching && <p role="status">Szukam materiałów…</p>}{results.isError && <p role="alert">Nie udało się pobrać materiałów.</p>}
      {results.data && <div className="sc-editor-results">{Object.values(results.data.timeline).flat().map(a => <div key={a.id} className="sc-editor-result"><div><p className="sc-editor-result-title">{a.title}</p><p className="sc-editor-hint">{a.source.name} · {categoryLabel(a.category)} · {formatDateTimePl(a.published_date, a.date_precision)}</p></div><button disabled={picked.some(i => i.article.id === a.id) || full} onClick={() => add(a)} className="sc-editor-action">{picked.some(i => i.article.id === a.id) ? 'Dodano' : full ? 'Limit 15' : 'Dodaj +'}</button></div>)}{!results.data.total && <p>Brak wyników. Możesz dodać materiał ze sprawdzonego źródła.</p>}</div>}
    </section>
    <section><h2 className="sc-t-title-m">{journalist ? `2. Twoja nitka · ${picked.length}/${JOURNALIST_MAX} boxów` : `2. Twoja oś czasu · ${picked.length} materiałów`}</h2><p className="sc-editor-hint">{journalist ? 'Pierwszy box to box otwierający. Kolejność ustalasz strzałkami — tak zobaczą ją czytelnicy i tak pójdzie wątek na X.' : editorialSlot ? 'Wybierz wydarzenie główne. Pozostałe materiały utworzą kontekst od najstarszej publikacji; nieznane daty pozostaną na końcu.' : 'Materiały układamy od najstarszej publikacji. Materiały bez ustalonej daty pojawią się na końcu.'}</p>
      <div className="sc-editor-timeline">{ordered.map((item, index) => <div className="sc-editor-timeline-card" key={item.article.id}>{editorialSlot && <label className="sc-editor-check"><input type="radio" name="main-thread-article" checked={picked[0]?.article.id === item.article.id} onChange={() => setPicked(current => [item, ...current.filter(i => i.article.id !== item.article.id)])} />Wydarzenie główne</label>}{journalist && <p className="sc-editor-hint">{index === 0 ? <strong>Box otwierający</strong> : `Box ${index + 1}`} <button type="button" className="sc-editor-action" disabled={index === 0} onClick={() => move(index, -1)} aria-label="Przesuń wcześniej">←</button> <button type="button" className="sc-editor-action" disabled={index === ordered.length - 1} onClick={() => move(index, 1)} aria-label="Przesuń dalej">→</button></p>}<p className="sc-editor-timeline-date">{index + 1} · {formatDateTimePl(item.article.published_date, item.article.date_precision)}</p><h3 className="sc-editor-result-title">{item.article.title}</h3><a href={item.article.url} target="_blank" rel="noopener noreferrer" className="sc-editor-link-inline">Sprawdź źródło ↗</a><label className="sc-editor-field">Komentarz autora · {measurePost(item.editorial_note).weightedLength}/240<textarea maxLength={5000} rows={4} className={input} value={item.editorial_note} onChange={e => setPicked(current => current.map(i => i.article.id === item.article.id ? { ...i, editorial_note: e.target.value } : i))} /></label><button onClick={() => setPicked(current => current.filter(i => i.article.id !== item.article.id))} className="sc-editor-error">Usuń z nitki</button></div>)}</div>
      {picked.some(i => measurePost(i.editorial_note).weightedLength > 240) && <p role="alert" className="sc-editor-error">Skróć komentarze do 240 znaków ważonych. Pozostałe miejsce jest przeznaczone na numer wpisu i odnośnik.</p>}
    </section>
    <section className="sc-editor-save">{canPublish && <><label className="sc-editor-check"><input type="checkbox" checked={published} onChange={e => { setPublished(e.target.checked); if (!e.target.checked) setFeatured(false); }} />Opublikuj</label><label className="sc-editor-check"><input type="checkbox" checked={featured} disabled={!published} onChange={e => setFeatured(e.target.checked)} />Wyróżnij na głównej</label></>}
      <button disabled={busy || !title.trim() || !picked.length || picked.some(i => measurePost(i.editorial_note).weightedLength > 240) || Boolean(slug && !existing.data) || (journalist && !opening.fits)} className={button} onClick={async () => {
        setBusy(true); setError(''); setSaved('');
        try {
          const result = await apiWrite<{ slug: string; published: boolean }>(slug ? `/api/editor/threads/${encodeURIComponent(slug)}/` : '/api/editor/threads/', { title, description, ...(canPublish ? { published, is_featured: featured, editorial_slot: editorialSlot, is_sponsored: sponsored, sponsor_name: sponsored ? sponsorName : '' } : {}), items: ordered.map(i => ({ ...(i.article.reference_only ? { external_url: i.article.url } : { article_id: i.article.id }), editorial_note: i.editorial_note })) }, slug ? 'PATCH' : 'POST');
          await cache.invalidateQueries({ queryKey: ['editor-threads'] }); await cache.invalidateQueries({ queryKey: ['portal-threads'] }); await cache.invalidateQueries({ queryKey: ['portal-config'] });
          setPublished(result.published); setSaved(result.published ? 'Nitka została opublikowana.' : canPublish ? 'Szkic został zapisany.' : 'Szkic został zapisany. Publikację zatwierdza zespół spin.clinic.'); router.replace(`/editor?slug=${result.slug}`);
        } catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się zapisać nitki.'); } finally { setBusy(false); }
      }}>{busy ? 'Zapisuję…' : canPublish && published ? 'Zapisz i opublikuj' : 'Zapisz szkic'}</button>
      {slug && published && <Link href={`/thread/${slug}`} className="sc-editor-link-inline">Zobacz nitkę ↗</Link>}
      {slug && picked.length > 0 && <ShareThreadOnX thread={{ title, description, slug, items: ordered }} />}
    </section>
    {error && <p role="alert" className="sc-editor-message sc-editor-error">{error}</p>}{saved && <p role="status" className="sc-editor-message">{saved}</p>}
    <section className="sc-editor-saved"><h2 className="sc-t-title-m">Zapisane nitki</h2>{list.data?.results.map(t => <Link key={t.id} href={`/editor?slug=${t.slug}`} className="sc-editor-saved-link">{t.title}<span className="sc-editor-hint">{t.published ? 'Opublikowana' : 'Szkic'}</span></Link>)}{list.data && <div className="sc-editor-pagination"><button disabled={!list.data.previous || list.isFetching} className="sc-editor-action" onClick={() => setListPage(p => p - 1)}>← Poprzednie</button><span>Strona {listPage}</span><button disabled={!list.data.next || list.isFetching} className="sc-editor-action" onClick={() => setListPage(p => p + 1)}>Następne →</button></div>}<a href="/editor" className="sc-editor-link-inline">+ Rozpocznij nową nitkę</a></section>
  </div>;
}


