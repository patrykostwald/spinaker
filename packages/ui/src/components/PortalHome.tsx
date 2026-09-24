"use client";

import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { getPortalConfig } from '../lib/portal';
import { Baza } from './Baza';
import { DrSpin } from './DrSpin';
import { IllustrationStrip } from './IllustrationStrip';
import { NajnowszeWiadomosci } from './NajnowszeWiadomosci';
import { PrzekazDnia } from './PrzekazDnia';
import { TematDnia } from './TematDnia';
import { TopTenRedakcji } from './TopTenRedakcji';
import { SiteFooter } from '../kit/SiteFooter';

export function PortalHome() {
  const params = useSearchParams();
  const q = params.get('q') ?? '';
  const config = useQuery({ queryKey: ['mvp-portal-config'], queryFn: getPortalConfig, refetchInterval: 60_000, refetchIntervalInBackground: false });

  const bazaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (q) bazaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [q]);

  const categories = config.data?.categories ?? [];
  const sources = config.data?.sources ?? [];
  const topSources = config.data?.top_sources ?? [];

  return (
    <div className="sc-portal-home">
      <h1 className="sr-only">Wiadomości i ich kontekst</h1>
      <IllustrationStrip />
      <NajnowszeWiadomosci />
      <TopTenRedakcji topSources={sources.length ? sources : topSources} />
      <TematDnia />
      <DrSpin thread={null} />
      <PrzekazDnia government={config.data?.editorial.government ?? null} opposition={config.data?.editorial.opposition ?? null} />
      <Baza ref={bazaRef} categories={categories} sources={sources} initialQuery={q} />
      <SiteFooter
        brand={<strong>spin<span className="sc-wordmark__dot">.</span>clinic</strong>}
        note={<>Materiały prezentujemy w oryginalnym kontekście źródłowym.<br />Zestawienie publikacji nie jest potwierdzeniem zawartych w nich twierdzeń.</>}
        cta={{ eyebrow: "WSPARCIE PROJEKTU", label: "Wesprzyj spin.clinic", href: "/wsparcie" }}
        columns={[{ title: "Informacje", links: [{ label: "O nas", href: "/o-nas" }, { label: "Źródła", href: "/zrodla" }, { label: "Zasady korzystania", href: "/zasady-korzystania" }, { label: "Prywatność i cookies", href: "/polityka-prywatnosci" }] }]}
      />
    </div>
  );
}
