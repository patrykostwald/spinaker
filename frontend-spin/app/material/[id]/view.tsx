"use client";

import type { Article } from '@spin-clinic/ui';
import { Breadcrumbs, MaterialSurface, usePortalApi } from '@spin-clinic/ui/kit';
import { CiteShare, MaterialDetails, VotingDetails } from '@spin-clinic/ui';

export default function MaterialView({ article }: { article: Article }) {
  const portal = usePortalApi();
  return <>
  <Breadcrumbs items={[{ label: "Główna", href: "/" }, { label: article.title }]} />
  <MaterialSurface mode="page" article={article}
    actionSlot={<CiteShare title={article.title} path={`/material/${article.id}`} author={article.source.name} publishedAt={article.published_date} shareText={`${article.title} — ${article.source.name}`} />}
  >
    <MaterialDetails article={article} onSelect={(next) => portal.open(next)}>
      {article.voting ? <VotingDetails article={article} /> : null}
    </MaterialDetails>
  </MaterialSurface>
  </>;
}
