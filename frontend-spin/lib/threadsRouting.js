/**
 * Logika zależna od flagi NEXT_PUBLIC_THREADS_ENABLED (spinki/nitki/tropy), wspólna dla next.config.js i manifestu.
 * Zasada (etap 2 wycięcia spinek):
 *  - flaga true (obecna produkcja): zachowanie bez zmian (stare adresy /nitki, /tropy prowadzą do /spinki);
 *  - flaga false: /spinki*, /nitki*, /tropy*, /konto/spinki|nitki|tropy* kierują jednym przekierowaniem (302, nie 301,
 *    żeby przełączenie flagi z powrotem nie zostało zablokowane w pamięci przeglądarek) na /klinika.
 *    Wyjątek: osoby z ciasteczkiem podglądu sc_preview=1 widzą trasy jak dotąd (strony same sprawdzają serverFeature).
 * Plik jest zwykłym CommonJS, bo czyta go next.config.js.
 */
const LEGACY = ['nitki', 'tropy'];

function isThreadsEnabled(env = process.env) {
  return env.NEXT_PUBLIC_THREADS_ENABLED === 'true';
}

function threadRedirects(enabled) {
  if (enabled) {
    return [
      // „Nitki” nazywają się teraz „Spinki”: stare linki (powiadomienia, udostępnienia) prowadzą pod nowy adres.
      { source: '/nitki', destination: '/spinki', permanent: true },
      { source: '/nitki/:path*', destination: '/spinki/:path*', permanent: true },
      { source: '/konto/nitki/:path*', destination: '/konto/spinki/:path*', permanent: true },
      // Tropy -> Spinki (właściciel 3.10)
      { source: '/tropy', destination: '/spinki', permanent: true },
      { source: '/tropy/:path*', destination: '/spinki/:path*', permanent: true },
      { source: '/konto/tropy/:path*', destination: '/konto/spinki/:path*', permanent: true },
    ];
  }
  const noPreview = [{ type: 'cookie', key: 'sc_preview', value: '1' }];
  const sources = ['spinki', ...LEGACY].flatMap(name => [`/${name}`, `/${name}/:path*`, `/konto/${name}`, `/konto/${name}/:path*`]);
  return [
    // osoby w trybie podglądu fazy 2: stare nazwy dalej prowadzą do /spinki (strony same pilnują dostępu)
    ...LEGACY.flatMap(name => [`/${name}`, `/${name}/:path*`]).map(source => ({
      source, destination: source.replace(/^\/(nitki|tropy)/, '/spinki'), permanent: false, has: noPreview,
    })),
    ...sources.map(source => ({ source, destination: '/klinika', permanent: false, missing: noPreview })),
  ];
}

function manifestShortcuts(enabled) {
  if (enabled) {
    return [
      { name: 'Klinika', url: '/klinika' },
      { name: 'Wiadomości', url: '/' },
      { name: 'Spinki', url: '/spinki' },
    ];
  }
  return [
    { name: 'Klinika', url: '/klinika' },
    { name: 'Przekazy dnia', url: '/klinika/przekazy' },
    { name: 'Wiadomości', url: '/' },
  ];
}

module.exports = { isThreadsEnabled, threadRedirects, manifestShortcuts };
