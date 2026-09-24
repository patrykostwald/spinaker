import Link from "next/link";
import Image from "next/image";
import type { ThreadListItem } from "../types";
import { formatDatePl } from "../lib/utils";

function threadKind(thread: ThreadListItem) {
  if (thread.thread_type === "sponsored" || thread.is_sponsored) return thread.sponsorship_label || "Nitka sponsorowana";
  return thread.thread_type === "factcheck" ? "Weryfikacja wypowiedzi" : "Kontekst wydarzenia";
}

export function ThreadCard({ thread }: { thread: ThreadListItem }) {
  return <Link href={`/thread/${thread.slug}`} className="sc-thread-card">
    <div className="sc-thread-card__media">
      {thread.image_url ? <Image unoptimized src={thread.image_url} alt="" fill sizes="(min-width: 1024px) 33vw, 100vw" className="sc-thread-card__image" /> : <div className="sc-thread-card__placeholder"><span className="sc-t-caption">Historia w źródłach</span><strong className="sc-t-display">{String(thread.item_count).padStart(2, "0")}</strong><span className="sc-t-meta">materiałów</span></div>}
    </div>
    <div className="sc-thread-card__body"><p className="sc-t-caption sc-thread-card__kind">{threadKind(thread)}</p><h2 className="sc-t-title-m">{thread.title}</h2>{thread.description ? <p className="sc-t-body sc-text-2">{thread.description}</p> : null}<footer className="sc-thread-card__meta sc-t-meta sc-text-2"><span>{thread.item_count} materiałów · {new Intl.NumberFormat("pl-PL", { notation: "compact" }).format(thread.views_count)} wyświetleń</span><span>Utworzono {formatDatePl(thread.created_at)}</span></footer></div>
  </Link>;
}
