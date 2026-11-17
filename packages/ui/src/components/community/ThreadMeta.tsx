"use client";

import Link from 'next/link';
import type { CommunityThreadSummary } from '../../lib/community';
import { authorColor, kindTint, THREAD_KINDS, threadKind } from '../../lib/threadKind';

/**
 * Linia meta nad tytułem spinki (właściciel 6.10): AUTOR w jego kolorze (Dr. Spin niebieski, czytelnik - kolor nicka)
 * i RODZAJ spinki w kolorze przeważającej reakcji czytelników (bez reakcji neutralny). Jedna linia.
 * `withAuthor={false}` w wierszu listy, gdzie autor stoi już z lewej.
 */
export function ThreadMeta({ thread, withAuthor = true, className = 'sc-sp-meta' }: { thread: CommunityThreadSummary; withAuthor?: boolean; className?: string }) {
  const kind = THREAD_KINDS[threadKind(thread)];
  const tint = kindTint(thread);
  const who = thread.is_ai ? 'Dr. Spin (AI)' : thread.display_name || `@${thread.author}`;
  return <p className={className}>
    {withAuthor && <>{thread.is_ai
      ? <span className="sc-sp-meta__who" style={{ color: authorColor(thread) }}>{who}</span>
      : <Link className="sc-sp-meta__who" style={{ color: authorColor(thread) }} href={`/profile/${encodeURIComponent(thread.author)}`}>{who}</Link>}
      <span className="sc-sp-meta__sep" aria-hidden="true">·</span></>}
    <span className="sc-sp-meta__kind" data-tinted={tint ? '' : undefined} style={tint ? { color: tint } : undefined}
      title={tint ? 'Kolor według ocen czytelników' : 'Bez ocen czytelników'}>{kind.label}</span>
  </p>;
}
