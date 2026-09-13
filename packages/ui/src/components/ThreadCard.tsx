import Link from 'next/link';
import Image from 'next/image';
import type { ThreadListItem } from '../types';
import { formatDatePl } from '../lib/utils';
export function ThreadCard({ thread }: { thread: ThreadListItem }) {
  return <Link href={`/thread/${thread.slug}`} className="group flex h-full flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-md transition hover:-translate-y-1 hover:shadow-xl">
    <div className="relative h-48 overflow-hidden bg-slate-100">
      {thread.image_url ? <Image unoptimized src={thread.image_url} alt="" fill sizes="(min-width: 1024px) 33vw, 100vw" className="object-cover" /> : <div className="flex h-full flex-col justify-center px-6 text-primary"><span className="text-sm font-semibold uppercase tracking-widest">Historia w źródłach</span><span className="mt-3 text-5xl font-black">{String(thread.item_count).padStart(2, '0')}<span className="text-xl"> materiałów</span></span><div className="mt-5 border-t-2 border-current" /></div>}
    </div>
    <div className="flex flex-1 flex-col gap-3 p-5">
      <p className="text-xs font-semibold uppercase tracking-widest text-primary">{thread.thread_type === 'factcheck' ? 'Weryfikacja wypowiedzi' : 'Kontekst wydarzenia'}</p>
      <h2 className="line-clamp-2 text-lg font-bold group-hover:text-primary">{thread.title}</h2>
      <p className="line-clamp-2 text-sm text-slate-600">{thread.description}</p>
      <p className="mt-auto text-xs text-slate-500">{thread.item_count} materiałów · {new Intl.NumberFormat('pl-PL', { notation: 'compact' }).format(thread.views_count)} wyświetleń</p>
      <p className="text-xs text-slate-400">Utworzono {formatDatePl(thread.created_at)}</p>
    </div>
  </Link>;
}
