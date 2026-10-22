import { NextResponse } from 'next/server';
import manifest from '../manifest';
import { MANIFEST_CACHE, MANIFEST_VARY } from '../../lib/manifestCache';

// manifest zależy od hosta (middleware wybiera markę), więc odpowiedź nigdy nie jest statyczna
export const dynamic = 'force-dynamic';

/**
 * Manifest spin.clinic z własnymi nagłówkami pamięci (seria 2, 13.10.2026). Treść bez zmian: app/manifest.ts.
 * Middleware przepisuje /manifest.webmanifest na ten adres dla hostów innych niż przeszlosc.today, bo trasa metadanych
 * Next (app/manifest.ts) dokleja własne "Cache-Control: public, max-age=0, must-revalidate" i nadpisuje Vary.
 */
export function GET() {
  return new NextResponse(JSON.stringify(manifest()), {
    headers: { 'Content-Type': 'application/manifest+json; charset=utf-8', 'Cache-Control': MANIFEST_CACHE, Vary: MANIFEST_VARY },
  });
}
