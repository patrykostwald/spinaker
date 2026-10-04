import { NextResponse, type NextRequest } from 'next/server';

/**
 * Domena przeszlosc.today (właściciel 5.10): strona główna to drzewo tematów (/przeszlosc) z tej samej aplikacji;
 * pozostałe adresy spin.clinic pod tą domeną przekierowujemy na spin.clinic, żeby nie dublować treści.
 */
const OWN = ['/przeszlosc', '/_next', '/api', '/fonts', '/icons', '/favicon', '/robots.txt'];

export function middleware(request: NextRequest) {
  const host = (request.headers.get('host') || '').toLowerCase().replace(/:\d+$/, '').replace(/^www\./, '');
  if (host !== 'przeszlosc.today') return NextResponse.next();
  const { pathname, search } = request.nextUrl;
  if (pathname === '/') return NextResponse.rewrite(new URL(`/przeszlosc${search}`, request.url));
  if (OWN.some(prefix => pathname.startsWith(prefix))) return NextResponse.next();
  return NextResponse.redirect(`https://spin.clinic${pathname}${search}`, 308);
}

export const config = { matcher: ['/((?!_next/static|_next/image).*)'] };
