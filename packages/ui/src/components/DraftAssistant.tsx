"use client";
import { useState } from 'react';
import { apiWrite, searchTimeline } from '../lib/api';
import { categoryLabel, formatDateTimePl } from '../lib/utils';
import type { Article } from '../types';

type Draft = { status: 'draft'; items: Article[]; limitation: string; requires_review: true };
export function DraftAssistant({ articles, onAdd }: { articles: Article[]; onAdd: (article: Article) => void }) {
  const [topic, setTopic] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [draftTopic, setDraftTopic] = useState('');
  return <section className="space-y-3 rounded-xl border p-5" aria-labelledby="draft-assistant-title">
    <h2 id="draft-assistant-title" className="text-xl font-bold">spin.clinic · propozycja nitki</h2>
    <p className="text-sm text-slate-500">Wpisz temat. Narzędzie zaproponuje do 15 materiałów z bazy i Twojego wyboru. Przed publikacją sprawdź źródła — propozycja opiera się na metadanych, nie rozstrzyga prawdziwości twierdzeń ani związków przyczynowych.</p>
    <p className="text-xs text-slate-500">Na tym etapie analizujemy do 60 kandydatów: wybrane przez Ciebie materiały i pierwsze wyniki wyszukiwania. To propozycja z ograniczonego zestawu, nie pełna historia tematu.</p>
    <form className="flex flex-wrap gap-2" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(''); setDraft(null);
      const requestedTopic = topic.trim();
      try {
        const found = await searchTimeline(requestedTopic);
        const candidates = [...articles.filter(a => !a.reference_only), ...Object.values(found.timeline).flat()];
        const ids = [...new Set(candidates.map(a => a.id).filter(id => id > 0))].slice(0, 60);
        if (!ids.length) { setError('Nie mamy jeszcze materiałów dla tego tematu. Najpierw dodaj źródło po URL lub wyszukaj inną frazę.'); return; }
        const result = await apiWrite<Draft>('/api/editor/draft-thread/', { topic: requestedTopic, article_ids: ids });
        setDraft(result); setDraftTopic(requestedTopic);
      } catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się przygotować propozycji. Możesz nadal układać nitkę ręcznie.'); }
      finally { setBusy(false); }
    }}>
      <label className="sr-only" htmlFor="draft-topic">Temat propozycji dr. Spina</label>
      <input id="draft-topic" required maxLength={500} disabled={busy} value={topic} onChange={e => setTopic(e.target.value)} placeholder="Temat, wydarzenie lub nazwisko…" className="min-w-0 flex-1 rounded-lg border bg-white p-3" />
      <button disabled={busy || !topic.trim()} className="rounded-lg bg-primary px-4 py-3 font-semibold text-white disabled:opacity-50">{busy ? 'Przygotowuję propozycję…' : 'Poproś o propozycję'}</button>
    </form>
    <p className="text-xs text-slate-500">Artykuł po URL dodasz w formularzu źródła poniżej. Propozycja nie zmienia ani nie publikuje Twojej nitki.</p>
    {busy && <p role="status" className="text-sm text-slate-500">Wyszukujemy materiały i wybieramy kontekst. Możesz nadal przeglądać swoją nitkę.</p>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {draft && <div className="space-y-3">
      <h3 className="font-semibold">Do sprawdzenia · {draftTopic}</h3>
      <p className="text-sm text-slate-500">{draft.limitation}</p>
      {!draft.items.length && <p>Brak wystarczających materiałów do propozycji.</p>}
      {draft.items.map(article => <div key={article.id} className="flex items-center justify-between gap-4 border-t py-3">
        <div><a className="font-medium" href={article.url} target="_blank" rel="noopener noreferrer">{article.title} ↗</a><p className="text-xs text-slate-500">{article.source.name} · {categoryLabel(article.category)} · {formatDateTimePl(article.published_date, article.date_precision)}</p></div>
        <button className="shrink-0 rounded-lg border px-3 py-2 text-sm text-primary disabled:opacity-40" disabled={articles.some(a => a.id === article.id)} onClick={() => onAdd(article)}>{articles.some(a => a.id === article.id) ? 'Dodano' : 'Dodaj do nitki +'}</button>
      </div>)}
    </div>}
  </section>;
}
