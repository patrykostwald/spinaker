/**
 * PWA przeszłość.today (port v3, 13.10): wspólne dane manifestu i metadanych segmentu.
 * Kolory = tło v3 (--sc-bg ciemny #0b0c0e), ikony w public/przeszlosc/ (z prototypu przeszlosc-v3, logo właściciela).
 */
export const PT_THEME = '#0b0c0e';
export const PT_THEME_LIGHT = '#fafafa';
export const PT_ICON = (file: string) => `/przeszlosc/${file}`;

/** base: '/' na przeszlosc.today, '/przeszlosc' na innej domenie. Adresy stron zawsze /przeszlosc/... (tak linkuje aplikacja). */
export function przeszloscManifest(base: '/' | '/przeszlosc') {
  const icon192 = { src: PT_ICON('icon-192.png'), sizes: '192x192', type: 'image/png' };
  return {
    id: base,
    name: 'przeszłość.today',
    short_name: 'przeszłość',
    description: 'Rejestr powiązań osób publicznych: kto, co i kiedy, ze źródłem przy każdym fakcie.',
    lang: 'pl',
    dir: 'ltr',
    start_url: base,
    scope: base,
    display: 'standalone',
    orientation: 'any',
    background_color: PT_THEME,
    theme_color: PT_THEME,
    categories: ['news', 'government'],
    icons: [
      { ...icon192, purpose: 'any' },
      { src: PT_ICON('icon-512.png'), sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: PT_ICON('maskable-192.png'), sizes: '192x192', type: 'image/png', purpose: 'maskable' },
      { src: PT_ICON('maskable-512.png'), sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
    shortcuts: [
      { name: 'Szukaj osoby publicznej', short_name: 'Osoba', url: '/przeszlosc?tryb=osoba', description: 'Profil osoby: wpisy, głosowania, KRS', icons: [icon192] },
      { name: 'Szukaj podmiotu w KRS', short_name: 'Podmiot KRS', url: '/przeszlosc?tryb=spolka', description: 'Spółka, fundacja lub stowarzyszenie z KRS', icons: [icon192] },
      { name: 'Odstępstwa od klubu', short_name: 'Odstępstwa', url: '/przeszlosc/odstepstwa', description: 'Głosy inne niż większość klubu w Sejmie', icons: [icon192] },
    ],
  };
}
