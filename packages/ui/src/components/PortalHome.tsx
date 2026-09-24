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
    <div className="mvp-portal-home">
      <h1 className="sr-only">Wiadomości i ich kontekst</h1>
      <IllustrationStrip />
      <NajnowszeWiadomosci />
      <TopTenRedakcji topSources={sources.length ? sources : topSources} />
      <TematDnia />
      <DrSpin thread={null} />
      <PrzekazDnia government={config.data?.editorial.government ?? null} opposition={config.data?.editorial.opposition ?? null} />
      <Baza ref={bazaRef} categories={categories} sources={sources} initialQuery={q} />
      <footer className="mvp-footer">
        <div className="mvp-footer-main">
          <div><strong>spin<span>.</span>clinic</strong><p>Materiały prezentujemy w oryginalnym kontekście źródłowym.<br />Zestawienie publikacji nie jest potwierdzeniem zawartych w nich twierdzeń.</p></div>
          <div className="mvp-footer-support"><p>WSPARCIE PROJEKTU</p><a href="/wsparcie">Wesprzyj spin.clinic</a></div>
          <nav aria-label="Informacje o serwisie"><a href="/o-nas">O nas</a><a href="/zrodla">Źródła</a><a href="/zasady-korzystania">Zasady korzystania</a><a href="/polityka-prywatnosci">Prywatność i cookies</a></nav>
        </div>
      </footer>
    </div>
  );
}
