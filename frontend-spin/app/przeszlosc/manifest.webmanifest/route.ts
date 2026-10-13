import { NextResponse, type NextRequest } from 'next/server';
import { przeszloscManifest } from '../pwa';
import { MANIFEST_CACHE, MANIFEST_VARY } from '../../../lib/manifestCache';

// manifest zależy od nagłówka Host, więc nigdy nie jest generowany statycznie przy budowie
export const dynamic = 'force-dynamic';

/**
 * Manifest aplikacji przeszłość.today (port v3, 13.10). Na domenie przeszlosc.today middleware przepisuje
 * /manifest.webmanifest na ten adres, więc spin.clinic zachowuje swój manifest z app/manifest.ts bez zmian.
 * Na innej domenie (np. spin.clinic/przeszlosc) zakres i start to /przeszlosc, żeby nie wchodzić w aplikację spin.clinic.
 * Nagłówki pamięci (seria 2): te same co w next.config.js headers() - lib/manifestCache.js.
 */
export function GET(request: NextRequest) {
  const host = (request.headers.get('host') || '').toLowerCase().replace(/:\d+$/, '').replace(/^www\./, '');
  return new NextResponse(JSON.stringify(przeszloscManifest(host === 'przeszlosc.today' ? '/' : '/przeszlosc')), {
    headers: { 'Content-Type': 'application/manifest+json; charset=utf-8', 'Cache-Control': MANIFEST_CACHE, Vary: MANIFEST_VARY },
  });
}
