/**
 * PWA przeszłość.today (port v3, 13.10): wspólne dane manifestu i metadanych segmentu.
 * Kolory = tło v3 (--sc-bg ciemny #0b0c0e), ikony w public/przeszlosc/ (litera "p" w sepii z czerwoną kropką logo),
 * zrzuty ekranu w public/przeszlosc-app/screenshots/ (skrypt gust\przeszlosc\port\pwa-zrzuty.cjs).
 */
export const PT_THEME = '#0b0c0e';
export const PT_THEME_LIGHT = '#fafafa';
export const PT_ICON = (file: string) => `/przeszlosc/${file}`;
export const PT_SHOT = (file: string) => `/przeszlosc-app/screenshots/${file}`;

/** Zrzuty ekranu aplikacji: manifest (okno instalacji Chrome) i strona /przeszlosc/aplikacja czerpią z tej samej listy. */
export const PT_SCREENSHOTS = [
  { src: PT_SHOT('wide-1.png'), sizes: '1280x720', type: 'image/png', form_factor: 'wide', label: 'Wyszukiwarka: temat, osoba albo numer KRS' },
  { src: PT_SHOT('wide-2.png'), sizes: '1280x720', type: 'image/png', form_factor: 'wide', label: 'Temat: kto, co i kiedy, ze źródłem przy każdym fakcie' },
  { src: PT_SHOT('wide-3.png'), sizes: '1280x720', type: 'image/png', form_factor: 'wide', label: 'Odstępstwa od klubu: te same progi dla każdego klubu' },
  { src: PT_SHOT('narrow-1.png'), sizes: '780x1688', type: 'image/png', form_factor: 'narrow', label: 'Strona główna na telefonie' },
  { src: PT_SHOT('narrow-2.png'), sizes: '780x1688', type: 'image/png', form_factor: 'narrow', label: 'Temat na telefonie: wyniki w jednym widoku' },
  { src: PT_SHOT('narrow-3.png'), sizes: '780x1688', type: 'image/png', form_factor: 'narrow', label: 'Odstępstwa od klubu na telefonie' },
];

/**
 * base: '/' na przeszlosc.today, '/przeszlosc' na innej domenie. Adresy stron zawsze /przeszlosc/... (tak linkuje aplikacja).
 * id i scope: przeszlosc.today to osobne źródło (origin) niż spin.clinic, więc "/" nie koliduje; pod spin.clinic/przeszlosc
 * id i scope to "/przeszlosc", odrębne od aplikacji spin.clinic ("/"). Obie aplikacje instalują się naraz.
 */
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
    categories: ['news', 'politics'],
    prefer_related_applications: false,
    icons: [
      { ...icon192, purpose: 'any' },
      { src: PT_ICON('icon-512.png'), sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: PT_ICON('maskable-192.png'), sizes: '192x192', type: 'image/png', purpose: 'maskable' },
      { src: PT_ICON('maskable-512.png'), sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
    screenshots: PT_SCREENSHOTS,
    // Skrót "Głosowania" świadomie pominięty: trasa /przeszlosc/glosowania jest za flagą API PRZESZLOSC_VOTES_LIST_ENABLED
    // (domyślnie wyłączona), więc skrót prowadziłby do komunikatu "Funkcja jeszcze wyłączona". Zamiast niego "Funkcje".
    shortcuts: [
      { name: 'Szukaj tematu, osoby albo KRS', short_name: 'Szukaj', url: '/przeszlosc', description: 'Wyszukiwarka na stronie głównej', icons: [icon192] },
      { name: 'Szukaj osoby publicznej', short_name: 'Osoby', url: '/przeszlosc?tryb=osoba', description: 'Profil osoby: wpisy, głosowania, KRS', icons: [icon192] },
      { name: 'Odstępstwa od klubu', short_name: 'Odstępstwa', url: '/przeszlosc/odstepstwa', description: 'Głosy inne niż większość klubu w Sejmie', icons: [icon192] },
      { name: 'Co potrafi przeszłość.today', short_name: 'Funkcje', url: '/przeszlosc/funkcje', description: 'Lista funkcji z przykładami', icons: [icon192] },
    ],
  };
}
