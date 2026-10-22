import type { Metadata } from 'next';
import { cookies } from 'next/headers';
import { notFound } from 'next/navigation';
import { cache } from 'react';
import { PositionPairPage } from '@spin-clinic/ui';
import {
  normalizeBlock, normalizePair, pairMetaDescription, pairMetaTitle, POSITION_PAIRS_TITLE,
  type PositionPairData, type PositionPairPerson,
} from '@spin-clinic/ui/kit';

/**
 * Strona jednej pary „Wcześniej i teraz” (zlecenie właściciela 13.10.2026). Za flagą NEXT_PUBLIC_POSITION_PAIRS (domyślnie
 * wyłączona; w podglądzie właściciela, cookie sc_preview=1, włączona) - bez flagi 404. Dane: kontrakt API-v3.md, sekcja 5.
 *  - ?osoba=<id albo slug>: para z listy osoby GET /api/przeszlosc/osoba/<osoba>/stanowiska/ (istnieje w kontrakcie);
 *  - bez parametru: GET /api/stanowiska/<id>/ (DO POTWIERDZENIA z backendem; w kontrakcie jest tylko lista osoby i zgłoszenie).
 * Na hoście przeszłość.today ścieżki /klinika/* przekierowuje middleware; tam odnośniki prowadzą do
 * /przeszlosc/osoba/<slug>#wczesniej-i-teraz.
 * Indeksowanie: noindex, follow do czasu decyzji prawnika (tekst o osobach publicznych); Open Graph i kanoniczny adres są ustawione,
 * więc udostępnianie linku działa.
 */
const API = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function enabled() {
  return process.env.NEXT_PUBLIC_POSITION_PAIRS === 'true' || cookies().get('sc_preview')?.value === '1';
}

const person = (raw: unknown): PositionPairPerson | null => {
  const value = raw as { id?: unknown; slug?: unknown; name?: unknown } | null;
  return value && Number.isInteger(Number(value.id)) && typeof value.name === 'string'
    ? { id: Number(value.id), slug: typeof value.slug === 'string' ? value.slug : '', name: value.name } : null;
};

const load = cache(async (id: number, osoba: string | undefined): Promise<{ pair: PositionPairData | null; person: PositionPairPerson | null; paused: boolean } | null> => {
  const url = osoba ? `${API}/api/przeszlosc/osoba/${encodeURIComponent(osoba)}/stanowiska/` : `${API}/api/stanowiska/${id}/`;
  const response = await fetch(url, { cache: 'no-store' }).catch(() => null);
  if (!response || !response.ok) return null;
  const data = await response.json().catch(() => null) as Record<string, unknown> | null;
  if (!data) return null;
  if (osoba) {
    const block = normalizeBlock(data);
    return block ? { pair: block.items.find(item => item.id === id) ?? null, person: person(data.person), paused: block.paused } : null;
  }
  const pair = normalizePair(data.pair ?? data);
  return { pair, person: person(data.person), paused: data.paused === true };
});

const parse = (params: { id: string }) => (/^[1-9]\d{0,9}$/.test(params.id) ? Number(params.id) : null);
const ident = (searchParams: { osoba?: string | string[] }) => {
  const value = typeof searchParams.osoba === 'string' ? searchParams.osoba : undefined;
  return value && /^(figure:)?[1-9]\d{0,9}(-[a-z0-9-]{1,120})?$/.test(value) ? value : undefined;
};

export async function generateMetadata({ params, searchParams }: { params: { id: string }; searchParams: { osoba?: string | string[] } }): Promise<Metadata> {
  const id = parse(params);
  const fallback: Metadata = { title: `${POSITION_PAIRS_TITLE} - spin.clinic`, robots: { index: false, follow: true } };
  if (!id || !enabled()) return fallback;
  const data = await load(id, ident(searchParams));
  if (!data?.pair || data.paused) return fallback;
  const title = pairMetaTitle(data.pair, data.person?.name);
  const description = pairMetaDescription(data.pair, data.person?.name);
  return {
    title: `${title} - spin.clinic`,
    description,
    robots: { index: false, follow: true },
    alternates: { canonical: `/klinika/stanowiska/${id}` },
    openGraph: { title, description, type: 'article', siteName: 'spin.clinic', images: [] },
    twitter: { card: 'summary', title, description, images: [] },
  };
}

export default async function PositionPairRoute({ params, searchParams }: { params: { id: string }; searchParams: { osoba?: string | string[] } }) {
  const id = parse(params);
  if (!id || !enabled()) notFound();
  const data = await load(id, ident(searchParams));
  if (!data || (!data.pair && !data.paused)) notFound();
  return <PositionPairPage pair={data.pair} person={data.person} paused={data.paused} />;
}
