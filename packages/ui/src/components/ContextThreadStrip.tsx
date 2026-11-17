"use client";
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { getCommunityThreads } from '../lib/community';
import { useFeature } from '../lib/features';
import { AccountDataState } from './AccountPhase2';

/**
 * Przykładowa autoryzowana nitka kontekstowa: poziomy pasek boxów (O nas i zaproszenie dla dziennikarzy na głównej).
 * Box otwierający (materiał do wypromowania) → do 14 boxów kontekstu, razem najwyżej 15. Przykład jest wymyślony.
 */
export const EXAMPLE_THREAD = {
  title: 'Przetarg w spółce miejskiej - cała historia w pięciu materiałach',
  description: 'Od wywiadu z byłym dyrektorem do dokumentów przetargu: co wiedziano, kiedy i kto ostrzegał.',
  boxes: [
    { kind: 'Wywiad', source: 'Państwa redakcja', title: 'Rozmowa z byłym dyrektorem spółki: „Ostrzegałem zarząd pół roku wcześniej”', date: '12.09', opening: true },
    { kind: 'Komunikat', source: 'Prokuratura Krajowa', title: 'Zatrzymanie trzech osób w sprawie przetargu', date: '14.09' },
    { kind: 'Artykuł', source: 'inna redakcja', title: 'Kim są zatrzymani i co łączy ich ze spółką', date: '15.09' },
    { kind: 'Film', source: 'kanał YouTube', title: 'Nagranie z posiedzenia rady nadzorczej', date: '16.09' },
    { kind: 'Śledztwo', source: 'Państwa redakcja', title: 'Jak rozpisano przetarg - dokumenty krok po kroku', date: '18.09' },
  ],
};

type ContextTarget = { articleId?: number; figureId?: number; url?: string };
export function ContextThreadStrip(props: ContextTarget = {}) {
  const THREADS_ENABLED = useFeature('THREADS_ENABLED');
  if (props.articleId || props.figureId || props.url) return THREADS_ENABLED ? <RelatedThreads {...props} /> : null;
  return THREADS_ENABLED ? <ExampleStrip /> : null;
}
function RelatedThreads({ articleId, figureId, url }: ContextTarget) {
  const query = useQuery({ queryKey: ['context-thread-strip', articleId, figureId, url], retry: false,
    queryFn: () => getCommunityThreads(1, '', '', { article_id: articleId, figure_id: figureId, url }) });
  // Older backends ignore unknown filters. Do not claim unrelated threads contain this material.
  const rows = query.data?.context_filtered ? query.data.results : [];
  return <section className="sc-f2-context" aria-label="W spinkach"><h2>W spinkach</h2>
    {figureId && <p>Spinki zawierające materiały z potwierdzonym powiązaniem z tą osobą.</p>}
    <AccountDataState query={query} empty="Spinki będą dostępne wkrótce." />
    {query.isSuccess && !rows.length && <p>{query.data.context_filtered ? 'Nie ma jeszcze publicznych spinek z tym materiałem lub powiązaniem.' : 'Powiązane spinki będą dostępne wkrótce.'}</p>}
    {rows.length > 0 && <ul>{rows.slice(0, 3).map(thread => <li key={thread.id}><p className="sc-f2-muted">@{thread.author} · {thread.items_count} materiałów</p><Link href={`/spinki/${thread.id}`}>{thread.title}</Link></li>)}</ul>}
    {rows.length > 3 && <Link href={`/spinki?${new URLSearchParams(articleId ? { article_id: String(articleId) } : figureId ? { figure_id: String(figureId) } : { url: url! })}`}>Wszystkie powiązane spinki</Link>}
  </section>;
}
function ExampleStrip() {
  return (
    <figure className="sc-ctx__strip-wrap">
      <ol className="sc-ctx__strip" aria-label="Przykładowa spinka">
        {EXAMPLE_THREAD.boxes.map((box, index) => (
          <li key={box.title} className="sc-ctx__box" data-opening={box.opening || undefined}>
            {box.opening ? <span className="sc-ctx__badge">Box otwierający</span> : <span className="sc-ctx__num">{index + 1}</span>}
            <span className="sc-ctx__thumb" aria-hidden="true" />
            <span className="sc-ctx__kind">{box.kind}</span>
            <strong>{box.title}</strong>
            <small>{box.source} · {box.date}</small>
          </li>
        ))}
        <li className="sc-ctx__more" aria-label="5 z 15 możliwych boxów">5/15</li>
      </ol>
      <figcaption className="sc-ctx__caption">Przykład wymyślony - pokazuje zasadę, nie prawdziwą sprawę.</figcaption>
    </figure>
  );
}
