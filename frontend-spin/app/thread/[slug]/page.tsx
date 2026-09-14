"use client";
import { ThreadExport, ThreadFavoriteButton, HorizontalTimeline, ShareOnX, getThread, ApiError } from '@spin-clinic/ui';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
export default function ThreadPage({ params }: { params: { slug: string } }) {
  const result = useQuery({ queryKey: ['thread', params.slug], queryFn: () => getThread(params.slug), retry: false, refetchOnWindowFocus: false });
  if (result.isPending) return <p role="status">Ładuję historię…</p>;
  if (result.isError) return <div role="alert"><h1 className="text-2xl font-bold">{result.error instanceof ApiError && result.error.status === 404 ? 'Nie znaleziono opublikowanej historii.' : 'Nie udało się pobrać historii.'}</h1><Link href="/" className="mt-4 inline-block text-primary">Wróć na stronę główną</Link></div>;
  const thread = result.data;
  return <article className="space-y-6"><Link href="/" className="text-sm text-primary">← Wszystkie historie</Link>
    <p className="text-sm font-semibold uppercase tracking-widest text-primary">{thread.is_sponsored || thread.thread_type === 'sponsored' ? thread.sponsorship_label || 'Nitka sponsorowana' : 'Kontekst wydarzenia'}</p>
    <h1 className="max-w-4xl text-3xl font-black sm:text-4xl">{thread.title}</h1>
    {thread.author_name && <p className="thread-note-author text-sm" data-author-role={thread.author_role}>{thread.author_name} · {thread.author_role === 'journalist' ? 'Dziennikarz' : thread.author_role === 'editor' ? 'Redakcja' : 'Autor'}</p>}
    <p className="max-w-3xl text-lg text-slate-600">{thread.description}</p>
    <p className="text-sm text-slate-500">{thread.item_count} materiałów · {thread.views_count} wyświetleń</p>
    <div className="thread-actions"><ThreadFavoriteButton thread={thread} /><ShareOnX title={thread.title} path={`/thread/${thread.slug}`} /></div>
    <HorizontalTimeline items={thread.items} anchorFirst={Boolean(thread.editorial_slot)} />
    <ThreadExport thread={thread} />
  </article>;
}
