'use client';

import { useEffect, useRef, useState } from 'react';
import './pwa.css';
import { useFeature } from '@spin-clinic/ui';
import { useAccount } from '../../packages/ui/src/lib/account';
import {
  HASH_FOLLOWED, HASH_INSTALL, HASH_PUSH, WINDOW_HASHES,
  isIosDevice, permissionMessage, pushMessage, pushState, shouldRegisterServiceWorker, windowHash,
} from '../lib/pwa';

type InstallPrompt = Event & { prompt(): Promise<void>; userChoice: Promise<{ outcome: string }> };
type Config = { enabled: boolean; public_key: string; csrfToken: string; consent_version: string; results: { endpoint: string; topics: string[] }[] };
const allTopics = [['spiny-na-zywo', 'Każdy nowy spin - od razu po diagnozie'], ['spin-dnia', 'Spin dnia'], ['nitki-dr-spina', 'Spinki Dr. Spina'], ['obserwowani', 'Obserwowani (po zalogowaniu)']];
// Temat „nitki-dr-spina” (nazwa w bazie bez zmian) jest oferowany tylko przy włączonych spinkach.
const THREAD_TOPIC = 'nitki-dr-spina';
const FOLLOWED_TOPIC = 'obserwowani';
const standalone = () => window.matchMedia('(display-mode: standalone)').matches || Boolean((navigator as Navigator & { standalone?: boolean }).standalone);

/** Stan aplikacji dla strony /aplikacja (zdarzenia okna, bez wspólnego magazynu). */
export type PwaState = { installed: boolean; canPrompt: boolean; ios: boolean };
export const PWA_STATE_EVENT = 'sc:pwa-state';
export const PWA_INSTALL_EVENT = 'sc:pwa-install';
export const PWA_PUSH_EVENT = 'sc:pwa-push';
declare global { interface Window { __scPwa?: PwaState } }

/** Czeka na aktywny service worker, ale nie dłużej niż podany czas. */
async function activeRegistration(ms = 6000) {
  if (!('serviceWorker' in navigator)) return undefined;
  const ready = await Promise.race([navigator.serviceWorker.ready, new Promise<undefined>(resolve => setTimeout(() => resolve(undefined), ms))]);
  return ready ?? (await navigator.serviceWorker.getRegistration('/'));
}

export function PwaControls() {
  const pushEnabled = useFeature('PUSH_ENABLED');
  const threadsEnabled = useFeature('THREADS_ENABLED');
  const accountsEnabled = useFeature('ACCOUNTS_ENABLED');
  const account = useAccount();
  const loggedIn = Boolean(account.data?.user?.id);
  const topics = threadsEnabled ? allTopics : allTopics.filter(([key]) => key !== THREAD_TOPIC);
  const dialog = useRef<HTMLDialogElement>(null);
  const promptRef = useRef<InstallPrompt | null>(null);
  const preselect = useRef<string[]>([]);
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null);
  const [ios, setIos] = useState(false);
  const [installed, setInstalled] = useState(false);
  const [banner, setBanner] = useState(false);
  const [update, setUpdate] = useState(false);
  const [mode, setMode] = useState('install');
  const [config, setConfig] = useState<Config | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [device, setDevice] = useState('ok');
  const [opened, setOpened] = useState(0);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const isIos = isIosDevice({ userAgent: navigator.userAgent, platform: navigator.platform, maxTouchPoints: navigator.maxTouchPoints });
    setIos(isIos);
    setInstalled(standalone());
    const hasServiceWorker = 'serviceWorker' in navigator;
    const cleanups: (() => void)[] = [];
    if (shouldRegisterServiceWorker({ appEnabled: true, nodeEnv: process.env.NODE_ENV, hasServiceWorker })) {
      const hadController = Boolean(navigator.serviceWorker.controller);
      let first = !hadController;
      // Nowy service worker przejmuje stronę: proponujemy odświeżenie, nie przeładowujemy w trakcie czytania.
      const onController = () => { if (first) { first = false; return; } setUpdate(true); };
      navigator.serviceWorker.addEventListener('controllerchange', onController);
      navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' }).then(registration => {
        const check = () => { if (document.visibilityState === 'visible') void registration.update().catch(() => undefined); };
        document.addEventListener('visibilitychange', check);
        cleanups.push(() => document.removeEventListener('visibilitychange', check));
      }).catch(() => setMessage('Nie udało się przygotować aplikacji. Odśwież stronę.'));
      cleanups.push(() => navigator.serviceWorker.removeEventListener('controllerchange', onController));
    }
    const dismissed = () => { try { return Number(localStorage.getItem('spin-install-dismissed')) > Date.now(); } catch { return false; } };
    const onPrompt = (event: Event) => { event.preventDefault(); promptRef.current = event as InstallPrompt; setPrompt(event as InstallPrompt); setBanner(!dismissed() && !standalone()); };
    const onInstalled = () => { setInstalled(true); setPrompt(null); promptRef.current = null; setBanner(false); };
    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', onInstalled);
    if (isIos && !standalone() && !dismissed()) setBanner(true);
    const onHash = () => {
      const target = windowHash(location.hash, { install: true, push: pushEnabled });
      if (!target) return;
      preselect.current = target.preselect;
      setMode(target.mode);
      setOpened(value => value + 1);
      setMessage('');
      setSaved(false);
      if (!dialog.current?.open) dialog.current?.showModal();
    };
    window.addEventListener('hashchange', onHash);
    const onLink = (event: MouseEvent) => {
      const link = (event.target as Element).closest?.('a');
      const href = link?.getAttribute('href') || '';
      if (!WINDOW_HASHES.includes(href) || !windowHash(href, { install: true, push: pushEnabled })) return;
      event.preventDefault();
      history.replaceState(null, '', href);
      onHash();
    };
    document.addEventListener('click', onLink, true);
    // Przyciski ze strony /aplikacja: instalacja i zgoda na powiadomienia.
    const onInstallRequest = () => {
      const event = promptRef.current;
      if (event) void runInstall(event); else { history.replaceState(null, '', HASH_INSTALL); onHash(); }
    };
    const onPushRequest = () => { history.replaceState(null, '', HASH_FOLLOWED); onHash(); };
    window.addEventListener(PWA_INSTALL_EVENT, onInstallRequest);
    window.addEventListener(PWA_PUSH_EVENT, onPushRequest);
    onHash();
    return () => {
      cleanups.forEach(clean => clean());
      window.removeEventListener('beforeinstallprompt', onPrompt);
      window.removeEventListener('appinstalled', onInstalled);
      window.removeEventListener('hashchange', onHash);
      window.removeEventListener(PWA_INSTALL_EVENT, onInstallRequest);
      window.removeEventListener(PWA_PUSH_EVENT, onPushRequest);
      document.removeEventListener('click', onLink, true);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pushEnabled]);

  useEffect(() => {
    const state: PwaState = { installed, canPrompt: Boolean(prompt), ios };
    window.__scPwa = state;
    window.dispatchEvent(new CustomEvent(PWA_STATE_EVENT, { detail: state }));
  }, [installed, prompt, ios]);

  const refreshDevice = () => setDevice(pushState({
    ios, installed,
    hasPush: 'PushManager' in window, hasServiceWorker: 'serviceWorker' in navigator, hasNotification: 'Notification' in window,
    permission: 'Notification' in window ? Notification.permission : 'default', production: process.env.NODE_ENV === 'production',
  }));

  async function loadConfig() {
    const response = await fetch('/api/push/subscriptions/', { credentials: 'same-origin', cache: 'no-store' });
    if (!response.ok) throw new Error('Nie udało się pobrać ustawień. Spróbuj ponownie.');
    const data: Config = await response.json();
    setConfig(data);
    return data;
  }
  useEffect(() => {
    if (mode !== 'push' || !pushEnabled) return;
    let cancelled = false;
    setConfig(null);
    refreshDevice();
    loadConfig().then(async data => {
      const registration = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration('/') : undefined;
      const subscription = await registration?.pushManager?.getSubscription();
      const current = (data.results.find(row => row.endpoint === subscription?.endpoint)?.topics || []).filter(topic => threadsEnabled || topic !== THREAD_TOPIC);
      // Wejście z „Włącz alerty o obserwowanych” zaznacza temat „Obserwowani”, jeśli urządzenie nie ma jeszcze zgody.
      if (!cancelled) setSelected(current.length ? current : preselect.current);
    }).catch(error => { if (!cancelled) setMessage(error.message); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, opened, pushEnabled, threadsEnabled, ios, installed]);

  function dismiss() {
    setBanner(false);
    try { localStorage.setItem('spin-install-dismissed', String(Date.now() + 30 * 86400000)); } catch { /* Storage may be unavailable. */ }
  }
  function close() {
    dialog.current?.close();
    if (WINDOW_HASHES.includes(location.hash)) history.replaceState(null, '', location.pathname + location.search);
  }
  async function runInstall(event: InstallPrompt) {
    try {
      await event.prompt();
      const choice = await event.userChoice;
      if (choice.outcome === 'accepted') setBanner(false);
    } catch {
      setMessage('Nie udało się otworzyć instalacji. Spróbuj przez menu przeglądarki.');
    } finally { setPrompt(null); promptRef.current = null; }
  }
  async function install() {
    if (prompt) await runInstall(prompt);
  }
  async function save(disable = false) {
    if (!config) return;
    setBusy(true); setMessage(''); setSaved(false);
    let created: PushSubscription | null = null;
    try {
      if (!disable && device !== 'ok') throw new Error(pushMessage(device));
      if (!disable && selected.includes(FOLLOWED_TOPIC) && !loggedIn) throw new Error('Alerty o obserwowanych osobach wymagają konta. Zaloguj się albo odznacz „Obserwowani”.');
      // Zgodę prosimy bezpośrednio w kliknięciu (wymaga tego iOS).
      if (!disable) {
        const result = await Notification.requestPermission();
        if (result !== 'granted') { refreshDevice(); throw new Error(permissionMessage(result)); }
      }
      const registration = await activeRegistration();
      if (!registration?.active) throw new Error('Aplikacja jeszcze się przygotowuje. Spróbuj za chwilę.');
      let subscription = await registration.pushManager.getSubscription();
      if (!disable && !subscription) {
        const raw = atob(config.public_key.replace(/-/g, '+').replace(/_/g, '/'));
        const key = Uint8Array.from(raw, char => char.charCodeAt(0));
        subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
        created = subscription;
      }
      const current = await loadConfig();
      const response = await fetch('/api/push/subscriptions/', {
        method: disable ? 'DELETE' : 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': current.csrfToken },
        body: disable ? undefined : JSON.stringify({ ...subscription?.toJSON(), topics: selected, consent_version: current.consent_version }),
      });
      if (!response.ok) throw new Error(response.status === 409 ? 'Subskrypcja pochodzi z poprzedniej sesji. Wyłącz ją, a następnie włącz ponownie.' : response.status === 503 ? 'Powiadomienia są chwilowo wyłączone w serwisie.' : 'Nie udało się zapisać. Spróbuj ponownie.');
      if (disable) { await subscription?.unsubscribe(); setSelected([]); }
      setSaved(!disable && selected.includes(FOLLOWED_TOPIC));
      setMessage(disable ? 'Powiadomienia na tym urządzeniu są wyłączone.' : 'Zapisano tematy powiadomień.');
    } catch (error) {
      await created?.unsubscribe().catch(() => undefined);
      setMessage(error instanceof Error ? error.message : 'Nie udało się zapisać ustawień.');
    } finally { setBusy(false); }
  }
  const blocked = device !== 'ok';
  return <>
    {update && <aside className="sc-pwa-banner sc-pwa-update" role="status" aria-label="Aktualizacja aplikacji">
      <span>Dostępna nowa wersja aplikacji.</span>
      <button type="button" onClick={() => location.reload()}>Odśwież</button>
    </aside>}
    {banner && !update && <aside className="sc-pwa-banner" aria-label="Instalacja aplikacji">
      <a href={HASH_INSTALL}>Zainstaluj aplikację</a>
      <button type="button" onClick={dismiss} aria-label="Ukryj propozycję instalacji na 30 dni">Nie teraz</button>
    </aside>}
    <dialog ref={dialog} className="sc-pwa-dialog" aria-labelledby="sc-pwa-title" onCancel={close} onClose={() => {
      if (WINDOW_HASHES.includes(location.hash)) history.replaceState(null, '', location.pathname + location.search);
    }}>
      <button type="button" className="sc-pwa-close" onClick={close} aria-label="Zamknij okno">×</button>
      <h2 id="sc-pwa-title">{mode === 'push' ? 'Powiadomienia' : 'Zainstaluj aplikację'}</h2>
      {mode === 'install' ? <>
        <p>{threadsEnabled ? 'Klinika i spinki pod ręką - prosto z ekranu telefonu.' : 'Klinika i przekazy dnia pod ręką - prosto z ekranu telefonu.'}</p>
        {installed ? <p>Aplikacja jest już zainstalowana.</p> : ios ? <p>Otwórz stronę w Safari. Wybierz <strong>Udostępnij → Do ekranu początkowego → Dodaj</strong>. Potem uruchom aplikację z ekranu - dopiero stamtąd działają powiadomienia.</p> : prompt ? <button className="sc-pwa-primary" onClick={() => void install()}>Zainstaluj</button> : <p>W menu przeglądarki wybierz „Zainstaluj aplikację” lub „Dodaj do ekranu głównego”, jeśli ta opcja jest dostępna.</p>}
        <p><a href="/aplikacja">Instrukcja krok po kroku</a></p>
        <button onClick={() => { dismiss(); close(); }}>Nie pokazuj przez 30 dni</button>
        {pushEnabled && <p><a href={HASH_PUSH}>Wybierz powiadomienia</a></p>}
      </> : <>
        <p>{threadsEnabled ? 'Wybierz tematy. Konto nie jest potrzebne do spinu dnia i spinek Dr. Spina.' : 'Wybierz tematy. Konto nie jest potrzebne do nowych spinów i spinu dnia; alerty o obserwowanych osobach wymagają konta.'}</p>
        {blocked && <p role="alert">{pushMessage(device)}{device === 'ios-install' && <> <a href={HASH_INSTALL}>Jak zainstalować?</a></>}</p>}
        {config && !config.enabled && <p>Powiadomienia nie są jeszcze włączone w serwisie.</p>}
        <fieldset disabled={busy || !config?.enabled || blocked}>
          <legend>Tematy na tym urządzeniu</legend>
          {topics.map(([key, label]) => <label key={key}><input type="checkbox" checked={selected.includes(key)} onChange={event => setSelected(current => event.target.checked ? [...current, key] : current.filter(value => value !== key))} />{label}</label>)}
        </fieldset>
        {accountsEnabled && !loggedIn && selected.includes(FOLLOWED_TOPIC) && <p>Alerty o obserwowanych wymagają konta. <a href="/konto">Zaloguj się</a>, a potem wróć i zapisz urządzenie.</p>}
        <p className="sc-pwa-note">Klikając „Zapisz i włącz”, zgadzasz się na wybrane powiadomienia od iapply sp. z o.o. Zgodę możesz wycofać tutaj w dowolnym momencie. <a href="/polityka-prywatnosci">Prywatność</a></p>
        <button className="sc-pwa-primary" disabled={busy || !config?.enabled || blocked || !selected.length} onClick={() => void save()}>Zapisz i włącz</button>
        <button disabled={busy || !config || blocked} onClick={() => void save(true)}>Wyłącz na tym urządzeniu</button>
        {(saved || (loggedIn && selected.includes(FOLLOWED_TOPIC))) && <p><a href="/konto/alerty">Cisza nocna i osoby, które mogą Cię obudzić →</a></p>}
      </>}
      <p role="status" aria-live="polite">{busy ? 'Zapisywanie…' : message}</p>
    </dialog>
  </>;
}
