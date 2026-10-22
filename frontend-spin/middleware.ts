import { NextResponse, type NextRequest } from 'next/server';

/**
 * Domena przeszlosc.today (właściciel 5.10): strona główna to drzewo tematów (/przeszlosc) z tej samej aplikacji;
 * pozostałe adresy spin.clinic pod tą domeną przekierowujemy na spin.clinic, żeby nie dublować treści.
 */
// /przeszlosc obejmuje też public/przeszlosc (ikony PWA, strona offline); /sw.js musi być z tej samej domeny (bez przekierowania).
const OWN = ['/przeszlosc', '/_next', '/api', '/fonts', '/icons', '/favicon', '/robots.txt', '/sw.js'];

export function middleware(request: NextRequest) {
  const host = (request.headers.get('host') || '').toLowerCase().replace(/:\d+$/, '').replace(/^www\./, '');
  // seria 2: manifest spin.clinic przez route handler z Cache-Control i Vary: Host (treść nadal z app/manifest.ts)
  if (host !== 'przeszlosc.today') {
    if (request.nextUrl.pathname === '/manifest.webmanifest') return NextResponse.rewrite(new URL('/spin-manifest.webmanifest', request.url));
    return NextResponse.next();
  }
  const { pathname, search } = request.nextUrl;
  if (pathname === '/') return NextResponse.rewrite(new URL(`/przeszlosc${search}`, request.url));
  // PWA (port v3, 13.10): własny manifest przeszłości pod standardowym adresem; spin.clinic dalej dostaje app/manifest.ts
  if (pathname === '/manifest.webmanifest') return NextResponse.rewrite(new URL('/przeszlosc/manifest.webmanifest', request.url));
  // krótkie adresy stron przeszłości (PWA seria 2): /aplikacja i /jak-to-dziala to /przeszlosc/...; dawne /zrodla i /metodologia -> /jak-to-dziala
  const short = pathname.replace(/\/+$/, '');
  if (short === '/aplikacja' || short === '/jak-to-dziala') return NextResponse.rewrite(new URL(`/przeszlosc${short}${search}`, request.url));
  if (short === '/zrodla' || short === '/metodologia') return NextResponse.redirect(new URL('/jak-to-dziala', request.url), 308);
  // raport nastrojów dla znajomego (właściciel 8.10): statyczny plik z public/raporty, noindex
  if (pathname === '/pizza') return NextResponse.rewrite(new URL('/raporty/pizza.html', request.url));
  if (pathname.startsWith('/raporty/')) return NextResponse.next();
  if (OWN.some(prefix => pathname.startsWith(prefix))) return NextResponse.next();
  return NextResponse.redirect(`https://spin.clinic${pathname}${search}`, 308);
}

export const config = { matcher: ['/((?!_next/static|_next/image).*)'] };
