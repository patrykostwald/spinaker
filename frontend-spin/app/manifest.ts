import type { MetadataRoute } from 'next';

/** Aplikacja instalowana z przeglądarki (PWA) — pierwszy krok do aplikacji na telefon. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'spin.clinic — wiadomości i Klinika spinu',
    short_name: 'spin.clinic',
    description: 'Wiadomości ze źródłami i automatyczne diagnozy spinu polityków.',
    start_url: '/',
    display: 'standalone',
    background_color: '#000000',
    theme_color: '#000000',
    lang: 'pl',
    icons: [{ src: '/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }],
  };
}
