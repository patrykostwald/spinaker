"use client";

import { useQuery } from '@tanstack/react-query';
import type { Article } from '@spin-clinic/ui';
import { MaterialSurface, usePortalApi } from '@spin-clinic/ui/kit';
import { ArticleContext, ArticleOpinions, ShareOnX, VotingDetails, getRelatedArticles } from '@spin-clinic/ui';

export default function MaterialView({ article }: { article: Article }) {
  const portal = usePortalApi();
  const related = useQuery({ queryKey: ['article-related', article.id], queryFn: () => getRelatedArticles(article.id), staleTime: 60_000 });
  return <MaterialSurface mode="page" article={article} related={related.data ?? []}
    actionSlot={<ShareOnX title={`${article.title} — ${article.source.name}`} path={`/material/${article.id}`} label="Udostępnij na X" />}
  >
    <ArticleContext article={article} onSelect={(next) => portal.open(next)} />
    {article.voting ? <VotingDetails article={article} /> : null}
    <ArticleOpinions article={article} />
  </MaterialSurface>;
}
