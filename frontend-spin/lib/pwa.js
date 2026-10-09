/**
 * Wspólna, czysta logika aplikacji (PWA): flagi, rejestracja service workera, stan wsparcia push i komunikaty.
 * Zwykły CommonJS (jak threadsRouting.js), żeby dało się ją testować bez przeglądarki.
 *
 * Jedna flaga NEXT_PUBLIC_APP_ENABLED włącza całą aplikację: rejestrację service workera, okno instalacji,
 * stronę /aplikacja. Powiadomienia push wymagają dodatkowo NEXT_PUBLIC_PUSH_ENABLED (i backendowego PUSH_ENABLED
 * z kluczami VAPID), a alerty o obserwowanych osobach także NEXT_PUBLIC_ACCOUNTS_ENABLED (konto).
 */

/** Hasze obsługiwane przez okno aplikacji (PwaControls). */
const HASH_INSTALL = '#zainstaluj-aplikacje';
const HASH_PUSH = '#powiadomienia';
const HASH_FOLLOWED = '#alerty-obserwowani';
const WINDOW_HASHES = [HASH_INSTALL, HASH_PUSH, HASH_FOLLOWED];

function flagOn(value) {
  return value === true || value === 'true';
}

/** Co jest dostępne przy danym zestawie flag NEXT_PUBLIC_*. */
function pwaFeatures(flags = {}) {
  const app = flagOn(flags.app);
  const push = app && flagOn(flags.push);
  const accounts = flagOn(flags.accounts);
  return {
    app,
    install: app,
    page: app,
    serviceWorker: app,
    push,
    followedAlerts: push && accounts,
    quietHours: accounts,
  };
}

function featuresFromEnv(env = {}) {
  return pwaFeatures({
    app: env.NEXT_PUBLIC_APP_ENABLED,
    push: env.NEXT_PUBLIC_PUSH_ENABLED,
    accounts: env.NEXT_PUBLIC_ACCOUNTS_ENABLED,
  });
}

/** Service worker rejestrujemy tylko za flagą aplikacji, w produkcji i tam, gdzie przeglądarka go ma. */
function shouldRegisterServiceWorker({ appEnabled, nodeEnv, hasServiceWorker }) {
  return Boolean(appEnabled) && nodeEnv === 'production' && Boolean(hasServiceWorker);
}

function isIosDevice({ userAgent = '', platform = '', maxTouchPoints = 0 } = {}) {
  return /iPad|iPhone|iPod/.test(userAgent) || (platform === 'MacIntel' && maxTouchPoints > 1);
}

/**
 * Stan wsparcia powiadomień push na tym urządzeniu.
 * ok - można prosić o zgodę; ios-install - iOS poza zainstalowaną aplikacją; unsupported - przeglądarka bez push;
 * denied - użytkownik zablokował powiadomienia; dev - tryb deweloperski (service worker wyłączony).
 */
function pushState({ ios = false, installed = false, hasPush = false, hasServiceWorker = false, hasNotification = false, permission = 'default', production = true } = {}) {
  if (!production) return 'dev';
  if (ios && !installed) return 'ios-install';
  if (!hasPush || !hasServiceWorker || !hasNotification) return 'unsupported';
  if (permission === 'denied') return 'denied';
  return 'ok';
}

const PUSH_MESSAGES = {
  ok: '',
  'ios-install': 'Na iPhonie i iPadzie powiadomienia działają tylko w zainstalowanej aplikacji (iOS 16.4 lub nowszy). Otwórz w Safari Udostępnij → Do ekranu początkowego → Dodaj, a potem uruchom aplikację z ekranu.',
  unsupported: 'Ta przeglądarka nie obsługuje powiadomień aplikacji. Spróbuj w Chrome, Edge lub Firefox albo zainstaluj aplikację.',
  denied: 'Powiadomienia są zablokowane dla tej strony. Zmień uprawnienia w ustawieniach przeglądarki lub systemu, a potem wróć tutaj.',
  dev: 'W trybie deweloperskim powiadomienia są wyłączone.',
};

function pushMessage(state) {
  return Object.hasOwn(PUSH_MESSAGES, state) ? PUSH_MESSAGES[state] : PUSH_MESSAGES.unsupported;
}

/** Komunikat po odpowiedzi użytkownika na prośbę o zgodę (Notification.requestPermission). */
function permissionMessage(result) {
  if (result === 'granted') return '';
  if (result === 'denied') return 'Powiadomienia zostały zablokowane. Możesz je włączyć w ustawieniach przeglądarki dla tej strony.';
  return 'Nie udzielono zgody na powiadomienia. Możesz wrócić tu w każdej chwili.';
}

/** Hasz otwierający okno aplikacji (albo null). Push wymaga flagi push. */
function windowHash(hash, features) {
  if (hash === HASH_INSTALL) return features.install ? { mode: 'install', preselect: [] } : null;
  if (hash === HASH_PUSH) return features.push ? { mode: 'push', preselect: [] } : null;
  if (hash === HASH_FOLLOWED) return features.push ? { mode: 'push', preselect: ['obserwowani'] } : null;
  return null;
}

module.exports = {
  HASH_INSTALL, HASH_PUSH, HASH_FOLLOWED, WINDOW_HASHES,
  pwaFeatures, featuresFromEnv, shouldRegisterServiceWorker, isIosDevice,
  pushState, pushMessage, permissionMessage, windowHash,
};
