"use client";
import { ThreadExport, ThreadFavoriteButton, ThreadOpinions, ShareOnX, getThread, ApiError } from '@spin-clinic/ui';
import { Button, ThreadView } from '@spin-clinic/ui/kit';
import { useQuery } from '@tanstack/react-query';
export default function ThreadPage({ params }: { params: { slug: string } }) {
  const result = useQuery({ queryKey: ['thread', params.slug], queryFn: () => getThread(params.slug), retry: false, refetchOnWindowFocus: false });
  if (result.isPending) return <p role="status">Ładuję historię…</p>;
  if (result.isError) return <section className="sc-info-page" role="alert"><h1 className="sc-t-display">{result.error instanceof ApiError && result.error.status === 404 ? 'Nie znaleziono opublikowanej historii.' : 'Nie udało się pobrać historii.'}</h1><Button href="/" variant="secondary">Wróć na stronę główną</Button></section>;
  const thread = result.data;
  return <article className="sc-thread-page"><Button href="/" variant="quiet" size="sm">Wszystkie historie</Button>
    <p className="sc-t-meta sc-thread-page__kicker">{thread.is_sponsored || thread.thread_type === 'sponsored' ? thread.sponsorship_label || 'Nitka sponsorowana' : 'Kontekst wydarzenia'}</p>
    <h1 className="sc-t-display sc-thread-page__title">{thread.title}</h1>
    {thread.author_name && <p className="sc-t-meta sc-thread-page__author" data-author-role={thread.author_role}>{thread.author_name} · {thread.author_role === 'journalist' ? 'Dziennikarz' : thread.author_role === 'editor' ? 'Redakcja' : 'Autor'}</p>}
    <p className="sc-t-body sc-text-2 sc-thread-page__description">{thread.description}</p>
    <p className="sc-t-meta sc-text-2">{thread.item_count} materiałów · {thread.views_count} wyświetleń</p>
    <div className="sc-thread-page__actions"><ThreadFavoriteButton thread={thread} /><ShareOnX title={thread.title} path={`/thread/${thread.slug}`} /></div>
    <ThreadView items={thread.items} anchorFirst={Boolean(thread.editorial_slot)} />
    <ThreadOpinions slug={thread.slug} />
    <ThreadExport thread={thread} />
  </article>;
}
