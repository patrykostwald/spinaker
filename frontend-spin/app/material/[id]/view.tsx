"use client";

import type { Article } from '@spin-clinic/ui';
import { MaterialSurface, usePortalApi } from '@spin-clinic/ui/kit';
import { MaterialDetails, ShareOnX, VotingDetails } from '@spin-clinic/ui';

export default function MaterialView({ article }: { article: Article }) {
  const portal = usePortalApi();
  return <MaterialSurface mode="page" article={article}
    actionSlot={<ShareOnX title={`${article.title} — ${article.source.name}`} path={`/material/${article.id}`} label="Udostępnij na X" />}
  >
    <MaterialDetails article={article} onSelect={(next) => portal.open(next)}>
      {article.voting ? <VotingDetails article={article} /> : null}
    </MaterialDetails>
  </MaterialSurface>;
}
