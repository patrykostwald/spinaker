import type { MetadataRoute } from 'next';
import { isThreadsEnabled, manifestShortcuts } from '../lib/threadsRouting';

// Next 14 nie zna pól form_factor i label w typach, ale zapisuje je w manifeście bez zmian.
const screenshots = ([
  { src: '/app/screenshots/wide-1.png', sizes: '1280x720', type: 'image/png', form_factor: 'wide', label: 'Strona główna: przekazy dnia i najnowsze diagnozy' },
  { src: '/app/screenshots/wide-2.png', sizes: '1280x720', type: 'image/png', form_factor: 'wide', label: 'Instalacja aplikacji i alerty o obserwowanych osobach' },
  { src: '/app/screenshots/narrow-1.png', sizes: '780x1688', type: 'image/png', form_factor: 'narrow', label: 'Strona główna na telefonie' },
  { src: '/app/screenshots/narrow-2.png', sizes: '780x1688', type: 'image/png', form_factor: 'narrow', label: 'Ustawienia alertów i ciszy nocnej' },
]) as unknown as MetadataRoute.Manifest['screenshots'];

/**
 * Aplikacja instalowana z przeglądarki (PWA). Kryteria instalowalności Chrome: nazwa, ikony 192 i 512,
 * start_url, display standalone, HTTPS oraz service worker z obsługą fetch (public/sw.js).
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: '/',
    name: 'spin.clinic - wiadomości i Klinika spinu',
    short_name: 'spin.clinic',
    description: 'Wiadomości ze źródłami i automatyczne diagnozy spinu polityków. Alerty o wpisach obserwowanych osób.',
    scope: '/',
    start_url: '/',
    display: 'standalone',
    orientation: 'any',
    background_color: '#000000',
    theme_color: '#000000',
    lang: 'pl',
    dir: 'ltr',
    categories: ['news'],
    icons: [
      { src: '/app/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/app/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: '/app/maskable-192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
      { src: '/app/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
    // Zrzuty ekranu: szerokie (komputer) i wąskie (telefon) - Chrome pokazuje je w rozszerzonym oknie instalacji.
    screenshots,
    // skróty zależą od flagi spinek: przy false zamiast „Spinki” jest „Przekazy dnia” (lib/threadsRouting.js)
    shortcuts: manifestShortcuts(isThreadsEnabled()),
  };
}
