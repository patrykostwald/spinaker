"use client";

import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { MotionRoot, PortalLayer, PortalProvider } from "@spin-clinic/ui/kit";
import { MaterialDetails, apiFetch, type Article } from "@spin-clinic/ui";
import { useCallback, useState, type ReactNode } from "react";

function PortalDataLayer() {
  const client = useQueryClient();
  const resolveArticle = useCallback(async (id: number) => {
    const key = ["article", id] as const;
    return client.ensureQueryData({ queryKey: key, queryFn: () => apiFetch<Article>(`/api/articles/${id}/`), staleTime: 60_000 }).catch(() => null);
  }, [client]);
  // Powiększony box: oś czasu 15 powiązanych, reakcje i komentarze, baza powiązanych (kategorie × daty).
  // Oś czasu zastępuje dawną taśmę „Powiązane materiały”, więc `relatedFor` nie jest już potrzebne.
  const renderDetails = useCallback((article: Article, navigate: (next: Article) => void) => <MaterialDetails article={article} onSelect={navigate} />, []);
  return <PortalLayer resolveArticle={resolveArticle} renderDetails={renderDetails} />;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false } } }));
  return <MotionRoot><QueryClientProvider client={client}><PortalProvider historyMode="path">{children}<PortalDataLayer /></PortalProvider></QueryClientProvider></MotionRoot>;
}
