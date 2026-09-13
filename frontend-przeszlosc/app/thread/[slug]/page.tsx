"use client";
import { ThreadExport, HorizontalTimeline, getThread, ApiError } from '@spin-clinic/ui';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
export default function ThreadPage({ params }: { params: { slug: string } }) {
  const result = useQuery({ queryKey: ['thread', params.slug], queryFn: () => getThread(params.slug), retry: false, refetchOnWindowFocus: false });
  if (result.isPending) return <p role="status">Ładuję historię…</p>;
  if (result.isError) return <div role="alert"><h1 className="text-2xl font-bold">{result.error instanceof ApiError && result.error.status === 404 ? 'Nie znaleziono opublikowanej historii.' : 'Nie udało się pobrać historii.'}</h1><Link href="/" className="mt-4 inline-block text-primary">Wróć na stronę główną</Link></div>;
  const thread = result.data;
  return <article className="space-y-6"><Link href="/" className="text-sm text-primary">← Wszystkie historie</Link>
    <p className="text-sm font-semibold uppercase tracking-widest text-primary">{thread.thread_type === 'sponsored' ? 'Nitka sponsorowana' : 'Kontekst wydarzenia'}</p>
    <h1 className="max-w-4xl text-3xl font-black sm:text-4xl">{thread.title}</h1>
    <p className="max-w-3xl text-lg text-slate-600">{thread.description}</p>
    <p className="text-sm text-slate-500">{thread.item_count} materiałów · {thread.views_count} wyświetleń</p>
    <HorizontalTimeline items={thread.items} />
    <ThreadExport thread={thread} />
  </article>;
}
