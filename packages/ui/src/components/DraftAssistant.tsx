"use client";
import { useState } from 'react';
import { apiWrite, searchTimeline } from '../lib/api';
import { categoryLabel, formatDateTimePl } from '../lib/utils';
import type { Article } from '../types';
import { Button, SearchField } from '../kit';

type Draft = { status: 'draft'; items: Article[]; limitation: string; requires_review: true };
export function DraftAssistant({ articles, onAdd }: { articles: Article[]; onAdd: (article: Article) => void }) {
  const [topic, setTopic] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [draftTopic, setDraftTopic] = useState('');
  return <section className="sc-draft-assistant" aria-labelledby="draft-assistant-title">
    <h2 id="draft-assistant-title" className="sc-t-title-m">spin.clinic · propozycja nitki</h2>
    <p className="sc-t-body sc-text-2">Wpisz temat. Narzędzie zaproponuje do 15 materiałów z bazy i Twojego wyboru. Przed publikacją sprawdź źródła — propozycja opiera się na metadanych, nie rozstrzyga prawdziwości twierdzeń ani związków przyczynowych.</p>
    <p className="sc-t-caption sc-text-2">Na tym etapie analizujemy do 60 kandydatów: wybrane przez Ciebie materiały i pierwsze wyniki wyszukiwania. To propozycja z ograniczonego zestawu, nie pełna historia tematu.</p>
    <form className="sc-draft-assistant__form" onSubmit={async event => {
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
      <SearchField id="draft-topic" required maxLength={500} disabled={busy} label="Temat propozycji dr. Spina" value={topic} onChange={setTopic} placeholder="Temat, wydarzenie lub nazwisko…" />
      <Button type="submit" variant="primary" loading={busy} disabled={!topic.trim()}>{busy ? 'Przygotowuję propozycję…' : 'Poproś o propozycję'}</Button>
    </form>
    <p className="sc-t-caption sc-text-2">Artykuł po URL dodasz w formularzu źródła poniżej. Propozycja nie zmienia ani nie publikuje Twojej nitki.</p>
    {busy && <p role="status" className="sc-t-body sc-text-2">Wyszukujemy materiały i wybieramy kontekst. Możesz nadal przeglądać swoją nitkę.</p>}
    {error && <p role="alert" className="sc-draft-assistant__error">{error}</p>}
    {draft && <div className="sc-draft-assistant__results">
      <h3 className="sc-t-title-s">Do sprawdzenia · {draftTopic}</h3>
      <p className="sc-t-body sc-text-2">{draft.limitation}</p>
      {!draft.items.length && <p>Brak wystarczających materiałów do propozycji.</p>}
      {draft.items.map(article => <div key={article.id} className="sc-draft-assistant__item">
        <div><a className="sc-draft-assistant__link" href={article.url} target="_blank" rel="noopener noreferrer">{article.title} ↗</a><p className="sc-t-caption sc-text-2">{article.source.name} · {categoryLabel(article.category)} · {formatDateTimePl(article.published_date, article.date_precision)}</p></div>
        <Button size="sm" variant="secondary" disabled={articles.some(a => a.id === article.id)} onClick={() => onAdd(article)}>{articles.some(a => a.id === article.id) ? 'Dodano' : 'Dodaj do nitki +'}</Button>
      </div>)}
    </div>}
  </section>;
}
