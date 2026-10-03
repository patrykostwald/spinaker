import type { MetadataRoute } from 'next';

/** Aplikacja instalowana z przeglądarki (PWA) - pierwszy krok do aplikacji na telefon. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'spin.clinic - wiadomości i Klinika spinu',
    short_name: 'spin.clinic',
    description: 'Wiadomości ze źródłami i automatyczne diagnozy spinu polityków.',
    id: '/',
    scope: '/',
    start_url: '/',
    display: 'standalone',
    background_color: '#000000',
    theme_color: '#000000',
    lang: 'pl',
    categories: ['news'],
    icons: [
      { src: '/app/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/app/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: '/app/maskable-192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
      { src: '/app/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
    shortcuts: [
      { name: 'Klinika', url: '/klinika' },
      { name: 'Wiadomości', url: '/' },
      { name: 'Spinki', url: '/spinki' },
    ],
  };
}
