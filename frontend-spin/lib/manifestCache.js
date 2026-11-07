// Nagłówki manifestu PWA (seria 2, 13.10.2026): jedna wartość dla next.config.js (headers) i route handlera przeszłości.
// Manifest zależy od hosta (spin.clinic / przeszlosc.today pod /manifest.webmanifest), więc:
// - przeglądarka trzyma go krótko (5 min), CDN do godziny, potem odświeża w tle;
// - Vary: Host dopisuje host do klucza pamięci pośredników, którzy go respektują.
const MANIFEST_CACHE = 'public, max-age=300, s-maxage=3600, stale-while-revalidate=86400';
const MANIFEST_VARY = 'Host';

module.exports = { MANIFEST_CACHE, MANIFEST_VARY };
