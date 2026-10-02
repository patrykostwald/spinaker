'use client';

import { useEffect, useRef, useState } from 'react';
import './pwa.css';
import { useFeature } from '@spin-clinic/ui';

type InstallPrompt = Event & { prompt(): Promise<void>; userChoice: Promise<{ outcome: string }> };
type Config = { enabled: boolean; public_key: string; csrfToken: string; consent_version: string; results: { endpoint: string; topics: string[] }[] };
const topics = [['spiny-na-zywo', 'Każdy nowy spin - od razu po diagnozie'], ['spin-dnia', 'Spin dnia'], ['nitki-dr-spina', 'Nitki Dr. Spina'], ['obserwowani', 'Obserwowani (po zalogowaniu)']];
const standalone = () => window.matchMedia('(display-mode: standalone)').matches || Boolean((navigator as Navigator & { standalone?: boolean }).standalone);

export function PwaControls() {
  const pushEnabled = useFeature('PUSH_ENABLED');
  const dialog = useRef<HTMLDialogElement>(null);
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null);
  const [ios, setIos] = useState(false);
  const [installed, setInstalled] = useState(false);
  const [banner, setBanner] = useState(false);
  const [mode, setMode] = useState('install');
  const [config, setConfig] = useState<Config | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [supported, setSupported] = useState(false);
  const [opened, setOpened] = useState(0);

  useEffect(() => {
    setIos(/iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1));
    setInstalled(standalone());
    setSupported('serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window && process.env.NODE_ENV === 'production');
    if (process.env.NODE_ENV === 'production' && 'serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' }).catch(() => setMessage('Nie udało się przygotować aplikacji. Odśwież stronę.'));
    }
    const dismissed = () => { try { return Number(localStorage.getItem('spin-install-dismissed')) > Date.now(); } catch { return false; } };
    const onPrompt = (event: Event) => { event.preventDefault(); setPrompt(event as InstallPrompt); setBanner(!dismissed() && !standalone()); };
    const onInstalled = () => { setInstalled(true); setPrompt(null); setBanner(false); };
    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', onInstalled);
    if (/iPad|iPhone|iPod/.test(navigator.userAgent) && !standalone() && !dismissed()) setBanner(true);
    const onHash = () => {
      if (location.hash === '#zainstaluj-aplikacje' || (pushEnabled && location.hash === '#powiadomienia')) {
        setMode(location.hash === '#powiadomienia' ? 'push' : 'install');
        setOpened(value => value + 1);
        setMessage('');
        if (!dialog.current?.open) dialog.current?.showModal();
      }
    };
    window.addEventListener('hashchange', onHash);
    const onLink = (event: MouseEvent) => {
      const link = (event.target as Element).closest?.('a');
      const href = link?.getAttribute('href');
      if (href !== '#zainstaluj-aplikacje' && !(pushEnabled && href === '#powiadomienia')) return;
      event.preventDefault();
      history.replaceState(null, '', href);
      onHash();
    };
    document.addEventListener('click', onLink, true);
    onHash();
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt);
      window.removeEventListener('appinstalled', onInstalled);
      window.removeEventListener('hashchange', onHash);
      document.removeEventListener('click', onLink, true);
    };
  }, [pushEnabled]);

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
    loadConfig().then(async data => {
      const registration = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration('/') : undefined;
      const subscription = await registration?.pushManager?.getSubscription();
      if (!cancelled) setSelected(data.results.find(row => row.endpoint === subscription?.endpoint)?.topics || []);
    }).catch(error => { if (!cancelled) setMessage(error.message); });
    return () => { cancelled = true; };
  }, [mode, opened, pushEnabled]);

  function dismiss() {
    setBanner(false);
    try { localStorage.setItem('spin-install-dismissed', String(Date.now() + 30 * 86400000)); } catch { /* Storage may be unavailable. */ }
  }
  function close() {
    dialog.current?.close();
    if (['#zainstaluj-aplikacje', '#powiadomienia'].includes(location.hash)) history.replaceState(null, '', location.pathname + location.search);
  }
  async function install() {
    if (!prompt) return;
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      if (choice.outcome === 'accepted') setBanner(false);
    } catch {
      setMessage('Nie udało się otworzyć instalacji. Spróbuj przez menu przeglądarki.');
    } finally { setPrompt(null); }
  }
  async function save(disable = false) {
    if (!config) return;
    setBusy(true); setMessage('');
    let created: PushSubscription | null = null;
    try {
      if (!disable && Notification.permission === 'denied') throw new Error('Powiadomienia są zablokowane. Zmień uprawnienia tej strony w ustawieniach przeglądarki.');
      // Request permission directly in the click handler (required by iOS).
      if (!disable && await Notification.requestPermission() !== 'granted') throw new Error('Nie udzielono zgody na powiadomienia.');
      const registration = await navigator.serviceWorker.getRegistration('/');
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
      if (!response.ok) throw new Error(response.status === 409 ? 'Subskrypcja pochodzi z poprzedniej sesji. Wyłącz ją, a następnie włącz ponownie.' : 'Nie udało się zapisać. Spróbuj ponownie.');
      if (disable) { await subscription?.unsubscribe(); setSelected([]); }
      setMessage(disable ? 'Powiadomienia na tym urządzeniu są wyłączone.' : 'Zapisano tematy powiadomień.');
    } catch (error) {
      await created?.unsubscribe().catch(() => undefined);
      setMessage(error instanceof Error ? error.message : 'Nie udało się zapisać ustawień.');
    } finally { setBusy(false); }
  }
  return <>
    {banner && <aside className="sc-pwa-banner" aria-label="Instalacja aplikacji">
      <a href="#zainstaluj-aplikacje">Zainstaluj aplikację</a>
      <button type="button" onClick={dismiss} aria-label="Ukryj propozycję instalacji na 30 dni">Nie teraz</button>
    </aside>}
    <dialog ref={dialog} className="sc-pwa-dialog" aria-labelledby="sc-pwa-title" onCancel={close} onClose={() => {
      if (['#zainstaluj-aplikacje', '#powiadomienia'].includes(location.hash)) history.replaceState(null, '', location.pathname + location.search);
    }}>
      <button type="button" className="sc-pwa-close" onClick={close} aria-label="Zamknij okno">×</button>
      <h2 id="sc-pwa-title">{mode === 'push' ? 'Powiadomienia' : 'Zainstaluj aplikację'}</h2>
      {mode === 'install' ? <>
        <p>Klinika, wiadomości i nitki pod ręką - prosto z ekranu telefonu.</p>
        {installed ? <p>Aplikacja jest już zainstalowana.</p> : ios ? <p>Otwórz stronę w Safari. Wybierz <strong>Udostępnij → Do ekranu początkowego → Dodaj</strong>.</p> : prompt ? <button className="sc-pwa-primary" onClick={() => void install()}>Zainstaluj</button> : <p>W menu przeglądarki wybierz „Zainstaluj aplikację” lub „Dodaj do ekranu głównego”, jeśli ta opcja jest dostępna.</p>}
        <button onClick={() => { dismiss(); close(); }}>Nie pokazuj przez 30 dni</button>
        {pushEnabled && <p><a href="#powiadomienia">Wybierz powiadomienia</a></p>}
      </> : <>
        <p>Wybierz tematy. Konto nie jest potrzebne do spinu dnia i nitek Dr. Spina.</p>
        {ios && !installed && <p>Na iPhonie i iPadzie push działa tylko w zainstalowanej PWA (iOS 16.4 lub nowszy). <a href="#zainstaluj-aplikacje">Jak zainstalować?</a></p>}
        {!supported && <p>Ta przeglądarka nie obsługuje teraz powiadomień aplikacji.</p>}
        {config && !config.enabled && <p>Powiadomienia nie są jeszcze włączone w serwisie.</p>}
        <fieldset disabled={busy || !config?.enabled || !supported || (ios && !installed)}>
          <legend>Tematy na tym urządzeniu</legend>
          {topics.map(([key, label]) => <label key={key}><input type="checkbox" checked={selected.includes(key)} onChange={event => setSelected(current => event.target.checked ? [...current, key] : current.filter(value => value !== key))} />{label}</label>)}
        </fieldset>
        <p className="sc-pwa-note">Klikając „Zapisz i włącz”, zgadzasz się na wybrane powiadomienia od iapply sp. z o.o. Zgodę możesz wycofać tutaj w dowolnym momencie. <a href="/polityka-prywatnosci">Prywatność</a></p>
        <button className="sc-pwa-primary" disabled={busy || !config?.enabled || !supported || !selected.length || (ios && !installed)} onClick={() => void save()}>Zapisz i włącz</button>
        <button disabled={busy || !config || !supported} onClick={() => void save(true)}>Wyłącz na tym urządzeniu</button>
      </>}
      <p role="status" aria-live="polite">{busy ? 'Zapisywanie…' : message}</p>
    </dialog>
  </>;
}
