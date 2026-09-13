"use client";

import Image from "next/image";
import { useQuery, type InfiniteData } from '@tanstack/react-query';
import type { ArticleContext } from '../lib/portal';

import { categoryLabel, cn, formatDateTimePl } from "../lib/utils";
import type { Article } from "../types";
import { voteLabel } from './VotingDetails';

type Props = {
  article: Article;
  note?: string;
  authorName?: string;
  authorRole?: 'editor' | 'journalist' | 'reader';
  sponsorshipLabel?: string;
  showNote?: boolean;
  onSelect?: (article: Article) => void;
};

export function ArticleCard({ article, onSelect, note, authorName, authorRole, sponsorshipLabel, showNote }: Props) {
  // Subscribe to already fetched context only. Hundreds of cards must not each
  // launch a full-archive count; opening the modal supplies the actual count.
  const context = useQuery<InfiniteData<ArticleContext>>({ queryKey: ['article-context', article.id], enabled: false });
  const relatedCount = context.data?.pages[0]?.total;
  return (
    <button
      type="button"
      onClick={() => onSelect?.(article)}
      className="source-card group flex w-full flex-1 flex-col overflow-hidden rounded-sm bg-white text-left"
    >
      {sponsorshipLabel && <span className="card-sponsorship">{sponsorshipLabel}</span>}
      <div className="relative aspect-[16/9] bg-slate-100">
        {article.image_url ? (
          <Image
            unoptimized
            src={article.image_url}
            alt=""
            fill
            sizes="(max-width: 768px) 100vw, 33vw"
            className="object-cover"
          />
        ) : (
          <div className="missing-thumbnail" aria-hidden="true">Brak miniatury źródłowej</div>
        )}
        <span
          data-category={article.category}
          className={cn(
            "absolute left-3 top-3 rounded-full px-2 py-0.5 text-xs font-semibold text-white",
            "bg-primary",
          )}
        >
          {categoryLabel(article.category)}
        </span>
        {note && <div className={`absolute inset-0 overflow-y-auto bg-slate-950/90 p-4 text-sm leading-relaxed text-white transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 ${showNote ? 'opacity-100' : 'opacity-0'}`}><p data-author-role={authorRole ?? 'editor'} className="thread-note-author mb-2 font-semibold">{authorName || 'Redakcja'} · komentarz</p><p className="whitespace-pre-wrap">{note}</p></div>}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-3">
        <h3 className="line-clamp-3 text-sm font-semibold leading-snug text-slate-900">{article.title}</h3>
        {article.voting && <p className="line-clamp-2 text-xs text-slate-600">{article.voting.motion}</p>}
        {article.voting?.matching_ballots.slice(0, 3).map(ballot => <p key={ballot.mp_id} className="rounded bg-rose-50 px-2 py-1 text-xs text-slate-800">{ballot.name}: <strong>{voteLabel(ballot.vote)}</strong></p>)}
        <p className="mt-auto text-xs text-slate-500">
          {article.source.name} · {formatDateTimePl(article.published_date, article.date_precision)}
        </p>
        <span className="card-context-link">Powiązania{relatedCount !== undefined ? ` · ${relatedCount.toLocaleString('pl-PL')}` : ''} <span aria-hidden="true">↗</span></span>
      </div>
    </button>
  );
}
