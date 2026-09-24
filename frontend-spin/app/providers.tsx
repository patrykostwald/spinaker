"use client";

import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { MotionRoot, PortalLayer, PortalProvider, usePortalState } from "@spin-clinic/ui/kit";
import { apiFetch, type Article } from "@spin-clinic/ui";
import { useCallback, useState, type ReactNode } from "react";

function PortalDataLayer() {
  const client = useQueryClient();
  const portal = usePortalState();
  const related = useQuery({
    queryKey: ["article-related", portal.active?.id],
    queryFn: () => apiFetch<{ related: Article[] }>(`/api/articles/${portal.active!.id}/related/`).then((result) => result.related),
    enabled: Boolean(portal.active), staleTime: 60_000,
  });
  const resolveArticle = useCallback(async (id: number) => {
    const key = ["article", id] as const;
    return client.ensureQueryData({ queryKey: key, queryFn: () => apiFetch<Article>(`/api/articles/${id}/`), staleTime: 60_000 }).catch(() => null);
  }, [client]);
  const relatedFor = useCallback((article: Article) => article.id === portal.active?.id ? related.data ?? [] : client.getQueryData<Article[]>(["article-related", article.id]) ?? [], [client, portal.active?.id, related.data]);
  return <PortalLayer resolveArticle={resolveArticle} relatedFor={relatedFor} />;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false } } }));
  return <MotionRoot><QueryClientProvider client={client}><PortalProvider historyMode="path">{children}<PortalDataLayer /></PortalProvider></QueryClientProvider></MotionRoot>;
}
